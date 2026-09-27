//! DRM software scanout through a seat-controlled fd, with two dumb buffers.
use super::*;
use smithay::wayland::seat::WaylandFocus;
use smithay::{
    backend::{
        allocator::{
            Allocator, Modifier,
            dmabuf::{AsDmabuf, Dmabuf},
            dumb::{DumbAllocator, DumbBuffer},
        },
        drm::{
            DrmDevice, DrmDeviceFd, DrmEvent, DrmSurface, PlaneConfig, PlaneDamageClips,
            PlaneState,
            dumb::{DumbFramebuffer, framebuffer_from_dumb_buffer},
        },
        input::{
            AbsolutePositionEvent, Event as InputEventTime, InputEvent, KeyboardKeyEvent,
            PointerAxisEvent, PointerButtonEvent, PointerMotionEvent,
        },
        libinput::{LibinputInputBackend, LibinputSessionInterface},
        session::{Event as SessionEvent, Session, libseat::LibSeatSession},
    },
    reexports::{
        calloop::EventLoop,
        drm::control::{Device, connector, crtc},
        input::Libinput,
        rustix::fs::OFlags,
    },
    utils::DeviceFd,
};

use super::visual::SoftwareElement;
struct Runtime {
    app: App,
    drm: DrmDevice,
    input: Libinput,
    active: bool,
    pending: std::collections::HashSet<crtc::Handle>,
    heads: Vec<Head>,
    display_transaction: Option<forge_desktop_core::OutputTransaction>,
    epoch: Instant,
    reset: bool,
    error: Option<String>,
}

struct Head {
    connector: connector::Handle,
    output: Output,
    global: smithay::reexports::wayland_server::backend::GlobalId,
    surface: DrmSurface,
    buffers: Vec<(DumbBuffer, DumbFramebuffer, Dmabuf)>,
    damage: OutputDamageTracker,
    current: usize,
    rendered: [bool; 2],
}
impl Runtime {
    fn rescan(
        &mut self,
        fd: &DrmDeviceFd,
        dh: &smithay::reexports::wayland_server::DisplayHandle,
    ) -> AppResult<()> {
        let resources = fd.resource_handles()?;
        // Force probe is required on virtual DRM connectors after QEMU UI resize.
        let connected: Vec<_> = resources
            .connectors()
            .iter()
            .filter_map(|id| fd.get_connector(*id, true).ok())
            .filter(|c| c.state() == connector::State::Connected && !c.modes().is_empty())
            .take(4)
            .collect();
        let before: Vec<_> = self.heads.iter().map(|h| h.connector).collect();
        let topology_changed=before.len()!=connected.len() || before.iter().any(|id|!connected.iter().any(|c|c.handle()==*id));
        // A hardware change must not implicitly confirm an unconfirmed scale.
        if topology_changed {
            if let Some(transaction)=self.display_transaction.as_mut().filter(|t|t.pending()) {
                let _=transaction.cancel(self.epoch.elapsed().as_millis() as u64);
                for output in transaction.active() {
                    if let Some(head)=self.heads.iter_mut().find(|h|u32::from(h.connector)==output.id) {
                        head.output.change_current_state(None,None,Some(smithay::output::Scale::Fractional(f64::from(output.scale_milli)/1000.0)),Some((output.geometry.x,output.geometry.y).into()));
                    }
                }
            }
        }
        self.heads.retain(|head| {
            if connected.iter().any(|c| c.handle() == head.connector) {
                return true;
            }
            for mapped in &self.app.windows {
                if let Some(surface)=mapped.window.wl_surface() {head.output.leave(surface.as_ref());}
            }
            dh.remove_global::<App>(head.global.clone());
            self.pending.remove(&head.surface.crtc());
            eprintln!("ForgeDesktop output removed: {}", head.output.name());
            false
        });
        for connector in connected {
            if self.heads.iter().any(|h| h.connector == connector.handle()) {
                continue;
            }
            let Some(crtc) = connector
                .encoders()
                .iter()
                .filter_map(|id| fd.get_encoder(*id).ok())
                .flat_map(|e| resources.filter_crtcs(e.possible_crtcs()))
                .find(|crtc| !self.heads.iter().any(|h| h.surface.crtc() == *crtc))
            else {
                continue;
            };
            let mode = *connector
                .modes()
                .iter()
                .find(|m| m.size() == (1280, 800))
                .unwrap_or(&connector.modes()[0]);
            let surface = self.drm.create_surface(crtc, mode, &[connector.handle()])?;
            if !fd
                .get_plane(surface.plane())?
                .formats()
                .contains(&(Fourcc::Xrgb8888 as u32))
            {
                return Err("output lacks XRGB8888 software scanout".into());
            }
            let mut allocator = DumbAllocator::new(fd.clone());
            let mut buffers = Vec::new();
            for _ in 0..2 {
                let buffer = allocator.create_buffer(
                    u32::from(mode.size().0),
                    u32::from(mode.size().1),
                    Fourcc::Xrgb8888,
                    &[Modifier::Linear],
                )?;
                let fb = framebuffer_from_dumb_buffer(fd, &buffer, true)?;
                let dmabuf = buffer.export()?;
                buffers.push((buffer, fb, dmabuf));
            }
            let (output, global) = if let Some(global) = self.app.output_global.take() {
                (self.app.output.clone(), global)
            } else {
                let output = Output::new(
                    format!("Forge-DRM-{}", u32::from(connector.handle())),
                    PhysicalProperties {
                        size: (0, 0).into(),
                        subpixel: Subpixel::Unknown,
                        make: "ForgeOS".into(),
                        model: "Pixman software output".into(),
                    },
                );
                let global = output.create_global::<App>(dh);
                (output, global)
            };
            let location = self
                .heads
                .iter()
                .map(|h| {
                    let r = outputs::geometry(&h.output);
                    r.loc.x + r.size.w
                })
                .max()
                .unwrap_or(0);
            let wl_mode = Mode {
                size: (i32::from(mode.size().0), i32::from(mode.size().1)).into(),
                refresh: 60000,
            };
            output.change_current_state(
                Some(wl_mode),
                Some(Transform::Normal),
                Some(smithay::output::Scale::Integer(1)),
                Some((location, 0).into()),
            );
            output.set_preferred(wl_mode);
            let damage = OutputDamageTracker::from_output(&output);
            eprintln!(
                "ForgeDesktop output added: {} connector={} logical-x={location}",
                output.name(),
                u32::from(connector.handle())
            );
            self.heads.push(Head {
                connector: connector.handle(),
                output,
                global,
                surface,
                buffers,
                damage,
                current: 0,
                rendered: [false; 2],
            });
        }
        if before != self.heads.iter().map(|h| h.connector).collect::<Vec<_>>() {
            if let Some(first)=self.heads.first() {
                let origin=first.output.current_location();
                if origin.x!=0 || origin.y!=0 {
                    for head in &self.heads {let loc=head.output.current_location();head.output.change_current_state(None,None,None,Some(((loc.x-origin.x).max(0),(loc.y-origin.y).max(0)).into()));}
                }
            }
            {

                if let Some(saved) =
                    output_config::path().and_then(|p| output_config::load(&p).ok())
                {
                    let compatible = saved.len() == self.heads.len()
                        && saved.iter().zip(&self.heads).all(|(o, h)| {
                            let mode = h.output.current_mode().unwrap();
                            o.id == u32::from(h.connector)
                                && o.geometry.width
                                    == (f64::from(mode.size.w) * 1000.0 / f64::from(o.scale_milli))
                                        .round() as u32
                                && o.geometry.height
                                    == (f64::from(mode.size.h) * 1000.0 / f64::from(o.scale_milli))
                                        .round() as u32
                        });
                    if compatible {
                        for (o, h) in saved.iter().zip(&mut self.heads) {
                            h.output.change_current_state(
                                None,
                                None,
                                Some(smithay::output::Scale::Fractional(
                                    f64::from(o.scale_milli) / 1000.0,
                                )),
                                Some((o.geometry.x, o.geometry.y).into()),
                            );
                        }
                    }
                }
            }
            self.display_transaction = forge_desktop_core::OutputTransaction::new(
                self.layout(),
                self.epoch.elapsed().as_millis() as u64,
            )
            .ok();
            self.app
                .update_output_layout(self.heads.iter().map(|h| h.output.clone()).collect());
            self.reset = true;
        }
        Ok(())
    }
    fn layout(&self) -> Vec<forge_desktop_core::Output> {
        self.heads
            .iter()
            .map(|h| {
                let r = outputs::geometry(&h.output);
                forge_desktop_core::Output {
                    id: u32::from(h.connector),
                    enabled: true,
                    geometry: Geometry {
                        x: r.loc.x,
                        y: r.loc.y,
                        width: r.size.w as u32,
                        height: r.size.h as u32,
                    },
                    scale_milli: (h.output.current_scale().fractional_scale() * 1000.0).round()
                        as u32,
                }
            })
            .collect()
    }
    fn display_tick(&mut self) {
        use forge_compositor::protocol::Command;
        let now = self.epoch.elapsed().as_millis() as u64;
        let mut changed = self
            .display_transaction
            .as_mut()
            .is_some_and(|t| t.tick(now).unwrap_or(false));
        for request in std::mem::take(&mut self.app.output_requests) {
            let result = match request {
                Command::Output { id, scale, x, y } => {
                    let mut layout = self.layout();
                    if let Some((index, output)) =
                        layout.iter_mut().enumerate().find(|(_, o)| o.id == id)
                    {
                        if index == 0 && (x != 0 || y != 0) {
                            Err("primary output must stay at origin".into())
                        } else {
                            let mode = self.heads[index].output.current_mode().unwrap();
                            output.scale_milli = scale;
                            output.geometry = Geometry {
                                x,
                                y,
                                width: (f64::from(mode.size.w) * 1000.0 / f64::from(scale)).round()
                                    as u32,
                                height: (f64::from(mode.size.h) * 1000.0 / f64::from(scale)).round()
                                    as u32,
                            };
                            self.display_transaction
                                .as_mut()
                                .ok_or("no active display transaction".to_string())
                                .and_then(|t| {
                                    t.stage(layout, now, 15000).map_err(|e| format!("{e:?}"))
                                })
                        }
                    } else {
                        Err("unknown output".into())
                    }
                }
                Command::DisplayConfirm => self
                    .display_transaction
                    .as_mut()
                    .ok_or("no displays".into())
                    .and_then(|t| {
                        t.confirm(now).map_err(|e| format!("{e:?}"))?;
                        if let Some(path) = output_config::path() {
                            if let Err(error) = output_config::save(&path, t.active()) {
                                eprintln!(
                                    "ForgeDesktop could not persist display confirmation: {error}"
                                );
                            }
                        }
                        Ok(())
                    }),
                Command::DisplayRevert => self
                    .display_transaction
                    .as_mut()
                    .ok_or("no displays".into())
                    .and_then(|t| t.cancel(now).map_err(|e| format!("{e:?}"))),
                _ => Err("not a display command".into()),
            };
            match result {
                Ok(()) => changed = true,
                Err(error) => eprintln!("ForgeDesktop display request rejected: {error}"),
            }
        }
        if changed {
            if let Some(transaction) = &self.display_transaction {
                for output in transaction.active() {
                    if let Some(head) = self
                        .heads
                        .iter_mut()
                        .find(|h| u32::from(h.connector) == output.id)
                    {
                        head.output.change_current_state(
                            None,
                            None,
                            Some(smithay::output::Scale::Fractional(
                                f64::from(output.scale_milli) / 1000.0,
                            )),
                            Some((output.geometry.x, output.geometry.y).into()),
                        );
                        head.damage = OutputDamageTracker::from_output(&head.output);
                        head.rendered = [false; 2];
                    }
                }
            }
            self.app
                .update_output_layout(self.heads.iter().map(|h| h.output.clone()).collect());
        }
        let mut state = format!(
            "d\t{}\n",
            u8::from(
                self.display_transaction
                    .as_ref()
                    .is_some_and(|t| t.pending())
            )
        );
        for head in &self.heads {
            let loc = head.output.current_location();
            let size = head.output.current_mode().unwrap().size;
            state.push_str(&format!(
                "o\t{}\t{}\t{}\t{}\t{}\t{}\n",
                u32::from(head.connector),
                (head.output.current_scale().fractional_scale() * 1000.0).round() as u32,
                loc.x,
                loc.y,
                size.w,
                size.h
            ));
        }
        self.app.output_state = state;
    }
}
impl Head {
    fn render(
        &mut self,
        app: &App,
        fd: &DrmDeviceFd,
        renderer: &mut PixmanRenderer,
        reset: bool,
    ) -> AppResult<bool> {
        let origin = self.output.current_location();
        let scale = self.output.current_scale().fractional_scale();
        let mut elements = app.pointer_elements(renderer, origin, scale);
        for mapped in app.windows.iter().rev().filter(|m| app.visible(m)) {
            let g = app.geometry(mapped.id);
            let physical = Point::<i32, Logical>::from((g.x - origin.x, g.y - origin.y))
                .to_physical_precise_round(scale);
            elements.extend(mapped.window.render_elements::<SoftwareElement>(
                renderer,
                physical,
                scale.into(),
                1.0,
            ));
        }
        let size = self.output.current_mode().unwrap().size;
        let mut framebuffer = renderer.bind(&mut self.buffers[self.current].2)?;
        let result = self.damage.render_output(
            renderer,
            &mut framebuffer,
            if self.rendered[self.current] { 2 } else { 0 },
            &elements,
            [0.055, 0.065, 0.09, 1.0],
        )?;
        let Some(rectangles) = result.damage else {
            return Ok(false);
        };
        result.sync.wait()?;
        let clips = PlaneDamageClips::from_damage(
            fd,
            Rectangle::from_size((f64::from(size.w), f64::from(size.h)).into()),
            Rectangle::from_size(size),
            rectangles.iter().copied(),
        )?;
        let plane = PlaneState {
            handle: self.surface.plane(),
            config: Some(PlaneConfig {
                src: Rectangle::from_size((f64::from(size.w), f64::from(size.h)).into()),
                dst: Rectangle::from_size(size),
                transform: Transform::Normal,
                alpha: 1.0,
                damage_clips: clips.as_ref().map(|c| c.blob()),
                fb: *self.buffers[self.current].1.as_ref(),
                fence: None,
            }),
        };
        if reset || self.surface.commit_pending() {
            self.surface.test_state([plane.clone()], true)?;
            self.surface.commit([plane], true)?;
        } else {
            self.surface.page_flip([plane], true)?;
        }
        self.rendered[self.current] = true;
        self.current = 1 - self.current;
        Ok(true)
    }
}

pub(super) fn run(path: &str) -> AppResult<()> {
    let (mut session, notifier) =
        LibSeatSession::new().map_err(|e| format!("DRM libseat initialization: {e}"))?;
    let seat_name = session.seat();
    let fd = DrmDeviceFd::new(DeviceFd::from(
        session
            .open(
                std::path::Path::new(path),
                OFlags::RDWR | OFlags::CLOEXEC | OFlags::NONBLOCK,
            )
            .map_err(|e| format!("DRM seat open {path}: {e}"))?,
    ));
    let (drm, drm_notifier) =
        DrmDevice::new(fd.clone(), false).map_err(|e| format!("DRM device initialization: {e}"))?;
    let mut input = Libinput::new_with_udev(LibinputSessionInterface::from(session.clone()));
    input
        .udev_assign_seat(&seat_name)
        .map_err(|_| "libinput seat assignment failed")?;
    let input_backend = LibinputInputBackend::new(input.clone());
    let mut display =
        Display::<App>::new().map_err(|e| format!("DRM Wayland display creation: {e}"))?;
    let mut dh = display.handle();
    let listener = ListeningSocket::bind("forge-wayland-0")
        .map_err(|e| format!("DRM Wayland socket bind: {e}"))?;
    let app = App::new(&dh, (1280, 800), "Forge-DRM-1")
        .map_err(|e| format!("DRM Wayland seat/output initialization: {e}"))?;
    let mut state = Runtime {
        app,
        drm,
        input,
        active: session.is_active(),
        pending: Default::default(),
        heads: Vec::new(),
        display_transaction: None,
        epoch: Instant::now(),
        reset: true,
        error: None,
    };
    let mut event_loop = EventLoop::<Runtime>::try_new()?;
    event_loop
        .handle()
        .insert_source(notifier, |event, _, state| match event {
            SessionEvent::PauseSession => {
                state.active = false;
                state.input.suspend();
                state.drm.pause();
                state.pending.clear();
            }
            SessionEvent::ActivateSession => {
                if let Err(error) = state.drm.activate(false) {
                    state.error = Some(error.to_string());
                    return;
                }
                if state.input.resume().is_err() {
                    state.error = Some("libinput resume failed".into());
                    return;
                }
                state.active = true;
                state.reset = true;
                state.app.dirty = true;
            }
        })
        .map_err(|error| error.error)?;
    event_loop
        .handle()
        .insert_source(drm_notifier, |event, _, state| match event {
            DrmEvent::VBlank(crtc) => {
                state.pending.remove(&crtc);
            }
            DrmEvent::Error(error) => state.error = Some(error.to_string()),
        })
        .map_err(|error| error.error)?;
    event_loop
        .handle()
        .insert_source(input_backend, |event, _, state| {
            if !state.active {
                return;
            }
            match event {
                InputEvent::Keyboard { event } => {
                    state.app.keyboard_event(
                        u32::from(event.key_code()),
                        event.state(),
                        event.time_msec(),
                    );
                }
                InputEvent::PointerMotion { event } => {
                    let point = state.app.pointer + event.delta();
                    let point = state.app.clamp_pointer(point);
                    state.app.motion(point, event.time_msec());
                    state.app.dirty = true;
                }
                InputEvent::PointerMotionAbsolute { event } => {
                    // Absolute devices describe one mapped output. QEMU's
                    // per-head VNC tablet coordinates have no head identity;
                    // bind to the primary output, never stretch over all heads.
                    let primary = outputs::geometry(&state.app.output);
                    let point = event.position_transformed(primary.size) + primary.loc.to_f64();
                    let point = state.app.clamp_pointer(point);
                    state.app.motion(point, event.time_msec());
                    state.app.dirty = true;
                }
                InputEvent::PointerButton { event } => {
                    let detail = match event.button_code() {
                        0x110 => 1,
                        0x112 => 2,
                        0x111 => 3,
                        _ => return,
                    };
                    state.app.button(
                        detail,
                        event.state() == ButtonState::Pressed,
                        event.time_msec(),
                    );
                }
                InputEvent::PointerAxis { event } => {
                    state.app.reconcile_pointer(event.time_msec());
                    let samples =
                        [Axis::Horizontal, Axis::Vertical].map(|axis| super::axis::AxisInput {
                            pixels: event.amount(axis),
                            v120: event.amount_v120(axis),
                            direction: event.relative_direction(axis),
                        });
                    let frame = super::axis::frame(event.time_msec(), event.source(), samples);
                    let pointer = state.app.seat.get_pointer().unwrap();
                    pointer.axis(&mut state.app, frame);
                    pointer.frame(&mut state.app);
                }
                _ => {}
            }
        })
        .map_err(|error| error.error)?;
    let mut renderer =
        PixmanRenderer::new().map_err(|e| format!("DRM Pixman initialization: {e}"))?;
    let start = Instant::now();
    let mut perf = perf::Recorder::new();
    state.rescan(&fd, &dh)?;
    let mut last_probe = Instant::now();
    eprintln!(
        "ForgeDesktop DRM Pixman ready; WAYLAND_DISPLAY=forge-wayland-0; outputs={}",
        state.heads.len()
    );
    loop {
        event_loop.dispatch(Duration::from_millis(4), &mut state)?;
        if let Some(error) = state.error.take() {
            return Err(error.into());
        }
        while let Some(stream) = listener.accept()? {
            let client_state = ClientState::for_stream(&stream);
            dh.insert_client(stream, Arc::new(client_state))?;
        }
        display.dispatch_clients(&mut state.app)?;
        state.app.popups.cleanup();
        state.app.shell_tick();
        state.app.ime.tick();
        state.display_tick();
        if state.active && last_probe.elapsed() >= Duration::from_millis(500) {
            state.rescan(&fd, &dh)?;
            last_probe = Instant::now();
        }
        if state.active && state.pending.is_empty() && state.app.dirty && !state.heads.is_empty() {
            let frame_start = Instant::now();
            let mut damaged = false;
            state.app.sync_output_membership();
            for head in &mut state.heads {
                if state.reset {
                    head.damage = OutputDamageTracker::from_output(&head.output);
                    head.rendered = [false; 2];
                }
                if head.render(&state.app, &fd, &mut renderer, state.reset)? {
                    state.pending.insert(head.surface.crtc());
                    damaged = true;
                }
                for mapped in state.app.windows.iter().filter(|m| state.app.visible(m)) {
                    mapped
                        .window
                        .send_frame(&head.output, start.elapsed(), None, |_, _| {
                            Some(head.output.clone())
                        });
                }
            }
            state.reset = false;
            state.app.dirty = false;
            state.app.frame_submitted(damaged);
            perf.frame(frame_start, damaged);
        }
        display.flush_clients()?;
    }
}



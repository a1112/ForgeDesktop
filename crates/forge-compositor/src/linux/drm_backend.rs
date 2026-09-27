//! DRM software scanout through a seat-controlled fd, with two dumb buffers.
use super::*;
use smithay::{
    backend::{
        allocator::{Allocator, Modifier, dmabuf::AsDmabuf, dumb::DumbAllocator},
        drm::{
            DrmDevice, DrmDeviceFd, DrmEvent, PlaneConfig, PlaneDamageClips, PlaneState,
            dumb::framebuffer_from_dumb_buffer,
        },
        input::{
            AbsolutePositionEvent, Event as InputEventTime, InputEvent, KeyboardKeyEvent,
            PointerAxisEvent, PointerButtonEvent, PointerMotionEvent,
        },
        libinput::{LibinputInputBackend, LibinputSessionInterface},
        renderer::element::{
            Kind,
            solid::{SolidColorBuffer, SolidColorRenderElement},
        },
        session::{Event as SessionEvent, Session, libseat::LibSeatSession},
    },
    reexports::{
        calloop::EventLoop,
        drm::control::{Device, connector},
        input::Libinput,
        rustix::fs::OFlags,
    },
    utils::DeviceFd,
};

smithay::render_elements! {
    SoftwareElement<=PixmanRenderer>;
    Surface=WaylandSurfaceRenderElement<PixmanRenderer>,
    Cursor=SolidColorRenderElement,
}
struct Runtime {
    app: App,
    drm: DrmDevice,
    input: Libinput,
    active: bool,
    pending: bool,
    reset: bool,
    error: Option<String>,
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
    let (mut drm, drm_notifier) =
        DrmDevice::new(fd.clone(), false).map_err(|e| format!("DRM device initialization: {e}"))?;
    let resources = fd
        .resource_handles()
        .map_err(|e| format!("DRM enumerate resources: {e}"))?;
    let connector = resources
        .connectors()
        .iter()
        .filter_map(|handle| fd.get_connector(*handle, true).ok())
        .find(|info| info.state() == connector::State::Connected && !info.modes().is_empty())
        .ok_or("no connected DRM output")?;
    let mode = connector
        .modes()
        .iter()
        .find(|m| m.size() == (1280, 800))
        .unwrap_or(&connector.modes()[0])
        .to_owned();
    let crtc = connector
        .encoders()
        .iter()
        .filter_map(|h| fd.get_encoder(*h).ok())
        .flat_map(|encoder| resources.filter_crtcs(encoder.possible_crtcs()))
        .next()
        .ok_or("no compatible DRM CRTC")?;
    let surface = drm
        .create_surface(crtc, mode, &[connector.handle()])
        .map_err(|e| format!("DRM create output surface: {e}"))?;
    let primary = fd
        .get_plane(surface.plane())
        .map_err(|e| format!("DRM query primary plane formats: {e}"))?;
    if !primary.formats().contains(&(Fourcc::Xrgb8888 as u32)) {
        return Err("DRM primary plane does not support software XRGB8888 scanout".into());
    }
    let (width, height) = mode.size();
    let size = (i32::from(width), i32::from(height));
    let mut allocator = DumbAllocator::new(fd.clone());
    let mut buffers = Vec::new();
    for _ in 0..2 {
        let buffer = allocator
            .create_buffer(
                u32::from(width),
                u32::from(height),
                Fourcc::Xrgb8888,
                &[Modifier::Linear],
            )
            .map_err(|e| format!("DRM allocate dumb buffer: {e}"))?;
        let framebuffer = framebuffer_from_dumb_buffer(&fd, &buffer, true)
            .map_err(|e| format!("DRM attach dumb framebuffer: {e}"))?;
        let dmabuf = buffer
            .export()
            .map_err(|e| format!("DRM export dumb buffer to PRIME: {e}"))?;
        buffers.push((buffer, framebuffer, dmabuf));
    }
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
    let app = App::new(&dh, size, "Forge-DRM-1")
        .map_err(|e| format!("DRM Wayland seat/output initialization: {e}"))?;
    let mut state = Runtime {
        app,
        drm,
        input,
        active: session.is_active(),
        pending: false,
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
                state.pending = false;
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
            DrmEvent::VBlank(_) => state.pending = false,
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
                    let keyboard = state.app.seat.get_keyboard().unwrap();
                    keyboard.input::<(), _>(
                        &mut state.app,
                        event.key_code(),
                        event.state(),
                        SERIAL_COUNTER.next_serial(),
                        event.time_msec(),
                        |_, _, _| FilterResult::Forward,
                    );
                }
                InputEvent::PointerMotion { event } => {
                    let point = state.app.pointer + event.delta();
                    let point = (
                        point.x.clamp(0.0, f64::from(state.app.size.0 - 1)),
                        point.y.clamp(0.0, f64::from(state.app.size.1 - 1)),
                    )
                        .into();
                    state.app.motion(point, event.time_msec());
                    state.app.dirty = true;
                }
                InputEvent::PointerMotionAbsolute { event } => {
                    let point = event.position_transformed(state.app.size.into());
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
    let cursor = SolidColorBuffer::new((7, 16), [0.95, 0.95, 1.0, 1.0]);
    let mut damage = OutputDamageTracker::from_output(&state.app.output);
    let start = Instant::now();
    let mut perf = perf::Recorder::new();
    let mut current = 0;
    let mut rendered = [false; 2];
    eprintln!(
        "ForgeDesktop DRM Pixman ready; WAYLAND_DISPLAY=forge-wayland-0; {}x{}",
        width, height
    );
    loop {
        event_loop.dispatch(Duration::from_millis(4), &mut state)?;
        if let Some(error) = state.error.take() {
            return Err(error.into());
        }
        while let Some(stream) = listener.accept()? {
            dh.insert_client(stream, Arc::new(ClientState::default()))?;
        }
        display.dispatch_clients(&mut state.app)?;
        state.app.popups.cleanup();
        state.app.shell_tick();
        if state.active && !state.pending && state.app.dirty {
            let frame_start = Instant::now();
            if state.reset {
                damage = OutputDamageTracker::from_output(&state.app.output);
                rendered = [false; 2];
            }
            let mut elements: Vec<SoftwareElement> = vec![
                SolidColorRenderElement::from_buffer(
                    &cursor,
                    (
                        state.app.pointer.x.round() as i32,
                        state.app.pointer.y.round() as i32,
                    ),
                    1.0,
                    1.0,
                    Kind::Cursor,
                )
                .into(),
            ];
            for mapped in state
                .app
                .windows
                .iter()
                .rev()
                .filter(|w| state.app.visible(w))
            {
                let g = state.app.geometry(mapped.id);
                elements.extend(mapped.window.render_elements::<SoftwareElement>(
                    &mut renderer,
                    (g.x, g.y).into(),
                    1.0.into(),
                    1.0,
                ));
            }
            let mut framebuffer = renderer
                .bind(&mut buffers[current].2)
                .map_err(|e| format!("DRM map PRIME buffer for Pixman: {e}"))?;
            let result = damage
                .render_output(
                    &mut renderer,
                    &mut framebuffer,
                    if rendered[current] { 2 } else { 0 },
                    &elements,
                    [0.055, 0.065, 0.09, 1.0],
                )
                .map_err(|e| format!("DRM Pixman render: {e:?}"))?;
            let damaged = result.damage.is_some();
            if let Some(rectangles) = result.damage {
                result.sync.wait()?;
                let clips = PlaneDamageClips::from_damage(
                    &fd,
                    Rectangle::from_size((f64::from(width), f64::from(height)).into()),
                    Rectangle::from_size(size.into()),
                    rectangles.iter().copied(),
                )?;
                let plane = PlaneState {
                    handle: surface.plane(),
                    config: Some(PlaneConfig {
                        src: Rectangle::from_size((f64::from(width), f64::from(height)).into()),
                        dst: Rectangle::from_size(size.into()),
                        transform: Transform::Normal,
                        alpha: 1.0,
                        damage_clips: clips.as_ref().map(|c| c.blob()),
                        fb: *buffers[current].1.as_ref(),
                        fence: None,
                    }),
                };
                if state.reset || surface.commit_pending() {
                    surface
                        .test_state([plane.clone()], true)
                        .map_err(|e| format!("DRM initial atomic state test: {e:?}"))?;
                    surface
                        .commit([plane], true)
                        .map_err(|e| format!("DRM initial modeset: {e}"))?;
                } else {
                    surface
                        .page_flip([plane], true)
                        .map_err(|e| format!("DRM page flip: {e}"))?;
                }
                state.pending = true;
                state.reset = false;
                rendered[current] = true;
                current = 1 - current;
            }
            for mapped in &state.app.windows {
                mapped
                    .window
                    .send_frame(&state.app.output, start.elapsed(), None, |_, _| {
                        Some(state.app.output.clone())
                    });
            }
            state.app.dirty = false;
            state.app.frame_submitted(damaged);
            perf.frame(frame_start, damaged);
        }
        display.flush_clients()?;
    }
}

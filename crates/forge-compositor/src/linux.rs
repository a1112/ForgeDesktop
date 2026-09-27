//! Unprivileged, software-only compositor. No capture/control protocol.
mod axis;
mod control;
mod drm_backend;
mod perf;
mod shell;
use forge_desktop_core::{Desktop, Geometry, WindowId};
use smithay::{
    backend::{
        allocator::Fourcc,
        input::{Axis, AxisSource, ButtonState, KeyState},
        renderer::{
            Bind, ExportMem, Offscreen,
            damage::OutputDamageTracker,
            element::{AsRenderElements, surface::WaylandSurfaceRenderElement},
            pixman::PixmanRenderer,
            utils::{on_commit_buffer_handler, with_renderer_surface_state},
        },
    },
    delegate_compositor, delegate_data_device, delegate_output, delegate_seat, delegate_shm,
    delegate_xdg_shell,
    desktop::{
        PopupKeyboardGrab, PopupManager, PopupPointerGrab, Window, WindowSurfaceType,
        find_popup_root_surface,
    },
    input::{
        Seat, SeatHandler, SeatState,
        keyboard::FilterResult,
        pointer::{ButtonEvent, CursorImageStatus, Focus, MotionEvent},
    },
    output::{Mode, Output, PhysicalProperties, Subpixel},
    reexports::{
        wayland_protocols::xdg::shell::server::xdg_toplevel,
        wayland_server::{
            Client, Display, ListeningSocket, Resource,
            backend::{ClientData, ClientId, DisconnectReason},
            protocol::{wl_buffer, wl_seat, wl_surface::WlSurface},
        },
        x11rb::{
            self, COPY_DEPTH_FROM_PARENT,
            connection::{Connection, RequestConnection},
            protocol::{Event, xproto::*},
            wrapper::ConnectionExt as _,
        },
    },
    utils::{Logical, Point, Rectangle, SERIAL_COUNTER, Serial, Transform},
    wayland::{
        buffer::BufferHandler,
        compositor::{CompositorClientState, CompositorHandler, CompositorState},
        output::{OutputHandler, OutputManagerState},
        selection::{
            SelectionHandler,
            data_device::{
                ClientDndGrabHandler, DataDeviceHandler, DataDeviceState, ServerDndGrabHandler,
                set_data_device_focus,
            },
        },
        shell::xdg::{
            PopupSurface, PositionerState, ToplevelSurface, XdgShellHandler, XdgShellState,
        },
        shm::{ShmHandler, ShmState},
    },
};
use std::{
    error::Error,
    os::unix::io::OwnedFd,
    sync::Arc,
    time::{Duration, Instant},
};

type AppResult<T> = std::result::Result<T, Box<dyn Error>>;
struct Mapped {
    id: WindowId,
    window: Window,
    has_buffer: bool,
    role: Option<String>,
}
struct Drag {
    id: WindowId,
    origin: Point<f64, Logical>,
    geometry: Geometry,
    edges: u32,
}
struct App {
    display: smithay::reexports::wayland_server::DisplayHandle,
    compositor: CompositorState,
    xdg: XdgShellState,
    shm: ShmState,
    seats: SeatState<Self>,
    seat: Seat<Self>,
    data: DataDeviceState,
    _outputs: OutputManagerState,
    output: Output,
    popups: PopupManager,
    desktop: Desktop,
    windows: Vec<Mapped>,
    pointer: Point<f64, Logical>,
    pointer_target: Option<(WlSurface, Point<f64, Logical>)>,
    keyboard_active: bool,
    drag: Option<Drag>,
    dirty: bool,
    size: (i32, i32),
    shell: shell::Shell,
    launcher: bool,
    launcher_key_down: bool,
    launcher_pending: Option<u32>,
}
impl BufferHandler for App {
    fn buffer_destroyed(&mut self, _: &wl_buffer::WlBuffer) {}
}
impl CompositorHandler for App {
    fn compositor_state(&mut self) -> &mut CompositorState {
        &mut self.compositor
    }
    fn client_compositor_state<'a>(&self, client: &'a Client) -> &'a CompositorClientState {
        &client
            .get_data::<ClientState>()
            .expect("server-owned client state")
            .compositor
    }
    fn commit(&mut self, surface: &WlSurface) {
        on_commit_buffer_handler::<Self>(surface);
        self.popups.commit(surface);
        let mut newly_mapped = None;
        let mut unmapped = false;
        for mapped in &mut self.windows {
            mapped.window.on_commit();
            let toplevel = mapped.window.toplevel().unwrap();
            let root = toplevel.wl_surface();
            if root == surface && !toplevel.is_initial_configure_sent() {
                toplevel.send_configure();
            }
            let has_buffer =
                with_renderer_surface_state(root, |s| s.buffer().is_some()).unwrap_or(false);
            if has_buffer != mapped.has_buffer {
                mapped.has_buffer = has_buffer;
                if has_buffer {
                    self.output.enter(root);
                    if mapped.role.is_none() {
                        let _ = self.desktop.restore(mapped.id);
                        newly_mapped = Some(mapped.id);
                    } else if mapped.role.as_deref() == Some("forge.launcher") && self.launcher {
                        newly_mapped = Some(mapped.id);
                    }
                } else {
                    self.output.leave(root);
                    let _ = self.desktop.minimize(mapped.id);
                    if self.drag.as_ref().is_some_and(|d| d.id == mapped.id) {
                        self.drag = None;
                    }
                    unmapped = true;
                }
            }
        }
        for mapped in self
            .windows
            .iter()
            .filter(|m| m.has_buffer && m.role.is_none())
        {
            if self.drag.is_none() {
                let size = mapped.window.geometry().size;
                if size.w > 0 && size.h > 0 {
                    let mut geometry = self.geometry(mapped.id);
                    geometry.width = size.w as u32;
                    geometry.height = size.h as u32;
                    let _ = self.desktop.set_geometry(mapped.id, geometry);
                }
            }
        }
        if let Some(id) = newly_mapped {
            self.focus(id);
        } else if unmapped {
            self.restore_focus();
        }
        self.reconcile_pointer(0);
        self.dirty = true;
    }
}
impl ShmHandler for App {
    fn shm_state(&self) -> &ShmState {
        &self.shm
    }
}
impl OutputHandler for App {}
impl SelectionHandler for App {
    type SelectionUserData = ();
}
impl DataDeviceHandler for App {
    fn data_device_state(&self) -> &DataDeviceState {
        &self.data
    }
}
impl ClientDndGrabHandler for App {}
impl ServerDndGrabHandler for App {
    fn send(&mut self, _: String, _: OwnedFd, _: Seat<Self>) {}
}
impl SeatHandler for App {
    type KeyboardFocus = WlSurface;
    type PointerFocus = WlSurface;
    type TouchFocus = WlSurface;
    fn seat_state(&mut self) -> &mut SeatState<Self> {
        &mut self.seats
    }
    fn focus_changed(&mut self, seat: &Seat<Self>, focused: Option<&WlSurface>) {
        set_data_device_focus(&self.display, seat, focused.and_then(Resource::client));
    }
    fn cursor_image(&mut self, _: &Seat<Self>, _: CursorImageStatus) {}
}
impl App {
    fn restore_focus(&mut self) {
        if let Some(id) = self.desktop.focused() {
            self.focus(id);
        } else {
            self.seat
                .get_keyboard()
                .unwrap()
                .set_focus(self, None, SERIAL_COUNTER.next_serial());
        }
    }
    fn geometry(&self, id: WindowId) -> Geometry {
        self.desktop
            .window(id)
            .expect("mapped policy window")
            .geometry()
    }
    fn locate(&self, surface: &ToplevelSurface) -> Option<WindowId> {
        self.windows
            .iter()
            .find(|w| w.window.toplevel() == Some(surface))
            .map(|w| w.id)
    }
    fn focus(&mut self, id: WindowId) {
        if let Some(role) = self
            .windows
            .iter()
            .find(|m| m.id == id)
            .and_then(|m| m.role.clone())
        {
            if role != "forge.background" {
                let mapped = self.windows.iter().find(|m| m.id == id).unwrap();
                if mapped.window.set_activated(true) {
                    mapped.window.toplevel().unwrap().send_configure();
                }
                let surface = mapped.window.toplevel().unwrap().wl_surface().clone();
                self.seat.get_keyboard().unwrap().set_focus(
                    self,
                    Some(surface),
                    SERIAL_COUNTER.next_serial(),
                );
            }
            return;
        }
        if !self.windows.iter().any(|m| m.id == id && m.has_buffer) {
            return;
        }
        if self.desktop.focus(id).is_err() {
            return;
        }
        if let Some(index) = self.windows.iter().position(|w| w.id == id) {
            let mapped = self.windows.remove(index);
            self.windows.push(mapped);
        }
        self.arrange();
        let surface = self
            .windows
            .iter()
            .find(|w| w.id == id)
            .and_then(|w| w.window.toplevel())
            .map(|s| s.wl_surface().clone());
        for mapped in &self.windows {
            if mapped.window.set_activated(mapped.id == id) {
                mapped.window.toplevel().unwrap().send_configure();
            }
        }
        self.seat.get_keyboard().unwrap().set_focus(
            self,
            surface.filter(|_| self.keyboard_active),
            SERIAL_COUNTER.next_serial(),
        );
        self.dirty = true;
    }
    fn begin_drag(
        &mut self,
        surface: &ToplevelSurface,
        seat: &wl_seat::WlSeat,
        serial: Serial,
        edges: u32,
    ) {
        if Seat::from_resource(seat).as_ref() != Some(&self.seat) {
            return;
        }
        let pointer = self.seat.get_pointer().unwrap();
        if !pointer.has_grab(serial) {
            return;
        }
        let Some(start) = pointer.grab_start_data() else {
            return;
        };
        let Some((focus, _)) = start.focus else {
            return;
        };
        if focus.client().map(|c| c.id()) != surface.wl_surface().client().map(|c| c.id()) {
            return;
        }
        if let Some(id) = self.locate(surface) {
            if self.windows.iter().any(|m| m.id == id && m.role.is_some())
                || self
                    .desktop
                    .window(id)
                    .is_some_and(|w| w.maximized() || w.fullscreen())
            {
                return;
            }
            self.drag = Some(Drag {
                id,
                origin: self.pointer,
                geometry: self.geometry(id),
                edges,
            });
        }
    }
    fn motion(&mut self, point: Point<f64, Logical>, time: u32) {
        self.pointer = point;
        if let Some(drag) = &self.drag {
            let g = drag.geometry;
            let dx = (point.x - drag.origin.x) as i32;
            let dy = (point.y - drag.origin.y) as i32;
            let changed = if drag.edges == 0 {
                Some((g.x + dx, g.y + dy, g.width as i32, g.height as i32))
            } else {
                forge_compositor::resize_geometry(
                    (g.x, g.y, g.width as i32, g.height as i32),
                    (dx, dy),
                    drag.edges,
                )
            };
            if let Some((x, y, w, h)) = changed {
                let _ = self.desktop.set_geometry(
                    drag.id,
                    Geometry {
                        x,
                        y,
                        width: w as u32,
                        height: h as u32,
                    },
                );
                if drag.edges != 0 {
                    if let Some(window) = self.windows.iter().find(|m| m.id == drag.id) {
                        let surface = window.window.toplevel().unwrap();
                        surface.with_pending_state(|s| {
                            s.size = Some((w, h).into());
                            s.states.set(xdg_toplevel::State::Resizing);
                        });
                        surface.send_pending_configure();
                    }
                }
                self.dirty = true;
            }
        }
        self.send_pointer_motion(time, true);
    }
    fn reconcile_pointer(&mut self, time: u32) {
        if !self.seat.get_pointer().unwrap().is_grabbed() {
            self.send_pointer_motion(time, false);
        }
    }
    fn send_pointer_motion(&mut self, time: u32, moved: bool) {
        let point = self.pointer;
        let focus = self
            .windows
            .iter()
            .rev()
            .filter(|m| self.visible(m))
            .find_map(|mapped| {
                let g = self.geometry(mapped.id);
                let location: Point<i32, Logical> = (g.x, g.y).into();
                mapped
                    .window
                    .surface_under(point - location.to_f64(), WindowSurfaceType::ALL)
                    .map(|(s, p)| (s, (p + location).to_f64()))
            });
        let pointer = self.seat.get_pointer().unwrap();
        if !moved
            && self.pointer_target == focus
            && pointer.current_focus() == focus.as_ref().map(|(s, _)| s.clone())
        {
            return;
        }
        self.pointer_target = focus.clone();
        pointer.motion(
            self,
            focus,
            &MotionEvent {
                location: point,
                serial: SERIAL_COUNTER.next_serial(),
                time,
            },
        );
        pointer.frame(self);
    }
    fn button(&mut self, detail: u8, pressed: bool, time: u32) {
        self.reconcile_pointer(time);
        if (4..=7).contains(&detail) {
            if pressed {
                let axis = if detail < 6 {
                    Axis::Vertical
                } else {
                    Axis::Horizontal
                };
                let sign = if detail == 4 || detail == 6 {
                    -1.0
                } else {
                    1.0
                };
                let pointer = self.seat.get_pointer().unwrap();
                pointer.axis(
                    self,
                    axis::frame(
                        time,
                        AxisSource::Wheel,
                        [Axis::Horizontal, Axis::Vertical].map(|candidate| {
                            if candidate == axis {
                                axis::AxisInput {
                                    v120: Some(sign * 120.0),
                                    ..Default::default()
                                }
                            } else {
                                axis::AxisInput::default()
                            }
                        }),
                    ),
                );
                pointer.frame(self);
            }
            return;
        }
        let button = match detail {
            1 => 0x110,
            2 => 0x112,
            3 => 0x111,
            _ => return,
        };
        if pressed && !self.seat.get_pointer().unwrap().is_grabbed() {
            if let Some(id) = self
                .windows
                .iter()
                .rev()
                .filter(|m| self.visible(m))
                .find_map(|m| {
                    let g = self.geometry(m.id);
                    m.window
                        .surface_under(
                            self.pointer - Point::from((g.x as f64, g.y as f64)),
                            WindowSurfaceType::ALL,
                        )
                        .map(|_| m.id)
                })
            {
                self.focus(id);
                self.reconcile_pointer(time);
            }
        }
        let pointer = self.seat.get_pointer().unwrap();
        pointer.button(
            self,
            &ButtonEvent {
                serial: SERIAL_COUNTER.next_serial(),
                time,
                button,
                state: if pressed {
                    ButtonState::Pressed
                } else {
                    ButtonState::Released
                },
            },
        );
        pointer.frame(self);
        if !pressed {
            if let Some(drag) = self.drag.take() {
                if let Some(mapped) = self.windows.iter().find(|m| m.id == drag.id) {
                    let s = mapped.window.toplevel().unwrap();
                    s.with_pending_state(|p| p.states.unset(xdg_toplevel::State::Resizing));
                    s.send_pending_configure();
                }
            }
            self.reconcile_pointer(time);
        }
    }
}
impl XdgShellHandler for App {
    fn xdg_shell_state(&mut self) -> &mut XdgShellState {
        &mut self.xdg
    }
    fn new_toplevel(&mut self, surface: ToplevelSurface) {
        let shell_client = surface
            .wl_surface()
            .client()
            .and_then(|c| c.get_credentials(&self.display).ok())
            .is_some_and(|c| self.shell.credentials() == Some((c.pid as u32, c.uid)));
        if self.windows.len() >= 52
            || (!shell_client && self.windows.iter().filter(|m| m.role.is_none()).count() >= 48)
        {
            surface.send_close();
            return;
        }
        let offset = (self.windows.len() % 8) as i32 * 30;
        let Ok(id) = self.desktop.map(
            self.desktop.active_workspace(),
            Geometry {
                x: 50 + offset,
                y: 60 + offset,
                width: 640,
                height: 480,
            },
        ) else {
            surface.send_close();
            return;
        };
        surface.with_pending_state(|s| {
            s.size = Some((640, 480).into());
        });
        surface.send_configure();
        // Policy IDs exist before the client attaches its first buffer.
        // Keep that role out of focus/visibility until it actually maps.
        let _ = self.desktop.minimize(id);
        self.windows.push(Mapped {
            id,
            window: Window::new_wayland_window(surface),
            has_buffer: false,
            role: None,
        });
    }
    fn title_changed(&mut self, s: ToplevelSurface) {
        self.update_role(&s);
    }
    fn maximize_request(&mut self, s: ToplevelSurface) {
        if let Some(id) = self.locate(&s) {
            if !self.desktop.window(id).unwrap().maximized() {
                let _ = self.action(id, "maximize");
            } else {
                s.send_configure();
            }
        }
    }
    fn unmaximize_request(&mut self, s: ToplevelSurface) {
        if let Some(id) = self.locate(&s) {
            let _ = self.desktop.set_maximized(id, None);
            self.configure(id);
        }
    }
    fn fullscreen_request(
        &mut self,
        s: ToplevelSurface,
        _: Option<smithay::reexports::wayland_server::protocol::wl_output::WlOutput>,
    ) {
        if let Some(id) = self.locate(&s) {
            if !self.desktop.window(id).unwrap().fullscreen() {
                let _ = self.action(id, "fullscreen");
            } else {
                s.send_configure();
            }
        }
    }
    fn unfullscreen_request(&mut self, s: ToplevelSurface) {
        if let Some(id) = self.locate(&s) {
            let _ = self.desktop.set_fullscreen(id, None);
            self.configure(id);
        }
    }
    fn minimize_request(&mut self, s: ToplevelSurface) {
        if let Some(id) = self.locate(&s) {
            let _ = self.action(id, "minimize");
        }
    }
    fn toplevel_destroyed(&mut self, surface: ToplevelSurface) {
        if let Some(id) = self.locate(&surface) {
            self.windows.retain(|m| m.id != id);
            let _ = self.desktop.unmap(id);
            self.restore_focus();
            self.reconcile_pointer(0);
            self.dirty = true;
        }
    }
    fn new_popup(&mut self, surface: PopupSurface, positioner: PositionerState) {
        surface.with_pending_state(|s| s.geometry = positioner.get_geometry());
        let _ = surface.send_configure();
        let _ = self.popups.track_popup(surface.into());
    }
    fn reposition_request(
        &mut self,
        surface: PopupSurface,
        positioner: PositionerState,
        token: u32,
    ) {
        surface.with_pending_state(|s| s.geometry = positioner.get_geometry());
        surface.send_repositioned(token);
    }
    fn grab(&mut self, surface: PopupSurface, resource: wl_seat::WlSeat, serial: Serial) {
        let pointer = self.seat.get_pointer().unwrap();
        if Seat::from_resource(&resource).as_ref() != Some(&self.seat) || !pointer.has_grab(serial)
        {
            surface.send_popup_done();
            return;
        }
        let kind = surface.clone().into();
        let Ok(root) = find_popup_root_surface(&kind) else {
            surface.send_popup_done();
            return;
        };
        let Some(start) = pointer.grab_start_data() else {
            surface.send_popup_done();
            return;
        };
        if start.focus.and_then(|(s, _)| s.client()).map(|c| c.id())
            != root.client().map(|c| c.id())
        {
            surface.send_popup_done();
            return;
        }
        let Ok(grab) = self.popups.grab_popup(root, kind, &self.seat, serial) else {
            return;
        };
        let keyboard = self.seat.get_keyboard().unwrap();
        keyboard.set_focus(self, grab.current_grab(), serial);
        keyboard.set_grab(self, PopupKeyboardGrab::new(&grab), serial);
        pointer.set_grab(self, PopupPointerGrab::new(&grab), serial, Focus::Keep);
    }
    fn move_request(&mut self, s: ToplevelSurface, seat: wl_seat::WlSeat, serial: Serial) {
        self.begin_drag(&s, &seat, serial, 0);
    }
    fn resize_request(
        &mut self,
        s: ToplevelSurface,
        seat: wl_seat::WlSeat,
        serial: Serial,
        edges: xdg_toplevel::ResizeEdge,
    ) {
        self.begin_drag(&s, &seat, serial, edges as u32);
    }
}

#[derive(Default)]
struct ClientState {
    compositor: CompositorClientState,
}
impl ClientData for ClientState {
    fn initialized(&self, _: ClientId) {}
    fn disconnected(&self, _: ClientId, _: DisconnectReason) {}
}
delegate_compositor!(App);
delegate_xdg_shell!(App);
delegate_shm!(App);
delegate_seat!(App);
delegate_data_device!(App);
delegate_output!(App);

impl App {
    fn new(
        dh: &smithay::reexports::wayland_server::DisplayHandle,
        size: (i32, i32),
        name: &str,
    ) -> AppResult<Self> {
        let output = Output::new(
            name.into(),
            PhysicalProperties {
                size: (0, 0).into(),
                subpixel: Subpixel::Unknown,
                make: "ForgeOS".into(),
                model: "Pixman software output".into(),
            },
        );
        output.create_global::<App>(dh);
        let mode = Mode {
            size: size.into(),
            refresh: 60000,
        };
        output.change_current_state(
            Some(mode),
            Some(Transform::Normal),
            None,
            Some((0, 0).into()),
        );
        output.set_preferred(mode);
        let mut seats = SeatState::new();
        let mut seat = seats.new_wl_seat(dh, "seat0");
        seat.add_keyboard(Default::default(), 500, 25)?;
        seat.add_pointer();
        let state = App {
            display: dh.clone(),
            compositor: CompositorState::new::<App>(dh),
            xdg: XdgShellState::new_with_capabilities::<App>(
                dh,
                [
                    xdg_toplevel::WmCapabilities::Maximize,
                    xdg_toplevel::WmCapabilities::Fullscreen,
                    xdg_toplevel::WmCapabilities::Minimize,
                ],
            ),
            shm: ShmState::new::<App>(dh, vec![]),
            data: DataDeviceState::new::<App>(dh),
            _outputs: OutputManagerState::new_with_xdg_output::<App>(dh),
            seats,
            seat,
            output,
            popups: PopupManager::default(),
            desktop: Desktop::default(),
            windows: vec![],
            pointer: (0.0, 0.0).into(),
            pointer_target: None,
            keyboard_active: true,
            drag: None,
            dirty: true,
            size,
            shell: shell::Shell::new(),
            launcher: false,
            launcher_key_down: false,
            launcher_pending: None,
        };

        Ok(state)
    }
}

pub fn run() -> AppResult<()> {
    if smithay::reexports::rustix::process::geteuid().is_root() {
        return Err("compositor must run as an ordinary user".into());
    }
    use std::os::unix::fs::MetadataExt;
    let runtime = std::env::var_os("XDG_RUNTIME_DIR").ok_or("XDG_RUNTIME_DIR is required")?;
    let metadata = std::fs::metadata(&runtime)
        .map_err(|error| format!("runtime directory metadata {:?}: {error}", runtime))?;
    if !forge_compositor::private_runtime_directory(
        metadata.uid(),
        smithay::reexports::rustix::process::geteuid().as_raw(),
        metadata.mode(),
        metadata.is_dir(),
    ) {
        return Err("XDG_RUNTIME_DIR must be a private directory owned by the current user".into());
    }
    let args: Vec<_> = std::env::args().skip(1).collect();
    match args.as_slice() {
        [] => {}
        [mode] if mode == "--nested" => {}
        [mode, device] if mode == "--drm" && device.starts_with("/dev/dri/card") => {
            return drm_backend::run(device);
        }
        _ => return Err("usage: forge-compositor --nested | --drm /dev/dri/cardN".into()),
    }
    let (conn, screen_index) = x11rb::connect(None)?;
    let screen = &conn.setup().roots[screen_index];
    if screen.root_depth != 24 {
        return Err("nested output requires X11 depth 24".into());
    }
    let window = conn.generate_id()?;
    let gc = conn.generate_id()?;
    conn.create_window(
        COPY_DEPTH_FROM_PARENT,
        window,
        screen.root,
        0,
        0,
        1280,
        800,
        0,
        WindowClass::INPUT_OUTPUT,
        0,
        &CreateWindowAux::new()
            .background_pixel(0x141824)
            .event_mask(
                EventMask::EXPOSURE
                    | EventMask::STRUCTURE_NOTIFY
                    | EventMask::POINTER_MOTION
                    | EventMask::BUTTON_PRESS
                    | EventMask::BUTTON_RELEASE
                    | EventMask::KEY_PRESS
                    | EventMask::KEY_RELEASE
                    | EventMask::FOCUS_CHANGE,
            ),
    )?;
    conn.change_property8(
        PropMode::REPLACE,
        window,
        AtomEnum::WM_NAME,
        AtomEnum::STRING,
        b"ForgeDesktop - Pixman native Wayland",
    )?;
    let wm_protocols = conn.intern_atom(false, b"WM_PROTOCOLS")?.reply()?.atom;
    let wm_delete = conn.intern_atom(false, b"WM_DELETE_WINDOW")?.reply()?.atom;
    conn.change_property32(
        PropMode::REPLACE,
        window,
        wm_protocols,
        AtomEnum::ATOM,
        &[wm_delete],
    )?;
    conn.create_gc(gc, window, &CreateGCAux::new())?;
    conn.map_window(window)?;
    conn.flush()?;
    let mut display = Display::<App>::new()?;
    let mut dh = display.handle();
    let listener = ListeningSocket::bind("forge-wayland-0")?;
    let mut state = App::new(&dh, (1280, 800), "Forge-Nested-1")?;
    let mut renderer = PixmanRenderer::new()?;
    let mut target = renderer.create_buffer(Fourcc::Argb8888, state.size.into())?;
    let mut damage = OutputDamageTracker::from_output(&state.output);
    let start = Instant::now();
    let mut perf = perf::Recorder::new();
    let mut previous_frame = Instant::now() - Duration::from_millis(17);
    eprintln!("ForgeDesktop nested Pixman ready; WAYLAND_DISPLAY=forge-wayland-0");
    loop {
        while let Some(stream) = listener.accept()? {
            dh.insert_client(stream, Arc::new(ClientState::default()))?;
        }
        display.dispatch_clients(&mut state)?;
        state.popups.cleanup();
        state.shell_tick();
        while let Some(event) = conn.poll_for_event()? {
            match event {
                Event::ClientMessage(e)
                    if e.type_ == wm_protocols && e.data.as_data32()[0] == wm_delete =>
                {
                    return Ok(());
                }
                Event::DestroyNotify(_) => return Ok(()),
                Event::Expose(_) => {
                    state.dirty = true;
                    damage = OutputDamageTracker::from_output(&state.output);
                }
                Event::FocusOut(e) if e.mode == NotifyMode::NORMAL => {
                    state.keyboard_active = false;
                    state.launcher_key_down = false;
                    let keyboard = state.seat.get_keyboard().unwrap();
                    for code in keyboard.pressed_keys() {
                        keyboard.input::<(), _>(
                            &mut state,
                            code,
                            KeyState::Released,
                            SERIAL_COUNTER.next_serial(),
                            0,
                            |_, _, _| FilterResult::Forward,
                        );
                    }
                    keyboard.set_focus(&mut state, None, SERIAL_COUNTER.next_serial());
                }
                Event::FocusIn(e) if e.mode == NotifyMode::NORMAL => {
                    let keyboard = state.seat.get_keyboard().unwrap();
                    let keys = conn.query_keymap()?.reply()?.keys;
                    for code in 8..256u32 {
                        if keys[code as usize / 8] & (1 << (code % 8)) != 0 {
                            keyboard.input::<(), _>(
                                &mut state,
                                code.into(),
                                KeyState::Pressed,
                                SERIAL_COUNTER.next_serial(),
                                0,
                                |_, _, _| FilterResult::Forward,
                            );
                        }
                    }
                    state.keyboard_active = true;
                    state.restore_focus();
                    state.reconcile_pointer(0);
                }
                Event::ConfigureNotify(e)
                    if (e.width as i32, e.height as i32) != state.size
                        && e.width > 0
                        && e.height > 0 =>
                {
                    state.size = (i32::from(e.width), i32::from(e.height));
                    let mode = Mode {
                        size: state.size.into(),
                        refresh: 60000,
                    };
                    state
                        .output
                        .change_current_state(Some(mode), None, None, None);
                    state.output.set_preferred(mode);
                    let roles: Vec<_> = state
                        .windows
                        .iter()
                        .filter(|m| m.role.is_some())
                        .map(|m| m.window.toplevel().unwrap().clone())
                        .collect();
                    for role in roles {
                        state.update_role(&role);
                    }
                    target = renderer.create_buffer(Fourcc::Argb8888, state.size.into())?;
                    damage = OutputDamageTracker::from_output(&state.output);
                    state.dirty = true;
                }
                Event::MotionNotify(e) => {
                    state.motion((f64::from(e.event_x), f64::from(e.event_y)).into(), e.time)
                }
                Event::ButtonPress(e) => state.button(e.detail, true, e.time),
                Event::ButtonRelease(e) => state.button(e.detail, false, e.time),
                Event::KeyPress(e) => {
                    state.keyboard_event(u32::from(e.detail), KeyState::Pressed, e.time)
                }
                Event::KeyRelease(e) => {
                    state.keyboard_event(u32::from(e.detail), KeyState::Released, e.time)
                }
                _ => {}
            }
        }
        if state.dirty && previous_frame.elapsed() >= Duration::from_millis(16) {
            let frame_start = Instant::now();
            let mut elements: Vec<WaylandSurfaceRenderElement<PixmanRenderer>> = Vec::new();
            for mapped in state.windows.iter().rev().filter(|m| state.visible(m)) {
                let g = state.geometry(mapped.id);
                elements.extend(mapped.window.render_elements(
                    &mut renderer,
                    (g.x, g.y).into(),
                    1.0.into(),
                    1.0,
                ));
            }
            let mut framebuffer = renderer.bind(&mut target)?;
            let result = damage.render_output(
                &mut renderer,
                &mut framebuffer,
                1,
                &elements,
                [0.055, 0.065, 0.09, 1.0],
            )?;
            let damaged = result.damage.is_some();
            if let Some(rectangles) = result.damage {
                for rect in rectangles {
                    let mapping = renderer.copy_framebuffer(
                        &framebuffer,
                        Rectangle::new(
                            (rect.loc.x, rect.loc.y).into(),
                            (rect.size.w, rect.size.h).into(),
                        ),
                        Fourcc::Argb8888,
                    )?;
                    let bytes = renderer.map_texture(&mapping)?;
                    let width = rect.size.w as usize;
                    let height = rect.size.h as usize;
                    let rows = forge_compositor::upload_rows(width, conn.maximum_request_bytes())
                        .ok_or("X11 maximum upload too small")?;
                    for y in (0..height).step_by(rows) {
                        let count = rows.min(height - y);
                        conn.put_image(
                            ImageFormat::Z_PIXMAP,
                            window,
                            gc,
                            width as u16,
                            count as u16,
                            rect.loc.x as i16,
                            (rect.loc.y + y as i32) as i16,
                            0,
                            24,
                            &bytes[y * width * 4..(y + count) * width * 4],
                        )?;
                    }
                }
                conn.flush()?;
            }
            for mapped in state.windows.iter().filter(|m| state.visible(m)) {
                mapped
                    .window
                    .send_frame(&state.output, start.elapsed(), None, |_, _| {
                        Some(state.output.clone())
                    });
            }
            state.dirty = false;
            previous_frame = Instant::now();
            state.frame_submitted(damaged);
            perf.frame(frame_start, damaged);
        }
        display.flush_clients()?;
        // Bounded poll also observes disconnects; idle iterations never repaint.
        std::thread::sleep(Duration::from_millis(4));
    }
}

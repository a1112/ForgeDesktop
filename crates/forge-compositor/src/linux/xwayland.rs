//! Rootless XWayland, supervised independently from native Wayland clients.
use super::*;
use smithay::{
    reexports::calloop::EventLoop,
    wayland::{
        selection::{
            SelectionSource, SelectionTarget,
            data_device::{
                clear_data_device_selection, request_data_device_client_selection,
                set_data_device_selection,
            },
            primary_selection::{
                clear_primary_selection, request_primary_client_selection, set_primary_selection,
            },
        },
        xwayland_shell::{XWaylandShellHandler, XWaylandShellState},
    },
    xwayland::{
        X11Surface, X11Wm, XWayland, XWaylandEvent, XwmHandler,
        xwm::{Reorder, ResizeEdge, XwmId},
    },
};
use std::process::Stdio;
pub(super) struct Runtime {
    events: EventLoop<'static, App>,
    token: Option<smithay::reexports::calloop::RegistrationToken>,
    started: bool,
    next: Instant,
    display: Option<u32>,
    failures: u32,
}
impl Runtime {
    pub fn new() -> AppResult<Self> {
        Ok(Self {
            events: EventLoop::try_new()?,
            token: None,
            started: false,
            next: Instant::now(),
            display: None,
            failures: 0,
        })
    }
    pub fn tick(&mut self, app: &mut App) -> AppResult<()> {
        self.events.dispatch(Duration::ZERO, app)?;
        if app.xwayland_failed {
            app.xwayland_failed = false;
            let clipboard =
                smithay::wayland::selection::data_device::current_data_device_selection_userdata(
                    &app.seat,
                )
                .is_some();
            let primary =
                smithay::wayland::selection::primary_selection::current_primary_selection_userdata(
                    &app.seat,
                )
                .is_some();
            if clipboard {
                clear_data_device_selection(&app.display, &app.seat);
            }
            if primary {
                clear_primary_selection(&app.display, &app.seat);
            }
            app.xwm = None;
            app.xwayland_handle = None;
            if let Some(token) = self.token.take() {
                self.events.handle().remove(token);
            }
            // XWayland restarts its surface serial counter. The shell helper
            // caches serial -> wl_surface without an XWM generation key;
            // retaining it can associate a new X11 window with a dead surface
            // when the X11 serial event wins the race against Wayland commit.
            app.display
                .remove_global::<App>(app.xwayland_shell.global());
            app.xwayland_shell = XWaylandShellState::new::<App>(&app.display);
            self.events = EventLoop::try_new()?;
            self.started = false;
            let ids: Vec<_> = app
                .windows
                .iter()
                .filter(|m| m.window.x11_surface().is_some())
                .map(|m| m.id)
                .collect();
            for id in ids {
                let _ = app.desktop.unmap(id);
            }
            app.windows.retain(|m| m.window.x11_surface().is_none());
            app.restore_focus();
            app.reconcile_pointer(0);
            app.dirty = true;
            self.failures = (self.failures + 1).min(6);
            self.next = Instant::now() + Duration::from_millis(250 * (1 << self.failures));
        }
        if !self.started && Instant::now() >= self.next {
            let result = XWayland::spawn(
                &app.display,
                self.display,
                [("PATH", "/usr/bin")],
                false,
                Stdio::null(),
                Stdio::inherit(),
                |_| {},
            );
            match result {
                Ok((server, client)) => {
                    self.display = Some(server.display_number());
                    let handle = self.events.handle();
                    let xwm_handle = handle.clone();
                    app.xwayland_handle = Some(handle.clone());
                    let token = handle
                        .insert_source(server, move |event, _, app| match event {
                            XWaylandEvent::Ready {
                                x11_socket,
                                display_number,
                            } => match X11Wm::start_wm(
                                xwm_handle.clone(),
                                x11_socket,
                                client.clone(),
                            ) {
                                Ok(wm) => {
                                    app.xwm = Some(wm);
                                    app.shell.set_xdisplay(format!(":{display_number}"));
                                    app.ime.set_xdisplay(format!(":{display_number}"));
                                    eprintln!(
                                        "ForgeDesktop XWayland ready DISPLAY=:{display_number}"
                                    );
                                }
                                Err(error) => {
                                    eprintln!("ForgeDesktop XWM failed: {error}");
                                    app.xwayland_failed = true;
                                }
                            },
                            XWaylandEvent::Error => app.xwayland_failed = true,
                        })
                        .map_err(|e| e.error)?;
                    self.token = Some(token);
                    self.started = true;
                }
                Err(error) => {
                    eprintln!("ForgeDesktop XWayland spawn failed: {error}");
                    self.failures = (self.failures + 1).min(6);
                    self.next = Instant::now() + Duration::from_millis(250 * (1 << self.failures));
                }
            }
        }
        Ok(())
    }
}
impl App {
    fn x11_id(&self, window: &X11Surface) -> Option<WindowId> {
        self.windows
            .iter()
            .find(|m| m.window.x11_surface() == Some(window))
            .map(|m| m.id)
    }
    fn map_x11(&mut self, window: X11Surface) {
        if self.x11_id(&window).is_some() || self.windows.len() >= 128 {
            return;
        }
        let original = window.geometry();
        let offset = (self.windows.len() % 8) as i32 * 30;
        let geometry = Geometry {
            x: if window.is_override_redirect() {
                original.loc.x
            } else {
                50 + offset
            },
            y: if window.is_override_redirect() {
                original.loc.y
            } else {
                60 + offset
            },
            width: original.size.w.clamp(64, 16384) as u32,
            height: original.size.h.clamp(32, 16384) as u32,
        };
        let Ok(id) = self.desktop.map(self.desktop.active_workspace(), geometry) else {
            return;
        };
        let _ = window.configure(Rectangle::new(
            (geometry.x, geometry.y).into(),
            (geometry.width as i32, geometry.height as i32).into(),
        ));
        let _ = self.desktop.minimize(id);
        self.windows.push(Mapped {
            id,
            window: Window::new_x11_window(window),
            has_buffer: false,
            role: None,
        });
        self.dirty = true;
    }
    fn unmap_x11(&mut self, window: &X11Surface) {
        if let Some(id) = self.x11_id(window) {
            self.windows.retain(|m| m.id != id);
            let _ = self.desktop.unmap(id);
            if self.drag.as_ref().is_some_and(|d| d.id == id) {
                self.drag = None;
            }
            self.restore_focus();
            self.reconcile_pointer(0);
            self.dirty = true;
        }
    }
    fn x11_drag(&mut self, window: &X11Surface, edges: u32) {
        let pointer = self.seat.get_pointer().unwrap();
        let Some(start) = pointer.grab_start_data() else {
            return;
        };
        if start.focus.map(|(s, _)| s) != window.wl_surface() {
            return;
        }
        if let Some(id) = self.x11_id(window) {
            if self
                .desktop
                .window(id)
                .is_some_and(|w| w.fullscreen() || w.maximized())
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
}
impl XWaylandShellHandler for App {
    fn xwayland_shell_state(&mut self) -> &mut XWaylandShellState {
        &mut self.xwayland_shell
    }
    fn surface_associated(&mut self, _: XwmId, surface: WlSurface, w: X11Surface) {
        eprintln!("ForgeDesktop X11 associated {}", w.window_id());
        self.commit(&surface);
        self.dirty = true;
    }
}
impl XwmHandler for App {
    fn xwm_state(&mut self, _: XwmId) -> &mut X11Wm {
        self.xwm.as_mut().expect("live XWM event source")
    }
    fn new_window(&mut self, _: XwmId, w: X11Surface) {
        eprintln!("ForgeDesktop X11 created {}", w.window_id());
    }
    fn new_override_redirect_window(&mut self, _: XwmId, _: X11Surface) {}
    fn map_window_request(&mut self, _: XwmId, window: X11Surface) {
        eprintln!("ForgeDesktop X11 map {}", window.window_id());
        if window.set_mapped(true).is_ok() {
            self.map_x11(window);
        }
    }
    fn mapped_override_redirect_window(&mut self, _: XwmId, window: X11Surface) {
        self.map_x11(window);
    }
    fn unmapped_window(&mut self, _: XwmId, window: X11Surface) {
        self.unmap_x11(&window);
    }
    fn destroyed_window(&mut self, _: XwmId, window: X11Surface) {
        self.unmap_x11(&window);
    }
    fn configure_request(
        &mut self,
        _: XwmId,
        window: X11Surface,
        x: Option<i32>,
        y: Option<i32>,
        w: Option<u32>,
        h: Option<u32>,
        _: Option<Reorder>,
    ) {
        if let Some(id) = self.x11_id(&window) {
            let policy = self.desktop.window(id).unwrap();
            if !policy.maximized() && !policy.fullscreen() {
                let mut g = policy.geometry();
                if let Some(w) = w {
                    g.width = w;
                }
                if let Some(h) = h {
                    g.height = h;
                }
                let _ = self.desktop.set_geometry(id, g);
            }
            self.configure(id);
        } else {
            // Toolkits commonly set their final size before mapping. Rejecting
            // that request leaves fixed-size clients at their placeholder size.
            let mut geometry = window.geometry();
            if let Some(x) = x {
                geometry.loc.x = x;
            }
            if let Some(y) = y {
                geometry.loc.y = y;
            }
            if let Some(w) = w {
                geometry.size.w = w.clamp(64, 16384) as i32;
            }
            if let Some(h) = h {
                geometry.size.h = h.clamp(32, 16384) as i32;
            }
            let _ = window.configure(geometry);
        }
    }
    fn configure_notify(
        &mut self,
        _: XwmId,
        window: X11Surface,
        g: Rectangle<i32, Logical>,
        _: Option<u32>,
    ) {
        if window.is_override_redirect() {
            if let Some(id) = self.x11_id(&window) {
                let _ = self.desktop.set_geometry(
                    id,
                    Geometry {
                        x: g.loc.x,
                        y: g.loc.y,
                        width: g.size.w as u32,
                        height: g.size.h as u32,
                    },
                );
                self.dirty = true;
            }
        }
    }
    fn maximize_request(&mut self, _: XwmId, w: X11Surface) {
        if let Some(id) = self.x11_id(&w) {
            if !self.desktop.window(id).unwrap().maximized() {
                let _ = self.action(id, "maximize");
            }
        }
    }
    fn unmaximize_request(&mut self, _: XwmId, w: X11Surface) {
        if let Some(id) = self.x11_id(&w) {
            let _ = self.desktop.set_maximized(id, None);
            self.configure(id);
        }
    }
    fn fullscreen_request(&mut self, _: XwmId, w: X11Surface) {
        if let Some(id) = self.x11_id(&w) {
            if !self.desktop.window(id).unwrap().fullscreen() {
                let _ = self.action(id, "fullscreen");
            }
        }
    }
    fn unfullscreen_request(&mut self, _: XwmId, w: X11Surface) {
        if let Some(id) = self.x11_id(&w) {
            let _ = self.desktop.set_fullscreen(id, None);
            self.configure(id);
        }
    }
    fn minimize_request(&mut self, _: XwmId, w: X11Surface) {
        if let Some(id) = self.x11_id(&w) {
            let _ = self.action(id, "minimize");
        }
    }
    fn unminimize_request(&mut self, _: XwmId, w: X11Surface) {
        if let Some(id) = self.x11_id(&w) {
            let _ = self.action(id, "restore");
        }
    }
    fn resize_request(&mut self, _: XwmId, w: X11Surface, _: u32, edge: ResizeEdge) {
        self.x11_drag(
            &w,
            match edge {
                ResizeEdge::Top => 1,
                ResizeEdge::Bottom => 2,
                ResizeEdge::Left => 4,
                ResizeEdge::TopLeft => 5,
                ResizeEdge::BottomLeft => 6,
                ResizeEdge::Right => 8,
                ResizeEdge::TopRight => 9,
                ResizeEdge::BottomRight => 10,
            },
        );
    }
    fn move_request(&mut self, _: XwmId, w: X11Surface, _: u32) {
        self.x11_drag(&w, 0);
    }
    fn disconnected(&mut self, _: XwmId) {
        self.xwayland_failed = true;
    }
    fn allow_selection_access(&mut self, _: XwmId, _: SelectionTarget) -> bool {
        self.desktop.ensure_unlocked().is_ok()
            && self
                .seat
                .get_keyboard()
                .unwrap()
                .current_focus()
                .is_some_and(|s| {
                    self.windows.iter().any(|m| {
                        m.window
                            .x11_surface()
                            .and_then(X11Surface::wl_surface)
                            .as_ref()
                            == Some(&s)
                    })
                })
    }
    fn send_selection(&mut self, _: XwmId, target: SelectionTarget, mime: String, fd: OwnedFd) {
        let _ = match target {
            SelectionTarget::Clipboard => {
                request_data_device_client_selection(&self.seat, mime, fd).ok()
            }
            SelectionTarget::Primary => request_primary_client_selection(&self.seat, mime, fd).ok(),
        };
    }
    fn new_selection(&mut self, xwm: XwmId, target: SelectionTarget, mimes: Vec<String>) {
        if self.desktop.ensure_unlocked().is_err() {
            return;
        }
        match target {
            SelectionTarget::Clipboard => {
                set_data_device_selection(&self.display, &self.seat, mimes, xwm)
            }
            SelectionTarget::Primary => {
                set_primary_selection(&self.display, &self.seat, mimes, xwm)
            }
        }
    }
    fn cleared_selection(&mut self, _: XwmId, target: SelectionTarget) {
        match target {
            SelectionTarget::Clipboard => clear_data_device_selection(&self.display, &self.seat),
            SelectionTarget::Primary => clear_primary_selection(&self.display, &self.seat),
        }
    }
}
impl SelectionHandler for App {
    type SelectionUserData = XwmId;
    fn new_selection(
        &mut self,
        target: SelectionTarget,
        source: Option<SelectionSource>,
        _: Seat<Self>,
    ) {
        if let Some(xwm) = &mut self.xwm {
            let _ = xwm.new_selection(target, source.map(|s| s.mime_types()));
        }
    }
    fn send_selection(
        &mut self,
        target: SelectionTarget,
        mime: String,
        fd: OwnedFd,
        _: Seat<Self>,
        owner: &XwmId,
    ) {
        if self.desktop.ensure_unlocked().is_err() {
            return;
        }
        if let (Some(xwm), Some(handle)) = (&mut self.xwm, &self.xwayland_handle) {
            if xwm.id() == *owner {
                let _ = xwm.send_selection(target, mime, fd, handle.clone());
            }
        }
    }
}
smithay::delegate_xwayland_shell!(App);

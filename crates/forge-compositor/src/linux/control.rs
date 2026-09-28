use super::*;
use forge_compositor::protocol::{Command, hex, opaque_id, resolve_window, trusted_role};
use smithay::wayland::{compositor::with_states, shell::xdg::XdgToplevelSurfaceData};
pub(super) fn metadata(surface: &ToplevelSurface) -> (String, String) {
    with_states(surface.wl_surface(), |states| {
        let data = states
            .data_map
            .get::<XdgToplevelSurfaceData>()
            .unwrap()
            .lock()
            .unwrap();
        (
            data.title.clone().unwrap_or_default(),
            data.app_id.clone().unwrap_or_default(),
        )
    })
}
impl App {
    pub(super) fn visible(&self, m: &Mapped) -> bool {
        m.has_buffer
            && self.desktop.ensure_unlocked().is_ok()
            && match m.role.as_deref() {
                Some("forge.launcher") => self.launcher,
                Some("forge.panel" | "forge.dock") => {
                    self.launcher
                        || !self
                            .desktop
                            .focused()
                            .and_then(|id| self.desktop.window(id))
                            .is_some_and(|w| {
                                let g = w.geometry();
                                w.fullscreen()
                                    && outputs::geometry(&self.output).overlaps(Rectangle::new(
                                        (g.x, g.y).into(),
                                        (g.width as i32, g.height as i32).into(),
                                    ))
                            })
                }
                Some(_) => true,
                None => self.desktop.visible(m.id),
            }
    }
    pub(super) fn arrange(&mut self) {
        self.windows.sort_by_key(|m| match m.role.as_deref() {
            Some("forge.background") => 0,
            None => 1,
            Some("forge.launcher") => 3,
            Some(_) => 2,
        });
    }
    fn role_geometry(&self, role: &str) -> Geometry {
        let (w, h) = self.size;
        match role {
            "forge.panel" => Geometry {
                x: 0,
                y: 0,
                width: w as u32,
                height: 38,
            },
            "forge.dock" => Geometry {
                x: 0,
                y: h - 84,
                width: w as u32,
                height: 84,
            },
            "forge.launcher" => Geometry {
                x: (w - 760).max(0) / 2,
                y: 76,
                width: w.min(760) as u32,
                height: (h - 190).max(100) as u32,
            },
            "forge.traymenu" => Geometry {
                x: (w - 334).max(0),
                y: 38,
                width: w.clamp(1, 320) as u32,
                height: (h - 38).clamp(1, 320) as u32,
            },
            _ => Geometry {
                x: 0,
                y: 0,
                width: w as u32,
                height: h as u32,
            },
        }
    }
    pub(super) fn update_role(&mut self, surface: &ToplevelSurface) {
        let Some(id) = self.locate(surface) else {
            return;
        };
        let (title, _) = metadata(surface);
        let actual = surface
            .wl_surface()
            .client()
            .and_then(|c| c.get_credentials(&self.display).ok())
            .map(|c| (c.pid as u32, c.uid));
        if !actual.is_some_and(|c| trusted_role(self.shell.credentials(), c, &title)) {
            return;
        }
        if self
            .windows
            .iter()
            .any(|m| m.id != id && m.role.as_deref() == Some(&title))
        {
            surface.send_close();
            return;
        }
        let geometry = self.role_geometry(&title);
        if let Some(m) = self.windows.iter_mut().find(|m| m.id == id) {
            m.role = Some(title);
        }
        let _ = self.desktop.set_geometry(id, geometry);
        let _ = self.desktop.minimize(id);
        surface.with_pending_state(|s| {
            s.size = Some((geometry.width as i32, geometry.height as i32).into());
        });
        surface.send_pending_configure();
        self.arrange();
        self.dirty = true;
    }
    pub(super) fn configure(&mut self, id: WindowId) {
        if let Some(m) = self.windows.iter().find(|m| m.id == id) {
            let g = self.geometry(id);
            let p = self.desktop.window(id).unwrap();
            if let Some(x) = m.window.x11_surface() {
                let _ = x.set_maximized(p.maximized());
                let _ = x.set_fullscreen(p.fullscreen());
                let _ = x.configure(Rectangle::new(
                    (g.x, g.y).into(),
                    (g.width as i32, g.height as i32).into(),
                ));
                self.dirty = true;
                return;
            }
            let s = m.window.toplevel().unwrap();
            s.with_pending_state(|state| {
                state.size = Some((g.width as i32, g.height as i32).into());
                if p.maximized() {
                    state.states.set(xdg_toplevel::State::Maximized);
                } else {
                    state.states.unset(xdg_toplevel::State::Maximized);
                }
                if p.fullscreen() {
                    state.states.set(xdg_toplevel::State::Fullscreen);
                } else {
                    state.states.unset(xdg_toplevel::State::Fullscreen);
                }
            });
            s.send_pending_configure();
        }
        self.dirty = true;
    }
    pub(super) fn action(
        &mut self,
        id: WindowId,
        action: &str,
    ) -> Result<(), forge_desktop_core::Error> {
        self.desktop.ensure_unlocked()?;
        if !self.windows.iter().any(|m| m.id == id && m.role.is_none()) {
            return Err(forge_desktop_core::Error::UnknownWindow);
        }
        let output = self.window_output(id);
        let area = outputs::geometry(output);
        let primary = *output == self.output;
        let work = Geometry {
            x: area.loc.x,
            y: area.loc.y + if primary { 38 } else { 0 },
            width: area.size.w as u32,
            height: (area.size.h - if primary { 122 } else { 0 }).max(1) as u32,
        };
        match action {
            "close" => {
                let window = &self.windows.iter().find(|m| m.id == id).unwrap().window;
                if let Some(top) = window.toplevel() {
                    top.send_close();
                }
                if let Some(x) = window.x11_surface() {
                    let _ = x.close();
                }
            }
            "activate" | "restore" => {
                let workspace = self.desktop.window(id).unwrap().workspace();
                self.desktop.switch_workspace(workspace)?;
                self.desktop.restore(id)?;
                self.focus(id);
            }
            "minimize" => self.desktop.minimize(id)?,
            "maximize" => {
                let target = (!self.desktop.window(id).unwrap().maximized()).then_some(work);
                self.desktop.set_maximized(id, target)?;
            }
            "fullscreen" => {
                let target = (!self.desktop.window(id).unwrap().fullscreen()).then_some(Geometry {
                    x: area.loc.x,
                    y: area.loc.y,
                    width: area.size.w as u32,
                    height: area.size.h as u32,
                });
                self.desktop.set_fullscreen(id, target)?;
            }
            "normal" | "left" | "right" => {
                self.desktop.set_fullscreen(id, None)?;
                self.desktop.set_maximized(id, None)?;
                if action != "normal" {
                    self.desktop.set_geometry(
                        id,
                        Geometry {
                            x: work.x + if action == "left" { 0 } else { area.size.w / 2 },
                            width: work.width / 2,
                            ..work
                        },
                    )?;
                }
            }
            _ => return Err(forge_desktop_core::Error::UnknownWindow),
        }
        if matches!(
            action,
            "maximize" | "fullscreen" | "normal" | "left" | "right"
        ) && self.windows.iter().any(|m| m.id == id && m.has_buffer)
        {
            let workspace = self.desktop.window(id).unwrap().workspace();
            self.desktop.switch_workspace(workspace)?;
            self.desktop.restore(id)?;
            self.focus(id);
        }
        self.configure(id);
        self.restore_focus();
        self.reconcile_pointer(0);
        Ok(())
    }
    pub(super) fn set_launcher(&mut self, open: bool, serial: Option<u32>) {
        if self.desktop.ensure_unlocked().is_err() {
            return;
        }
        self.launcher = open;
        self.launcher_pending = if open { serial } else { None };
        if open {
            if let Some(id) = self
                .windows
                .iter()
                .find(|m| m.role.as_deref() == Some("forge.launcher") && m.has_buffer)
                .map(|m| m.id)
            {
                self.focus(id);
            }
        } else {
            self.restore_focus();
        }
        self.dirty = true;
        self.reconcile_pointer(0);
    }
    pub(super) fn keyboard_event(&mut self, code: u32, state: KeyState, time: u32) {
        let reserved = matches!(code, 133 | 134);
        let keyboard = self.seat.get_keyboard().unwrap();
        keyboard.input::<(), _>(
            self,
            code.into(),
            state,
            SERIAL_COUNTER.next_serial(),
            time,
            |_, _, _| {
                if reserved {
                    FilterResult::Intercept(())
                } else {
                    FilterResult::Forward
                }
            },
        );
        if reserved {
            if state == KeyState::Pressed && !self.launcher_key_down {
                self.set_launcher(!self.launcher, None);
            }
            self.launcher_key_down = state == KeyState::Pressed;
        }
    }
    pub(super) fn shell_tick(&mut self) {
        let previous = self.shell.credentials();
        let commands = self.shell.poll();
        if previous != self.shell.credentials() {
            self.notices.authorize(None);
            self.launcher = false;
            self.launcher_pending = None;
            self.restore_focus();
        }
        for cmd in commands {
            if std::env::var_os("FORGE_DESKTOP_TRACE").is_some() {
                eprintln!("ForgeDesktop command {cmd:?}");
            }
            let result = match cmd {
                Command::Window(action, handle) => resolve_window(
                    &handle,
                    self.windows
                        .iter()
                        .filter(|m| m.role.is_none())
                        .map(|m| m.id),
                )
                .ok_or(forge_desktop_core::Error::UnknownWindow)
                .and_then(|id| self.action(id, &action)),
                Command::Workspace(n) => {
                    let r = self.desktop.switch_workspace(n);
                    self.restore_focus();
                    r
                }
                Command::Move(handle, n) => {
                    let result = self
                        .windows
                        .iter()
                        .find(|m| opaque_id(m.id) == handle && m.role.is_none())
                        .map(|m| m.id)
                        .ok_or(forge_desktop_core::Error::UnknownWindow)
                        .and_then(|id| self.desktop.move_to_workspace(id, n));
                    self.restore_focus();
                    result
                }
                Command::Launcher(open, serial) => {
                    self.set_launcher(open, Some(serial));
                    Ok(())
                }
                Command::NoticesBus(name) => {
                    self.notices.authorize(Some(name));
                    Ok(())
                }
                command @ (Command::Output { .. }
                | Command::DisplayConfirm
                | Command::DisplayRevert) => {
                    if self.desktop.ensure_unlocked().is_ok() && self.output_requests.len() < 32 {
                        self.output_requests.push(command);
                        Ok(())
                    } else {
                        Err(forge_desktop_core::Error::Locked)
                    }
                }
            };
            if let Err(e) = result {
                eprintln!("ForgeDesktop shell request rejected: {e:?}");
            }
            self.dirty = true;
            self.reconcile_pointer(0);
        }
        self.notices.poll();
        let mut state = format!(
            "1\tstate\t{}\t{}\t{}\t{}\n",
            self.size.0,
            self.size.1,
            self.desktop.active_workspace(),
            u8::from(self.launcher)
        );
        let mut normal: Vec<_> = self
            .windows
            .iter()
            .filter(|m| {
                m.role.is_none()
                    && m.has_buffer
                    && !m
                        .window
                        .x11_surface()
                        .is_some_and(|w| w.is_override_redirect())
            })
            .collect();
        normal.sort_by_key(|m| m.id);
        for m in normal {
            let (title, app) = if let Some(top) = m.window.toplevel() {
                metadata(top)
            } else if let Some(x) = m.window.x11_surface() {
                (x.title(), x.class())
            } else {
                continue;
            };
            let p = self.desktop.window(m.id).unwrap();
            state.push_str(&format!(
                "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n",
                opaque_id(m.id),
                hex(&title),
                hex(&app),
                p.workspace(),
                u8::from(p.minimized()),
                u8::from(p.maximized()),
                u8::from(p.fullscreen()),
                u8::from(self.desktop.focused() == Some(m.id))
            ));
        }
        state.push_str(&self.output_state);
        self.shell.state(state);
    }
    pub(super) fn frame_submitted(&mut self, damaged: bool) {
        if damaged
            && self.launcher
            && self
                .windows
                .iter()
                .any(|m| m.role.as_deref() == Some("forge.launcher") && self.visible(m))
        {
            if let Some(serial) = self.launcher_pending.take() {
                self.shell.presented(serial);
            }
        }
    }
}

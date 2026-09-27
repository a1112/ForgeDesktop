//! A single supervised foreground input method; its keyboard role is private.
use super::*;
use smithay::wayland::{
    compositor::get_parent,
    input_method::{InputMethodHandler, InputMethodManagerState, PopupSurface},
    virtual_keyboard::VirtualKeyboardManagerState,
};
use std::{
    process::{Child, Command, Stdio},
    sync::atomic::{AtomicU32, Ordering},
};

pub(super) struct Ime {
    child: Option<Child>,
    authorized_pid: Arc<AtomicU32>,
    next_start: Instant,
    failures: u32,
    started: Instant,
    xdisplay: Option<String>,
}
impl Ime {
    pub fn new(dh: &smithay::reexports::wayland_server::DisplayHandle) -> Self {
        let authorized_pid = Arc::new(AtomicU32::new(0));
        let allowed = authorized_pid.clone();
        let uid = smithay::reexports::rustix::process::geteuid().as_raw();
        let filter = move |client: &Client| {
            let expected = allowed.load(Ordering::Acquire);
            // Global filters run under the display backend lock. Read the
            // SO_PEERCRED captured at accept; querying DisplayHandle here deadlocks.
            expected != 0
                && client.get_data::<ClientState>().and_then(|s| s.credentials)
                    == Some((expected, uid))
        };
        InputMethodManagerState::new::<App, _>(dh, filter.clone());
        VirtualKeyboardManagerState::new::<App, _>(dh, filter);
        Self {
            child: None,
            authorized_pid,
            next_start: Instant::now(),
            failures: 0,
            started: Instant::now(),
            xdisplay: None,
        }
    }
    pub fn set_xdisplay(&mut self, display: String) {
        if self.xdisplay.as_ref() != Some(&display) {
            self.xdisplay = Some(display);
            if self.child.is_some() {
                self.failed();
                self.next_start = Instant::now();
            }
        }
    }
    pub fn tick(&mut self) {
        if self
            .child
            .as_mut()
            .is_some_and(|child| !matches!(child.try_wait(), Ok(None)))
        {
            self.failed();
        }
        if self.child.is_none() && Instant::now() >= self.next_start {
            let mut command = Command::new("/usr/bin/fcitx5");
            command
                .args(["-D", "--replace"])
                .env("WAYLAND_DISPLAY", "forge-wayland-0")
                .env_remove("DISPLAY")
                .stdin(Stdio::null());
            if let Some(display) = &self.xdisplay {
                command.env("DISPLAY", display);
            }
            match command.spawn() {
                Ok(child) => {
                    self.authorized_pid.store(child.id(), Ordering::Release);
                    eprintln!("ForgeDesktop input method started pid={}", child.id());
                    self.child = Some(child);
                    self.started = Instant::now();
                }
                Err(error) => {
                    eprintln!("ForgeDesktop input method start: {error}");
                    self.failed();
                }
            }
        }
    }
    fn failed(&mut self) {
        self.authorized_pid.store(0, Ordering::Release);
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        self.failures = if self.started.elapsed() > Duration::from_secs(60) {
            1
        } else {
            (self.failures + 1).min(6)
        };
        self.next_start = Instant::now() + Duration::from_millis(250 * (1 << self.failures));
    }
}
impl Drop for Ime {
    fn drop(&mut self) {
        self.failed();
    }
}
impl InputMethodHandler for App {
    fn new_popup(&mut self, popup: PopupSurface) {
        let caret = popup.text_input_rectangle();
        popup.set_location((caret.loc.x, caret.loc.y + caret.size.h).into());
        let _ = self.popups.track_popup(popup.into());
        self.dirty = true;
    }
    fn dismiss_popup(&mut self, popup: PopupSurface) {
        let kind = smithay::desktop::PopupKind::InputMethod(popup);
        if let Ok(root) = find_popup_root_surface(&kind) {
            // The IME may reuse this still-live surface after focus changes.
            // cleanup() alone only drops dead surfaces, leaving stale trees.
            let _ = PopupManager::dismiss_popup(&root, &kind);
        }
        self.popups.cleanup();
        self.dirty = true;
    }
    fn popup_repositioned(&mut self, popup: PopupSurface) {
        let caret = popup.text_input_rectangle();
        popup.set_location((caret.loc.x, caret.loc.y + caret.size.h).into());
        self.dirty = true;
    }
    fn parent_geometry(&self, parent: &WlSurface) -> Rectangle<i32, Logical> {
        if let Some(popup) = self.popups.find_popup(parent) {
            return popup.geometry();
        }
        let mut root = parent.clone();
        while let Some(p) = get_parent(&root) {
            root = p;
        }
        self.windows
            .iter()
            .find(|m| m.window.toplevel().is_some_and(|t| t.wl_surface() == &root))
            // PopupManager subtracts this rectangle's location from the
            // window-relative popup offset. This is the client's surface
            // geometry (including CSD offset), never the output/global position.
            .map(|m| m.window.geometry())
            .unwrap_or_default()
    }
}

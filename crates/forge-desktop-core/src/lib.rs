//! Pure policy state for a compositor adapter to consume.
//!
//! This crate implements no Wayland protocols, rendering or authentication.
//! The adapter must associate `LockerId` with the live protocol resource and
//! route unlock only from its authenticated lock client. Tokens are handles,
//! not credentials. Output changes here are logical: the backend must test
//! modes before staging and apply the returned active layout after changes.
#![forbid(unsafe_code)]

use std::collections::{BTreeMap, BTreeSet};

#[cfg(test)]
mod tests;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error {
    InvalidGeometry,
    InvalidWorkspace,
    UnknownWindow,
    NotVisible,
    ManagedGeometry,
    Locked,
    InvalidLocker,
    IdExhausted,
    InvalidOutputs,
    PendingOutputChange,
    NoPendingOutputChange,
    TimeWentBackwards,
    Expired,
    InvalidTimeout,
}

/// Logical coordinates; all public entry points revalidate caller-built values.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Geometry {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}
impl Geometry {
    pub fn new(x: i32, y: i32, width: u32, height: u32) -> Result<Self, Error> {
        let result = Self {
            x,
            y,
            width,
            height,
        };
        result.validate()?;
        Ok(result)
    }
    fn validate(self) -> Result<(), Error> {
        const LIMIT: i64 = 1_000_000;
        if self.width == 0
            || self.height == 0
            || self.width > 16_384
            || self.height > 16_384
            || i64::from(self.x).abs() > LIMIT
            || i64::from(self.y).abs() > LIMIT
            || i64::from(self.x) + i64::from(self.width) > LIMIT
            || i64::from(self.y) + i64::from(self.height) > LIMIT
        {
            return Err(Error::InvalidGeometry);
        }
        Ok(())
    }
}

/// Monotonic handle, unique within one Desktop lifetime; never reused.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct WindowId(u64);
impl WindowId {
    pub fn get(self) -> u64 {
        self.0
    }
}

/// Adapter-owned live locker handle. Never accept this from untrusted IPC.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LockerId(u64);
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub enum LockState {
    #[default]
    Unlocked,
    Pending,
    Locked,
}

#[derive(Debug, Clone)]
pub struct Window {
    workspace: u32,
    normal_geometry: Geometry,
    maximized_geometry: Option<Geometry>,
    fullscreen_geometry: Option<Geometry>,
    minimized: bool,
}
impl Window {
    pub fn geometry(&self) -> Geometry {
        self.fullscreen_geometry
            .or(self.maximized_geometry)
            .unwrap_or(self.normal_geometry)
    }
    pub fn workspace(&self) -> u32 {
        self.workspace
    }
    pub fn minimized(&self) -> bool {
        self.minimized
    }
    pub fn maximized(&self) -> bool {
        self.maximized_geometry.is_some()
    }
    pub fn fullscreen(&self) -> bool {
        self.fullscreen_geometry.is_some()
    }
}

/// Single-threaded policy model. Workspace indices are bounded to 0..64.
#[derive(Debug, Default)]
pub struct Desktop {
    windows: BTreeMap<WindowId, Window>,
    focus_order: Vec<WindowId>,
    focused: Option<WindowId>,
    workspace: u32,
    next_window: u64,
    next_locker: u64,
    lock: LockState,
    locker: Option<LockerId>,
}

fn validate_workspace(workspace: u32) -> Result<(), Error> {
    if workspace < 64 {
        Ok(())
    } else {
        Err(Error::InvalidWorkspace)
    }
}

impl Desktop {
    /// Client lifecycle remains available while locked, without showing clients.
    pub fn map(&mut self, workspace: u32, geometry: Geometry) -> Result<WindowId, Error> {
        validate_workspace(workspace)?;
        geometry.validate()?;
        self.next_window = self.next_window.checked_add(1).ok_or(Error::IdExhausted)?;
        let id = WindowId(self.next_window);
        self.windows.insert(
            id,
            Window {
                workspace,
                normal_geometry: geometry,
                maximized_geometry: None,
                fullscreen_geometry: None,
                minimized: false,
            },
        );
        self.focus_order.push(id);
        self.reconcile_focus();
        Ok(id)
    }
    /// Lifecycle removal only. A shell close request needs the lock gate too.
    pub fn unmap(&mut self, id: WindowId) -> Result<(), Error> {
        self.windows.remove(&id).ok_or(Error::UnknownWindow)?;
        self.focus_order.retain(|candidate| *candidate != id);
        self.reconcile_focus();
        Ok(())
    }
    pub fn window(&self, id: WindowId) -> Option<&Window> {
        self.windows.get(&id)
    }
    pub fn focused(&self) -> Option<WindowId> {
        self.focused
    }
    pub fn active_workspace(&self) -> u32 {
        self.workspace
    }
    /// Regular surfaces must not render or receive input while pending/locked.
    pub fn visible(&self, id: WindowId) -> bool {
        self.lock == LockState::Unlocked
            && self
                .windows
                .get(&id)
                .is_some_and(|window| window.workspace == self.workspace && !window.minimized)
    }
    /// Also use for adapter-side close, capture and other privileged controls.
    pub fn ensure_unlocked(&self) -> Result<(), Error> {
        if self.lock == LockState::Unlocked {
            Ok(())
        } else {
            Err(Error::Locked)
        }
    }
    fn control_window(&mut self, id: WindowId) -> Result<&mut Window, Error> {
        self.ensure_unlocked()?;
        self.windows.get_mut(&id).ok_or(Error::UnknownWindow)
    }
    fn reconcile_focus(&mut self) {
        self.focused = self
            .focus_order
            .iter()
            .rev()
            .copied()
            .find(|id| self.visible(*id));
    }
    pub fn focus(&mut self, id: WindowId) -> Result<(), Error> {
        self.ensure_unlocked()?;
        if !self.windows.contains_key(&id) {
            return Err(Error::UnknownWindow);
        }
        if !self.visible(id) {
            return Err(Error::NotVisible);
        }
        self.focus_order.retain(|candidate| *candidate != id);
        self.focus_order.push(id);
        self.reconcile_focus();
        Ok(())
    }
    pub fn set_geometry(&mut self, id: WindowId, geometry: Geometry) -> Result<(), Error> {
        let window = self.control_window(id)?;
        geometry.validate()?;
        if window.maximized() || window.fullscreen() {
            return Err(Error::ManagedGeometry);
        }
        window.normal_geometry = geometry;
        Ok(())
    }
    pub fn minimize(&mut self, id: WindowId) -> Result<(), Error> {
        self.control_window(id)?.minimized = true;
        self.reconcile_focus();
        Ok(())
    }
    /// Unminimize; restore focus only when the window is on the active workspace.
    pub fn restore(&mut self, id: WindowId) -> Result<(), Error> {
        self.control_window(id)?.minimized = false;
        if self.visible(id) {
            self.focus(id)?;
        }
        Ok(())
    }
    /// Fullscreen temporarily overrides this geometry; original geometry is retained.
    pub fn set_maximized(&mut self, id: WindowId, target: Option<Geometry>) -> Result<(), Error> {
        let window = self.control_window(id)?;
        if let Some(geometry) = target {
            geometry.validate()?;
        }
        window.maximized_geometry = target;
        Ok(())
    }
    /// Exiting fullscreen restores the current maximized or original geometry.
    pub fn set_fullscreen(&mut self, id: WindowId, target: Option<Geometry>) -> Result<(), Error> {
        let window = self.control_window(id)?;
        if let Some(geometry) = target {
            geometry.validate()?;
        }
        window.fullscreen_geometry = target;
        Ok(())
    }
    pub fn switch_workspace(&mut self, workspace: u32) -> Result<(), Error> {
        self.ensure_unlocked()?;
        validate_workspace(workspace)?;
        self.workspace = workspace;
        self.reconcile_focus();
        Ok(())
    }
    pub fn move_to_workspace(&mut self, id: WindowId, workspace: u32) -> Result<(), Error> {
        let window = self.control_window(id)?;
        validate_workspace(workspace)?;
        window.workspace = workspace;
        self.reconcile_focus();
        Ok(())
    }
    pub fn lock_state(&self) -> LockState {
        self.lock
    }
    /// Immediately hide regular surfaces and clear focus, before locker readiness.
    pub fn request_lock(&mut self) -> Result<LockerId, Error> {
        self.ensure_unlocked()?;
        self.next_locker = self.next_locker.checked_add(1).ok_or(Error::IdExhausted)?;
        let locker = LockerId(self.next_locker);
        self.locker = Some(locker);
        self.lock = LockState::Pending;
        self.reconcile_focus();
        Ok(locker)
    }
    /// Adapter calls after lock surfaces are ready on every enabled output.
    pub fn lock_ready(&mut self, locker: LockerId) -> Result<(), Error> {
        if self.locker != Some(locker) || self.lock != LockState::Pending {
            return Err(Error::InvalidLocker);
        }
        self.lock = LockState::Locked;
        Ok(())
    }
    /// Fail closed. Recovery requires ending this session, not reusing a stale token.
    pub fn locker_disconnected(&mut self, locker: LockerId) -> Result<(), Error> {
        if self.locker != Some(locker) {
            return Err(Error::InvalidLocker);
        }
        self.locker = None;
        self.lock = LockState::Locked;
        self.reconcile_focus();
        Ok(())
    }
    pub fn unlock(&mut self, locker: LockerId) -> Result<(), Error> {
        if self.locker != Some(locker) || self.lock != LockState::Locked {
            return Err(Error::InvalidLocker);
        }
        self.locker = None;
        self.lock = LockState::Unlocked;
        self.reconcile_focus();
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Output {
    pub id: u32,
    pub enabled: bool,
    pub geometry: Geometry,
    /// 1000 = 100%, 1500 = 150%, 2000 = 200%.
    pub scale_milli: u32,
}
fn validate_outputs(outputs: &[Output]) -> Result<(), Error> {
    if outputs.is_empty() || outputs.len() > 16 || !outputs.iter().any(|output| output.enabled) {
        return Err(Error::InvalidOutputs);
    }
    let mut ids = BTreeSet::new();
    for output in outputs {
        if !ids.insert(output.id)
            || output.scale_milli == 0
            || output.scale_milli > 8000
            || output.geometry.validate().is_err()
        {
            return Err(Error::InvalidOutputs);
        }
    }
    Ok(())
}

/// One in-flight display change. Caller must schedule tick at the deadline,
/// using elapsed monotonic milliseconds, and apply rollback to the real backend.
#[derive(Debug)]
pub struct OutputTransaction {
    confirmed: Vec<Output>,
    staged: Option<(Vec<Output>, u64)>,
    last_ms: u64,
}
impl OutputTransaction {
    pub fn new(outputs: Vec<Output>, now_ms: u64) -> Result<Self, Error> {
        validate_outputs(&outputs)?;
        Ok(Self {
            confirmed: outputs,
            staged: None,
            last_ms: now_ms,
        })
    }
    pub fn active(&self) -> &[Output] {
        self.staged
            .as_ref()
            .map_or(&self.confirmed, |(outputs, _)| outputs)
    }
    pub fn pending(&self) -> bool {
        self.staged.is_some()
    }
    pub fn stage(
        &mut self,
        outputs: Vec<Output>,
        now_ms: u64,
        timeout_ms: u64,
    ) -> Result<(), Error> {
        self.tick(now_ms)?;
        if self.pending() {
            return Err(Error::PendingOutputChange);
        }
        validate_outputs(&outputs)?;
        let deadline = now_ms
            .checked_add(timeout_ms)
            .filter(|_| timeout_ms != 0)
            .ok_or(Error::InvalidTimeout)?;
        self.staged = Some((outputs, deadline));
        Ok(())
    }
    pub fn confirm(&mut self, now_ms: u64) -> Result<(), Error> {
        if self.tick(now_ms)? {
            return Err(Error::Expired);
        }
        let (outputs, _) = self.staged.take().ok_or(Error::NoPendingOutputChange)?;
        self.confirmed = outputs;
        Ok(())
    }
    /// Returns true exactly when an unconfirmed configuration was rolled back.
    pub fn tick(&mut self, now_ms: u64) -> Result<bool, Error> {
        if now_ms < self.last_ms {
            return Err(Error::TimeWentBackwards);
        }
        self.last_ms = now_ms;
        if self
            .staged
            .as_ref()
            .is_some_and(|(_, deadline)| now_ms >= *deadline)
        {
            self.staged = None;
            return Ok(true);
        }
        Ok(false)
    }
    pub fn cancel(&mut self, now_ms: u64) -> Result<(), Error> {
        if self.tick(now_ms)? {
            return Err(Error::Expired);
        }
        self.staged.take().ok_or(Error::NoPendingOutputChange)?;
        Ok(())
    }
}

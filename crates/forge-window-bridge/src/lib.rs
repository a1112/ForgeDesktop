#![forbid(unsafe_code)]
//! Admission policy only. `admit` is not delivery: the compositor must repeat
//! authorization and hit/focus checks atomically with injection. IDs are handles,
//! never credentials. Observer and broker channels must be authenticated outside
//! this library; browsers must not supply observations, grants or lock state.
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub const PROTOCOL_VERSION: u32 = 1;
pub const MAX_MESSAGE: usize = 65_536;
const MAX_WINDOWS: usize = 4096;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WindowKey {
    pub session_epoch: u64,
    pub id: String,
    pub generation: u64,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Geometry {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}
impl Geometry {
    fn validate(self) -> Result<(), Error> {
        if self.width == 0
            || self.height == 0
            || self.width > 16384
            || self.height > 16384
            || i64::from(self.x).abs() > 1_000_000
            || i64::from(self.y).abs() > 1_000_000
        {
            return Err(Error::InvalidGeometry);
        }
        Ok(())
    }
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WindowKind {
    Normal,
    Dialog,
    Popup,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Window {
    pub key: WindowKey,
    pub parent: Option<WindowKey>,
    pub kind: WindowKind,
    pub geometry: Geometry,
    pub geometry_epoch: u64,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
pub enum Input {
    Pointer { x: u32, y: u32 },
    Key { code: u32, pressed: bool },
    Button { button: u32, pressed: bool },
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InputRequest {
    pub controller: String,
    pub target: WindowKey,
    pub geometry_epoch: u64,
    pub lease_epoch: u64,
    pub sequence: u64,
    pub event: Input,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Error {
    WrongSession,
    InvalidIdentity,
    ReusedIdentity,
    UnknownWindow,
    InvalidGeometry,
    InvalidParent,
    Limit,
    Locked,
    SeatBusy,
    NotGranted,
    WrongTarget,
    StaleGeometry,
    StaleLease,
    Replay,
    OutsideWindow,
    InvalidInput,
    Exhausted,
}

pub struct Bridge {
    session_epoch: u64,
    windows: BTreeMap<WindowKey, Window>,
    generations: BTreeMap<String, u64>,
    locked: bool,
    controller: Option<String>,
    grants: BTreeSet<WindowKey>,
    lease_epoch: u64,
    sequence: u64,
}
impl Bridge {
    pub fn new(session_epoch: u64) -> Result<Self, Error> {
        if session_epoch == 0 {
            return Err(Error::WrongSession);
        }
        Ok(Self {
            session_epoch,
            windows: BTreeMap::new(),
            generations: BTreeMap::new(),
            locked: true,
            controller: None,
            grants: BTreeSet::new(),
            lease_epoch: 1,
            sequence: 0,
        })
    }
    pub fn windows(&self) -> impl Iterator<Item = &Window> {
        self.windows.values()
    }
    pub fn lease_epoch(&self) -> u64 {
        self.lease_epoch
    }
    pub fn observe(
        &mut self,
        key: WindowKey,
        parent: Option<WindowKey>,
        kind: WindowKind,
        geometry: Geometry,
    ) -> Result<(), Error> {
        if key.session_epoch != self.session_epoch {
            return Err(Error::WrongSession);
        }
        if key.generation == 0
            || key.id.is_empty()
            || key.id.len() > 128
            || !key
                .id
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"-_{}".contains(&b))
        {
            return Err(Error::InvalidIdentity);
        }
        geometry.validate()?;
        if self
            .generations
            .get(&key.id)
            .is_some_and(|g| *g >= key.generation)
            || self.windows.keys().any(|k| k.id == key.id)
        {
            return Err(Error::ReusedIdentity);
        }
        if self.windows.len() >= MAX_WINDOWS || self.generations.len() >= 65_536 {
            return Err(Error::Limit);
        }
        if parent
            .as_ref()
            .is_some_and(|p| !self.windows.contains_key(p))
            || (kind != WindowKind::Normal && parent.is_none())
        {
            return Err(Error::InvalidParent);
        }
        self.generations.insert(key.id.clone(), key.generation);
        self.windows.insert(
            key.clone(),
            Window {
                key,
                parent,
                kind,
                geometry,
                geometry_epoch: 1,
            },
        );
        Ok(())
    }
    pub fn geometry(&mut self, key: &WindowKey, geometry: Geometry) -> Result<u64, Error> {
        geometry.validate()?;
        let w = self.windows.get_mut(key).ok_or(Error::UnknownWindow)?;
        if w.geometry != geometry {
            w.geometry_epoch = w.geometry_epoch.checked_add(1).ok_or(Error::Exhausted)?;
            w.geometry = geometry;
        }
        Ok(w.geometry_epoch)
    }
    fn descends_from(&self, key: &WindowKey, root: &WindowKey) -> bool {
        let mut current = Some(key);
        for _ in 0..MAX_WINDOWS {
            let Some(k) = current else {
                return false;
            };
            if k == root {
                return true;
            }
            current = self.windows.get(k).and_then(|w| w.parent.as_ref());
        }
        false
    }
    pub fn close(&mut self, key: &WindowKey) -> Result<(), Error> {
        if !self.windows.contains_key(key) {
            return Err(Error::UnknownWindow);
        }
        let removed: Vec<_> = self
            .windows
            .keys()
            .filter(|k| self.descends_from(k, key))
            .cloned()
            .collect();
        for k in removed {
            self.windows.remove(&k);
            self.grants.remove(&k);
        }
        if self.grants.is_empty() {
            self.revoke();
        }
        Ok(())
    }
    /// Returns the new lease. Only an authenticated authorization broker calls this.
    pub fn grant(&mut self, controller: &str, root: &WindowKey) -> Result<u64, Error> {
        if self.locked {
            return Err(Error::Locked);
        }
        if controller.is_empty() || controller.len() > 128 {
            return Err(Error::InvalidIdentity);
        }
        if !self.windows.contains_key(root) {
            return Err(Error::UnknownWindow);
        }
        if self.controller.as_deref().is_some_and(|c| c != controller) {
            return Err(Error::SeatBusy);
        }
        if self.lease_epoch == u64::MAX {
            return Err(Error::Exhausted);
        }
        self.controller = Some(controller.into());
        self.grants.insert(root.clone());
        Ok(self.lease_epoch)
    }
    /// Adapter must release all held input and stop streams when this is called.
    pub fn revoke(&mut self) {
        self.controller = None;
        self.grants.clear();
        self.sequence = 0;
        self.lease_epoch = self.lease_epoch.saturating_add(1);
    }
    /// Unlock is accepted only from the system locker observer, never the web API.
    pub fn set_locked(&mut self, locked: bool) {
        if locked {
            self.revoke();
        }
        self.locked = locked;
    }
    pub fn admit(
        &mut self,
        request: &InputRequest,
        compositor_target: &WindowKey,
    ) -> Result<(), Error> {
        if self.locked {
            return Err(Error::Locked);
        }
        let w = self
            .windows
            .get(&request.target)
            .ok_or(Error::UnknownWindow)?;
        if self.controller.as_ref() != Some(&request.controller)
            || !self
                .grants
                .iter()
                .any(|r| self.descends_from(&request.target, r))
        {
            return Err(Error::NotGranted);
        }
        if request.lease_epoch != self.lease_epoch {
            return Err(Error::StaleLease);
        }
        if request.geometry_epoch != w.geometry_epoch {
            return Err(Error::StaleGeometry);
        }
        if &request.target != compositor_target {
            return Err(Error::WrongTarget);
        }
        match request.event {
            Input::Pointer { x, y } if x >= w.geometry.width || y >= w.geometry.height => {
                return Err(Error::OutsideWindow);
            }
            Input::Key { code, .. } if code > 767 => return Err(Error::InvalidInput),
            Input::Button { button, .. } if !(272..=279).contains(&button) => {
                return Err(Error::InvalidInput);
            }
            _ => {}
        }
        if request.sequence <= self.sequence {
            return Err(Error::Replay);
        }
        self.sequence = request.sequence;
        Ok(())
    }
}

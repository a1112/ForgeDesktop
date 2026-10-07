//! Trusted private companion metadata only; never browser authorization/input.
use crate::{Geometry, WindowKey, WindowKind};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub const MAX_SAFE_INTEGER: u64 = 9_007_199_254_740_991;
pub const MAX_LIVE_WINDOWS: usize = 4096;
pub const MAX_QUARANTINED_WINDOWS: usize = 4096;
pub const MAX_RETIRED_WINDOWS: usize = 65_536;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ObserverError {
    InvalidFrame,
    UnsupportedVersion,
    InvalidIdentity,
    InvalidGeometry,
    InvalidParent,
    InvalidHint,
    Limit,
    Disconnected,
    UnsafeCounter,
    InvalidPage,
    UnsupportedCapabilities,
}
impl std::fmt::Display for ObserverError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{self:?}")
    }
}
impl std::error::Error for ObserverError {}

fn required_parent<'de, D: serde::Deserializer<'de>>(
    deserializer: D,
) -> Result<Option<String>, D::Error> {
    Option::<String>::deserialize(deserializer)
}
#[derive(Debug, Clone, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
pub enum ObserverEvent {
    Window {
        version: u32,
        id: String,
        #[serde(deserialize_with = "required_parent")]
        parent: Option<String>,
        kind: WindowKind,
        geometry: Geometry,
        caption: String,
        app_id: String,
    },
    Closed {
        version: u32,
        id: String,
    },
    Active {
        version: u32,
        id: String,
    },
    Lock {
        version: u32,
        locked: bool,
    },
    Capabilities {
        version: u32,
        capture: bool,
        atomic_input: bool,
    },
    Disconnected {
        version: u32,
    },
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ObserverWindow {
    pub key: WindowKey,
    pub parent: Option<WindowKey>,
    pub kind: WindowKind,
    pub geometry: Geometry,
    pub geometry_epoch: u64,
    pub caption: String,
    pub app_id: String,
}
#[derive(Debug, Clone, Serialize)]
pub struct ObserverSnapshot {
    pub version: u32,
    pub session_epoch: u64,
    pub connected: bool,
    pub locked: bool,
    pub revocation_epoch: u64,
    pub revision: u64,
    pub capture: bool,
    pub atomic_input: bool,
    pub runtime_verified: bool,
    pub active_hint: Option<WindowKey>,
    pub last_error: Option<ObserverError>,
    pub window_count: usize,
    pub quarantined_count: usize,
    pub retired_count: usize,
    pub offset: usize,
    pub next_offset: Option<usize>,
    pub windows: Vec<ObserverWindow>,
}
#[derive(Clone)]
struct PendingWindow {
    parent: Option<String>,
}
pub struct ObserverReducer {
    session_epoch: u64,
    connected: bool,
    locked: bool,
    revocation_epoch: u64,
    revision: u64,
    active_hint: Option<WindowKey>,
    last_error: Option<ObserverError>,
    live: BTreeMap<String, ObserverWindow>,
    quarantined: BTreeMap<String, PendingWindow>,
    retired: BTreeMap<String, u64>,
}
fn valid_id(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 128
        && id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"-_{}".contains(&byte))
}
fn advance(counter: u64) -> Result<u64, ObserverError> {
    counter
        .checked_add(1)
        .filter(|value| *value <= MAX_SAFE_INTEGER)
        .ok_or(ObserverError::UnsafeCounter)
}
impl ObserverEvent {
    fn version(&self) -> u32 {
        match self {
            Self::Window { version, .. }
            | Self::Closed { version, .. }
            | Self::Active { version, .. }
            | Self::Lock { version, .. }
            | Self::Capabilities { version, .. }
            | Self::Disconnected { version } => *version,
        }
    }
    fn validate(&self) -> Result<(), ObserverError> {
        if self.version() != crate::PROTOCOL_VERSION {
            return Err(ObserverError::UnsupportedVersion);
        }
        match self {
            Self::Window {
                id,
                parent,
                geometry,
                caption,
                app_id,
                ..
            } => {
                if !valid_id(id) || parent.as_ref().is_some_and(|parent| !valid_id(parent)) {
                    return Err(ObserverError::InvalidIdentity);
                }
                geometry
                    .validate()
                    .map_err(|_| ObserverError::InvalidGeometry)?;
                if caption.encode_utf16().count() > 4096 || app_id.encode_utf16().count() > 1024 {
                    return Err(ObserverError::InvalidHint);
                }
                if parent.as_deref() == Some(id) {
                    return Err(ObserverError::InvalidParent);
                }
            }
            Self::Closed { id, .. } | Self::Active { id, .. } if !valid_id(id) => {
                return Err(ObserverError::InvalidIdentity);
            }
            Self::Capabilities {
                capture,
                atomic_input,
                ..
            } if *capture || *atomic_input => return Err(ObserverError::UnsupportedCapabilities),
            _ => {}
        }
        Ok(())
    }
}
impl ObserverReducer {
    pub fn new(session_epoch: u64) -> Result<Self, ObserverError> {
        if session_epoch == 0 || session_epoch > MAX_SAFE_INTEGER {
            return Err(ObserverError::UnsafeCounter);
        }
        Ok(Self {
            session_epoch,
            connected: true,
            locked: true,
            revocation_epoch: 1,
            revision: 0,
            active_hint: None,
            last_error: None,
            live: BTreeMap::new(),
            quarantined: BTreeMap::new(),
            retired: BTreeMap::new(),
        })
    }
    pub fn connected(&self) -> bool {
        self.connected
    }
    fn fail_closed(&mut self, error: ObserverError) -> ObserverError {
        self.connected = false;
        self.locked = true;
        self.active_hint = None;
        self.revocation_epoch = advance(self.revocation_epoch).unwrap_or(MAX_SAFE_INTEGER);
        self.live.clear();
        self.quarantined.clear();
        self.last_error = Some(error);
        error
    }
    pub fn apply_frame(&mut self, frame: &[u8]) -> Result<(), ObserverError> {
        if !self.connected {
            return Err(ObserverError::Disconnected);
        }
        if frame.is_empty()
            || frame.len() > crate::MAX_MESSAGE
            || frame.last() != Some(&b'\n')
            || frame[..frame.len() - 1].contains(&b'\n')
            || std::str::from_utf8(frame).is_err()
        {
            return Err(self.fail_closed(ObserverError::InvalidFrame));
        }
        let event = serde_json::from_slice::<ObserverEvent>(frame)
            .map_err(|_| self.fail_closed(ObserverError::InvalidFrame))?;
        self.apply_event(event)
    }
    pub fn apply_event(&mut self, event: ObserverEvent) -> Result<(), ObserverError> {
        if !self.connected {
            return Err(ObserverError::Disconnected);
        }
        let result = event
            .validate()
            .and_then(|()| advance(self.revision))
            .and_then(|revision| {
                self.apply_valid(event)?;
                self.revision = revision;
                Ok(())
            });
        result.map_err(|error| self.fail_closed(error))
    }
    fn apply_valid(&mut self, event: ObserverEvent) -> Result<(), ObserverError> {
        match event {
            ObserverEvent::Window {
                id,
                parent,
                kind,
                geometry,
                caption,
                app_id,
                ..
            } => self.observe(id, parent, kind, geometry, caption, app_id),
            ObserverEvent::Closed { id, .. } => self.retire_tree(&id),
            ObserverEvent::Active { id, .. } => {
                self.active_hint = self.live.get(&id).map(|window| window.key.clone());
                Ok(())
            }
            ObserverEvent::Lock { locked, .. } => {
                if locked {
                    self.revocation_epoch = advance(self.revocation_epoch)?;
                    self.active_hint = None;
                }
                self.locked = locked;
                Ok(())
            }
            ObserverEvent::Capabilities { .. } => Ok(()),
            ObserverEvent::Disconnected { .. } => {
                self.disconnect();
                Ok(())
            }
        }
    }
    fn generation(&self, id: &str) -> Result<u64, ObserverError> {
        self.retired.get(id).copied().map(advance).unwrap_or(Ok(1))
    }
    fn observe(
        &mut self,
        id: String,
        parent: Option<String>,
        kind: WindowKind,
        geometry: Geometry,
        caption: String,
        app_id: String,
    ) -> Result<(), ObserverError> {
        let parent_key = parent
            .as_ref()
            .and_then(|id| self.live.get(id))
            .map(|window| window.key.clone());
        if (parent.is_some() && parent_key.is_none())
            || (kind != WindowKind::Normal && parent_key.is_none())
        {
            if self.live.contains_key(&id) {
                self.retire_tree(&id)?;
            }
            if !self.quarantined.contains_key(&id)
                && self.quarantined.len() >= MAX_QUARANTINED_WINDOWS
            {
                return Err(ObserverError::Limit);
            }
            self.quarantined.insert(id, PendingWindow { parent });
            return Ok(());
        }
        let mut ancestor = parent_key.as_ref();
        for _ in 0..=MAX_LIVE_WINDOWS {
            let Some(key) = ancestor else {
                break;
            };
            if key.id == id {
                return Err(ObserverError::InvalidParent);
            }
            ancestor = self
                .live
                .get(&key.id)
                .and_then(|window| window.parent.as_ref());
        }
        if self
            .live
            .get(&id)
            .is_some_and(|window| window.parent != parent_key || window.kind != kind)
        {
            self.retire_tree(&id)?;
        }
        if let Some(window) = self.live.get_mut(&id) {
            if window.geometry != geometry {
                window.geometry_epoch = advance(window.geometry_epoch)?;
                window.geometry = geometry;
            }
            window.caption = caption;
            window.app_id = app_id;
            return Ok(());
        }
        if self.live.len() >= MAX_LIVE_WINDOWS {
            return Err(ObserverError::Limit);
        }
        let generation = self.generation(&id)?;
        let key = WindowKey {
            session_epoch: self.session_epoch,
            id: id.clone(),
            generation,
        };
        self.quarantined.remove(&id);
        self.live.insert(
            id,
            ObserverWindow {
                key,
                parent: parent_key,
                kind,
                geometry,
                geometry_epoch: 1,
                caption,
                app_id,
            },
        );
        Ok(())
    }
    fn retire_tree(&mut self, root: &str) -> Result<(), ObserverError> {
        let mut children: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
        for (id, window) in &self.live {
            if let Some(parent) = &window.parent {
                children.entry(&parent.id).or_default().push(id);
            }
        }
        for (id, window) in &self.quarantined {
            if let Some(parent) = &window.parent {
                children.entry(parent).or_default().push(id);
            }
        }
        let mut queue = vec![root];
        let mut removed = BTreeSet::new();
        while let Some(id) = queue.pop() {
            if removed.insert(id.to_owned()) {
                if let Some(ids) = children.get(id) {
                    queue.extend(ids.iter().copied());
                }
            }
        }
        let mut retire = BTreeMap::new();
        for id in &removed {
            if let Some(window) = self.live.get(id) {
                retire.insert(id.clone(), window.key.generation);
            } else if self.quarantined.contains_key(id) {
                retire.insert(id.clone(), self.generation(id)?);
            }
        }
        let new_ids = retire
            .keys()
            .filter(|id| !self.retired.contains_key(*id))
            .count();
        if self.retired.len() + new_ids > MAX_RETIRED_WINDOWS {
            return Err(ObserverError::Limit);
        }
        if removed.iter().any(|id| self.live.contains_key(id)) {
            self.revocation_epoch = advance(self.revocation_epoch)?;
        }
        for (id, generation) in retire {
            self.retired.insert(id, generation);
        }
        for id in &removed {
            self.live.remove(id);
            self.quarantined.remove(id);
        }
        if self
            .active_hint
            .as_ref()
            .is_some_and(|key| removed.contains(&key.id))
        {
            self.active_hint = None;
        }
        Ok(())
    }
    pub fn disconnect(&mut self) {
        if self.connected {
            let _ = self.fail_closed(ObserverError::Disconnected);
        }
    }
    pub fn snapshot(&self, offset: usize, limit: usize) -> Result<ObserverSnapshot, ObserverError> {
        if limit == 0 || limit > 64 || offset > self.live.len() {
            return Err(ObserverError::InvalidPage);
        }
        let mut snapshot = ObserverSnapshot {
            version: 1,
            session_epoch: self.session_epoch,
            connected: self.connected,
            locked: self.locked,
            revocation_epoch: self.revocation_epoch,
            revision: self.revision,
            capture: false,
            atomic_input: false,
            runtime_verified: false,
            active_hint: self.active_hint.clone(),
            last_error: self.last_error,
            window_count: self.live.len(),
            quarantined_count: self.quarantined.len(),
            retired_count: self.retired.len(),
            offset,
            next_offset: None,
            windows: vec![],
        };
        for window in self.live.values().skip(offset).take(limit) {
            snapshot.windows.push(window.clone());
            snapshot.next_offset = Some(offset + snapshot.windows.len());
            let encoded = serde_json::to_vec(&snapshot).map_err(|_| ObserverError::InvalidFrame)?;
            if encoded.len() + 1 > crate::MAX_MESSAGE - 256 {
                snapshot.windows.pop();
                break;
            }
        }
        if offset < self.live.len() && snapshot.windows.is_empty() {
            return Err(ObserverError::Limit);
        }
        let next = offset + snapshot.windows.len();
        snapshot.next_offset = if next < self.live.len() {
            Some(next)
        } else {
            None
        };
        Ok(snapshot)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn event(id: &str, x: i32) -> ObserverEvent {
        ObserverEvent::Window {
            version: 1,
            id: id.into(),
            parent: None,
            kind: WindowKind::Normal,
            geometry: Geometry {
                x,
                y: 0,
                width: 100,
                height: 100,
            },
            caption: String::new(),
            app_id: String::new(),
        }
    }
    #[test]
    fn geometry_generation_and_revocation_exhaustion_fail_closed_without_wrapping() {
        let mut geometry = ObserverReducer::new(1).unwrap();
        geometry.apply_event(event("id", 0)).unwrap();
        geometry.live.get_mut("id").unwrap().geometry_epoch = MAX_SAFE_INTEGER;
        assert_eq!(
            geometry.apply_event(event("id", 1)),
            Err(ObserverError::UnsafeCounter)
        );
        assert!(!geometry.connected && geometry.locked);
        let mut generation = ObserverReducer::new(1).unwrap();
        generation.retired.insert("id".into(), MAX_SAFE_INTEGER);
        assert_eq!(
            generation.apply_event(event("id", 0)),
            Err(ObserverError::UnsafeCounter)
        );
        assert!(generation.live.is_empty());
        let mut revocation = ObserverReducer::new(1).unwrap();
        revocation.revocation_epoch = MAX_SAFE_INTEGER;
        assert_eq!(
            revocation.apply_event(ObserverEvent::Lock {
                version: 1,
                locked: true
            }),
            Err(ObserverError::UnsafeCounter)
        );
        assert_eq!(revocation.revocation_epoch, MAX_SAFE_INTEGER);
        assert!(!revocation.connected);
        let mut revision = ObserverReducer::new(1).unwrap();
        revision.revision = MAX_SAFE_INTEGER;
        assert_eq!(
            revision.apply_event(event("id", 0)),
            Err(ObserverError::UnsafeCounter)
        );
        assert!(revision.live.is_empty());
    }
    #[test]
    fn retired_limit_is_enforced_before_new_retirement() {
        let mut reducer = ObserverReducer::new(1).unwrap();
        for index in 0..MAX_RETIRED_WINDOWS {
            reducer.retired.insert(format!("retired-{index}"), 1);
        }
        reducer.apply_event(event("new", 0)).unwrap();
        assert_eq!(
            reducer.apply_event(ObserverEvent::Closed {
                version: 1,
                id: "new".into()
            }),
            Err(ObserverError::Limit)
        );
        assert!(!reducer.connected);
    }
}

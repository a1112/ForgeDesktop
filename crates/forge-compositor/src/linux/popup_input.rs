//! Short-lived, client-bound popup authorization from delivered input events.
use std::time::{Duration, Instant};

pub(super) struct PopupInput<C> {
    delivered: Vec<(u32, C, Instant)>,
}
impl<C: PartialEq> Default for PopupInput<C> {
    fn default() -> Self {
        Self {
            delivered: Vec::new(),
        }
    }
}
impl<C: PartialEq> PopupInput<C> {
    pub fn record(&mut self, serial: u32, client: C, now: Instant) {
        self.delivered.retain(|(_, owner, at)| {
            *owner == client && now.duration_since(*at) < Duration::from_secs(2)
        });
        if self.delivered.len() == 2 {
            self.delivered.remove(0);
        }
        self.delivered.push((serial, client, now));
    }
    pub fn consume(&mut self, serial: u32, client: &C, now: Instant) -> bool {
        let valid = self.delivered.iter().any(|(s, c, at)| {
            *s == serial && c == client && now.duration_since(*at) < Duration::from_secs(2)
        });
        if valid {
            self.delivered.clear();
        }
        valid
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn popup_input_is_client_bound_recent_and_one_use() {
        let mut auth = PopupInput::default();
        let now = Instant::now();
        auth.record(41, 7, now);
        auth.record(42, 7, now);
        assert!(!auth.consume(42, &8, now));
        assert!(!auth.consume(43, &7, now));
        assert!(auth.consume(41, &7, now));
        assert!(!auth.consume(42, &7, now));
        auth.record(50, 7, now);
        assert!(!auth.consume(50, &7, now + Duration::from_secs(2)));
        auth.record(51, 7, now);
        auth.record(52, 8, now);
        assert!(!auth.consume(51, &7, now));
    }
}

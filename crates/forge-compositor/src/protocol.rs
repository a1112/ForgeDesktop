//! Private shell protocol, shared policy and framing bounds.
pub const MAX_FRAME: usize = 65536;
#[derive(Debug, PartialEq, Eq)]
pub enum Command {
    Window(String, String),
    Workspace(u32),
    Move(String, u32),
    Launcher(bool, u32),
}
#[derive(Default)]
pub struct Decoder {
    bytes: Vec<u8>,
}
impl Decoder {
    pub fn feed(&mut self, bytes: &[u8]) -> Result<(), String> {
        if self.bytes.len() + bytes.len() > MAX_FRAME * 2 {
            return Err("input queue exceeded".into());
        }
        self.bytes.extend_from_slice(bytes);
        if self.bytes.len() >= 4 && self.length()? > MAX_FRAME {
            return Err("frame exceeded".into());
        }
        Ok(())
    }
    fn length(&self) -> Result<usize, String> {
        let n = u32::from_be_bytes(self.bytes[..4].try_into().unwrap()) as usize;
        if n == 0 || n > MAX_FRAME {
            Err("invalid frame length".into())
        } else {
            Ok(n)
        }
    }
    pub fn next_frame(&mut self) -> Result<Option<Vec<u8>>, String> {
        if self.bytes.len() < 4 {
            return Ok(None);
        }
        let n = self.length()?;
        if self.bytes.len() < n + 4 {
            return Ok(None);
        }
        let result = self.bytes[4..n + 4].to_vec();
        self.bytes.drain(..n + 4);
        Ok(Some(result))
    }
}
pub fn frame(payload: &[u8]) -> Result<Vec<u8>, String> {
    if payload.is_empty() || payload.len() > MAX_FRAME {
        return Err("invalid frame length".into());
    }
    let mut r = (payload.len() as u32).to_be_bytes().to_vec();
    r.extend_from_slice(payload);
    Ok(r)
}
pub fn command(payload: &[u8]) -> Result<Command, String> {
    if payload.len() > 128 {
        return Err("command exceeded".into());
    }
    let text = std::str::from_utf8(payload).map_err(|_| "invalid UTF-8")?;
    let fields: Vec<_> = text.split('\t').collect();
    fn id(s: &str) -> bool {
        s.len() == 17 && s.starts_with('w') && s[1..].bytes().all(|b| b.is_ascii_hexdigit())
    }
    fn workspace(s: &str) -> Option<u32> {
        s.parse::<u32>().ok().filter(|n| *n < 4)
    }
    match fields.as_slice() {
        ["1", "workspace", value] => workspace(value).map(Command::Workspace),
        ["1", "move", window, value] if id(window) => {
            workspace(value).map(|n| Command::Move((*window).into(), n))
        }
        ["1", "launcher", open @ ("0" | "1"), serial] => serial
            .parse::<u32>()
            .ok()
            .map(|serial| Command::Launcher(*open == "1", serial)),
        [
            "1",
            action @ ("activate" | "close" | "minimize" | "restore" | "maximize" | "fullscreen"
            | "normal" | "left" | "right"),
            window,
        ] if id(window) => Some(Command::Window((*action).into(), (*window).into())),
        _ => None,
    }
    .ok_or_else(|| "unknown or malformed command".into())
}
pub fn trusted_role(expected: Option<(u32, u32)>, actual: (u32, u32), role: &str) -> bool {
    expected == Some(actual)
        && matches!(
            role,
            "forge.background" | "forge.panel" | "forge.dock" | "forge.launcher"
        )
}
pub fn opaque_id(id: forge_desktop_core::WindowId) -> String {
    format!("w{:016x}", id.get())
}
pub fn resolve_window(
    handle: &str,
    windows: impl Iterator<Item = forge_desktop_core::WindowId>,
) -> Option<forge_desktop_core::WindowId> {
    windows.into_iter().find(|id| opaque_id(*id) == handle)
}
pub fn hex(text: &str) -> String {
    text.as_bytes()
        .iter()
        .take(256)
        .map(|b| format!("{b:02x}"))
        .collect()
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn partial_frames_and_multiple_messages() {
        let a = frame(b"1\tworkspace\t2").unwrap();
        let mut decoder = Decoder::default();
        decoder.feed(&a[..3]).unwrap();
        assert!(decoder.next_frame().unwrap().is_none());
        decoder.feed(&a[3..]).unwrap();
        decoder.feed(&a).unwrap();
        assert_eq!(
            command(&decoder.next_frame().unwrap().unwrap()).unwrap(),
            Command::Workspace(2)
        );
        assert_eq!(decoder.next_frame().unwrap().unwrap(), b"1\tworkspace\t2");
        assert!(decoder.next_frame().unwrap().is_none());
    }
    #[test]
    fn rejects_bounds_version_and_unknown_verbs() {
        assert!(frame(&vec![0; MAX_FRAME + 1]).is_err());
        let mut d = Decoder::default();
        assert!(d.feed(&((MAX_FRAME + 1) as u32).to_be_bytes()).is_err());
        for s in [
            "2\tworkspace\t0",
            "1\tworkspace\t4",
            "1\texec\txterm",
            "1\tactivate\t../../x",
            "1\tminimize\tw0001\textra",
        ] {
            assert!(command(s.as_bytes()).is_err(), "{s}");
        }
        assert_eq!(
            command(b"1\tactivate\tw0000000000000001").unwrap(),
            Command::Window("activate".into(), "w0000000000000001".into())
        );
    }
    #[test]
    fn roles_require_exact_live_child_credentials() {
        assert!(trusted_role(Some((12, 1000)), (12, 1000), "forge.panel"));
        assert!(!trusted_role(Some((12, 1000)), (13, 1000), "forge.panel"));
        assert!(!trusted_role(Some((12, 1000)), (12, 0), "forge.panel"));
        assert!(!trusted_role(None, (12, 1000), "forge.panel"));
        assert!(!trusted_role(Some((12, 1000)), (12, 1000), "ordinary"));
    }
    #[test]
    fn stale_ids_cannot_control_replacement_windows() {
        use forge_desktop_core::{Desktop, Geometry};
        let mut d = Desktop::default();
        let g = Geometry {
            x: 0,
            y: 0,
            width: 640,
            height: 480,
        };
        let old = d.map(0, g).unwrap();
        let stale = opaque_id(old);
        d.unmap(old).unwrap();
        let new = d.map(0, g).unwrap();
        assert_eq!(resolve_window(&stale, [new].into_iter()), None);
        assert_eq!(
            resolve_window(&opaque_id(new), [new].into_iter()),
            Some(new)
        );
    }
    #[test]
    fn pending_input_has_a_hard_queue_bound() {
        let mut d = Decoder::default();
        let bytes = frame(b"1\tworkspace\t0").unwrap();
        let mut rejected = false;
        for _ in 0..10000 {
            if d.feed(&bytes).is_err() {
                rejected = true;
                break;
            }
        }
        assert!(rejected);
    }
}

#![forbid(unsafe_code)]
pub mod protocol;

/// Wayland sockets must live in a directory private to the compositor user.
pub fn private_runtime_directory(owner: u32, user: u32, mode: u32, is_directory: bool) -> bool {
    owner == user && mode & 0o077 == 0 && is_directory
}

/// Split X11 uploads below its request limit, preserving complete scanlines.
pub fn upload_rows(width: usize, maximum_request_bytes: usize) -> Option<usize> {
    let stride = width.checked_mul(4).filter(|n| *n > 0)?;
    let rows = maximum_request_bytes.checked_sub(64)? / stride;
    (rows > 0).then_some(rows)
}

/// Resize around the opposite edge; reject invalid client edge combinations.
pub fn resize_geometry(
    start: (i32, i32, i32, i32),
    delta: (i32, i32),
    edges: u32,
) -> Option<(i32, i32, i32, i32)> {
    if !matches!(edges, 1 | 2 | 4 | 5 | 6 | 8 | 9 | 10) {
        return None;
    }
    let (mut x, mut y, mut w, mut h) = start;
    if edges & 4 != 0 {
        let next = w.saturating_sub(delta.0).clamp(64, 16384);
        x = x.saturating_add(w - next);
        w = next;
    }
    if edges & 8 != 0 {
        w = w.saturating_add(delta.0).clamp(64, 16384);
    }
    if edges & 1 != 0 {
        let next = h.saturating_sub(delta.1).clamp(32, 16384);
        y = y.saturating_add(h - next);
        h = next;
    }
    if edges & 2 != 0 {
        h = h.saturating_add(delta.1).clamp(32, 16384);
    }
    Some((x, y, w, h))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn runtime_directory_is_private_and_owned() {
        assert!(private_runtime_directory(1000, 1000, 0o40700, true));
        assert!(!private_runtime_directory(1001, 1000, 0o40700, true));
        assert!(!private_runtime_directory(1000, 1000, 0o40750, true));
        assert!(!private_runtime_directory(1000, 1000, 0o40777, true));
        assert!(!private_runtime_directory(1000, 1000, 0o100700, false));
    }
    #[test]
    fn bounded_uploads() {
        assert_eq!(upload_rows(1280, 262144), Some(51));
        assert_eq!(upload_rows(0, 262144), None);
        assert_eq!(upload_rows(1280, 5120), None);
        assert_eq!(upload_rows(usize::MAX, 262144), None);
    }
    #[test]
    fn opposite_resize_edge_stays_fixed() {
        assert_eq!(
            resize_geometry((30, 40, 200, 100), (50, 10), 5),
            Some((80, 50, 150, 90))
        );
        assert_eq!(
            resize_geometry((30, 40, 200, 100), (500, 500), 5),
            Some((166, 108, 64, 32))
        );
        assert_eq!(
            resize_geometry((30, 40, 200, 100), (50, 10), 10),
            Some((30, 40, 250, 110))
        );
        assert_eq!(resize_geometry((30, 40, 200, 100), (0, 0), 3), None);
    }
}

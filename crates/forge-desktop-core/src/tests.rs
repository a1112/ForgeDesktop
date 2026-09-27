use super::*;

fn rect() -> Geometry {
    Geometry::new(10, 20, 640, 480).unwrap()
}
fn screen() -> Geometry {
    Geometry::new(0, 0, 1280, 800).unwrap()
}
fn outputs(width: u32) -> Vec<Output> {
    vec![Output {
        id: 1,
        enabled: true,
        geometry: Geometry::new(0, 0, width, 800).unwrap(),
        scale_milli: 1000,
    }]
}

#[test]
fn geometry_rejects_empty_oversized_and_out_of_bounds() {
    for (x, y, w, h) in [
        (0, 0, 0, 1),
        (0, 0, 1, 0),
        (0, 0, 16385, 1),
        (0, 0, 1, 16385),
        (i32::MAX, 0, 1, 1),
        (0, i32::MIN, 1, 1),
        (1_000_000, 0, 2, 2),
    ] {
        assert_eq!(Geometry::new(x, y, w, h), Err(Error::InvalidGeometry));
    }
    assert!(Geometry::new(-1280, -800, 1280, 800).is_ok());
}

#[test]
fn lifecycle_ids_never_reuse_and_focus_falls_back() {
    let mut d = Desktop::default();
    let a = d.map(0, rect()).unwrap();
    let b = d.map(0, rect()).unwrap();
    assert_eq!(d.focused(), Some(b));
    d.unmap(b).unwrap();
    assert_eq!(d.focused(), Some(a));
    let c = d.map(0, rect()).unwrap();
    assert!(c.get() > b.get() && b.get() > a.get());
    assert_eq!(d.focus(b), Err(Error::UnknownWindow));
    assert_eq!(d.unmap(b), Err(Error::UnknownWindow));
    d.unmap(a).unwrap();
    d.unmap(c).unwrap();
    assert_eq!(d.focused(), None);
}

#[test]
fn invalid_map_and_geometry_do_not_change_window() {
    let mut d = Desktop::default();
    assert_eq!(d.map(64, rect()), Err(Error::InvalidWorkspace));
    let id = d.map(0, rect()).unwrap();
    let bad = Geometry { width: 0, ..rect() };
    assert_eq!(d.set_geometry(id, bad), Err(Error::InvalidGeometry));
    assert_eq!(d.window(id).unwrap().geometry(), rect());
    let moved = Geometry::new(-500, 100, 500, 400).unwrap();
    d.set_geometry(id, moved).unwrap();
    assert_eq!(d.window(id).unwrap().geometry(), moved);
}

#[test]
fn minimize_restores_visibility_and_preserves_geometry() {
    let mut d = Desktop::default();
    let a = d.map(0, rect()).unwrap();
    let b = d.map(0, rect()).unwrap();
    d.minimize(b).unwrap();
    assert!(d.window(b).unwrap().minimized());
    assert!(!d.visible(b));
    assert_eq!(d.focused(), Some(a));
    assert_eq!(d.focus(b), Err(Error::NotVisible));
    d.restore(b).unwrap();
    assert!(d.visible(b));
    assert_eq!(d.focused(), Some(b));
    assert_eq!(d.window(b).unwrap().geometry(), rect());
}

#[test]
fn fullscreen_returns_to_maximized_then_original_geometry() {
    let mut d = Desktop::default();
    let id = d.map(0, rect()).unwrap();
    let max = Geometry::new(0, 30, 1280, 720).unwrap();
    d.set_maximized(id, Some(max)).unwrap();
    assert!(d.window(id).unwrap().maximized());
    assert_eq!(d.window(id).unwrap().geometry(), max);
    d.set_fullscreen(id, Some(screen())).unwrap();
    assert!(d.window(id).unwrap().fullscreen());
    assert_eq!(d.window(id).unwrap().geometry(), screen());
    assert_eq!(d.set_geometry(id, rect()), Err(Error::ManagedGeometry));
    d.minimize(id).unwrap();
    d.restore(id).unwrap();
    assert_eq!(d.window(id).unwrap().geometry(), screen());
    d.set_fullscreen(id, None).unwrap();
    assert_eq!(d.window(id).unwrap().geometry(), max);
    d.set_maximized(id, None).unwrap();
    assert_eq!(d.window(id).unwrap().geometry(), rect());
    assert!(!d.window(id).unwrap().fullscreen());
    assert!(!d.window(id).unwrap().maximized());
}

#[test]
fn workspace_switch_and_transfer_keep_focus_visible() {
    let mut d = Desktop::default();
    let a = d.map(0, rect()).unwrap();
    let b = d.map(1, rect()).unwrap();
    assert_eq!(d.focused(), Some(a));
    assert!(!d.visible(b));
    d.switch_workspace(1).unwrap();
    assert_eq!(d.active_workspace(), 1);
    assert_eq!(d.focused(), Some(b));
    assert_eq!(d.focus(a), Err(Error::NotVisible));
    d.move_to_workspace(b, 0).unwrap();
    assert_eq!(d.focused(), None);
    assert_eq!(d.window(b).unwrap().workspace(), 0);
    d.switch_workspace(0).unwrap();
    assert!(d.visible(d.focused().unwrap()));
    let before = d.focused();
    assert_eq!(d.switch_workspace(64), Err(Error::InvalidWorkspace));
    assert_eq!(d.move_to_workspace(a, 64), Err(Error::InvalidWorkspace));
    assert_eq!(d.focused(), before);
}

#[test]
fn lock_pending_denies_controls_and_only_live_owner_can_unlock() {
    let mut d = Desktop::default();
    let id = d.map(0, rect()).unwrap();
    let locker = d.request_lock().unwrap();
    assert_eq!(d.lock_state(), LockState::Pending);
    assert_eq!(d.focused(), None);
    assert!(!d.visible(id));
    assert_eq!(d.focus(id), Err(Error::Locked));
    assert_eq!(d.set_geometry(id, screen()), Err(Error::Locked));
    assert_eq!(d.minimize(id), Err(Error::Locked));
    assert_eq!(d.restore(id), Err(Error::Locked));
    assert_eq!(d.set_maximized(id, Some(screen())), Err(Error::Locked));
    assert_eq!(d.set_fullscreen(id, Some(screen())), Err(Error::Locked));
    assert_eq!(d.switch_workspace(1), Err(Error::Locked));
    assert_eq!(d.move_to_workspace(id, 1), Err(Error::Locked));
    assert_eq!(d.request_lock(), Err(Error::Locked));
    assert_eq!(d.unlock(locker), Err(Error::InvalidLocker));
    let wrong = LockerId(locker.0 + 1);
    assert_eq!(d.lock_ready(wrong), Err(Error::InvalidLocker));
    d.lock_ready(locker).unwrap();
    assert_eq!(d.unlock(wrong), Err(Error::InvalidLocker));
    assert_eq!(d.locker_disconnected(wrong), Err(Error::InvalidLocker));
    d.unlock(locker).unwrap();
    assert_eq!(d.lock_state(), LockState::Unlocked);
    assert_eq!(d.focused(), Some(id));
    let next = d.request_lock().unwrap();
    assert_ne!(next, locker);
    assert_eq!(d.lock_ready(locker), Err(Error::InvalidLocker));
}

#[test]
fn locker_crash_before_or_after_ready_stays_locked() {
    for ready in [false, true] {
        let mut d = Desktop::default();
        let owner = d.request_lock().unwrap();
        if ready {
            d.lock_ready(owner).unwrap();
        }
        d.locker_disconnected(owner).unwrap();
        assert_eq!(d.lock_state(), LockState::Locked);
        assert_eq!(d.unlock(owner), Err(Error::InvalidLocker));
        assert_eq!(d.lock_ready(owner), Err(Error::InvalidLocker));
        assert_eq!(d.request_lock(), Err(Error::Locked));
        let id = d.map(0, rect()).unwrap();
        assert!(!d.visible(id));
        assert_eq!(d.focused(), None);
        d.unmap(id).unwrap();
    }
}

#[test]
fn output_confirm_and_timeout_preserve_last_confirmed_layout() {
    let mut t = OutputTransaction::new(outputs(1280), 100).unwrap();
    t.stage(outputs(1024), 110, 1000).unwrap();
    assert!(t.pending());
    assert_eq!(t.active(), outputs(1024));
    t.confirm(111).unwrap();
    assert!(!t.pending());
    t.stage(outputs(800), 120, 1000).unwrap();
    assert!(!t.tick(1119).unwrap());
    assert!(t.tick(1120).unwrap());
    assert_eq!(t.active(), outputs(1024));
    assert_eq!(t.confirm(1121), Err(Error::NoPendingOutputChange));
}

#[test]
fn output_expired_confirmation_rolls_back_at_exact_deadline() {
    let mut t = OutputTransaction::new(outputs(1280), 0).unwrap();
    t.stage(outputs(800), 1, 10).unwrap();
    assert_eq!(t.confirm(11), Err(Error::Expired));
    assert_eq!(t.active(), outputs(1280));
    assert!(!t.pending());
}

#[test]
fn output_changes_reject_invalid_or_ambiguous_layouts_atomically() {
    let mut invalid = vec![vec![]];
    let mut disabled = outputs(1280);
    disabled[0].enabled = false;
    invalid.push(disabled);
    let mut scale = outputs(1280);
    scale[0].scale_milli = 0;
    invalid.push(scale);
    let mut size = outputs(1280);
    size[0].geometry.width = 0;
    invalid.push(size);
    let mut duplicate = outputs(1280);
    duplicate.push(duplicate[0].clone());
    invalid.push(duplicate);
    let mut t = OutputTransaction::new(outputs(1280), 0).unwrap();
    for layout in invalid {
        assert!(matches!(
            OutputTransaction::new(layout.clone(), 0),
            Err(Error::InvalidOutputs)
        ));
        assert_eq!(t.stage(layout, 1, 100), Err(Error::InvalidOutputs));
        assert_eq!(t.active(), outputs(1280));
        assert!(!t.pending());
    }
    assert_eq!(t.stage(outputs(800), 2, 0), Err(Error::InvalidTimeout));
    assert_eq!(
        t.stage(outputs(800), u64::MAX, 1),
        Err(Error::InvalidTimeout)
    );
}

#[test]
fn output_monotonic_time_and_single_pending_transaction() {
    let mut t = OutputTransaction::new(outputs(1280), 100).unwrap();
    t.stage(outputs(800), 110, 10).unwrap();
    assert_eq!(
        t.stage(outputs(1024), 111, 10),
        Err(Error::PendingOutputChange)
    );
    assert_eq!(t.tick(109), Err(Error::TimeWentBackwards));
    assert_eq!(t.confirm(109), Err(Error::TimeWentBackwards));
    assert_eq!(t.cancel(109), Err(Error::TimeWentBackwards));
    assert_eq!(t.active(), outputs(800));
    t.cancel(115).unwrap();
    assert_eq!(t.active(), outputs(1280));
    assert_eq!(t.cancel(115), Err(Error::NoPendingOutputChange));
}

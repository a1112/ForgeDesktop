use forge_window_bridge::*;

fn key(id: &str) -> WindowKey {
    WindowKey {
        session_epoch: 7,
        id: id.into(),
        generation: 1,
    }
}
fn rect() -> Geometry {
    Geometry {
        x: 10,
        y: 20,
        width: 640,
        height: 480,
    }
}
fn setup() -> Bridge {
    let mut b = Bridge::new(7).unwrap();
    b.observe(key("root"), None, WindowKind::Normal, rect())
        .unwrap();
    b.set_locked(false);
    b.grant("controller", &key("root")).unwrap();
    b
}
fn event(b: &Bridge, target: WindowKey) -> InputRequest {
    InputRequest {
        controller: "controller".into(),
        target,
        geometry_epoch: 1,
        lease_epoch: b.lease_epoch(),
        sequence: 1,
        event: Input::Pointer { x: 10, y: 10 },
    }
}
#[test]
fn stale_geometry_focus_and_replay_fail_closed() {
    let mut b = setup();
    let e = event(&b, key("root"));
    assert_eq!(b.admit(&e, &key("other")), Err(Error::WrongTarget));
    assert!(b.admit(&e, &key("root")).is_ok());
    assert_eq!(b.admit(&e, &key("root")), Err(Error::Replay));
    b.geometry(
        &key("root"),
        Geometry {
            width: 800,
            ..rect()
        },
    )
    .unwrap();
    let mut next = e;
    next.sequence = 2;
    assert_eq!(b.admit(&next, &key("root")), Err(Error::StaleGeometry));
}
#[test]
fn popup_inherits_but_unrelated_and_stale_window_do_not() {
    let mut b = setup();
    b.observe(key("popup"), Some(key("root")), WindowKind::Popup, rect())
        .unwrap();
    b.observe(key("other"), None, WindowKind::Normal, rect())
        .unwrap();
    assert!(b.admit(&event(&b, key("popup")), &key("popup")).is_ok());
    assert_eq!(
        b.admit(&event(&b, key("other")), &key("other")),
        Err(Error::NotGranted)
    );
    b.close(&key("root")).unwrap();
    assert_eq!(
        b.admit(&event(&b, key("popup")), &key("popup")),
        Err(Error::UnknownWindow)
    );
    assert_eq!(
        b.observe(key("root"), None, WindowKind::Normal, rect()),
        Err(Error::ReusedIdentity)
    );
}
#[test]
fn locking_revokes_and_unlock_does_not_restore_grants() {
    let mut b = setup();
    let e = event(&b, key("root"));
    b.set_locked(true);
    assert_eq!(b.admit(&e, &key("root")), Err(Error::Locked));
    b.set_locked(false);
    assert_eq!(b.admit(&e, &key("root")), Err(Error::NotGranted));
}
#[test]
fn seat_is_exclusive_and_lease_invalidated_on_revoke() {
    let mut b = setup();
    let e = event(&b, key("root"));
    assert_eq!(b.grant("second", &key("root")), Err(Error::SeatBusy));
    b.revoke();
    b.grant("controller", &key("root")).unwrap();
    assert_eq!(b.admit(&e, &key("root")), Err(Error::StaleLease));
}
#[test]
fn malformed_geometry_coordinates_and_cross_session_rejected() {
    let mut b = setup();
    let mut e = event(&b, key("root"));
    e.event = Input::Pointer { x: 640, y: 1 };
    assert_eq!(b.admit(&e, &key("root")), Err(Error::OutsideWindow));
    assert_eq!(
        b.geometry(&key("root"), Geometry { width: 0, ..rect() }),
        Err(Error::InvalidGeometry)
    );
    let mut foreign = key("foreign");
    foreign.session_epoch = 8;
    assert_eq!(
        b.observe(foreign, None, WindowKind::Normal, rect()),
        Err(Error::WrongSession)
    );
}

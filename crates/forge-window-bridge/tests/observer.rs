use forge_window_bridge::observer::{MAX_LIVE_WINDOWS, MAX_SAFE_INTEGER};
use forge_window_bridge::{ObserverError, ObserverReducer};
use serde_json::{Value, json};
use std::io::Write;
use std::process::{Command, Stdio};
fn frame(value: Value) -> Vec<u8> {
    let mut bytes = serde_json::to_vec(&value).unwrap();
    bytes.push(b'\n');
    bytes
}
fn window(id: &str, parent: Option<&str>, kind: &str, x: i32) -> Value {
    json!({"version":1,"type":"window","id":id,"parent":parent,"kind":kind,"geometry":{"x":x,"y":20,"width":800,"height":600},"caption":"真实窗口","app_id":"org.example.App"})
}
fn apply(reducer: &mut ObserverReducer, value: Value) {
    reducer.apply_frame(&frame(value)).unwrap();
}
#[test]
fn actual_companion_metadata_updates_and_reuses_generations_without_authorizing_hints() {
    let mut reducer = ObserverReducer::new(7).unwrap();
    apply(
        &mut reducer,
        json!({"version":1,"type":"lock","locked":false}),
    );
    apply(&mut reducer, window("root", None, "normal", 10));
    let first = reducer.snapshot(0, 64).unwrap();
    assert_eq!(first.windows[0].key.generation, 1);
    let mut updated = window("root", None, "normal", 50);
    updated["caption"] = json!("Android administrator grant");
    updated["app_id"] = json!("fake.android.identity");
    apply(&mut reducer, updated.clone());
    apply(&mut reducer, updated);
    let current = reducer.snapshot(0, 64).unwrap();
    assert_eq!(current.windows[0].geometry_epoch, 2);
    assert_eq!(current.windows[0].key, first.windows[0].key);
    assert_eq!(current.windows[0].caption, "Android administrator grant");
    assert!(!current.capture && !current.atomic_input && !current.runtime_verified);
    apply(
        &mut reducer,
        json!({"version":1,"type":"closed","id":"root"}),
    );
    apply(&mut reducer, window("root", None, "normal", 0));
    assert_eq!(
        reducer.snapshot(0, 64).unwrap().windows[0].key.generation,
        2
    );
}
#[test]
fn unknown_parent_requires_fresh_child_observation_and_close_retires_subtree() {
    let mut reducer = ObserverReducer::new(8).unwrap();
    apply(&mut reducer, window("child", Some("parent"), "dialog", 0));
    assert_eq!(reducer.snapshot(0, 64).unwrap().quarantined_count, 1);
    apply(&mut reducer, window("parent", None, "normal", 0));
    assert_eq!(reducer.snapshot(0, 64).unwrap().window_count, 1);
    apply(&mut reducer, window("child", Some("parent"), "dialog", 0));
    apply(&mut reducer, window("popup", Some("child"), "popup", 0));
    let initial = reducer.snapshot(0, 64).unwrap();
    assert_eq!(initial.window_count, 3);
    apply(
        &mut reducer,
        json!({"version":1,"type":"closed","id":"parent"}),
    );
    assert_eq!(reducer.snapshot(0, 64).unwrap().window_count, 0);
    apply(&mut reducer, window("parent", None, "normal", 0));
    assert_eq!(
        reducer.snapshot(0, 64).unwrap().window_count,
        1,
        "Old children cannot resurrect with the parent name"
    );
    apply(&mut reducer, window("child", Some("parent"), "dialog", 0));
    let result = reducer.snapshot(0, 64).unwrap();
    let child = result.windows.iter().find(|w| w.key.id == "child").unwrap();
    assert_eq!(child.key.generation, 2);
    assert_eq!(child.parent.as_ref().unwrap().generation, 2);
}
#[test]
fn lock_revokes_and_disconnect_never_unlocks_or_revives_same_epoch() {
    let mut reducer = ObserverReducer::new(9).unwrap();
    apply(&mut reducer, window("root", None, "normal", 0));
    apply(
        &mut reducer,
        json!({"version":1,"type":"active","id":"root"}),
    );
    let before = reducer.snapshot(0, 64).unwrap();
    assert!(before.active_hint.is_some());
    apply(
        &mut reducer,
        json!({"version":1,"type":"lock","locked":true}),
    );
    let locked = reducer.snapshot(0, 64).unwrap();
    assert!(locked.locked);
    assert!(locked.active_hint.is_none());
    assert!(locked.revocation_epoch > before.revocation_epoch);
    apply(&mut reducer, json!({"version":1,"type":"disconnected"}));
    let closed = reducer.snapshot(0, 64).unwrap();
    assert!(!closed.connected && closed.locked);
    assert!(closed.windows.is_empty());
    assert_eq!(
        reducer.apply_frame(&frame(json!({"version":1,"type":"lock","locked":false}))),
        Err(ObserverError::Disconnected)
    );
    assert!(
        reducer
            .apply_frame(&frame(window("root", None, "normal", 0)))
            .is_err()
    );
    let mut fresh = ObserverReducer::new(10).unwrap();
    apply(&mut fresh, window("root", None, "normal", 0));
    assert_eq!(
        fresh.snapshot(0, 64).unwrap().windows[0].key.session_epoch,
        10
    );
}
#[test]
fn strict_frames_and_browser_control_messages_fail_closed() {
    let mut invalid = vec![
        b"{}".to_vec(),
        b"{}\n\n".to_vec(),
        b"\xff\n".to_vec(),
        vec![b'x'; 65537],
        b"{\"version\":1,\"version\":1,\"type\":\"lock\",\"locked\":false}\n".to_vec(),
        b"{\"version\":1,\"type\":\"lock\",\"locked\":false,\"locked\":false}\n".to_vec(),
        frame(json!({"version":2,"type":"lock","locked":false})),
        frame(json!({"version":1,"type":"grant","controller":"browser","root":{}})),
        frame(json!({"version":1,"type":"capabilities","capture":true,"atomic_input":false})),
    ];
    let mut unknown = window("root", None, "normal", 0);
    unknown["geometry"]["scale"] = json!(1);
    invalid.push(frame(unknown));
    let mut missing = window("root", None, "normal", 0);
    missing.as_object_mut().unwrap().remove("parent");
    invalid.push(frame(missing));
    let mut huge = window("root", None, "normal", 0);
    huge["geometry"]["width"] = json!(16385);
    invalid.push(frame(huge));
    for bytes in invalid {
        let mut reducer = ObserverReducer::new(1).unwrap();
        assert!(reducer.apply_frame(&bytes).is_err());
        let state = reducer.snapshot(0, 64).unwrap();
        assert!(
            !state.connected && state.locked && !state.capture && !state.atomic_input,
            "Malformed input cannot keep an open observer"
        );
    }
}
#[test]
fn counters_and_registry_are_bounded_and_pages_fit_real_json_budget() {
    assert!(ObserverReducer::new(0).is_err());
    assert!(ObserverReducer::new(MAX_SAFE_INTEGER + 1).is_err());
    let mut reducer = ObserverReducer::new(MAX_SAFE_INTEGER).unwrap();
    for index in 0..64 {
        let mut item = window(&format!("window-{index:05}"), None, "normal", 0);
        item["caption"] = json!("\u{0001}".repeat(4096));
        item["app_id"] = json!("中".repeat(1024));
        apply(&mut reducer, item);
    }
    let mut offset = 0;
    let mut count = 0;
    loop {
        let page = reducer.snapshot(offset, 64).unwrap();
        assert!(!page.windows.is_empty());
        assert!(serde_json::to_vec(&page).unwrap().len() < 65536);
        count += page.windows.len();
        if let Some(next) = page.next_offset {
            offset = next;
        } else {
            break;
        }
    }
    assert_eq!(count, 64);
    assert!(reducer.snapshot(0, 65).is_err());
    let mut bounded = ObserverReducer::new(11).unwrap();
    for index in 0..MAX_LIVE_WINDOWS {
        apply(
            &mut bounded,
            window(&format!("id-{index}"), None, "normal", 0),
        );
    }
    assert_eq!(
        bounded.apply_frame(&frame(window("overflow", None, "normal", 0))),
        Err(ObserverError::Limit)
    );
    assert!(!bounded.connected());
}
#[test]
fn quarantined_limit_and_parent_cycles_fail_closed() {
    let mut quarantine = ObserverReducer::new(1).unwrap();
    for index in 0..forge_window_bridge::observer::MAX_QUARANTINED_WINDOWS {
        apply(
            &mut quarantine,
            window(&format!("orphan-{index}"), Some("missing"), "popup", 0),
        );
    }
    assert_eq!(
        quarantine.apply_frame(&frame(window("too-many", Some("missing"), "popup", 0))),
        Err(ObserverError::Limit)
    );
    let mut cycle = ObserverReducer::new(1).unwrap();
    apply(&mut cycle, window("parent", None, "normal", 0));
    apply(&mut cycle, window("child", Some("parent"), "dialog", 0));
    assert_eq!(
        cycle.apply_frame(&frame(window("parent", Some("child"), "normal", 0))),
        Err(ObserverError::InvalidParent)
    );
    assert!(!cycle.connected());
}
#[test]
fn reparenting_retires_old_descendants_and_binds_a_fresh_generation() {
    let mut reducer = ObserverReducer::new(12).unwrap();
    apply(&mut reducer, window("one", None, "normal", 0));
    apply(&mut reducer, window("two", None, "normal", 0));
    apply(&mut reducer, window("child", Some("one"), "dialog", 0));
    apply(&mut reducer, window("popup", Some("child"), "popup", 0));
    apply(&mut reducer, window("child", Some("two"), "dialog", 0));
    let state = reducer.snapshot(0, 64).unwrap();
    assert_eq!(state.window_count, 3);
    let child = state
        .windows
        .iter()
        .find(|window| window.key.id == "child")
        .unwrap();
    assert_eq!(child.key.generation, 2);
    assert_eq!(child.parent.as_ref().unwrap().id, "two");
    assert!(!state.windows.iter().any(|window| window.key.id == "popup"));
    apply(&mut reducer, window("popup", Some("child"), "popup", 0));
    assert_eq!(
        reducer
            .snapshot(0, 64)
            .unwrap()
            .windows
            .iter()
            .find(|window| window.key.id == "popup")
            .unwrap()
            .key
            .generation,
        2
    );
}
#[test]
fn qt_utf16_hint_limits_and_exact_frame_boundary_are_observed() {
    let mut reducer = ObserverReducer::new(1).unwrap();
    let mut unicode = window("unicode", None, "normal", 0);
    unicode["caption"] = json!("😀".repeat(2048));
    apply(&mut reducer, unicode);
    let mut frame =
        frame(json!({"version":1,"type":"capabilities","capture":false,"atomic_input":false}));
    frame.pop();
    frame.resize(65535, b' ');
    frame.push(b'\n');
    assert!(reducer.apply_frame(&frame).is_ok());
    let mut large = window("bad", None, "normal", 0);
    large["app_id"] = json!("😀".repeat(513));
    assert_eq!(
        reducer.apply_frame(&crate::frame(large)),
        Err(ObserverError::InvalidHint)
    );
}
fn run_observer(input: &[u8]) -> std::process::Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_forge-window-bridge"))
        .args(["--observer-events", "--session-epoch", "7"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child.stdin.take().unwrap().write_all(input).unwrap();
    child.wait_with_output().unwrap()
}
#[test]
fn real_cli_consumes_companion_events_and_eof_disconnects_without_runtime_capabilities() {
    let mut input = frame(window("{real-uuid}", None, "normal", 10));
    input.extend(frame(json!({"version":1,"type":"lock","locked":false})));
    input.extend(frame(
        json!({"version":1,"type":"closed","id":"{real-uuid}"}),
    ));
    input.extend(frame(window("{real-uuid}", None, "normal", 20)));
    let output = run_observer(&input);
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let snapshots = output
        .stdout
        .split(|byte| *byte == b'\n')
        .filter(|line| !line.is_empty())
        .map(|line| serde_json::from_slice::<Value>(line).unwrap())
        .collect::<Vec<_>>();
    assert_eq!(snapshots.len(), 5);
    assert_eq!(snapshots[0]["windows"][0]["key"]["generation"], 1);
    assert_eq!(snapshots[3]["windows"][0]["key"]["generation"], 2);
    assert_eq!(snapshots[4]["connected"], false);
    assert_eq!(snapshots[4]["locked"], true);
    assert_eq!(snapshots[4]["window_count"], 0);
    for snapshot in snapshots {
        assert_eq!(snapshot["capture"], false);
        assert_eq!(snapshot["atomic_input"], false);
        assert_eq!(snapshot["runtime_verified"], false);
    }
}
#[test]
fn real_cli_rejects_browser_commands_and_truncated_input_with_locked_metadata() {
    for input in [
        b"{\"version\":1,\"type\":\"grant\",\"controller\":\"browser\"}\n".as_slice(),
        b"{}".as_slice(),
        b"\xff\n".as_slice(),
    ] {
        let output = run_observer(input);
        assert!(!output.status.success());
        let state: Value = serde_json::from_slice(output.stdout.trim_ascii())
            .expect("Rejected input must still report actual closed metadata");
        assert_eq!(state["connected"], false);
        assert_eq!(state["locked"], true);
        assert_eq!(state["capture"], false);
        assert!(state["last_error"].is_string());
    }
}

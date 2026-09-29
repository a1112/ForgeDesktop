use std::io::Write;
use std::process::{Command, Stdio};
fn run(input: &[u8]) -> std::process::Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_forge-window-bridge"))
        .args(["--session-epoch", "7"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap();
    child.stdin.take().unwrap().write_all(input).unwrap();
    child.wait_with_output().unwrap()
}
#[test]
fn capabilities_never_claim_runtime_input_and_version_is_checked() {
    let out = run(b"{\"version\":1,\"request_id\":1,\"command\":{\"type\":\"capabilities\"}}\n{\"version\":2,\"request_id\":2,\"command\":{\"type\":\"capabilities\"}}\n");
    assert!(out.status.success());
    let lines: Vec<serde_json::Value> = String::from_utf8(out.stdout)
        .unwrap()
        .lines()
        .map(|s| serde_json::from_str(s).unwrap())
        .collect();
    assert_eq!(lines[0]["result"]["capture"], false);
    assert_eq!(lines[0]["result"]["atomic_input"], false);
    assert_eq!(lines[1]["error"], "unsupported_version");
}
#[test]
fn oversized_line_terminates_instead_of_allocating_unbounded() {
    let out = run(&vec![b'a'; 65_537]);
    assert!(!out.status.success());
    assert!(
        String::from_utf8(out.stdout)
            .unwrap()
            .contains("message_too_large")
    );
}
#[test]
fn non_json_unknown_fields_and_truncated_frame_are_rejected() {
    assert!(
        String::from_utf8(run(b"x\n").stdout)
            .unwrap()
            .contains("invalid_message")
    );
    assert!(String::from_utf8(run(b"{\"version\":1,\"request_id\":1,\"evil\":true,\"command\":{\"type\":\"capabilities\"}}\n").stdout).unwrap().contains("invalid_message"));
    assert!(!run(b"{}").status.success());
}

#![forbid(unsafe_code)]
use forge_window_bridge::*;
use serde::Deserialize;
use serde_json::{Value, json};
use std::io::{self, BufRead, Read, Write};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Envelope {
    version: u32,
    request_id: u64,
    command: Command,
}
#[derive(Deserialize)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
enum Command {
    Capabilities {},
    Snapshot {
        #[serde(default)]
        offset: usize,
        #[serde(default = "page_size")]
        limit: usize,
    },
    Observe {
        key: WindowKey,
        parent: Option<WindowKey>,
        kind: WindowKind,
        geometry: Geometry,
    },
    Geometry {
        key: WindowKey,
        geometry: Geometry,
    },
    Close {
        key: WindowKey,
    },
    Lock {
        locked: bool,
    },
    Grant {
        controller: String,
        root: WindowKey,
    },
    Revoke {},
    Admit {
        request: InputRequest,
        compositor_target: WindowKey,
    },
}
fn page_size() -> usize {
    64
}
fn handle(bridge: &mut Bridge, command: Command) -> Result<Value, Error> {
    match command {
        Command::Capabilities {} => Ok(json!({"policy":true,"capture":false,"atomic_input":false,
            "runtime_verified":false,"reason":"compositor_atomic_adapter_not_installed"})),
        Command::Snapshot { offset, limit } => {
            if limit == 0 || limit > 64 || offset > 4096 {
                return Err(Error::Limit);
            }
            let windows = bridge
                .windows()
                .skip(offset)
                .take(limit)
                .collect::<Vec<_>>();
            let next = offset + windows.len();
            Ok(json!({"windows":windows,"lease_epoch":bridge.lease_epoch(),
                "next_offset":if next < bridge.windows().count() {Some(next)} else {None}}))
        }
        Command::Observe {
            key,
            parent,
            kind,
            geometry,
        } => {
            bridge.observe(key, parent, kind, geometry)?;
            Ok(json!({"observed":true}))
        }
        Command::Geometry { key, geometry } => {
            Ok(json!({"geometry_epoch":bridge.geometry(&key, geometry)?}))
        }
        Command::Close { key } => {
            bridge.close(&key)?;
            Ok(json!({"closed":true}))
        }
        Command::Lock { locked } => {
            bridge.set_locked(locked);
            Ok(json!({"locked":locked,"stop_streams":locked,"release_input":locked}))
        }
        Command::Grant { controller, root } => {
            Ok(json!({"lease_epoch":bridge.grant(&controller, &root)?}))
        }
        Command::Revoke {} => {
            bridge.revoke();
            Ok(json!({"stop_streams":true,"release_input":true}))
        }
        Command::Admit {
            request,
            compositor_target,
        } => {
            bridge.admit(&request, &compositor_target)?;
            Ok(json!({"admitted":true,"delivered":false}))
        }
    }
}
fn emit(out: &mut impl Write, value: Value) -> io::Result<()> {
    let bytes = serde_json::to_vec(&value)?;
    if bytes.len() >= MAX_MESSAGE {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "response exceeds frame limit",
        ));
    }
    out.write_all(&bytes)?;
    out.write_all(b"\n")?;
    out.flush()
}
fn emit_observer(
    out: &mut impl Write,
    reducer: &ObserverReducer,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut offset = 0;
    loop {
        let page = reducer.snapshot(offset, 64)?;
        let next = page.next_offset;
        emit(out, serde_json::to_value(page)?)?;
        match next {
            Some(next) => offset = next,
            None => return Ok(()),
        }
    }
}
fn observer_events(epoch: u64) -> Result<(), Box<dyn std::error::Error>> {
    let mut reducer = ObserverReducer::new(epoch)?;
    let mut input = io::stdin().lock();
    let mut output = io::stdout().lock();
    loop {
        let mut frame = Vec::new();
        let read = match (&mut input)
            .take((MAX_MESSAGE + 1) as u64)
            .read_until(b'\n', &mut frame)
        {
            Ok(read) => read,
            Err(error) => {
                reducer.disconnect();
                emit_observer(&mut output, &reducer)?;
                return Err(error.into());
            }
        };
        if read == 0 {
            reducer.disconnect();
            emit_observer(&mut output, &reducer)?;
            return Ok(());
        }
        let applied = reducer.apply_frame(&frame);
        emit_observer(&mut output, &reducer)?;
        if let Err(error) = applied {
            return Err(error.into());
        }
        if !reducer.connected() {
            return Ok(());
        }
    }
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() == 3 && args[0] == "--observer-events" && args[1] == "--session-epoch" {
        return observer_events(args[2].parse()?);
    }
    if args.len() != 2 || args[0] != "--session-epoch" {
        return Err("usage: forge-window-bridge --session-epoch NONZERO_U64; or --observer-events --session-epoch SAFE_NONZERO_INTEGER".into());
    }
    let mut bridge = Bridge::new(args[1].parse()?).map_err(|e| format!("{e:?}"))?;
    let mut input = io::stdin().lock();
    let mut output = io::stdout().lock();
    loop {
        let mut bytes = Vec::new();
        let read = (&mut input)
            .take((MAX_MESSAGE + 1) as u64)
            .read_until(b'\n', &mut bytes)?;
        if read == 0 {
            bridge.revoke();
            return Ok(());
        }
        if bytes.len() > MAX_MESSAGE || bytes.last() != Some(&b'\n') {
            bridge.revoke();
            emit(
                &mut output,
                json!({"version":1,"error":if bytes.len()>MAX_MESSAGE {"message_too_large"} else {"truncated_message"}}),
            )?;
            return Err("invalid frame; all grants revoked".into());
        }
        let envelope: Envelope = match serde_json::from_slice(&bytes) {
            Ok(value) => value,
            Err(_) => {
                emit(&mut output, json!({"version":1,"error":"invalid_message"}))?;
                continue;
            }
        };
        let response = if envelope.version != PROTOCOL_VERSION {
            json!({"version":1,"request_id":envelope.request_id,"error":"unsupported_version"})
        } else {
            match handle(&mut bridge, envelope.command) {
                Ok(result) => json!({"version":1,"request_id":envelope.request_id,"result":result}),
                Err(error) => json!({"version":1,"request_id":envelope.request_id,"error":error}),
            }
        };
        emit(&mut output, response)?;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn maximum_registry_snapshot_is_paged_under_frame_limit() {
        let mut bridge = Bridge::new(1).unwrap();
        for i in 0..4096 {
            bridge
                .observe(
                    WindowKey {
                        session_epoch: 1,
                        id: format!("{i:0128}"),
                        generation: 1,
                    },
                    None,
                    WindowKind::Normal,
                    Geometry {
                        x: 0,
                        y: 0,
                        width: 100,
                        height: 100,
                    },
                )
                .unwrap();
        }
        let result = handle(
            &mut bridge,
            serde_json::from_value(json!({"type":"snapshot","offset":0,"limit":64})).unwrap(),
        )
        .unwrap();
        assert_eq!(result["windows"].as_array().unwrap().len(), 64);
        assert_eq!(result["next_offset"], 64);
        assert!(serde_json::to_vec(&result).unwrap().len() < MAX_MESSAGE - 256);
        let command =
            serde_json::from_value(json!({"type":"snapshot","offset":0,"limit":65})).unwrap();
        assert_eq!(handle(&mut bridge, command), Err(Error::Limit));
    }
}

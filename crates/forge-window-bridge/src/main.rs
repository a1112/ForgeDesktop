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
    Capabilities,
    Snapshot,
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
    Revoke,
    Admit {
        request: InputRequest,
        compositor_target: WindowKey,
    },
}
fn handle(bridge: &mut Bridge, command: Command) -> Result<Value, Error> {
    match command {
        Command::Capabilities => Ok(json!({"policy":true,"capture":false,"atomic_input":false,
            "runtime_verified":false,"reason":"compositor_atomic_adapter_not_installed"})),
        Command::Snapshot => Ok(
            json!({"windows":bridge.windows().collect::<Vec<_>>(),"lease_epoch":bridge.lease_epoch()}),
        ),
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
        Command::Revoke => {
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
    serde_json::to_writer(&mut *out, &value)?;
    out.write_all(b"\n")?;
    out.flush()
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 2 || args[0] != "--session-epoch" {
        return Err("usage: forge-window-bridge --session-epoch NONZERO_U64".into());
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

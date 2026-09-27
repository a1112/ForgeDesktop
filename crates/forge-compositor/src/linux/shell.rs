//! Private inherited socket. No pathname, listener, arbitrary executable or exec verb.
use forge_compositor::protocol::{self, Command, Decoder};
use std::{
    io::{Read, Write},
    os::unix::{io::OwnedFd, net::UnixStream},
    process::{Child, Command as Process, Stdio},
    time::{Duration, Instant},
};
pub(super) struct Shell {
    child: Option<Child>,
    socket: Option<UnixStream>,
    decoder: Decoder,
    output: Vec<u8>,
    event: Option<String>,
    written: usize,
    last_state: String,
    next_start: Instant,
    failures: u32,
    started: Instant,
}
impl Shell {
    pub fn new() -> Self {
        Self {
            child: None,
            socket: None,
            decoder: Decoder::default(),
            output: vec![],
            event: None,
            written: 0,
            last_state: String::new(),
            next_start: Instant::now(),
            failures: 0,
            started: Instant::now(),
        }
    }
    pub fn credentials(&self) -> Option<(u32, u32)> {
        self.child.as_ref().map(|c| {
            (
                c.id(),
                smithay::reexports::rustix::process::geteuid().as_raw(),
            )
        })
    }
    fn failed(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        self.socket = None;
        self.output.clear();
        self.event = None;
        self.written = 0;
        self.last_state.clear();
        self.decoder = Decoder::default();
        self.failures = if self.started.elapsed() > Duration::from_secs(60) {
            1
        } else {
            (self.failures + 1).min(6)
        };
        self.next_start = Instant::now() + Duration::from_millis(250 * (1 << self.failures));
    }
    pub fn poll(&mut self) -> Vec<Command> {
        if self
            .child
            .as_mut()
            .is_some_and(|c| !matches!(c.try_wait(), Ok(None)))
        {
            self.failed();
        }
        if self.child.is_none() && Instant::now() >= self.next_start {
            let result = (|| -> std::io::Result<()> {
                let (server, client) = UnixStream::pair()?;
                server.set_nonblocking(true)?;
                let child = Process::new("/usr/libexec/forge-desktop/forge-shell")
                    .stdin(Stdio::from(OwnedFd::from(client)))
                    .env("WAYLAND_DISPLAY", "forge-wayland-0")
                    .env("QT_QPA_PLATFORM", "wayland")
                    .env_remove("DISPLAY")
                    .env("QT_QUICK_BACKEND", "software")
                    .env("QSG_RENDER_LOOP", "basic")
                    .env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
                    .spawn()?;
                eprintln!("ForgeDesktop shell started pid={}", child.id());
                self.child = Some(child);
                self.socket = Some(server);
                self.started = Instant::now();
                Ok(())
            })();
            if let Err(error) = result {
                eprintln!("ForgeDesktop shell start: {error}");
                self.failed();
            }
        }
        let mut commands = vec![];
        let result = (|| -> Result<(), String> {
            let Some(socket) = self.socket.as_mut() else {
                return Ok(());
            };
            let mut bytes = [0; 4096];
            // Read and command dispatch budgets avoid monopolizing compositor input/rendering.
            for _ in 0..4 {
                match socket.read(&mut bytes) {
                    Ok(0) => return Err("shell EOF".into()),
                    Ok(n) => self.decoder.feed(&bytes[..n])?,
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => break,
                    Err(e) => return Err(e.to_string()),
                }
            }
            for _ in 0..32 {
                let Some(frame) = self.decoder.next_frame()? else {
                    break;
                };
                commands.push(protocol::command(&frame)?);
            }
            while self.written < self.output.len() {
                match socket.write(&self.output[self.written..]) {
                    Ok(0) => return Err("shell write EOF".into()),
                    Ok(n) => self.written += n,
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => break,
                    Err(e) => return Err(e.to_string()),
                }
            }
            if self.written == self.output.len() {
                self.output.clear();
                self.written = 0;
                if let Some(event) = self.event.take() {
                    self.output = protocol::frame(event.as_bytes())?;
                }
            }
            Ok(())
        })();
        if let Err(error) = result {
            eprintln!("ForgeDesktop shell disconnected: {error}");
            self.failed();
            commands.clear();
        }
        commands
    }
    pub fn state(&mut self, state: String) {
        // At most one bounded frame queued. Coalesce new snapshots until drained.
        if self.socket.is_none() || !self.output.is_empty() || state == self.last_state {
            return;
        }
        if let Ok(bytes) = protocol::frame(state.as_bytes()) {
            self.output = bytes;
            self.last_state = state;
        }
    }
    pub fn presented(&mut self, serial: u32) {
        self.event = Some(format!("1\tpresented\t{serial}"));
    }
}
impl Drop for Shell {
    fn drop(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

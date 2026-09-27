//! Supervises the session notification service with an inherited authority FD.
use std::{
    io::Write,
    os::unix::{io::OwnedFd, net::UnixStream},
    process::{Child, Command, Stdio},
    time::{Duration, Instant},
};

pub(super) struct Notices {
    child: Option<Child>,
    socket: Option<UnixStream>,
    authorized_bus: Option<String>,
    needs_sync: bool,
    next_start: Instant,
    failures: u32,
    started: Instant,
}

impl Notices {
    pub fn new() -> Self {
        Self {
            child: None,
            socket: None,
            authorized_bus: None,
            needs_sync: false,
            next_start: Instant::now(),
            failures: 0,
            started: Instant::now(),
        }
    }

    pub fn authorize(&mut self, bus: Option<String>) {
        if self.authorized_bus != bus {
            self.authorized_bus = bus;
            self.needs_sync = true;
        }
    }

    fn failed(&mut self) {
        self.socket = None;
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        self.failures = if self.started.elapsed() > Duration::from_secs(60) {
            1
        } else {
            (self.failures + 1).min(6)
        };
        self.next_start = Instant::now() + Duration::from_millis(250 * (1 << self.failures));
    }

    pub fn poll(&mut self) {
        if self
            .child
            .as_mut()
            .is_some_and(|child| !matches!(child.try_wait(), Ok(None)))
        {
            self.failed();
        }
        if self.child.is_none()
            && Instant::now() >= self.next_start
            && std::env::var_os("DBUS_SESSION_BUS_ADDRESS").is_some()
        {
            let result = (|| -> std::io::Result<()> {
                let (server, client) = UnixStream::pair()?;
                server.set_nonblocking(true)?;
                let child = Command::new("/usr/libexec/forge-desktop/forge-notificationd")
                    .stdin(Stdio::from(OwnedFd::from(client)))
                    .spawn()?;
                eprintln!(
                    "ForgeDesktop notification service started pid={}",
                    child.id()
                );
                self.child = Some(child);
                self.socket = Some(server);
                self.started = Instant::now();
                self.needs_sync = true;
                Ok(())
            })();
            if let Err(error) = result {
                eprintln!("ForgeDesktop notification service start: {error}");
                self.failed();
            }
        }
        if !self.needs_sync {
            return;
        }
        let Some(socket) = self.socket.as_mut() else {
            return;
        };
        let line = self.authorized_bus.as_ref().map_or_else(
            || "1\trevoke\n".to_owned(),
            |name| format!("1\tauthorize\t{name}\n"),
        );
        match socket.write(line.as_bytes()) {
            Ok(n) if n == line.len() => self.needs_sync = false,
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {}
            Ok(_) | Err(_) => self.failed(), // A partial frame cannot be reused safely.
        }
    }
}

impl Drop for Notices {
    fn drop(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

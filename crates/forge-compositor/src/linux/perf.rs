//! Opt-in capped records. No files/log volume or timing claims by default.
use std::{
    fs::{File, OpenOptions},
    io::Write,
    time::Instant,
};
pub(super) struct Recorder {
    file: Option<File>,
    remaining: u32,
}
impl Recorder {
    pub fn new() -> Self {
        let file = std::env::var_os("FORGE_DESKTOP_PERF_FILE").and_then(|path| {
            match OpenOptions::new().write(true).create_new(true).open(path) {
                Ok(mut f) => {
                    let _ = writeln!(f, "kind,elapsed_us,damaged");
                    Some(f)
                }
                Err(e) => {
                    eprintln!("performance recording unavailable: {e}");
                    None
                }
            }
        });
        Self {
            file,
            remaining: 100_000,
        }
    }
    pub fn frame(&mut self, start: Instant, damaged: bool) {
        if self.remaining > 0 {
            if let Some(file) = self.file.as_mut() {
                if writeln!(
                    file,
                    "frame,{},{}",
                    start.elapsed().as_micros(),
                    u8::from(damaged)
                )
                .is_err()
                {
                    self.file = None;
                }
                self.remaining -= 1;
            }
        }
    }
}

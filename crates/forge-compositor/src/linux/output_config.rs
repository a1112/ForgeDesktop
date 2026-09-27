//! Versioned, bounded display settings. Only confirmed transactions are saved.
use forge_desktop_core::{Geometry, Output, OutputTransaction};
use std::{
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    os::unix::fs::OpenOptionsExt,
    path::{Path, PathBuf},
};

fn invalid() -> std::io::Error {
    std::io::Error::new(
        std::io::ErrorKind::InvalidData,
        "invalid display configuration",
    )
}
fn validate(outputs: &[Output]) -> std::io::Result<()> {
    if outputs.len() > 4
        || outputs.iter().any(|o| {
            !o.enabled
                || o.id == 0
                || !matches!(o.scale_milli, 1000 | 1500 | 2000)
                || o.geometry.x < 0
                || o.geometry.y < 0
        })
        || outputs
            .first()
            .is_none_or(|o| o.geometry.x != 0 || o.geometry.y != 0)
    {
        return Err(invalid());
    }
    OutputTransaction::new(outputs.to_vec(), 0).map_err(|_| invalid())?;
    Ok(())
}
pub(super) fn path() -> Option<PathBuf> {
    let base = std::env::var_os("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .filter(|p| p.is_absolute())
        .or_else(|| std::env::var_os("HOME").map(|h| PathBuf::from(h).join(".config")))?;
    Some(base.join("forge-desktop/v1/outputs.conf"))
}
pub(super) fn load(path: &Path) -> std::io::Result<Vec<Output>> {
    let mut data = String::new();
    File::open(path)?.take(4097).read_to_string(&mut data)?;
    if data.len() > 4096 {
        return Err(invalid());
    }
    let mut lines = data.lines();
    if lines.next() != Some("ForgeDesktop outputs 1") {
        return Err(invalid());
    }
    let mut outputs = Vec::new();
    for line in lines {
        let cells: Vec<_> = line.split('\t').collect();
        if cells.len() != 6 {
            return Err(invalid());
        }
        let values: Vec<u32> = cells
            .iter()
            .map(|v| v.parse().map_err(|_| invalid()))
            .collect::<Result<_, _>>()?;
        if values[1] > 16384 || values[2] > 16384 {
            return Err(invalid());
        }
        outputs.push(Output {
            id: values[0],
            enabled: true,
            geometry: Geometry {
                x: values[1] as i32,
                y: values[2] as i32,
                width: values[3],
                height: values[4],
            },
            scale_milli: values[5],
        });
    }
    validate(&outputs)?;
    Ok(outputs)
}
pub(super) fn save(path: &Path, outputs: &[Output]) -> std::io::Result<()> {
    validate(outputs)?;
    let parent = path.parent().ok_or_else(invalid)?;
    fs::create_dir_all(parent)?;
    let temp = parent.join(format!(".outputs-{}.tmp", std::process::id()));
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&temp)?;
    let result = (|| {
        writeln!(file, "ForgeDesktop outputs 1")?;
        for o in outputs {
            writeln!(
                file,
                "{}\t{}\t{}\t{}\t{}\t{}",
                o.id,
                o.geometry.x,
                o.geometry.y,
                o.geometry.width,
                o.geometry.height,
                o.scale_milli
            )?;
        }
        file.sync_all()?;
        fs::rename(&temp, path)?;
        File::open(parent)?.sync_all()
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temp);
    }
    result
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn confirmed_settings_roundtrip_and_bad_save_preserves_previous() {
        let root = std::env::temp_dir().join(format!("forge-output-test-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let path = root.join("outputs");
        let outputs = vec![Output {
            id: 1,
            enabled: true,
            geometry: Geometry {
                x: 0,
                y: 0,
                width: 853,
                height: 533,
            },
            scale_milli: 1500,
        }];
        save(&path, &outputs).unwrap();
        assert_eq!(load(&path).unwrap(), outputs);
        let mut bad = outputs.clone();
        bad[0].scale_milli = 1250;
        assert!(save(&path, &bad).is_err());
        assert_eq!(load(&path).unwrap(), outputs);
        fs::write(&path, "ForgeDesktop outputs 2\n").unwrap();
        assert!(load(&path).is_err());
        fs::write(&path, "ForgeDesktop outputs 1\n1\t0\t0\t0\t800\t1000\n").unwrap();
        assert!(load(&path).is_err());
        fs::write(&path, "x".repeat(4097)).unwrap();
        assert!(load(&path).is_err());
        fs::remove_file(&path).unwrap();
        fs::remove_dir(&root).unwrap();
    }
}

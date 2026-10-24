use std::path::{Path, PathBuf};

pub fn data_dir() -> PathBuf {
    if let Ok(p) = std::env::var("TETHER_HOME") {
        return PathBuf::from(p);
    }
    let base = std::env::var("XDG_DATA_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| home().join(".local/share"));
    base.join("tether")
}

pub(crate) fn home() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."))
}

pub fn db_path() -> PathBuf {
    if let Ok(p) = std::env::var("TETHER_DB") {
        return PathBuf::from(p);
    }
    data_dir().join("mailbox.db")
}

pub fn disabled_beside(db: &Path) -> PathBuf {
    db.parent()
        .unwrap_or_else(|| Path::new("."))
        .join("disabled")
}

pub fn disabled_path() -> PathBuf {
    disabled_beside(&db_path())
}

pub fn is_on() -> bool {
    !disabled_path().exists()
}

pub fn set_on(on: bool) -> std::io::Result<()> {
    let p = disabled_path();
    if on {
        if p.exists() {
            std::fs::remove_file(p)?;
        }
    } else {
        if let Some(dir) = p.parent() {
            std::fs::create_dir_all(dir)?;
        }
        std::fs::write(p, b"off\n")?;
    }
    Ok(())
}

pub fn agent_id() -> Option<String> {
    std::env::var("TETHER_AGENT_ID")
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

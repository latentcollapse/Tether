//! One-shot worker spawn. Not a TUI injector.

use std::fs::{self, OpenOptions};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use crate::paths::{data_dir, db_path};
use crate::Result;

pub fn hook_dir() -> PathBuf {
    if let Ok(p) = std::env::var("TETHER_WAKE_DIR") {
        return PathBuf::from(p);
    }
    config_dir().join("wake")
}

fn config_dir() -> PathBuf {
    if let Ok(p) = std::env::var("TETHER_CONFIG") {
        return PathBuf::from(p);
    }
    let base = std::env::var("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| crate::paths::home().join(".config"));
    base.join("tether")
}

fn pid_path(agent: &str) -> PathBuf {
    data_dir().join("wake").join(format!("{agent}.pid"))
}

fn log_path(agent: &str) -> PathBuf {
    data_dir().join("wake").join(format!("{agent}.log"))
}

fn hook_path(agent: &str) -> Option<PathBuf> {
    let p = hook_dir().join(agent);
    if p.is_file() {
        Some(p)
    } else {
        None
    }
}

#[cfg(unix)]
fn is_exec(p: &Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    p.metadata()
        .map(|m| m.permissions().mode() & 0o111 != 0)
        .unwrap_or(false)
}

#[cfg(not(unix))]
fn is_exec(p: &Path) -> bool {
    p.is_file()
}

fn pid_alive(pid: u32) -> bool {
    Path::new(&format!("/proc/{pid}")).exists()
}

fn running(agent: &str) -> bool {
    let p = pid_path(agent);
    let Ok(text) = fs::read_to_string(&p) else {
        return false;
    };
    let Ok(pid) = text.trim().parse::<u32>() else {
        let _ = fs::remove_file(&p);
        return false;
    };
    if pid_alive(pid) {
        true
    } else {
        let _ = fs::remove_file(&p);
        false
    }
}

/// After a successful send: spawn the recipient hook if present and idle.
/// Failures are for the caller to print; the row is already stored.
pub fn nudge(agent: &str, msg_id: &str) -> Result<()> {
    if agent == "*" {
        return Ok(());
    }
    let Some(hook) = hook_path(agent) else {
        return Ok(());
    };
    if !is_exec(&hook) {
        return Ok(());
    }
    if running(agent) {
        return Ok(());
    }
    spawn(&hook, agent, msg_id)
}

fn spawn(hook: &Path, agent: &str, msg_id: &str) -> Result<()> {
    let dir = data_dir().join("wake");
    fs::create_dir_all(&dir)?;
    let log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path(agent))?;
    let err = log.try_clone()?;
    let mut cmd = Command::new(hook);
    cmd.arg(msg_id)
        .env("TETHER_AGENT_ID", agent)
        .env("TETHER_DB", db_path())
        .env("TETHER_HOME", data_dir())
        .env("TETHER_MSG_ID", msg_id)
        .stdin(Stdio::null())
        .stdout(Stdio::from(log))
        .stderr(Stdio::from(err));
    #[cfg(unix)]
    unsafe {
        use std::os::unix::process::CommandExt;
        cmd.pre_exec(|| {
            extern "C" {
                fn setsid() -> i32;
            }
            let _ = setsid();
            Ok(())
        });
    }
    let mut child = cmd.spawn()?;
    fs::write(pid_path(agent), format!("{}\n", child.id()))?;
    std::thread::spawn(move || {
        let _ = child.wait();
    });
    Ok(())
}

pub fn status_lines() -> Vec<String> {
    let dir = hook_dir();
    let Ok(entries) = fs::read_dir(&dir) else {
        return vec!["wake     (no hooks)".into()];
    };
    let mut lines = Vec::new();
    let mut names: Vec<_> = entries.filter_map(|e| e.ok()).collect();
    names.sort_by_key(|e| e.file_name());
    for e in names {
        let name = e.file_name();
        let name = name.to_string_lossy();
        if name.starts_with('.') {
            continue;
        }
        let p = e.path();
        if !p.is_file() || !is_exec(&p) {
            continue;
        }
        let state = if running(&name) { "running" } else { "idle" };
        lines.push(format!("wake     {name}  {state}"));
    }
    if lines.is_empty() {
        lines.push("wake     (no hooks)".into());
    }
    lines
}

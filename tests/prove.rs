//! Two processes, one file. This is the product.

use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};

use serde_json::{json, Value};

static N: AtomicU64 = AtomicU64::new(0);

struct Home {
    dir: PathBuf,
}

impl Home {
    fn new() -> Self {
        let n = N.fetch_add(1, Ordering::Relaxed);
        let dir = std::env::temp_dir().join(format!("tether-prove-{}-{n}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        Self { dir }
    }

    fn db(&self) -> PathBuf {
        self.dir.join("mailbox.db")
    }

    fn cmd(&self, agent: &str) -> Command {
        let mut c = Command::new(env!("CARGO_BIN_EXE_tether"));
        c.env("TETHER_DB", self.db());
        c.env("TETHER_HOME", &self.dir);
        c.env("TETHER_WAKE_DIR", self.dir.join("hooks"));
        c.env("TETHER_AGENT_ID", agent);
        c
    }

    fn run(&self, agent: &str, args: &[&str]) -> (i32, String, String) {
        let out = self.cmd(agent).args(args).output().expect("spawn tether");
        (
            out.status.code().unwrap_or(255),
            String::from_utf8_lossy(&out.stdout).into_owned(),
            String::from_utf8_lossy(&out.stderr).into_owned(),
        )
    }
}

impl Drop for Home {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

struct Mcp {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<std::process::ChildStdout>,
}

impl Mcp {
    fn spawn(home: &Home, agent: &str) -> Self {
        let mut child = home
            .cmd(agent)
            .arg("mcp")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("spawn tether mcp");
        let stdin = child.stdin.take().unwrap();
        let stdout = BufReader::new(child.stdout.take().unwrap());
        Self {
            child,
            stdin,
            stdout,
        }
    }

    fn rpc(&mut self, req: Value) -> Value {
        writeln!(self.stdin, "{req}").unwrap();
        self.stdin.flush().unwrap();
        let mut line = String::new();
        self.stdout.read_line(&mut line).expect("mcp stdout");
        serde_json::from_str(line.trim()).unwrap_or_else(|_| json!({"raw": line}))
    }
}

impl Drop for Mcp {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

#[test]
fn cli_grok_sends_claude_receives() {
    let home = Home::new();
    let (code, id, err) = home.run("grok", &["send", "claude", "drill", "can you see this"]);
    assert_eq!(code, 0, "{err}");
    let id = id.trim().to_string();
    assert!(!id.is_empty());

    let (code, inbox, err) = home.run("claude", &["inbox"]);
    assert_eq!(code, 0, "{err}");
    assert!(inbox.contains(&id), "{inbox}");
    assert!(inbox.contains("drill"), "{inbox}");

    let (code, body, err) = home.run("claude", &["recv", "grok"]);
    assert_eq!(code, 0, "{err}");
    assert!(body.contains("can you see this"), "{body}");
    assert!(body.contains(&id), "{body}");

    let (code, inbox, err) = home.run("claude", &["inbox"]);
    assert_eq!(code, 0, "{err}");
    assert!(inbox.contains("(empty)"), "{inbox}");
}

#[test]
fn recv_with_no_id_pops_oldest() {
    let home = Home::new();
    home.run("grok", &["send", "claude", "first", "one"]);
    home.run("grok", &["send", "claude", "second", "two"]);
    let (code, body, err) = home.run("claude", &["recv"]);
    assert_eq!(code, 0, "{err}");
    assert!(body.contains("first"), "{body}");
    assert!(!body.contains("second"), "{body}");
}

#[test]
fn identical_cli_sends_are_two_rows() {
    let home = Home::new();
    let (_, a, _) = home.run("grok", &["send", "claude", "hi", "same"]);
    let (_, b, _) = home.run("grok", &["send", "claude", "hi", "same"]);
    assert_ne!(a.trim(), b.trim());
    let (_, inbox, _) = home.run("claude", &["inbox"]);
    assert_eq!(inbox.lines().count(), 2, "{inbox}");
}

#[test]
fn off_fails_closed() {
    let home = Home::new();
    let (code, _, err) = home.run("grok", &["off"]);
    assert_eq!(code, 0, "{err}");
    let (code, _, err) = home.run("grok", &["send", "claude", "nope", "must fail"]);
    assert_eq!(code, 2, "{err}");
    assert!(err.contains("tether is off"), "{err}");
    let (code, _, err) = home.run("grok", &["on"]);
    assert_eq!(code, 0, "{err}");
    let (code, _, err) = home.run("grok", &["send", "claude", "ok", "back"]);
    assert_eq!(code, 0, "{err}");
}

#[test]
fn two_writers_one_db() {
    let home = Home::new();
    tether::Mailbox::open(&home.db()).unwrap();
    let db = home.db();
    let bin = env!("CARGO_BIN_EXE_tether");
    let grok = std::thread::spawn({
        let db = db.clone();
        move || writer(bin, &db, "grok", "claude", 20)
    });
    let claude = std::thread::spawn({
        let db = db.clone();
        move || writer(bin, &db, "claude", "grok", 20)
    });
    grok.join().unwrap();
    claude.join().unwrap();
    let (_, status, err) = home.run("grok", &["status"]);
    assert!(err.is_empty() || !status.is_empty(), "{err}");
    assert!(
        status.contains("messages  40"),
        "expected 40 messages:\n{status}"
    );
}

fn writer(bin: &str, db: &Path, from: &str, to: &str, n: usize) {
    for i in 0..n {
        let home = db.parent().unwrap();
        let out = Command::new(bin)
            .args(["send", to, "load", &format!("{from}-{i}")])
            .env("TETHER_DB", db)
            .env("TETHER_HOME", home)
            .env("TETHER_WAKE_DIR", home.join("hooks"))
            .env("TETHER_AGENT_ID", from)
            .output()
            .unwrap();
        assert!(
            out.status.success(),
            "{from} send {i}: {}",
            String::from_utf8_lossy(&out.stderr)
        );
    }
}

#[test]
fn mcp_stdio_two_agents() {
    let home = Home::new();
    let mut grok = Mcp::spawn(&home, "grok");
    let init = grok.rpc(json!({
        "jsonrpc":"2.0","id":1,"method":"initialize",
        "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"prove","version":"0"}}
    }));
    assert_eq!(init["result"]["serverInfo"]["name"], "tether");

    let listed = grok.rpc(json!({"jsonrpc":"2.0","id":2,"method":"tools/list"}));
    let names: Vec<&str> = listed["result"]["tools"]
        .as_array()
        .unwrap()
        .iter()
        .map(|t| t["name"].as_str().unwrap())
        .collect();
    assert_eq!(
        names,
        [
            "tether_send",
            "tether_inbox",
            "tether_recv",
            "tether_ack",
            "tether_who"
        ]
    );

    let sent = grok.rpc(json!({
        "jsonrpc":"2.0","id":3,"method":"tools/call",
        "params":{"name":"tether_send","arguments":{"to":"claude","subject":"mcp","text":"hello from grok"}}
    }));
    assert_eq!(sent["result"]["isError"], false, "{sent}");

    let mut claude = Mcp::spawn(&home, "claude");
    let inbox = claude.rpc(json!({
        "jsonrpc":"2.0","id":1,"method":"tools/call",
        "params":{"name":"tether_inbox","arguments":{}}
    }));
    let text = inbox["result"]["content"][0]["text"].as_str().unwrap();
    assert!(text.contains("hello from grok"), "{text}");
}

#[test]
fn wake_hook_runs_on_send() {
    let home = Home::new();
    let hooks = home.dir.join("hooks");
    std::fs::create_dir_all(&hooks).unwrap();
    let hook = hooks.join("claude");
    std::fs::write(
        &hook,
        "#!/bin/sh\nprintf '%s\\n' \"$TETHER_MSG_ID\" >> \"$TETHER_HOME/woke\"\n",
    )
    .unwrap();
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&hook, std::fs::Permissions::from_mode(0o755)).unwrap();
    }
    let (code, id, err) = home.run("grok", &["send", "claude", "wake", "go"]);
    assert_eq!(code, 0, "{err}");
    let id = id.trim().to_string();
    let woke = home.dir.join("woke");
    let mut ok = false;
    for _ in 0..50 {
        if std::fs::read_to_string(&woke)
            .map(|s| s.contains(&id))
            .unwrap_or(false)
        {
            ok = true;
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(20));
    }
    assert!(ok, "hook did not run for {id}; stderr={err}");
}

#[test]
fn recv_wait_sees_late_send() {
    let home = Home::new();
    let db = home.db();
    let bin = env!("CARGO_BIN_EXE_tether");
    let sender = std::thread::spawn({
        let db = db.clone();
        move || {
            std::thread::sleep(std::time::Duration::from_millis(200));
            Command::new(bin)
                .args(["send", "claude", "late", "hello"])
                .env("TETHER_DB", &db)
                .env("TETHER_HOME", db.parent().unwrap())
                .env("TETHER_WAKE_DIR", db.parent().unwrap().join("hooks"))
                .env("TETHER_AGENT_ID", "grok")
                .output()
                .unwrap()
        }
    });
    let (code, body, err) = home.run("claude", &["recv", "--wait", "--timeout", "3"]);
    sender.join().unwrap();
    assert_eq!(code, 0, "{err}");
    assert!(body.contains("hello"), "{body}");
}

#[test]
fn simplicity_budget() {
    let toml = std::fs::read_to_string(manifest_dir().join("Cargo.toml")).unwrap();
    let rest = toml.split("[dependencies]").nth(1).unwrap_or("");
    let section = rest.split("\n[").next().unwrap_or(rest);
    let deps: Vec<&str> = section
        .lines()
        .filter_map(|l| {
            let l = l.trim();
            if l.is_empty() || l.starts_with('#') {
                return None;
            }
            l.split('=').next().map(str::trim)
        })
        .filter(|s| !s.is_empty())
        .collect();
    assert_eq!(deps, ["rusqlite", "serde", "serde_json"], "{deps:?}");

    let loc = production_loc(&manifest_dir().join("src"));
    assert!(
        loc <= 1500,
        "production src is {loc} lines; crate is getting heavy"
    );
}

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn production_loc(dir: &Path) -> usize {
    let mut n = 0;
    for p in std::fs::read_dir(dir).unwrap() {
        let p = p.unwrap().path();
        if p.extension().and_then(|s| s.to_str()) != Some("rs") {
            continue;
        }
        n += strip_test_modules(&std::fs::read_to_string(p).unwrap());
    }
    n
}

fn strip_test_modules(text: &str) -> usize {
    let lines: Vec<&str> = text.lines().collect();
    let mut i = 0;
    let mut n = 0;
    while i < lines.len() {
        if lines[i].contains("#[cfg(test)]") {
            let mut j = i;
            while j < lines.len()
                && (lines[j].trim().starts_with('#') || lines[j].trim().is_empty())
            {
                j += 1;
            }
            if j < lines.len() && lines[j].trim_start().starts_with("mod tests") {
                let mut k = j;
                let mut depth = 0;
                let mut started = false;
                while k < lines.len() {
                    depth += lines[k].chars().filter(|c| *c == '{').count() as i32;
                    depth -= lines[k].chars().filter(|c| *c == '}').count() as i32;
                    if lines[k].contains('{') {
                        started = true;
                    }
                    k += 1;
                    if started && depth == 0 {
                        break;
                    }
                }
                i = k;
                continue;
            }
        }
        n += 1;
        i += 1;
    }
    n
}

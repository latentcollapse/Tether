use std::path::{Path, PathBuf};

use rusqlite::{params, Connection, ErrorCode, OptionalExtension};

use crate::stamp::{fmt_ts, new_id, now_ms};
use crate::{Error, Result};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Message {
    pub id: String,
    pub ts: i64,
    pub from: String,
    pub to: String,
    pub thread: Option<String>,
    pub subject: String,
    pub body: String,
}

impl Message {
    pub fn when(&self) -> String {
        fmt_ts(self.ts)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Who {
    pub name: String,
    pub last_ts: i64,
    pub unread: i64,
}

impl Who {
    pub fn last(&self) -> String {
        fmt_ts(self.last_ts)
    }
}

pub struct Mailbox {
    conn: Connection,
    path: PathBuf,
}

impl Mailbox {
    pub fn open(path: &Path) -> Result<Self> {
        if let Some(dir) = path.parent() {
            if !dir.as_os_str().is_empty() {
                std::fs::create_dir_all(dir)?;
            }
        }
        with_retry(|| Self::connect(path))
    }

    fn connect(path: &Path) -> Result<Self> {
        let conn = Connection::open(path)?;
        conn.busy_timeout(std::time::Duration::from_secs(5))?;
        conn.pragma_update(None, "journal_mode", "WAL")?;
        conn.pragma_update(None, "synchronous", "NORMAL")?;
        conn.pragma_update(None, "foreign_keys", "ON")?;
        conn.execute_batch(
            "
            CREATE TABLE IF NOT EXISTS messages (
                id         TEXT PRIMARY KEY,
                ts         INTEGER NOT NULL,
                from_agent TEXT NOT NULL,
                to_agent   TEXT NOT NULL,
                thread     TEXT,
                subject    TEXT NOT NULL,
                body       TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS acks (
                id       TEXT NOT NULL,
                agent    TEXT NOT NULL,
                acked_at INTEGER NOT NULL,
                PRIMARY KEY (id, agent)
            );
            CREATE INDEX IF NOT EXISTS messages_to_ts ON messages(to_agent, ts);
            CREATE INDEX IF NOT EXISTS messages_ts ON messages(ts);
            ",
        )?;
        Ok(Mailbox {
            conn,
            path: path.to_path_buf(),
        })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn is_on(&self) -> bool {
        !crate::paths::disabled_beside(&self.path).exists()
    }

    pub fn require_on(&self) -> Result<()> {
        if self.is_on() {
            Ok(())
        } else {
            Err(Error::Off)
        }
    }

    pub fn send(
        &self,
        from: &str,
        to: &str,
        subject: &str,
        body: &str,
        thread: Option<&str>,
    ) -> Result<String> {
        let from = normalize_agent(from)?;
        let to = normalize_to(to)?;
        let subject = subject.trim();
        if subject.is_empty() {
            return Err(Error::Usage("subject is empty".into()));
        }
        let thread = thread.map(str::trim).filter(|s| !s.is_empty());
        let id = new_id();
        let ts = now_ms();
        with_retry(|| {
            self.conn.execute(
                "INSERT INTO messages (id, ts, from_agent, to_agent, thread, subject, body)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
                params![id, ts, from, to, thread, subject, body],
            )?;
            Ok(())
        })?;
        Ok(id)
    }

    pub fn inbox(&self, agent: &str, include_acked: bool) -> Result<Vec<Message>> {
        let agent = normalize_agent(agent)?;
        let mut stmt = self.conn.prepare(
            "SELECT m.id, m.ts, m.from_agent, m.to_agent, m.thread, m.subject, m.body
             FROM messages m
             WHERE (m.to_agent = ?1 OR (m.to_agent = '*' AND m.from_agent != ?1))
               AND (?2 OR NOT EXISTS (
                    SELECT 1 FROM acks a WHERE a.id = m.id AND a.agent = ?1
               ))
             ORDER BY m.ts ASC",
        )?;
        let rows = stmt.query_map(params![agent, include_acked], row_message)?;
        rows.collect::<std::result::Result<Vec<_>, _>>()
            .map_err(Error::from)
    }

    pub fn get(&self, id: &str) -> Result<Message> {
        self.conn
            .query_row(
                "SELECT id, ts, from_agent, to_agent, thread, subject, body
                 FROM messages WHERE id = ?1",
                [id],
                row_message,
            )
            .optional()?
            .ok_or_else(|| Error::Missing(id.to_string()))
    }

    pub fn ack(&self, id: &str, agent: &str) -> Result<()> {
        let agent = normalize_agent(agent)?;
        let _ = self.get(id)?;
        with_retry(|| {
            self.conn.execute(
                "INSERT OR IGNORE INTO acks (id, agent, acked_at) VALUES (?1, ?2, ?3)",
                params![id, agent, now_ms()],
            )?;
            Ok(())
        })?;
        Ok(())
    }

    pub fn recv(&self, id: &str, agent: &str) -> Result<Message> {
        let msg = self.get(id)?;
        self.ack(id, agent)?;
        Ok(msg)
    }

    /// Unread for `agent`. `from` None → the oldest one. `from` Some → all from that sender, oldest first.
    pub fn recv_unread(&self, agent: &str, from: Option<&str>) -> Result<Vec<Message>> {
        let mut msgs = self.inbox(agent, false)?;
        if let Some(from) = from {
            let from = normalize_agent(from)?;
            msgs.retain(|m| m.from == from);
            if msgs.is_empty() {
                return Err(Error::NoUnread(Some(from)));
            }
        } else {
            msgs.truncate(1);
            if msgs.is_empty() {
                return Err(Error::NoUnread(None));
            }
        }
        for m in &msgs {
            self.ack(&m.id, agent)?;
        }
        Ok(msgs)
    }

    pub fn recv_unread_wait(
        &self,
        agent: &str,
        from: Option<&str>,
        timeout: std::time::Duration,
    ) -> Result<Vec<Message>> {
        let start = std::time::Instant::now();
        loop {
            match self.recv_unread(agent, from) {
                Ok(m) => return Ok(m),
                Err(Error::NoUnread(_)) if start.elapsed() < timeout => {
                    std::thread::sleep(std::time::Duration::from_millis(100));
                }
                Err(Error::NoUnread(_)) => return Err(Error::WaitTimeout),
                Err(e) => return Err(e),
            }
        }
    }

    pub fn looks_like_id(s: &str) -> bool {
        s.len() == 24 && s.bytes().all(|b| b.is_ascii_hexdigit())
    }

    pub fn who(&self) -> Result<Vec<Who>> {
        let mut stmt = self.conn.prepare(
            "WITH agents AS (
                SELECT from_agent AS name FROM messages
                UNION
                SELECT to_agent FROM messages WHERE to_agent != '*'
             )
             SELECT a.name,
                    (SELECT MAX(ts) FROM messages m
                      WHERE m.from_agent = a.name OR m.to_agent = a.name) AS last_ts,
                    (SELECT COUNT(*) FROM messages m
                      WHERE (m.to_agent = a.name OR (m.to_agent = '*' AND m.from_agent != a.name))
                        AND NOT EXISTS (
                            SELECT 1 FROM acks x WHERE x.id = m.id AND x.agent = a.name
                        )) AS unread
             FROM agents a
             ORDER BY last_ts DESC",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok(Who {
                name: row.get(0)?,
                last_ts: row.get(1)?,
                unread: row.get(2)?,
            })
        })?;
        rows.collect::<std::result::Result<Vec<_>, _>>()
            .map_err(Error::from)
    }

    pub fn count(&self) -> Result<i64> {
        Ok(self
            .conn
            .query_row("SELECT COUNT(*) FROM messages", [], |r| r.get(0))?)
    }
}

fn locked(e: &rusqlite::Error) -> bool {
    matches!(
        e,
        rusqlite::Error::SqliteFailure(f, _)
            if matches!(f.code, ErrorCode::DatabaseBusy | ErrorCode::DatabaseLocked)
    )
}

fn with_retry<T>(mut f: impl FnMut() -> Result<T>) -> Result<T> {
    let mut last = None;
    for attempt in 0..40 {
        match f() {
            Ok(v) => return Ok(v),
            Err(Error::Db(e)) if locked(&e) && attempt < 39 => {
                last = Some(e);
                std::thread::sleep(std::time::Duration::from_millis(25));
            }
            Err(e) => return Err(e),
        }
    }
    Err(Error::Db(last.expect("retry")))
}

fn row_message(row: &rusqlite::Row<'_>) -> rusqlite::Result<Message> {
    Ok(Message {
        id: row.get(0)?,
        ts: row.get(1)?,
        from: row.get(2)?,
        to: row.get(3)?,
        thread: row.get(4)?,
        subject: row.get(5)?,
        body: row.get(6)?,
    })
}

fn normalize_agent(name: &str) -> Result<String> {
    let name = name.trim();
    if name.is_empty() {
        return Err(Error::MissingAgent);
    }
    if name == "*" {
        return Err(Error::Usage("agent name cannot be *".into()));
    }
    if name.len() > 64 || name.chars().any(|c| c.is_control() || c.is_whitespace()) {
        return Err(Error::Usage(format!("bad agent name {name:?}")));
    }
    Ok(name.to_string())
}

fn normalize_to(name: &str) -> Result<String> {
    let name = name.trim();
    if name == "*" {
        return Ok("*".into());
    }
    normalize_agent(name)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    static N: AtomicU64 = AtomicU64::new(0);

    fn tmp() -> std::path::PathBuf {
        let n = N.fetch_add(1, Ordering::Relaxed);
        let dir = std::env::temp_dir().join(format!("tether-mb-{}-{n}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::create_dir_all(&dir);
        dir.join("mailbox.db")
    }

    fn clean(p: &Path) {
        if let Some(dir) = p.parent() {
            let _ = std::fs::remove_dir_all(dir);
        }
    }

    #[test]
    fn send_inbox_recv() {
        let p = tmp();
        let mb = Mailbox::open(&p).unwrap();
        let id = mb
            .send("grok", "claude", "hi", "mailbox is up", None)
            .unwrap();
        let box_c = mb.inbox("claude", false).unwrap();
        assert_eq!(box_c.len(), 1);
        assert_eq!(box_c[0].id, id);
        assert!(mb.inbox("grok", false).unwrap().is_empty());
        let got = mb.recv(&id, "claude").unwrap();
        assert_eq!(got.body, "mailbox is up");
        assert!(mb.inbox("claude", false).unwrap().is_empty());
        assert_eq!(mb.inbox("claude", true).unwrap().len(), 1);
        clean(&p);
    }

    #[test]
    fn recv_unread_next_and_from() {
        let p = tmp();
        let mb = Mailbox::open(&p).unwrap();
        mb.send("grok", "matt", "one", "a", None).unwrap();
        mb.send("claude", "matt", "two", "b", None).unwrap();
        mb.send("grok", "matt", "three", "c", None).unwrap();
        let next = mb.recv_unread("matt", None).unwrap();
        assert_eq!(next.len(), 1);
        assert_eq!(next[0].from, "grok");
        assert_eq!(next[0].subject, "one");
        let from_grok = mb.recv_unread("matt", Some("grok")).unwrap();
        assert_eq!(from_grok.len(), 1);
        assert_eq!(from_grok[0].subject, "three");
        assert_eq!(mb.inbox("matt", false).unwrap().len(), 1);
        assert_eq!(mb.inbox("matt", false).unwrap()[0].from, "claude");
        clean(&p);
    }

    #[test]
    fn recv_wait_times_out() {
        let p = tmp();
        let mb = Mailbox::open(&p).unwrap();
        let err = mb
            .recv_unread_wait("matt", None, std::time::Duration::from_millis(50))
            .unwrap_err();
        assert!(matches!(err, Error::WaitTimeout));
        clean(&p);
    }

    #[test]
    fn duplicate_body_is_two_messages() {
        let p = tmp();
        let mb = Mailbox::open(&p).unwrap();
        let a = mb.send("grok", "claude", "hi", "same", None).unwrap();
        let b = mb.send("grok", "claude", "hi", "same", None).unwrap();
        assert_ne!(a, b);
        assert_eq!(mb.inbox("claude", false).unwrap().len(), 2);
        clean(&p);
    }

    #[test]
    fn broadcast_acks_are_per_agent() {
        let p = tmp();
        let mb = Mailbox::open(&p).unwrap();
        let id = mb.send("grok", "*", "standup", "go", None).unwrap();
        assert_eq!(mb.inbox("claude", false).unwrap().len(), 1);
        assert_eq!(mb.inbox("gemini", false).unwrap().len(), 1);
        mb.ack(&id, "claude").unwrap();
        assert!(mb.inbox("claude", false).unwrap().is_empty());
        assert_eq!(mb.inbox("gemini", false).unwrap().len(), 1);
        clean(&p);
    }

    #[test]
    fn who_counts_unread() {
        let p = tmp();
        let mb = Mailbox::open(&p).unwrap();
        mb.send("grok", "claude", "a", "1", None).unwrap();
        mb.send("claude", "grok", "b", "2", None).unwrap();
        let who = mb.who().unwrap();
        let claude = who.iter().find(|w| w.name == "claude").unwrap();
        assert_eq!(claude.unread, 1);
        clean(&p);
    }

    #[test]
    fn sender_does_not_inbox_own_broadcast() {
        let p = tmp();
        let mb = Mailbox::open(&p).unwrap();
        mb.send("grok", "*", "standup", "go", None).unwrap();
        assert!(mb.inbox("grok", false).unwrap().is_empty());
        assert_eq!(mb.inbox("claude", false).unwrap().len(), 1);
        clean(&p);
    }

    #[test]
    fn off_sentinel_is_beside_this_db() {
        let p = tmp();
        let mb = Mailbox::open(&p).unwrap();
        assert!(mb.is_on());
        std::fs::write(crate::paths::disabled_beside(&p), b"off\n").unwrap();
        assert!(!mb.is_on());
        assert!(matches!(mb.require_on(), Err(Error::Off)));
        let _ = std::fs::remove_file(crate::paths::disabled_beside(&p));
        clean(&p);
    }
}

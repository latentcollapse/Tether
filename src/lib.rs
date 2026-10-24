//! Local mailbox. SQLite is the bus.

mod mailbox;
mod mcp;
mod paths;
mod stamp;
mod wake;

pub use mailbox::{Mailbox, Message, Who};
pub use mcp::serve_mcp;
pub use paths::{agent_id, db_path, is_on, set_on};
pub use wake::{nudge, status_lines as wake_status};

use std::fmt;
use std::io;
use std::path::PathBuf;

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug)]
pub enum Error {
    Off,
    Usage(String),
    MissingAgent,
    Missing(String),
    NoUnread(Option<String>),
    WaitTimeout,
    Db(rusqlite::Error),
    Io(io::Error),
    Json(serde_json::Error),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Off => write!(f, "tether is off"),
            Error::Usage(s) => write!(f, "{s}"),
            Error::MissingAgent => {
                write!(f, "no agent name: set TETHER_AGENT_ID or pass --from")
            }
            Error::Missing(id) => write!(f, "no message {id}"),
            Error::NoUnread(None) => write!(f, "no unread"),
            Error::NoUnread(Some(from)) => write!(f, "no unread from {from}"),
            Error::WaitTimeout => write!(f, "wait timed out"),
            Error::Db(e) => write!(f, "{e}"),
            Error::Io(e) => write!(f, "{e}"),
            Error::Json(e) => write!(f, "{e}"),
        }
    }
}

impl std::error::Error for Error {}

impl From<rusqlite::Error> for Error {
    fn from(e: rusqlite::Error) -> Self {
        Error::Db(e)
    }
}

impl From<io::Error> for Error {
    fn from(e: io::Error) -> Self {
        Error::Io(e)
    }
}

impl From<serde_json::Error> for Error {
    fn from(e: serde_json::Error) -> Self {
        Error::Json(e)
    }
}

/// Fail if the sentinel file is present.
pub fn require_on() -> Result<()> {
    if is_on() {
        Ok(())
    } else {
        Err(Error::Off)
    }
}

pub fn open_default() -> Result<Mailbox> {
    Mailbox::open(&db_path())
}

pub fn default_db() -> PathBuf {
    db_path()
}

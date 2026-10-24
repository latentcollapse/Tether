use std::io::{self, BufRead, Write};

use serde_json::{json, Value};

use crate::mailbox::Mailbox;
use crate::paths::agent_id;
use crate::{Error, Result};

const VERSION: &str = env!("CARGO_PKG_VERSION");

pub fn serve_mcp(mb: &Mailbox) -> Result<()> {
    let stdin = io::stdin();
    let mut stdin = stdin.lock();
    let mut stdout = io::stdout().lock();
    let default_agent = agent_id();
    while let Some(req) = read_message(&mut stdin)? {
        if req.get("method").and_then(Value::as_str) == Some("notifications/initialized") {
            continue;
        }
        let resp = dispatch(mb, default_agent.as_deref(), req);
        writeln!(stdout, "{resp}")?;
        stdout.flush()?;
    }
    Ok(())
}

fn read_message(stdin: &mut impl BufRead) -> io::Result<Option<Value>> {
    let mut first = String::new();
    if stdin.read_line(&mut first)? == 0 {
        return Ok(None);
    }
    if first.to_ascii_lowercase().starts_with("content-length:") {
        let len: usize = first
            .split(':')
            .nth(1)
            .unwrap_or("0")
            .trim()
            .parse()
            .unwrap_or(0);
        let mut line = String::new();
        while stdin.read_line(&mut line)? > 0 {
            if line.trim().is_empty() {
                break;
            }
            line.clear();
        }
        let mut buf = vec![0u8; len];
        stdin.read_exact(&mut buf)?;
        return Ok(serde_json::from_slice(&buf).ok());
    }
    let t = first.trim();
    if t.is_empty() {
        return read_message(stdin);
    }
    Ok(serde_json::from_str(t).ok())
}

pub fn dispatch(mb: &Mailbox, default_agent: Option<&str>, req: Value) -> Value {
    let id = req.get("id").cloned().unwrap_or(Value::Null);
    if id.is_null() {
        return json!({"jsonrpc":"2.0","id":null,"result":{}});
    }
    let method = req.get("method").and_then(Value::as_str).unwrap_or("");
    let params = req.get("params").cloned().unwrap_or(json!({}));
    match method {
        "initialize" => result(id, initialize(&params)),
        "ping" => result(id, json!({})),
        "tools/list" => result(id, json!({"tools": tools()})),
        "tools/call" => match tools_call(mb, default_agent, &params) {
            Ok(v) => result(id, v),
            Err(e) => result(
                id,
                json!({"content":[{"type":"text","text":e.to_string()}],"isError":true}),
            ),
        },
        _ => json!({
            "jsonrpc":"2.0",
            "id": id,
            "error": {"code": -32601, "message": format!("unknown method {method}")}
        }),
    }
}

fn result(id: Value, value: Value) -> Value {
    json!({"jsonrpc":"2.0","id":id,"result":value})
}

fn initialize(params: &Value) -> Value {
    let ver = params
        .get("protocolVersion")
        .and_then(Value::as_str)
        .unwrap_or("2024-11-05");
    json!({
        "protocolVersion": ver,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "tether", "version": VERSION}
    })
}

fn tools() -> Vec<Value> {
    vec![
        tool(
            "tether_send",
            "Send a message to another agent (or * for everyone).",
            json!({
                "type":"object",
                "properties":{
                    "to":{"type":"string","description":"Recipient agent name, or *"},
                    "subject":{"type":"string"},
                    "text":{"type":"string","description":"Message body"},
                    "thread":{"type":"string"},
                    "from_agent":{"type":"string","description":"Override TETHER_AGENT_ID"}
                },
                "required":["to","subject","text"]
            }),
        ),
        tool(
            "tether_inbox",
            "Unread messages for an agent. Pass include_acked to see history.",
            json!({
                "type":"object",
                "properties":{
                    "for_agent":{"type":"string"},
                    "include_acked":{"type":"boolean","default":false}
                }
            }),
        ),
        tool(
            "tether_recv",
            "Read unread mail and mark it acked. No args: oldest unread. from: all unread from that agent. id: one message. wait_ms: poll until mail or timeout.",
            json!({
                "type":"object",
                "properties":{
                    "id":{"type":"string"},
                    "from":{"type":"string","description":"Sender to read unread from"},
                    "wait_ms":{"type":"integer","description":"Poll for unread this many milliseconds"},
                    "for_agent":{"type":"string"}
                }
            }),
        ),
        tool(
            "tether_ack",
            "Mark a message acked without returning the body.",
            json!({
                "type":"object",
                "properties":{
                    "id":{"type":"string"},
                    "for_agent":{"type":"string"}
                },
                "required":["id"]
            }),
        ),
        tool(
            "tether_who",
            "Agents seen on this mailbox, with unread counts.",
            json!({"type":"object","properties":{}}),
        ),
    ]
}

fn tool(name: &str, description: &str, schema: Value) -> Value {
    json!({
        "name": name,
        "description": description,
        "inputSchema": schema
    })
}

fn tools_call(mb: &Mailbox, default_agent: Option<&str>, params: &Value) -> Result<Value> {
    mb.require_on()?;
    let name = params.get("name").and_then(Value::as_str).unwrap_or("");
    let args = params.get("arguments").cloned().unwrap_or(json!({}));
    let text = match name {
        "tether_send" => {
            let from = arg_str(&args, "from_agent")
                .or_else(|| default_agent.map(str::to_string))
                .ok_or(Error::MissingAgent)?;
            let to = req_str(&args, "to")?;
            let subject = req_str(&args, "subject")?;
            let body = req_str(&args, "text")?;
            let thread = arg_str(&args, "thread");
            let id = mb.send(&from, &to, &subject, &body, thread.as_deref())?;
            if let Err(e) = crate::nudge(&to, &id) {
                eprintln!("wake {to}: {e}");
            }
            format!("sent {id}")
        }
        "tether_inbox" => {
            let agent = arg_str(&args, "for_agent")
                .or_else(|| default_agent.map(str::to_string))
                .ok_or(Error::MissingAgent)?;
            let include = args
                .get("include_acked")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            let msgs = mb.inbox(&agent, include)?;
            serde_json::to_string_pretty(&msgs_json(&msgs))?
        }
        "tether_recv" => {
            let agent = arg_str(&args, "for_agent")
                .or_else(|| default_agent.map(str::to_string))
                .ok_or(Error::MissingAgent)?;
            if let Some(id) = arg_str(&args, "id") {
                serde_json::to_string_pretty(&msg_json(&mb.recv(&id, &agent)?))?
            } else {
                let from = arg_str(&args, "from");
                let wait_ms = args.get("wait_ms").and_then(Value::as_u64);
                let msgs = if let Some(ms) = wait_ms {
                    mb.recv_unread_wait(
                        &agent,
                        from.as_deref(),
                        std::time::Duration::from_millis(ms),
                    )?
                } else {
                    mb.recv_unread(&agent, from.as_deref())?
                };
                serde_json::to_string_pretty(&msgs_json(&msgs))?
            }
        }
        "tether_ack" => {
            let agent = arg_str(&args, "for_agent")
                .or_else(|| default_agent.map(str::to_string))
                .ok_or(Error::MissingAgent)?;
            let id = req_str(&args, "id")?;
            mb.ack(&id, &agent)?;
            format!("acked {id}")
        }
        "tether_who" => serde_json::to_string_pretty(&who_json(&mb.who()?))?,
        other => return Err(Error::Usage(format!("unknown tool {other}"))),
    };
    Ok(json!({"content":[{"type":"text","text":text}],"isError":false}))
}

fn req_str(args: &Value, key: &str) -> Result<String> {
    arg_str(args, key).ok_or_else(|| Error::Usage(format!("missing {key}")))
}

fn arg_str(args: &Value, key: &str) -> Option<String> {
    args.get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

fn msg_json(m: &crate::Message) -> Value {
    json!({
        "id": m.id,
        "ts": m.when(),
        "from": m.from,
        "to": m.to,
        "thread": m.thread,
        "subject": m.subject,
        "body": m.body
    })
}

fn msgs_json(msgs: &[crate::Message]) -> Value {
    Value::Array(msgs.iter().map(msg_json).collect())
}

fn who_json(rows: &[crate::Who]) -> Value {
    Value::Array(
        rows.iter()
            .map(|w| {
                json!({
                    "name": w.name,
                    "last": w.last(),
                    "unread": w.unread
                })
            })
            .collect(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    static N: AtomicU64 = AtomicU64::new(0);

    fn mb() -> (Mailbox, std::path::PathBuf) {
        let n = N.fetch_add(1, Ordering::Relaxed);
        let dir = std::env::temp_dir().join(format!("tether-mcp-{}-{n}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let _ = std::fs::create_dir_all(&dir);
        let p = dir.join("mailbox.db");
        (Mailbox::open(&p).unwrap(), dir)
    }

    #[test]
    fn list_five_tools() {
        let (mb, p) = mb();
        let resp = dispatch(
            &mb,
            Some("grok"),
            json!({"jsonrpc":"2.0","id":1,"method":"tools/list"}),
        );
        let tools = resp["result"]["tools"].as_array().unwrap();
        assert_eq!(tools.len(), 5);
        let _ = std::fs::remove_dir_all(&p);
    }

    #[test]
    fn send_and_inbox_over_rpc() {
        let (mb, p) = mb();
        let send = dispatch(
            &mb,
            Some("grok"),
            json!({
                "jsonrpc":"2.0","id":1,"method":"tools/call",
                "params":{"name":"tether_send","arguments":{
                    "to":"claude","subject":"hi","text":"yo"
                }}
            }),
        );
        assert_eq!(send["result"]["isError"], false);
        let inbox = dispatch(
            &mb,
            Some("claude"),
            json!({
                "jsonrpc":"2.0","id":2,"method":"tools/call",
                "params":{"name":"tether_inbox","arguments":{}}
            }),
        );
        let text = inbox["result"]["content"][0]["text"].as_str().unwrap();
        assert!(text.contains("yo"), "{text}");
        let _ = std::fs::remove_dir_all(&p);
    }
}

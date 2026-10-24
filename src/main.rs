use std::env;
use std::io::{self, Write};
use std::process::ExitCode;

use tether::{
    agent_id, default_db, is_on, open_default, require_on, set_on, Mailbox, Message, Who,
};

fn main() -> ExitCode {
    match run(env::args().skip(1).collect()) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("{e}");
            ExitCode::from(if matches!(e, tether::Error::Off) {
                2
            } else {
                1
            })
        }
    }
}

fn run(mut args: Vec<String>) -> tether::Result<()> {
    if args.is_empty() {
        print_help();
        return Ok(());
    }
    let cmd = args.remove(0);
    match cmd.as_str() {
        "help" | "-h" | "--help" => print_help(),
        "version" | "-V" | "--version" => {
            println!("tether {}", env!("CARGO_PKG_VERSION"));
        }
        "on" => {
            set_on(true)?;
            println!("tether is on  {}", default_db().display());
        }
        "off" => {
            set_on(false)?;
            println!("tether is off");
        }
        "status" => status()?,
        "mcp" => {
            let mb = open_default()?;
            tether::serve_mcp(&mb)?;
        }
        "send" => send(args)?,
        "inbox" => inbox(args)?,
        "recv" => recv(args)?,
        "ack" => {
            require_on()?;
            let id = args
                .first()
                .ok_or_else(|| tether::Error::Usage("ack ID".into()))?;
            let agent = need_agent(None)?;
            open_default()?.ack(id, &agent)?;
            println!("acked {id}");
        }
        "who" => {
            require_on()?;
            print_who(&open_default()?.who()?);
        }
        other => {
            return Err(tether::Error::Usage(format!(
                "unknown command {other}. try tether help"
            )))
        }
    }
    Ok(())
}

fn send(args: Vec<String>) -> tether::Result<()> {
    require_on()?;
    let mut from = None;
    let mut thread = None;
    let rest = take_flags(&args, &mut from, &mut thread);
    if rest.len() < 2 {
        return Err(tether::Error::Usage(
            "send [--from NAME] [--thread T] TO SUBJECT [BODY...]".into(),
        ));
    }
    let to = &rest[0];
    let subject = &rest[1];
    let body = if rest.len() > 2 {
        rest[2..].join(" ")
    } else {
        String::new()
    };
    let from = need_agent(from.as_deref())?;
    let id = open_default()?.send(&from, to, subject, &body, thread.as_deref())?;
    if let Err(e) = tether::nudge(to, &id) {
        eprintln!("wake {to}: {e}");
    }
    println!("{id}");
    Ok(())
}

fn recv(mut args: Vec<String>) -> tether::Result<()> {
    require_on()?;
    let wait = pop_flag(&mut args, "--wait");
    let timeout = pop_opt(&mut args, "--timeout")
        .map(|s| s.parse::<u64>().unwrap_or(60))
        .unwrap_or(60);
    let me = need_agent(None)?;
    let mb = open_default()?;
    let dur = std::time::Duration::from_secs(timeout);
    let msgs = match args.first().map(String::as_str) {
        Some(s) if tether::Mailbox::looks_like_id(s) => vec![mb.recv(s, &me)?],
        Some(from) if wait => mb.recv_unread_wait(&me, Some(from), dur)?,
        Some(from) => mb.recv_unread(&me, Some(from))?,
        None if wait => mb.recv_unread_wait(&me, None, dur)?,
        None => mb.recv_unread(&me, None)?,
    };
    for (i, m) in msgs.iter().enumerate() {
        if i > 0 {
            println!("---");
        }
        print_message(m);
    }
    Ok(())
}

fn inbox(mut args: Vec<String>) -> tether::Result<()> {
    require_on()?;
    let include_acked = pop_flag(&mut args, "--all");
    let agent = if args.is_empty() {
        need_agent(None)?
    } else {
        args[0].clone()
    };
    let msgs = open_default()?.inbox(&agent, include_acked)?;
    if msgs.is_empty() {
        println!("(empty)");
        return Ok(());
    }
    for m in msgs {
        print_summary(&m);
    }
    Ok(())
}

fn status() -> tether::Result<()> {
    let db = default_db();
    let on = is_on();
    println!("tether {}", if on { "on" } else { "off" });
    println!("db      {}", db.display());
    if !on {
        return Ok(());
    }
    if !db.exists() {
        println!("messages  0  (no database yet)");
        return Ok(());
    }
    let mb = Mailbox::open(&db)?;
    println!("messages  {}", mb.count()?);
    print_who(&mb.who()?);
    for line in tether::wake_status() {
        println!("{line}");
    }
    Ok(())
}

fn take_flags(
    args: &[String],
    from: &mut Option<String>,
    thread: &mut Option<String>,
) -> Vec<String> {
    let mut rest = Vec::new();
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--from" if i + 1 < args.len() => {
                *from = Some(args[i + 1].clone());
                i += 2;
            }
            "--thread" if i + 1 < args.len() => {
                *thread = Some(args[i + 1].clone());
                i += 2;
            }
            s if s.starts_with("--from=") => {
                *from = Some(s[7..].to_string());
                i += 1;
            }
            s if s.starts_with("--thread=") => {
                *thread = Some(s[9..].to_string());
                i += 1;
            }
            _ => {
                rest.push(args[i].clone());
                i += 1;
            }
        }
    }
    rest
}

fn pop_flag(args: &mut Vec<String>, flag: &str) -> bool {
    let n = args.len();
    args.retain(|a| a != flag);
    args.len() != n
}

fn pop_opt(args: &mut Vec<String>, flag: &str) -> Option<String> {
    let eq = format!("{flag}=");
    if let Some(i) = args.iter().position(|a| a.starts_with(&eq)) {
        let v = args.remove(i)[eq.len()..].to_string();
        return Some(v);
    }
    if let Some(i) = args.iter().position(|a| a == flag) {
        args.remove(i);
        if i < args.len() {
            return Some(args.remove(i));
        }
    }
    None
}

fn need_agent(explicit: Option<&str>) -> tether::Result<String> {
    explicit
        .map(str::to_string)
        .or_else(agent_id)
        .ok_or(tether::Error::MissingAgent)
}

fn print_summary(m: &Message) {
    let thread = m
        .thread
        .as_deref()
        .map(|t| format!(" [{t}]"))
        .unwrap_or_default();
    println!(
        "{id}  {ts}  {from} → {to}{thread}  {subject}",
        id = m.id,
        ts = m.when(),
        from = m.from,
        to = m.to,
        subject = m.subject
    );
}

fn print_message(m: &Message) {
    println!("id       {}", m.id);
    println!("ts       {}", m.when());
    println!("from     {}", m.from);
    println!("to       {}", m.to);
    if let Some(t) = &m.thread {
        println!("thread   {t}");
    }
    println!("subject  {}", m.subject);
    println!();
    println!("{}", m.body);
}

fn print_who(rows: &[Who]) {
    if rows.is_empty() {
        return;
    }
    for w in rows {
        println!("{:<12} unread {:>3}   last {}", w.name, w.unread, w.last());
    }
}

fn print_help() {
    let _ = writeln!(
        io::stderr(),
        "tether — local mailbox for CLI agents\n\n\
         tether send [--from NAME] [--thread T] TO SUBJECT [BODY...]\n\
         tether inbox [--all] [AGENT]\n\
         tether recv [--wait] [--timeout SECS] [ID|FROM]\n\
         tether ack ID\n\
         tether who\n\
         tether status\n\
         tether on | off\n\
         tether mcp"
    );
}

use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

static SEQ: AtomicU64 = AtomicU64::new(0);

/// Sortable unique id: millis-hex + pid + sequence.
pub fn new_id() -> String {
    let ts = now_ms() as u64;
    let seq = SEQ.fetch_add(1, Ordering::Relaxed);
    format!(
        "{ts:012x}{pid:04x}{seq:08x}",
        pid = std::process::id() as u16
    )
}

pub fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

/// UTC `YYYY-MM-DDTHH:MM:SSZ` from unix millis. No time crate.
pub fn fmt_ts(ms: i64) -> String {
    let s = ms.div_euclid(1000);
    let days = s.div_euclid(86400);
    let tod = s.rem_euclid(86400);
    let hour = tod / 3600;
    let min = (tod % 3600) / 60;
    let sec = tod % 60;
    let (y, m, d) = civil_from_days(days);
    format!("{y:04}-{m:02}-{d:02}T{hour:02}:{min:02}:{sec:02}Z")
}

/// Howard Hinnant's `civil_from_days`.
fn civil_from_days(z: i64) -> (i32, u32, u32) {
    let z = z + 719468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = y + i64::from(m <= 2);
    (y as i32, m as u32, d as u32)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unix_epoch_formats() {
        assert_eq!(fmt_ts(0), "1970-01-01T00:00:00Z");
        assert_eq!(fmt_ts(1_000), "1970-01-01T00:00:01Z");
        assert_eq!(fmt_ts(1_735_689_600_000), "2025-01-01T00:00:00Z");
    }

    #[test]
    fn ids_are_unique() {
        let a = new_id();
        let b = new_id();
        assert_ne!(a, b);
        assert!(a < b);
    }
}

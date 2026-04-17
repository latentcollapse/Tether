"""TOML-backed message store for TetherLite."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tether.handles import (
    BLOB_PREFIX,
    INLINE_PREFIX,
    LEGACY_MESSAGES_PREFIX,
    TREE_PREFIX,
    canonical_json,
    digest12,
    kvfold_dir,
    suffix,
)

logger = logging.getLogger(__name__)

OPEN = "open"
READ = "read"
CLOSED = "closed"
STALE = "stale"
VALID_STATUSES = {OPEN, READ, CLOSED, STALE}


class MessageNotFound(FileNotFoundError):
    """Raised when a message handle has no backing TOML file."""


@dataclass(frozen=True)
class _MessageRecord:
    handle: str
    sender: str
    recipient: str
    subject: str
    created_at: str
    status: str
    ticket_id: str | None
    tags: list[str]
    text: str


class TetherLiteRuntime:
    """Persist Tether messages as one TOML file per handle."""

    def __init__(self, root: Path | str | None = None, stale_hours: float | None = None) -> None:
        env_root = os.environ.get("TETHER_LITE_DIR")
        self.root = Path(root or env_root or Path(__file__).resolve().parent)
        self.messages_dir = self.root / "messages"
        self.messages_dir.mkdir(parents=True, exist_ok=True)
        self.kvfold_dir = kvfold_dir(self.root / "kvfold")
        self.stale_hours = stale_hours if stale_hours is not None else self._env_stale_hours()

    def collapse(self, value: str | dict[str, Any]) -> str:
        """Collapse a small JSON-serializable value into an inline handle."""
        data = canonical_json(value)
        handle = f"{INLINE_PREFIX}{digest12(data)}"
        self._inline_path(handle).write_text(
            "\n".join(
                [
                    f"handle = {json.dumps(handle)}",
                    f"value_json = {json.dumps(data.decode('utf-8'))}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return handle

    def collapse_blob(self, data: bytes, content_type: str) -> str:
        """Collapse binary data into KVFold and return a blob handle."""
        digest = digest12(data)
        handle = f"{BLOB_PREFIX}{digest}"
        self._kvfold_path(digest).write_bytes(data)
        self._kvfold_path(f"{digest}.toml").write_text(
            f"handle = {json.dumps(handle)}\ncontent_type = {json.dumps(content_type)}\n",
            encoding="utf-8",
        )
        return handle

    def collapse_tree(self, handles: list[str]) -> str:
        """Collapse an ordered list of handles into KVFold and return a tree handle."""
        data = canonical_json(handles)
        digest = digest12(data)
        handle = f"{TREE_PREFIX}{digest}"
        self._kvfold_path(digest).write_bytes(data)
        return handle

    def resolve(self, handle: str) -> str | bytes | list[Any] | dict[str, Any]:
        """Resolve typed inline/blob/tree handles by prefix."""
        if handle.startswith(INLINE_PREFIX):
            with self._inline_path(handle).open("rb") as fh:
                data = tomllib.load(fh)
            return json.loads(str(data["value_json"]))
        if handle.startswith(BLOB_PREFIX):
            return self._kvfold_path(suffix(handle, BLOB_PREFIX)).read_bytes()
        if handle.startswith(TREE_PREFIX):
            raw = self._kvfold_path(suffix(handle, TREE_PREFIX)).read_bytes()
            handles = json.loads(raw.decode("utf-8"))
            if not isinstance(handles, list):
                raise ValueError(f"tree handle does not contain a list: {handle}")
            return [self.resolve(str(child)) for child in handles]
        if handle.startswith(LEGACY_MESSAGES_PREFIX):
            return self.receive(handle)
        raise ValueError(f"unknown handle prefix: {handle}")

    def inbox(self, agent_name: str) -> list[dict[str, Any]]:
        """List open messages addressed to agent_name, marking old opens stale first."""
        self._auto_stale()
        messages = [
            self._inbox_item(record)
            for record in self._iter_messages()
            if record.recipient == agent_name and record.status == OPEN
        ]
        messages.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
        return messages

    def receive(self, handle: str, for_agent: str | None = None) -> dict[str, Any]:
        """Read a message, mark it read, and return its metadata plus body text."""
        record = self._read_record(handle)
        if for_agent is not None and for_agent not in {record.sender, record.recipient}:
            raise PermissionError(f"handle {handle} is not addressed to {for_agent}")
        if record.status == OPEN:
            record = self._write_record(record, READ)
        return self._message_payload(record)

    def send(
        self,
        from_agent: str,
        to: str,
        subject: str,
        text: str,
        ticket_id: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Create a message TOML file and return its deterministic handle."""
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        clean_tags = list(tags or [])
        payload = {
            "from": from_agent,
            "to": to,
            "subject": subject,
            "created_at": created_at,
            "ticket_id": ticket_id,
            "tags": clean_tags,
            "text": text,
        }
        record = _MessageRecord(
            handle=f"h&l_messages_{self._digest(payload)}",
            sender=from_agent,
            recipient=to,
            subject=subject,
            created_at=created_at,
            status=OPEN,
            ticket_id=ticket_id,
            tags=clean_tags,
            text=text,
        )
        self._write_record(record, record.status)
        return record.handle

    def close(
        self,
        handle: str | None = None,
        ticket_id: str | None = None,
        status: str = CLOSED,
        reason: str | None = None,
    ) -> int:
        """Close one message by handle or matching open messages by ticket_id."""
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}")
        if handle is None and ticket_id is None:
            raise ValueError("handle or ticket_id is required")

        records = [self._read_record(handle)] if handle is not None else self._iter_messages()
        updated = 0
        for record in records:
            if ticket_id is not None and (record.ticket_id != ticket_id or record.status != OPEN):
                continue
            self._write_record(record, status)
            updated += 1
        if reason:
            logger.info("closed TetherLite message(s)", extra={"ticket_id": ticket_id, "reason": reason})
        return updated

    def _env_stale_hours(self) -> float:
        raw = os.environ.get("TETHER_STALE_HOURS", "24")
        try:
            return float(raw)
        except ValueError:
            logger.warning("invalid TETHER_STALE_HOURS; using default", extra={"value": raw})
            return 24.0

    def _message_path(self, handle: str) -> Path:
        clean = handle[:-5] if handle.endswith(".toml") else handle
        if "/" in clean or "\\" in clean:
            raise ValueError(f"invalid handle path component: {handle}")
        return self.messages_dir / f"{clean}.toml"

    def _inline_path(self, handle: str) -> Path:
        return self._message_path(handle)

    def _kvfold_path(self, name: str) -> Path:
        if "/" in name or "\\" in name:
            raise ValueError(f"invalid KVFold path component: {name}")
        return self.kvfold_dir / name

    def _iter_messages(self) -> list[_MessageRecord]:
        records: list[_MessageRecord] = []
        for path in sorted(self.messages_dir.glob(f"{LEGACY_MESSAGES_PREFIX}*.toml")):
            try:
                records.append(self._read_path(path))
            except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError, ValueError) as exc:
                logger.warning("skipping invalid TetherLite message", extra={"path": str(path), "error": str(exc)})
        return records

    def _read_record(self, handle: str) -> _MessageRecord:
        path = self._message_path(handle)
        if not path.exists():
            raise MessageNotFound(f"message not found: {handle}")
        return self._read_path(path)

    def _read_path(self, path: Path) -> _MessageRecord:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        body = data.get("body", {})
        tags = data.get("tags", [])
        if not isinstance(body, dict) or not isinstance(tags, list):
            raise TypeError("message body/tags have invalid TOML shape")
        ticket_id = data.get("ticket_id") or None
        return _MessageRecord(
            handle=str(data["handle"]),
            sender=str(data["from"]),
            recipient=str(data["to"]),
            subject=str(data["subject"]),
            created_at=str(data["created_at"]),
            status=str(data.get("status", OPEN)),
            ticket_id=str(ticket_id) if ticket_id is not None else None,
            tags=[str(tag) for tag in tags],
            text=str(body.get("text", "")),
        )

    def _write_record(self, record: _MessageRecord, status: str) -> _MessageRecord:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}")
        updated = _MessageRecord(**{**record.__dict__, "status": status})
        self._message_path(updated.handle).write_text(self._format_toml(updated), encoding="utf-8")
        return updated

    def _auto_stale(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.stale_hours)
        for record in self._iter_messages():
            if record.status != OPEN:
                continue
            try:
                created_at = self._parse_time(record.created_at)
            except ValueError as exc:
                logger.warning("cannot stale-check message", extra={"handle": record.handle, "error": str(exc)})
                continue
            if created_at < cutoff:
                self._write_record(record, STALE)

    def _parse_time(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

    def _digest(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            import blake3

            return blake3.blake3(canonical).hexdigest()[:12]
        except ImportError:
            logger.warning("blake3 unavailable; using local deterministic fallback")
            return hashlib.blake2b(canonical, digest_size=6).hexdigest()

    def _format_toml(self, record: _MessageRecord) -> str:
        fields = {
            "handle": record.handle,
            "from": record.sender,
            "to": record.recipient,
            "subject": record.subject,
            "created_at": record.created_at,
            "status": record.status,
            "ticket_id": record.ticket_id or "",
        }
        lines = [f"{key} = {json.dumps(value)}" for key, value in fields.items()]
        tags = ", ".join(json.dumps(tag) for tag in record.tags)
        lines.extend([f"tags = [{tags}]", "", "[body]", f"text = {json.dumps(record.text)}", ""])
        return "\n".join(lines)

    def _message_payload(self, record: _MessageRecord) -> dict[str, Any]:
        return {
            "handle": record.handle,
            "message": {
                "from": record.sender,
                "to": record.recipient,
                "subject": record.subject,
                "created_at": record.created_at,
                "status": record.status,
                "ticket_id": record.ticket_id,
                "tags": record.tags,
            },
            "text": record.text,
        }

    def _inbox_item(self, record: _MessageRecord) -> dict[str, Any]:
        return {
            "handle": record.handle,
            "from": record.sender,
            "subject": record.subject,
            "timestamp": record.created_at,
            "preview": record.text[:100] + "..." if len(record.text) > 100 else record.text,
            "read": record.status != OPEN,
            "status": record.status,
            "ticket_id": record.ticket_id,
        }

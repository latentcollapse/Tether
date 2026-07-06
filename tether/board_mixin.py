"""Board mixin for SQLiteRuntime — the smart board (tickets/CORE-N lifecycle),
its changelog projection, and the shared whiteboard.

Mixed into SQLiteRuntime; relies on the host for self._conn and the handles layer
(self.collapse / self.resolve). Owns its schema via _init_smart_board_db, wired from
the host's schema init. The DAoC-tiered ticket system: propose -> accept -> claim ->
flag -> finalize, plus author (admin direct-create), dormant/revive, and queries.
"""

import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from .runtime import contract_to_json


class BoardMixin:
    def _init_smart_board_db(self):
        """Initialize smart board tables (v2.0)."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS counters (
                category TEXT PRIMARY KEY,
                next INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                tier TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                owner TEXT,
                batch TEXT,
                principle TEXT,  -- JSON list
                bible_ref TEXT,  -- JSON list
                gate TEXT,
                blocks TEXT,      -- JSON list
                blocked_by TEXT,  -- JSON list
                work_done TEXT,
                implementers TEXT -- JSON list
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS changelog (
                id TEXT,
                category TEXT,
                tier TEXT,
                title TEXT,
                description TEXT,
                work_done TEXT,
                handle TEXT,
                summary TEXT,
                completed_by TEXT,
                completed_at TEXT
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS whiteboard (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.commit()

        # Seed default whiteboard if empty
        cursor = self._conn.execute("SELECT COUNT(*) FROM whiteboard")
        if cursor.fetchone()[0] == 0:
            default_content = """# 💡 Tether Whiteboard

Welcome to your team scratchpad! Use this space to collaborate, draft code, or coordinate tasks.

### Features:
1. **Auto-Save**: Everything you type here auto-saves and syncs in real-time.
2. **Ticket Synthesis**: Highlight any selection of text on this board and click **"Synthesize Ticket"** to instantly propose a new Debt (D) ticket.

-- Tether coordination layer"""
            self._conn.execute("INSERT INTO whiteboard (id, content) VALUES ('main', ?)", (default_content,))
            self._conn.commit()

    def sync_board_projection(self):
        """Reconstruct tickets and changelog tables from the 'board' event log."""
        cursor = self._conn.execute(
            "SELECT handle, lc_bytes, created_at, sender FROM tether_handles WHERE table_name = 'board'"
        )
        events = []
        for row in cursor.fetchall():
            handle_str = row["handle"]
            try:
                from .lc import decode_lc_b
                from .runtime import contract_to_json
                contract_val = decode_lc_b(row["lc_bytes"])
                event_data = contract_to_json(contract_val)
            except Exception:
                try:
                    event_data = json.loads(row["lc_bytes"].decode("utf-8"))
                except Exception:
                    continue
            
            event_data["handle"] = handle_str
            if "timestamp" not in event_data:
                event_data["timestamp"] = row["created_at"]
            if "actor" not in event_data:
                event_data["actor"] = row["sender"] or "unknown"
            events.append(event_data)
            
        events.sort(key=lambda x: x.get("timestamp", ""))
        
        tickets_map = {}
        changelog_list = []
        
        for ev in events:
            ev_type = ev.get("type")
            ticket_id = ev.get("ticket_id")
            actor = ev.get("actor", "unknown")
            timestamp = ev.get("timestamp")
            
            if ev_type == "propose":
                prop_id = ev.get("handle")
                ticket_data = ev.get("ticket", {}).copy()
                ticket_data.update({
                    "id": prop_id,
                    "status": "proposed",
                    "implementers": [],
                    "work_done": "",
                    "owner": ""
                })
                tickets_map[prop_id] = ticket_data
                
            elif ev_type == "accept":
                prop_id = ev.get("proposed_id")
                real_id = ev.get("ticket_id")
                if prop_id in tickets_map:
                    ticket_data = tickets_map.pop(prop_id)
                    tier = ev.get("tier") or ticket_data.get("tier", "blue")
                    if tier in ["grey", "green"]:
                        tier = "blue"
                    ticket_data.update({
                        "id": real_id,
                        "status": "open",
                        "tier": tier
                    })
                    tickets_map[real_id] = ticket_data
                else:
                    ticket_data = ev.get("ticket", {}).copy()
                    tier = ticket_data.get("tier", "blue")
                    if tier in ["grey", "green"]:
                        tier = "blue"
                    ticket_data.update({
                        "id": real_id,
                        "status": "open",
                        "tier": tier,
                        "implementers": [],
                        "work_done": "",
                        "owner": ""
                    })
                    tickets_map[real_id] = ticket_data
                    
            elif ev_type == "create":
                ticket_data = ev.get("ticket", {}).copy()
                initial_status = ticket_data.get("status", "open")
                tier = ticket_data.get("tier", "blue")
                if tier in ["grey", "green"]:
                    tier = "blue"
                ticket_data.update({
                    "id": ticket_id,
                    "status": initial_status,
                    "tier": tier,
                    "implementers": [],
                    "work_done": "",
                    "owner": ""
                })
                tickets_map[ticket_id] = ticket_data
                
            elif ev_type == "claim":
                if ticket_id in tickets_map:
                    t = tickets_map[ticket_id]
                    t["status"] = "active"
                    t["owner"] = actor
                    impls = t.get("implementers", [])
                    if actor not in impls:
                        impls.append(actor)
                    t["implementers"] = impls
                    
            elif ev_type == "flag":
                if ticket_id in tickets_map:
                    t = tickets_map[ticket_id]
                    t["status"] = "ready"
                    t["work_done"] = ev.get("work_done", "")
                    impls = t.get("implementers", [])
                    if actor not in impls:
                        impls.append(actor)
                    t["implementers"] = impls
                    
            elif ev_type == "finalize":
                if ticket_id in tickets_map:
                    t = tickets_map[ticket_id]
                    if t.get("category", "").upper() != "S":
                        t["status"] = "done"
                        tier = t.get("tier", "blue")
                        if tier in ["grey", "green"]:
                            tier = "blue"
                        changelog_list.append({
                            "id": ticket_id,
                            "category": t.get("category", ""),
                            "tier": tier,
                            "title": t.get("title", ""),
                            "description": t.get("description", ""),
                            "work_done": t.get("work_done", ""),
                            "handle": ev.get("changelog_handle", ""),
                            "summary": f"Completed {ticket_id}",
                            "completed_by": actor,
                            "completed_at": timestamp
                        })
            elif ev_type == "dormant":
                if ticket_id in tickets_map:
                    tickets_map[ticket_id]["status"] = "dormant"
            elif ev_type == "revive":
                if ticket_id in tickets_map:
                    tickets_map[ticket_id]["status"] = "open"
            elif ev_type == "update":
                if ticket_id in tickets_map:
                    t = tickets_map[ticket_id]
                    t.update(ev.get("fields", {}))
                    
        self._conn.execute("DELETE FROM tickets")
        self._conn.execute("DELETE FROM changelog")
        
        for tid, t in tickets_map.items():
            tier = t.get("tier", "blue")
            if tier in ["grey", "green"]:
                tier = "blue"
            self._conn.execute(
                """
                INSERT INTO tickets (id, category, tier, title, description, status, owner, batch, principle, bible_ref, gate, blocks, blocked_by, work_done, implementers)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tid,
                    t.get("category", ""),
                    tier,
                    t.get("title", ""),
                    t.get("description", ""),
                    t.get("status", "open"),
                    t.get("owner", ""),
                    t.get("batch", ""),
                    json.dumps(t.get("principle", [])),
                    json.dumps(t.get("bible_ref", [])),
                    t.get("gate", ""),
                    json.dumps(t.get("blocks", [])),
                    json.dumps(t.get("blocked_by", [])),
                    t.get("work_done", ""),
                    json.dumps(t.get("implementers", []))
                )
            )
            
        for c in changelog_list:
            self._conn.execute(
                """
                INSERT INTO changelog (id, category, tier, title, description, work_done, handle, summary, completed_by, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    c["id"],
                    c["category"],
                    c["tier"],
                    c["title"],
                    c["description"],
                    c["work_done"],
                    c["handle"],
                    c["summary"],
                    c["completed_by"],
                    c["completed_at"]
                )
            )
        self._conn.commit()

    def board_query(self, category=None, tier=None, status=None, owner=None, batch=None, sort="newest"):
        query = "SELECT * FROM tickets WHERE 1=1"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if tier:
            query += " AND tier = ?"
            params.append(tier)
        if status:
            query += " AND status = ?"
            params.append(status)
        if owner:
            query += " AND owner = ?"
            params.append(owner)
        if batch:
            query += " AND batch = ?"
            params.append(batch)
            
        if sort == "newest":
            query += " ORDER BY id DESC"
        elif sort == "oldest":
            query += " ORDER BY id ASC"
            
        cur = self._conn.execute(query, params)
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["principle"] = json.loads(d["principle"]) if d["principle"] else []
            d["bible_ref"] = json.loads(d["bible_ref"]) if d["bible_ref"] else []
            d["blocks"] = json.loads(d["blocks"]) if d["blocks"] else []
            d["blocked_by"] = json.loads(d["blocked_by"]) if d["blocked_by"] else []
            d["implementers"] = json.loads(d["implementers"]) if d["implementers"] else []
            rows.append(d)
        return rows

    def board_changelog_query(self, query_str=None):
        query = "SELECT * FROM changelog WHERE 1=1"
        params = []
        if query_str:
            query += " AND (id LIKE ? OR title LIKE ? OR description LIKE ?)"
            lk = f"%{query_str}%"
            params.extend([lk, lk, lk])
        query += " ORDER BY completed_at DESC"
        cur = self._conn.execute(query, params)
        return [dict(r) for r in cur.fetchall()]

    def board_propose(self, category: str, tier: str, title: str, description: str, actor: str) -> str:
        event_data = {
            "type": "propose",
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ticket": {
                "category": category.upper(),
                "tier": tier,
                "title": title,
                "description": description,
                "status": "proposed"
            }
        }
        handle = self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        return handle

    def board_accept(self, proposed_id: str, actor: str, tier: Optional[str] = None) -> str:
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (proposed_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Proposed ticket not found: {proposed_id}")
        if row["status"] != "proposed":
            raise ValueError(f"Ticket is not in proposed state: {row['status']}")
            
        category = row["category"]
        real_id = self._issue_next_id(category)
        
        event_data = {
            "type": "accept",
            "proposed_id": proposed_id,
            "ticket_id": real_id,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tier": tier or row["tier"]
        }
        self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        return real_id

    def board_author(self, category: str, tier: str, title: str, description: str, actor: str,
                     batch: Optional[str] = None, principle: Optional[List[str]] = None,
                     bible_ref: Optional[List[str]] = None, gate: Optional[str] = None,
                     blocks: Optional[List[str]] = None, blocked_by: Optional[List[str]] = None,
                     status: str = "open") -> str:
         real_id = self._issue_next_id(category)
         ticket = {
             "category": category.upper(),
             "tier": tier,
             "title": title,
             "description": description,
             "status": status,
             "batch": batch or "",
             "principle": principle or [],
             "bible_ref": bible_ref or [],
             "gate": gate or "",
             "blocks": blocks or [],
             "blocked_by": blocked_by or []
         }
         event_data = {
             "type": "create",
             "ticket_id": real_id,
             "actor": actor,
             "timestamp": datetime.now(timezone.utc).isoformat(),
             "ticket": ticket
         }
         self.collapse("board", event_data, sender=actor)
         self.sync_board_projection()
         return real_id

    def _issue_next_id(self, category: str) -> str:
        # Atomic, self-healing ticket-number issuance.
        #
        # Two historical bugs this guards against:
        #  1. Race: the old code did `UPDATE next=next+1` then a SEPARATE
        #     `SELECT next-1`. postoffice.db is shared by the CLI, the MCP
        #     server, and agent runtimes; a concurrent writer moving the
        #     counter between the UPDATE and the SELECT made the returned id
        #     disagree with the id actually persisted. We now increment and
        #     read in a SINGLE statement via RETURNING (SQLite >= 3.35), so no
        #     other writer can interleave (SQLite serializes writers).
        #  2. Drift: ids came only from the `counters` table while tickets are
        #     rebuilt from the event log by sync_board_projection(). A replay
        #     (e.g. the DB migration off /mnt/d) could leave the counter BELOW
        #     the real max ticket and re-issue a colliding id. We floor the
        #     next number at (projection max + 1) so a drifted counter always
        #     self-heals forward and can never collide with a live ticket.
        category = category.upper()
        self._conn.execute("INSERT OR IGNORE INTO counters (category, next) VALUES (?, 1)", (category,))

        # High-water mark from the projection (the source of truth for what
        # ids actually exist). Ignore non-conforming ids (legacy handle ids).
        cur = self._conn.execute("SELECT id FROM tickets WHERE category = ?", (category,))
        max_num = 0
        for row in cur.fetchall():
            suffix = str(row[0]).rsplit("-", 1)[-1]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))

        cur = self._conn.execute(
            "UPDATE counters SET next = MAX(next, ?) + 1 WHERE category = ? RETURNING next - 1",
            (max_num + 1, category),
        )
        num = cur.fetchone()[0]
        self._conn.commit()
        return f"{category}-{num}"

    def board_claim(self, ticket_id: str, actor: str) -> bool:
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Ticket not found: {ticket_id}")
        if row["status"] != "open":
            raise ValueError(f"Ticket {ticket_id} is not open (status: {row['status']})")
            
        event_data = {
            "type": "claim",
            "ticket_id": ticket_id,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        return True

    def board_flag(self, ticket_id: str, actor: str, work_done: str) -> bool:
        if not work_done.strip():
            raise ValueError("work_done cannot be empty")
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Ticket not found: {ticket_id}")
        if row["status"] != "active":
            raise ValueError(f"Ticket {ticket_id} is not active (status: {row['status']})")
            
        event_data = {
            "type": "flag",
            "ticket_id": ticket_id,
            "actor": actor,
            "work_done": work_done,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        flag_handle = self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        
        for admin in ["claude", "matt"]:
            self._fire_ping_sync(
                agent=admin,
                sender=actor,
                subject=f"TICKET READY: {ticket_id} — {row['title']}",
                handle=flag_handle
            )
        return True

    def board_finalize(self, ticket_id: str, actor: str) -> str:
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Ticket not found: {ticket_id}")
        if row["category"].upper() == "S":
            raise ValueError("Standing Order (category S) tickets have no finalize path.")
        if row["status"] != "ready":
            raise ValueError(f"Ticket {ticket_id} is not ready (status: {row['status']})")
            
        implementers = json.loads(row["implementers"]) if row["implementers"] else []
        if actor in implementers:
            raise ValueError(f"Separation of duties: actor '{actor}' is an implementer of '{ticket_id}' and cannot finalize it.")
            
        work_done = row["work_done"]
        if not work_done or not work_done.strip():
            raise ValueError(f"Cannot finalize: work_done is empty for {ticket_id}")
            
        events_cursor = self._conn.execute(
            "SELECT handle, lc_bytes, created_at, sender FROM tether_handles WHERE table_name = 'board'"
        )
        lineage = []
        for r in events_cursor.fetchall():
            try:
                from .lc import decode_lc_b
                from .runtime import contract_to_json
                contract_val = decode_lc_b(r["lc_bytes"])
                ev = contract_to_json(contract_val)
            except Exception:
                try:
                    ev = json.loads(r["lc_bytes"].decode("utf-8"))
                except Exception:
                    continue
            if ev.get("ticket_id") == ticket_id or ev.get("proposed_id") == ticket_id or ev.get("handle") == r["handle"]:
                ev["handle"] = r["handle"]
                lineage.append(ev)
                
        changelog_handle = self.collapse("changelog_proofs", {"lineage": lineage}, sender=actor)
        
        event_data = {
            "type": "finalize",
            "ticket_id": ticket_id,
            "actor": actor,
            "changelog_handle": changelog_handle,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        
        self._check_and_ping_unblocked(ticket_id)
        return changelog_handle

    def board_dormant(self, ticket_id: str, actor: str) -> bool:
        if actor not in ["claude", "matt"]:
            raise ValueError("Only admins can mark tickets as dormant.")
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Ticket not found: {ticket_id}")
        event_data = {
            "type": "dormant",
            "ticket_id": ticket_id,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        return True

    def board_revive(self, ticket_id: str, actor: str) -> bool:
        if actor not in ["claude", "matt"]:
            raise ValueError("Only admins can revive tickets.")
        cur = self._conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Ticket not found: {ticket_id}")
        event_data = {
            "type": "revive",
            "ticket_id": ticket_id,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.collapse("board", event_data, sender=actor)
        self.sync_board_projection()
        return True

    def get_whiteboard(self) -> str:
        cursor = self._conn.execute("SELECT content FROM whiteboard WHERE id = 'main'")
        row = cursor.fetchone()
        if row:
            return row[0]
        return ""

    def update_whiteboard(self, content: str):
        self._conn.execute("""
            INSERT INTO whiteboard (id, content) VALUES ('main', ?)
            ON CONFLICT(id) DO UPDATE SET content = excluded.content, updated_at = CURRENT_TIMESTAMP
        """, (content,))
        self._conn.commit()

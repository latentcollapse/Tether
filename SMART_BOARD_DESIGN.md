# Tether Smart Board — Design & Build Brief

**Status:** design of record + executable brief.
**Date:** 2026-06-08 · **Author:** Claude (architect). **Executor:** Gemini (web/Python — in-lane; zero Rust in this repo).
**Converges two side-quests:** (1) give the HLX job board a code-backed home; (2) make it a flagship Tether feature.

---

## 0. Thesis — honest-by-construction, dual-surface

The Smart Board is the **anti-JIRA**: a work tracker that **cannot lie about completion.** Every claim it makes is either verified by a second party or carries the content-addressed proof. It is the HLX v2 bible's first principle — *"no op silently turns a mistake into valid-looking state"* (P1) — reflected from the **language** into the **process**.

Two design commitments drive everything below:

1. **Build ON Tether's primitives, not beside them.** Tickets are content-addressed payloads; state changes are messages on the existing bus; the changelog is an append-only log. The board is a *demo of what Tether can build*, not a CRUD app squatting in Tether's UI. If it ends up as a plain Postgres-style table with a web form, **we have failed the brief.**
2. **Dual-surface.** One data model, two interaction surfaces tuned to their consumer:
   - **Human surface** (dashboard) — visual, spatial, recognition-driven: dropdowns, color chips, the dependency DAG.
   - **LLM surface** (MCP tools) — structured, token-dense, concision-driven: terse query args, TOON responses.
   *"Easy for a human ≠ easy for an LLM."* A collaboration tool earns its name by giving each collaborator a surface built for them.

---

## 1. Architecture — the hybrid, and why each layer exists

| Layer | Tech | Role | In-repo home |
|---|---|---|---|
| **Event log (source of truth)** | Tether handles | Authoritative append-only log: every state transition is a signed, content-addressed message (actor, from→to, ts, hash). **Nothing is "true" until it's in the log.** | `tether/handles.py`, `tether/lc.py` |
| **Index (projection)** | SQLite | Materialized view *of the log* for queries + dropdowns; owns the atomic number-issuance counter. Reconstructable from the log; never independently authoritative on state. | `tether/sqlite_runtime.py` |
| **Wire / serialization** | TOON | Token-dense format for content payloads + LLM-surface responses (~76% vs JSON). | `toon/` (SPEC.md, packages/) |
| **Human surface** | React/Vite dashboard | Visual board, filters, React-Flow DAG, gate panel. | `tether-dashboard/` |
| **LLM surface** | MCP tools | `board_*` tools returning TOON. | `tether/mcp_server.py` |
| **Notifications** | ping daemon | Inspection-ready pings, unblock pings. | `tether/ping_daemon.py` |

**The honesty guarantee is event-sourced — log-first, project second.** The board "cannot lie about completion" *only* if the message log is authoritative and SQLite is a **projection** of it. So every transition is **append-to-log first** (a signed message: actor, from-state, to-state, ts), and the SQLite row is *derived from / validated against* that log — never independently written as truth. `board_finalize` does **not** run `UPDATE status='done'`; it **appends a signed finalize event** (validated: finalizer ≠ implementer, `work_done` present, gate satisfied), and the projection follows. A SQLite state that can't be reconstructed from the log is a *bug, not a fact.* If SQLite is independently writable on state, the content-addressed log is decoration and the honesty claim is honor-system — **do not build it that way.** (This is §0 commitment 1 — "build ON primitives, not beside" — made concrete.)

**What TOON replaces — and what it leaves alone.** TOON is a serialization format; it stands in for **JSON** — the format we currently target — everywhere we write structured data to text (content payloads, MCP-tool responses). That swap is where the ~76% lands. It is **not** on the same layer as SQLite and never competed with it: SQLite is the query engine (relational columns); TOON is what the *content* gets serialized into. The only real footgun is **mixing the layers** — don't bury a queryable field inside a serialized TOON (or JSON) blob in a SQLite column, or you throw away querying. Keep queryable fields as real columns.
- **Index relational (columns). Serialize TOON, replacing JSON. Address by handle.**

---

## 2. Ticket schema

Categories are **project-configurable** (`[board.categories]`); the HLX-v2 tenant config is §10. Tiers use the **DAoC color-con** (difficulty), orthogonal to category (kind).

```toml
[[ticket]]
id          = "B-7"            # AUTO-ASSIGNED — author supplies category only (§4)
category    = "B"             # project-configured set; HLX-v2 = B/F/D/G/M/R
tier        = "red"           # grey<green<blue<yellow<orange<red<purple (difficulty)
title       = "Nominal sealed ADTs — Result/Option"
description = "..."           # the spec / acceptance criteria
status      = "open"          # open | active | ready | done   (state machine §3)
owner       = ""             # set on claim
batch       = "B1"           # optional grouping (HLX-v2: §11 batches B0..B7)
principle   = ["P1"]          # traceability — which principle(s) it serves
bible_ref   = ["§2", "§12a"]  # back-pointer to spec; required to finalize if set
gate        = "12a"           # §12 acceptance gate this closes, if any
blocks      = ["M-3"]         # dependency edges (drive the DAG view)
blocked_by  = ["B-1"]
work_done   = ""             # REQUIRED to reach `done` (§3 guard)
implementers= []             # everyone who advanced it; finalizer must NOT be here (§3)
```

Author-supplied fields are only **category + tier + title + description** (+ optional edges/batch/principle/gate). Everything else the board fills. (§4)

---

## 3. State machine — and the honest-board invariant

```
  [ ] open  ──claim──▶  [~] active  ──flag──▶  [/] ready  ──finalize──▶  [X] done ──auto──▶ changelog
              (owner set)         (work_done set)        (admin signoff)        (handle minted)
```

- **`[ ] open`** — authored, unclaimed.
- **`[~] active`** — an executor claimed it (`owner` set).
- **`[/] ready`** — executor flags inspection-ready; **`work_done` must be non-empty.** This is *"I think I'm done,"* not *"it's done."*
- **`[X] done`** — an admin signs off → **auto-promotes to changelog**, mints the content-addressed handle.

**Guards on `[X]`:**
1. **Separation of duties — the verifier ≠ the verified.** The finalizer must not appear in `implementers`. Whoever did the work — *including Claude* — can only flag `[/]`; a *different* admin marks `[X]`. (This is §4 of the bible — *"a conscience engine can't be a guest"* — as process: self-certification is how false-success leaks in.)
2. **The artifact must exist.** `work_done` non-empty, and if `gate`/`bible_ref` is set, that reference must be marked satisfied. **The board refuses to finalize a ticket that can't show what it closed.** Done can't be empty.

---

## 4. Permissions

Agents are role-tagged in the Tether registry (`admin` | `team`). In TetherLite/local mode the **dashboard operator = admin** (Matt); agents authenticate via MCP and are role-checked.

> **Honesty scope (don't overclaim).** The role split and separation-of-duties are **structural under authenticated identity** — but Tether's `from_agent` is *self-asserted on send.* In trusted local/TetherLite single-user mode that's fine. In any open/multi-party mode the guarantee degrades to honor-system until identity is authenticated (signed handles / keypairs — Tether already ships `tether_generate_keypair`). State it honestly: **structural under authenticated identity; honor-system without it.** The honest board must be honest about the limits of its own honesty.

| Action | Team (Codex, Gemini) | Admin (Claude, Matt) |
|---|---|---|
| Read / query | ✅ | ✅ |
| Claim (`open`→`active`) | ✅ | ✅ |
| Flag inspection-ready (`active`→`ready`, sets `work_done`) | ✅ | ✅ |
| **Finalize (`ready`→`done`, auto-changelog)** | ❌ | ✅ (and ≠ implementer) |
| **Author ticket** (category/tier/desc/edges) | **propose only** | ✅ |
| Edit category/tier/delete | ❌ | ✅ |

**Propose-tickets (executor-discovered debt):** a team member who finds debt mid-task calls `board_propose(category, tier, title, desc)` → ticket lands in a **`proposed`** holding state with no number. An admin `board_accept`s it → it gets a real auto-number and tier-confirm and joins the board. Surfaces debt at the moment of discovery without handing executors schema control.

---

## 5. Auto-numbering — atomic, per-category

SQLite owns a counter table; numbers are issued in a transaction so concurrent `board_author` calls from two agents never collide.

```sql
CREATE TABLE counters (category TEXT PRIMARY KEY, next INTEGER NOT NULL DEFAULT 1);
-- issue: UPDATE counters SET next = next + 1 WHERE category=? RETURNING next-1;  (in a txn)
```

Sequences are **independent per category** — `B-1` and `F-1` coexist; no single counter ever climbs to `D-3XX`. Author supplies category; the board returns the full id.

---

## 6. Human surface (dashboard, `tether-dashboard/`)

**Navigation placement.** Add **Job Board** and **Changelog** as top-level sidebar tabs, positioned **directly above Handles**: `Network · Messages · Connection · `**`Job Board · Changelog`**` · Handles · Usage · Settings`. The integration must be **native, not bolted-on** — reuse the existing nav styling, dark theme, cyan accents, `lucide-react` icons, and Tailwind tokens exactly. A user should not be able to tell the board wasn't always there.

- **Dependency DAG view** — point the existing **`@xyflow/react`** renderer (already a dep) at `blocks`/`blocked_by` edges. Tickets are nodes colored by tier, shaped/badged by category, lit green as they close. The same force-graph that draws agents now draws the **v2 batch DAG live** — critical path visible, blocked-by-undone edges flagged.
- **Dual-dropdown filter** — filter by **tier color**, **category**, sort **newest↔oldest** (+ owner, batch). Backed by SQLite queries; instant.
- **Gate panel (the v2 progress bar)** — a pinned **Recharts** view of the project's `gate` tickets (HLX-v2: the six §12 **G** gates). v2 is default-able only when all are green. One glance = how close the whole reform is.
- **Three-state checkboxes** — `[ ] / [/] / [X]` with the `/` and `X` semantics above; `X` greyed-out for non-admins and for the implementer.

---

## 7. LLM surface (MCP tools, `tether/mcp_server.py`)

Namespaced alongside existing tether tools. **All list responses return TOON**, terse args:

| Tool | Role | Notes |
|---|---|---|
| `board_query(cat?, tier?, status?, owner?, batch?, sort?)` | filtered list | TOON tabular out |
| `board_get(id)` | one ticket + lineage | full history via handle |
| `board_claim(id)` | `open`→`active` | sets owner=caller |
| `board_flag(id, work_done)` | `active`→`ready` | requires work_done |
| `board_propose(cat, tier, title, desc)` | team-file debt | → `proposed` |
| `board_author(cat, tier, title, desc, …)` | **admin** create | returns auto-id |
| `board_accept(id, tier?)` | **admin** | `proposed`→numbered |
| `board_finalize(id)` | **admin**, ≠implementer | `ready`→`done`+changelog |
| `board_changelog(query)` | search completed | TOON out |

**TOON response shape (the token win, visible):**
```
tickets[3]{id,cat,tier,status,owner,title}:
  B-1,B,red,active,codex,Nominal sealed ADTs Result/Option
  F-1,F,red,ready,gemini,Serializer trap fix
  D-1,D,yellow,open,,Clone-heavy lowerer compile-hang
```
Field names declared once, values streamed — vs JSON repeating every key per row. On a 40-ticket board queried dozens of times a session, this is the bulk of the savings.

---

## 8. Changelog (SQLite + handle)

On `[X]`, atomically: snapshot the ticket's full message lineage → changelog row, mint the handle.

```sql
CREATE TABLE changelog (
  id TEXT, category TEXT, tier TEXT, title TEXT, description TEXT,
  work_done TEXT, handle TEXT,          -- h&l_... content-addressed pointer to full history
  summary TEXT,                          -- few-words human label beside the handle
  completed_by TEXT, completed_at TEXT
);
```

The handle points to the **complete, tamper-evident lineage** (who claimed, who flagged, who signed off, the work). The changelog carries the *proof*, not just the claim — referenceable forever, honest by construction.

> **Note — two different "changelogs":** the existing `changelog/v1.*.md` files are *release notes* (version history) and stay as-is. This SQLite changelog is the *completed-ticket archive*. Don't conflate. (For HLX, the v1 completed-ticket archive becomes `HLX_V1_CHANGELOG.md`; v2 tickets flow into this SQLite changelog once the board is live.)

---

## 9. Notifications (reuse `ping_daemon.py`)

The board *drives* coordination, it doesn't just record it:
- Ticket → `[/] ready` → ping the **admins** to inspect.
- A `blocked_by` dependency closes → ping the **blocked ticket's owner**: you're unblocked.

Reuses the existing autoping nervous system — no new infra.

---

## 10. HLX-v2 tenant config (the category set + spec mapping)

The board feature is generic; HLX-v2 configures these categories (each maps to a distinction the bible itself draws):

| Cat | Means | Maps to | Rule |
|---|---|---|---|
| **B** | Build | §6/§2/§5 new construction | net-new capability |
| **F** | Fix | §3/§6.3/§6.4 | produces *wrong behavior now* (P1) — "it's broken" |
| **D** | Debt | §8, D-130 | *correct but costly* — perf/dup/coupling — "works, cut a corner" |
| **G** | Gate | §12 (a–f) | a *condition*, not work — definition-of-done |
| **M** | Migration | §11.2 / §11.5 | **irreversible** one-way-doors — "pay once" |
| **R** | Research | §7 / §11.4 | measure-not-build — honors "measure before building" |

`F`-vs-`D` decision rule: **wrong behavior now → F; correct but costly → D.** (Serializer trap = F; compile-hang = D.)

**Numbering — fresh start, all categories at 1.** The v1 board is **renumbered and re-categorized**, not carried over: live tickets are triaged into `B/F/D/G/M/R` with fresh numbers; everything else is frozen in `HLX_V1_CHANGELOG.md`. Because the old `D-`numbers are thereby removed from active circulation (closed historical record, disambiguated by the document they live in), **every category — including D — starts fresh at `-1`.** No global-uniqueness workaround is needed; the clean break removes the colliding set rather than dodging it. *(Triage pass is the board's first populated work item — see §10.1.)*

---

### 10.1 The triage pass (board's first work item)

Before v2 tickets are authored, the live v1 board is cleaned, not copied:
1. **Partition** the current `HLX_JOB_BOARD.toml`: `done`/`closed` → `HLX_V1_CHANGELOG.md`; dead v1-only → `HLX_V1_PARKED.md` (recoverable archive, not pretending to be done); **live/perpetual** → carry forward.
2. **Re-stamp the keepers** into the v2 scheme with fresh per-category numbers — e.g. D-100 release gate, D-102 hygiene, D-105 docs → standing items; D-107 llama backend, the paused D-176→D-192 comprehension frontier → triaged into `B/F/D/G/M/R` or parked.
3. The result seeds the fresh board. v1 `D-`numbers survive only as frozen history in the archive.

*(This is process work, admin-owned; not a Gemini build task — it's the data migration that the built board then hosts.)*

## 11. Build guardrails (Gemini)

- **Lane:** web (React/Vite/TS) + Python (`tether/`). **Zero Rust in this repo** — confirmed; the May incident's danger zone does not exist here.
- **Branch only. Never `main`. No destructive git** (`reset --hard`, force-push, etc.). The git constraint is language-independent and still applies.
- **Build ON primitives, not beside.** Tickets = content-addressed payloads; transitions = messages; changelog = append-only log. A plain CRUD table fails review.
- **Keep HLX board *data* local.** Ship the board *feature* in public Tether; HLX's ticket contents stay on the local SQLite (TetherLite/Local Mode) — never commit our roadmap to a public repo.
- **Dogfood on Tether's own board** (`TETHER_JOB_BOARD.toml` → migrate into the live board) before HLX adopts it.
- **TOON — canonical mode is mandatory.** Content-addressing needs same-content → same-bytes → same-hash. If TOON output is non-deterministic (key order, whitespace), the same ticket yields *different handles* and the log breaks. Verify `toon/SPEC.md` guarantees canonical/deterministic serialization and use that mode. Reference `toon/SPEC.md` + `toon/packages/`; use the SDK, don't reimplement. (Bible §2: *"deterministic hashing + canonical serialization, never process-random order."*)
- **Escalate on any blocked prerequisite** — stop and tmail, don't silently improvise.

---

## 12. Out of scope (v1) / future
- Stale/heartbeat detection ("is the owner stuck?") — later; ping infra makes it cheap.
- Cloud auth / multi-tenant roles — TetherLite local-admin model is enough for now.
- Burndown/velocity analytics — Recharts makes it cheap later; not v1.

---

*The Smart Board: content-addressed, agent-native, honest by construction. A ticket cannot mark itself done; a "done" ticket carries its proof. The one feature Atlassian could never ship — because it would empty half their customers' sprints.*

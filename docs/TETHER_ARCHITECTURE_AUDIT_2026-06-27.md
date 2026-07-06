# Tether Architecture Audit — 2026-06-27

**Auditor:** Claude (Opus 4.8), adversarial pass
**Scope:** `tether/` (Python backend) + `src/dashboard/src/app/` (Angular dashboard). **Excludes** `docs/toon/` (vendored `@toon-format/monorepo` v2.3.0).
**Trigger:** RoastMyCode flagged Architecture 45/100 ("Code crimes division"), Code Quality 55/100, 10× `any`, a 1274-line file. Bugs (90) and Security (85) scored well. This audit confirms the architecture score is *earned* — and explains why it isn't a skill gap.

---

## Verdict

The low architecture score is **not** sloppiness. Bugs and security are strong. The problem is a single accreted pattern, repeated on both sides of the stack:

> **No layering, and parallel implementations that were never deleted.**

Every concern lives in a few god-modules that mix data, transport, UI state, and business logic. When an approach was superseded (raw HTTP → FastAPI; ordering hints → presence sockets; mock data → real API), the old implementation stayed in the tree. The result *works* (hence the bug/security scores) but reads as "held together by vibes" because the structure was never designed — it grew, and nothing was reaped.

This is a **bounded, mechanical refactor**, not a rewrite. The sections below are tiered so it doesn't become a rabbit hole.

---

## Findings by severity

Tiers use DAoC color-con: 🟪 Purple (do first) → 🔴 Red → 🟠 Orange → 🟡 Yellow → 🔵 Blue → 🟢 Green (nice-to-have).

### 🟪 P-1 — The Messages compose path is a mock in the live product
- **`tether-state.ts:731 sendMessage()`** never calls the server (0 `fetch`). It updates a local signal and, because **`autonomousMode` defaults `true` (`:232`)**, fabricates a fake reply (`"Handshake confirmed… committed to SQLite…"`, `:747–763`).
- **`messages.ts:557`** — the live Messages-tab compose action — calls exactly this method. So in the shipped dashboard, **sending a message persists nothing and invents a fake response.** Inbound messages are real (`initMessagesFromApi:850`); outbound is theater.
- **Why it matters:** this is the single most damaging thing for a product with users. It's the literal embodiment of the roast. Fix: route compose through a real `POST /api/messages` (or the existing send endpoint) and delete the auto-reply fabrication.

### 🔴 R-1 — `tether-state.ts` is a 1290-line god service (≈10 responsibilities)
One `@Injectable` owns: theme tokens, settings, network nodes/edges, feed, messages, board tickets, changelog, channels + channel messages, presence WebSocket, Konsole driver, routes, **and** localStorage persistence. This is the "1274-line file" from the roast.
- **Fix (decomposition target):** split into focused services — `ThemeService` (exists, partially), `SettingsService`, `NetworkService`, `MessagesService`, `BoardService`, `ChannelsService`, `PresenceService`, `KonsoleService`, plus a `PersistenceService`. Each becomes ~100–200 lines and independently testable.

### 🔴 R-2 — Zero `HttpClient`; 23 raw `fetch()` with 22 silent error swallows
- **0** uses of Angular `HttpClient`; **23** raw `fetch()` calls scattered through state; **22** `.catch(() => {})` that drop every network error with no logging, no user feedback, no retry.
- **Why it matters:** non-idiomatic Angular (no interceptors, no typed responses, no central error handling), and the silent catches make field failures invisible — directly undercuts the "live product" story.
- **Fix:** introduce one `ApiService` wrapping `HttpClient`, with a typed error channel (toast/log). Every `fetch` becomes a typed method. This single change also kills R-3.

### 🔴 R-3 — `mcp_server.py`: two functions are 84% of the file
- **`list_tools()` = 589 lines**, **`call_tool()` = 441 lines** (of 1226 total). `list_tools` is a hand-maintained wall of `Tool(...)` literals; `call_tool` is a giant `if/elif` dispatch.
- **Fix:** a tool registry — each tool = `{schema, handler}` declared next to its implementation, with `list_tools`/`call_tool` derived by iteration. Turns a 1030-line blob into ~60 small, individually testable units and removes the merge-conflict magnet.

### 🟠 O-1 — Orphaned parallel implementations (dead code, never reaped)
- **`http_server.py` (449 lines)** — raw `BaseHTTPRequestHandler` server (`do_GET` 120 lines, `do_POST` 197 lines). Superseded by the FastAPI server in `__main__.py`. Not in `pyproject` scripts; only referenced by *name* in `reap.py` and its own docstring. **Legacy. Delete or quarantine.**
- **`headless_mcp.py` (24 tools, 12.8KB)** — defines its own `list_tools`/`call_tool`, but is imported by **no module** and wired into **no entry point**. Either dead or launched by an undocumented path. **Confirm, then delete or document.**
- **`full_runtime.py` (`TetherRuntime`)** — imported only by `__init__.py` (re-export); no internal consumers. Likely legacy alongside the canonical `sqlite_runtime.py`. **Confirm vs. public-API contract, then prune.**
- **Why it matters:** parallel runtimes/servers are the #1 reason the architecture reads as incoherent. Deleting dead implementations is the highest-leverage, lowest-risk win.

### 🟠 O-2 — `__main__.py`: 1771-line procedural mega-dispatcher
70 functions, **0 classes**; `main()` is 227 lines, `_build_parser()` 98. CLI parsing, FastAPI routes, WebSocket handlers, and business logic all in one module.
- **Fix:** split CLI (argparse) from the web app (FastAPI routers) from business logic. Move route handlers into a `web/` package with `APIRouter` modules.

### 🟡 Y-1 — The 10 `any` casts (typing malpractice the roast named)
- `tether-state.ts`: `:854, :878, :897, :997, :1005, :1059` — all untyped API responses. `feed-service.ts` ×3, `network.ts` ×1.
- **Fix:** define DTO interfaces for each backend response (these become the return types of the R-2 `ApiService` methods, so it's the same work). Enable `"strict": true` / `noImplicitAny` in `tsconfig` to keep them from creeping back.

### 🟡 Y-2 — Dead code in the dashboard
- `startTrafficSimulator()` (`:595`) and `generateInitialFeed()` (`:570`) — fake `Math.random()` traffic generators, **defined but never called**. ~75 lines of mock scaffolding.
- `purgeStaleHandles()` (`:1282`) — defined, never called.
- **Fix:** delete. (If the simulator is wanted for demos, move it behind an explicit dev flag, not a dangling private method.)

### 🟡 Y-3 — Persistence model is self-contradictory
- 13 near-identical `effect(() => localStorage.setItem(...))` blocks (`:295–362`) — copy-paste persistence.
- Messages are persisted to localStorage by an effect (`:347–351`) **and** removed by `initMessagesFromApi` (`:867`). Board/changelog do the same (`:891, :908`). localStorage and the API fight over the same keys.
- The custom-theme parse block is **duplicated verbatim** (`:413–420` then `:424–430`) — sets `customThemeTokens` twice. Straight bug/dead code.
- **Fix:** one `PersistenceService` with a declarative `persist(key, signal)` helper; decide per-store whether it's localStorage-backed *or* server-backed, never both.

### 🔵 B-1 — Two MCP tool surfaces with duplicated dispatch shape
`mcp_server.py` (61 tools) and `headless_mcp.py` (24 tools) each reimplement `list_tools`/`call_tool`. If headless is kept (see O-1), the headless set should be a *filtered view* of one shared registry (ties into R-3), not a hand-maintained fork.

### 🟢 G-1 — Minor hygiene
- Deprecated `String.prototype.substr` at `tether-state.ts:588, 614, 737, 755, 801` → `slice`/`substring`.
- `window.tetherApi` global (`:364–396`) uses `as unknown as Record<string, unknown>` — fine as an intentional automation surface, but worth a typed interface.
- **0** TODO/FIXME markers in the tree — debt is invisible, not absent. Consider tagging known gaps.

---

## Recommended sequence (bounded — stop when value tapers)

1. **P-1** — fix the mock send path. Small, highest user impact. *(½ day)*
2. **O-1** — delete `http_server.py`, confirm+delete `headless_mcp.py`/`full_runtime.py`. Pure deletion, biggest architecture-score lift per hour. *(½ day)*
3. **R-2 + Y-1** — introduce `ApiService` over `HttpClient`; type every response (kills the `any`s and the silent catches together). *(1–2 days)*
4. **R-1** — decompose `TetherState` into focused services, now that API access is centralized. *(2–3 days, the big one)*
5. **R-3 + B-1** — tool-registry refactor for `mcp_server.py`; make headless a filtered view. *(1–2 days)*
6. **Y-2, Y-3, O-2, G-1** — opportunistic cleanup during the above.

Steps 1–2 alone should move the architecture needle materially and are nearly risk-free. Steps 3–5 are the real structural work and should each be gated by the existing test pass before the next begins.

## Test posture note
Backend has real tests (`test_crypto`, `test_handles`, `test_ping_daemon`, `test_toon`, `test_mcp_server`). The **dashboard has only `app.spec.ts`** (a stub) — the god service has no unit tests, which is both *why* it grew unchecked and *why* R-1 is safe to do incrementally only if each extracted service ships with tests. Decomposition without tests just moves the risk.

# Tether — Roadmap to SaaS MVP

**Author:** Matt  
**Date:** April 2026  
**Target:** Pitch-ready in ~1 week. Production-grade from day one.

**What Tether is:** Coordination infrastructure for multi-agent AI systems. MCP-native, LLM-agnostic, relay-blind. Competes with Google A2A — without the lock-in. The relay routes handles between agents across machines. It never sees content. Handles are BLAKE3 pointers to data that lives on the agent's machine. The value is coordination, not storage.

**The pitch:** "AI agents have no shared memory layer. Tether is the coordination protocol — persistent, verified, cross-machine context passing over MCP."

**Distribution:** TetherLite as an OpenClaw upstream contribution. Tether Cloud relay as the natural upgrade for teams that need cross-machine coordination.

---

## Product Architecture

```
TetherLite                    Tether (full)              Tether Cloud
─────────────────             ─────────────────          ─────────────────────
TOML files                    SQLite + LC-B              Relay server (hosted)
~200 lines Python             Full local runtime         API key auth
No dependencies               Same MCP surface           WebSocket handshake
Free, OSS, self-hosted        Free, OSS, self-hosted     Paid tiers
                                                         Cross-machine delivery
                                                         Agent discovery
                                                         Web GUI dashboard
```

All three share: same protocol, same handle format, same MCP tool names.  
Code written for TetherLite works on Tether Cloud. Upgrade = change endpoint.

---

## Handle Scheme (Unified — applies to all three)

```
h&l_inline_{hash12}    Small JSON value, stored in index
h&l_blob_{hash12}      Binary blob, stored in KVFold
h&l_tree_{hash12}      Tree of handles, stored in KVFold
```

Hash is always BLAKE3 of canonical representation. Deduplication is free.  
Resolution routes to the correct backing store based on handle prefix.

---

## Pricing Tiers

| Feature | Free (TetherLite) | Duo ($1.99/mo) | Basic ($10/mo) | Pro ($100/mo) | Enterprise |
|---------|------------------|----------------|----------------|---------------|------------|
| Backend | SQLite local | SQLite + PAKE P2P | Hosted relay | Hosted relay | Self-hosted relay license |
| Cross-machine | No | Direct P2P only | Yes | Yes | Yes |
| Nodes | 1 (local) | 2 (direct) | Up to 10 | Up to 100 | Unlimited |
| Agents per node | Unlimited | Unlimited | Unlimited | Unlimited | Unlimited |
| Messages/day | Unlimited | Unlimited | Unlimited | Unlimited | Unlimited |
| WebSocket push | No | No | Yes | Yes | Yes |
| Agent discovery | No | No | Yes | Yes | Yes |
| PAKE P2P (LAN) | Yes (free) | Yes | Yes | Yes | Yes |
| PAKE P2P (WAN) | No | Yes (STUN) | Yes | Yes | Yes |
| Support | Community | Community | Email | Email | Dedicated SLA |
| Encrypted envelopes | No | Yes | Yes | Yes | Yes |

**What the paywall is:** cross-machine reach, nothing else. Local coordination (SQLite, unlimited agents, unlimited messages) is always free. No caps, no rate limits, no nickeling on throughput.

**WinRAR model:** free forever for individuals. Duos pay for P2P reach. Teams pay for the hosted relay. Enterprise pays for the license to run their own — regulated industries won't route agent traffic through someone else's server.

**AGPL everywhere:** TetherLite and the relay are both open source. "Relay-blind" is a trust claim that requires auditability. You sell the hosted service, not the software.

---

## Security Model

- Relay holds handles only — never plaintext blob data
- API keys are UUID v4, stored hashed (bcrypt), issued per agent registration
- Keys are scoped: a key can only resolve handles addressed to that agent
- TLS on all relay sockets (mandatory, no plaintext option)
- Encrypted envelopes (Team+): payload encrypted before collapse, relay is blind
- Key revocation: immediate, relay rejects all resolutions from revoked key
- Breach impact: attacker gets a key → revoke it → window not a vault
- Legal position: Tether Cloud is not a data custodian — blobs live in user KVFold

---

## Ticket Backlog

### T-002 — TetherLite: TOML Backing Store
**Priority:** High — foundation for everything  
**Scope:**
- New `tether_lite/` folder in repo root
- `tether_lite/runtime.py` — TOML read/write, inbox query, status updates (~150 lines)
- `tether_lite/mcp_server.py` — identical MCP tool surface to current server
- One TOML file per message: `messages/{handle}.toml`
- Frontmatter: handle, from, to, subject, created_at, status, ticket_id, tags
- Body: `[body]\ntext = "..."`
- Inbox = iterate files, filter status=open and owner=agent
- Read receipt = update status field in-place
- Auto-stale = check created_at on inbox fetch, mark stale if > threshold
- `pytest tether_lite/` — full coverage
- Type hints throughout, no bare excepts, proper logging

**Acceptance criteria:**
- All current MCP tools work identically via TetherLite
- `python -m tether_lite.mcp_server` starts cleanly
- Round-trip: send → inbox → receive → close all work
- No SQLite dependency in `tether_lite/`

---

### T-003 — Unified Handle Scheme
**Priority:** High — required before relay  
**Scope:**
- Add handle type prefix to both runtimes: `inline`, `blob`, `tree`
- `collapse_blob(bytes, content_type) -> handle` method on both runtimes
- KVFold integration: blob handles store/retrieve via KVFold
- `resolve(handle)` routes correctly based on prefix
- Backward compatible: existing `h&l_messages_*` handles still resolve
- Update `tether_contracts.json` with new handle type specs
- Tests for each handle type round-trip

---

### T-004 — Relay Server: Core
**Priority:** High — the SaaS backbone  
**Scope:**
- `relay/` folder, standalone FastAPI application
- `relay/main.py` — app entrypoint, lifespan, startup/shutdown
- `relay/routers/agents.py` — POST /agents/register, DELETE /agents/{id}
- `relay/routers/handles.py` — POST /handles/route, GET /handles/{handle}
- `relay/routers/ws.py` — WebSocket /ws/{agent_id} — persistent connection, push delivery
- `relay/models.py` — Pydantic models for all request/response types
- `relay/config.py` — environment-based config (no hardcoded values)
- `relay/auth.py` — API key middleware, key validation, scope check
- `relay/db.py` — SQLite for agent registry + key store (relay-side only, not message content)
- `docker-compose.yml` — relay + optional KVFold sidecar
- `Dockerfile` — multi-stage, slim final image
- Environment variables: `TETHER_RELAY_PORT`, `TETHER_DB_PATH`, `TETHER_TLS_CERT`, `TETHER_TLS_KEY`
- Full pytest coverage for all routes
- No print() — structured logging via Python `logging` module throughout

**Acceptance criteria:**
- `docker-compose up` starts relay cleanly
- Agent registers, gets API key back
- Second agent registers on different machine, both show in registry
- Handle sent from agent A delivered to agent B via WebSocket within 500ms

---

### T-005 — API Key Management
**Priority:** High — auth gate for all paid features  
**Scope:**
- Key generation: UUID v4 + prefix (`tk_live_` prod, `tk_test_` test)
- Storage: bcrypt hash in relay DB, never store plaintext after issuance
- Scoping: key tied to agent_id, can only resolve handles where owner = agent_id
- Revocation endpoint: DELETE /keys/{key_id} — immediate effect
- Key rotation: POST /keys/{key_id}/rotate — issues new, revokes old atomically
- Rate limiting: per-key, configurable per tier via relay config
- Auth middleware: extracts Bearer token, validates hash, attaches agent context
- Tests: valid key, revoked key, wrong scope, missing key all return correct HTTP status

---

### T-006 — Subscription Tier Enforcement
**Priority:** Medium — needed before launch  
**Scope:**
- Tier enum: Free, Teams, Enterprise
- Per-tier config: message rate limit, agent count limit, retention window, feature flags
- Middleware checks tier before: cross-machine routing, WebSocket upgrade, encrypted envelopes
- Graceful degradation: over-limit returns 429 with clear error and upgrade prompt
- Tier stored in relay DB against agent/org record
- Test each tier boundary condition

---

### T-007 — Encrypted Envelopes (Team+)
**Priority:** Medium — security requirement for Team tier  
**Scope:**
- `tether.collapse_encrypted(payload, recipient_pubkey) -> handle`
- X25519 key exchange, ChaCha20-Poly1305 encryption (libsodium via PyNaCl)
- Envelope format: `{ encrypted_payload, ephemeral_pubkey, nonce }`
- Relay cannot decrypt — it routes the handle, not the content
- `tether.resolve_encrypted(handle, privkey) -> payload`
- Key registration: agents publish pubkey to relay on registration
- Tests: encrypt → route → decrypt round-trip, relay sees only ciphertext

---

### T-008 — Web GUI Dashboard
**Priority:** Medium — demo surface + production UI  
**Scope:**
- Served by relay at `/dashboard` — no separate app to install
- Vanilla JS + CSS (no framework dependency for MVP — keep it auditable)
- Views:
  - **Agent Network** — live graph of registered agents, connection status (online/offline)
  - **Message Flow** — real-time feed of handle routing events (handle hash, from, to, timestamp)
  - **Handle Browser** — lookup a handle, see metadata (not body — relay is blind to content)
  - **Key Management** — issue, rotate, revoke API keys
  - **Usage** — message volume, delivery latency, tier usage vs limits
- WebSocket feed from relay for live updates
- Auth: session token from API key login
- Responsive, clean, minimal — this is the demo surface, make it look professional
- No user data displayed — relay shows routing metadata only, never payload

---

### T-009 — Website + Documentation
**Priority:** Medium — required for pitch  
**Scope:**
- Single-page landing: what Tether is, Lite vs Cloud, pricing table, CTA
- `/docs` — full API reference (auto-generated from FastAPI OpenAPI + hand-written guides)
- Self-host guide: `docker-compose up` in 5 minutes
- Protocol spec: handle format, MCP tool surface, wire format
- Security model page: honest, clear, what we hold vs what we don't
- TetherLite quickstart: install, send your first message in 10 lines
- Domain: tether.something (TBD)

---

### T-010 — OpenClaw Socket Integration
**Priority:** High for pitch — this is the reference customer story  
**Scope:**
- Register an OpenClaw agent with Tether Cloud relay
- WebSocket handshake from OpenClaw runtime
- Handle delivery to OpenClaw agent in real time
- Demo script: two OpenClaw agents on different machines exchange handles
- Document integration pattern for OpenClaw plugin authors

---

### T-011 — Cross-Machine Demo Script
**Priority:** High for pitch — the "aha" moment  
**Scope:**
- Two machines, two agents (claude@machine-a, codex@machine-b)
- Machine A: agent hits a problem, packages context as handle, sends via Tether Cloud
- Machine B: agent receives handle via WebSocket push, resolves, responds
- Machine A: receives response handle, continues
- Total latency target: < 1 second end-to-end
- Recorded demo video + live runnable script
- "Junior pings Senior" narrative wrapper for the pitch

---

## Best Practices (Non-Negotiable)

- **Type hints** on every function signature, no bare `Any` without comment
- **No bare excepts** — catch specific exceptions, log with context
- **Environment config** — zero hardcoded values in production code paths
- **Structured logging** — `logging` module, JSON formatter for production
- **pytest** — every module has a test file, coverage > 80% before T-010
- **Pydantic models** for all API request/response shapes
- **API versioning** — all relay routes under `/v1/`
- **Docker** — relay ships as a container, `docker-compose up` is the install story
- **No print()** in production code — ever
- **Secrets** — never committed, `.env.example` documents all required vars

---

## Week Timeline (Pitch Target)

| Day | Work |
|-----|------|
| 1-2 | T-002 TetherLite + T-003 Unified handles |
| 2-3 | T-004 Relay server core + Docker |
| 3-4 | T-005 API key auth + T-006 Tier enforcement |
| 4-5 | T-008 Web GUI dashboard |
| 5-6 | T-009 Website + T-010 OpenClaw socket |
| 6-7 | T-011 Cross-machine demo + pitch dry run |
| Parallel | T-007 Encrypted envelopes (can land after pitch if needed) |

---

## Open Questions

1. Domain name for Tether Cloud?
2. Server hardware — brother's box hosts the Teams relay. Specs + bandwidth TBD. Relay is lightweight (FastAPI + SQLite + WebSocket, no blob storage).
3. Stripe or Paddle for subscription billing?
4. TetherLite — MIT license, Tether Cloud relay — proprietary or AGPL?
5. OpenClaw integration — loop Charlotte in before or after demo is working?

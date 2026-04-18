# Tether Dashboard — Frontend Design Document

**For:** Gemini (Google AI Studio)  
**Author:** Matt & Claude (HLX Project)  
**Date:** April 2026  
**Stack:** React + TypeScript + Vite  
**Target:** Linux and Windows, browser-served by Tether relay (localhost or cloud)

---

## Overview

The Tether Dashboard is a real-time web GUI for monitoring and controlling a Tether agent network. It is served statically by the Tether relay server at `/dashboard` and communicates with the relay via REST API and WebSocket.

It must run cleanly on:
- **Linux** — Chrome, Firefox, any modern browser
- **Windows** — Chrome, Firefox, Edge

No Electron. No native dependencies. Pure browser application. The relay serves the built static files; the user opens `http://localhost:PORT/dashboard` or `https://tether-cloud-url/dashboard`.

This is both a developer tool and a pitch demo surface. It needs to look professional, feel responsive, and be immediately understandable to a non-technical person within thirty seconds of opening it.

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Framework | React 18 + TypeScript | Type-safe, Gemini-native, ecosystem |
| Build | Vite | Fast, minimal config, great DX |
| Styling | Tailwind CSS | Utility-first, consistent, no CSS file sprawl |
| Graph/Network viz | React Flow | Best-in-class node graph, MIT license |
| Charts/metrics | Recharts | Lightweight, React-native, composable |
| Icons | Lucide React | Clean, consistent, tree-shakeable |
| WebSocket | Native browser WebSocket API | No extra deps needed |
| HTTP client | Native fetch | No axios, keep deps minimal |
| State management | Zustand | Lightweight, no boilerplate, no Redux overhead |
| Animations | Framer Motion | Smooth transitions, professionally polished |

**No other major dependencies.** Keep `node_modules` lean. Every dependency must justify its presence.

---

## Project Structure

```
relay/dashboard/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
├── src/
│   ├── main.tsx                  # App entry point
│   ├── App.tsx                   # Root component, router
│   ├── store/
│   │   ├── agentStore.ts         # Agent registry state
│   │   ├── messageStore.ts       # Message feed state
│   │   ├── connectionStore.ts    # WebSocket connection state
│   │   └── authStore.ts          # API key / session state
│   ├── api/
│   │   ├── client.ts             # Base fetch wrapper, auth headers
│   │   ├── agents.ts             # Agent API calls
│   │   ├── handles.ts            # Handle API calls
│   │   └── keys.ts               # Key management API calls
│   ├── ws/
│   │   └── socket.ts             # WebSocket manager, reconnect logic
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx       # Left nav
│   │   │   ├── TopBar.tsx        # Connection status, tier badge, logout
│   │   │   └── Layout.tsx        # Shell wrapper
│   │   ├── network/
│   │   │   ├── AgentGraph.tsx    # React Flow network visualization
│   │   │   ├── AgentNode.tsx     # Custom node component
│   │   │   └── MessageEdge.tsx   # Animated edge for active message flow
│   │   ├── feed/
│   │   │   ├── MessageFeed.tsx   # Real-time handle routing log
│   │   │   └── FeedItem.tsx      # Single feed entry
│   │   ├── handles/
│   │   │   ├── HandleBrowser.tsx # Handle lookup + metadata display
│   │   │   └── HandleCard.tsx    # Handle metadata card
│   │   ├── keys/
│   │   │   ├── KeyManager.tsx    # Issue, rotate, revoke keys
│   │   │   └── KeyCard.tsx       # Single key display
│   │   ├── metrics/
│   │   │   ├── UsageChart.tsx    # Message volume over time
│   │   │   └── TierUsage.tsx     # Tier limit progress bars
│   │   └── shared/
│   │       ├── Badge.tsx         # Status badges (online/offline/stale)
│   │       ├── CopyButton.tsx    # Copy handle to clipboard
│   │       ├── EmptyState.tsx    # Empty state illustrations
│   │       └── LoadingSpinner.tsx
│   ├── views/
│   │   ├── NetworkView.tsx       # Agent graph + live feed side by side
│   │   ├── HandleBrowserView.tsx # Handle lookup full page
│   │   ├── KeysView.tsx          # Key management full page
│   │   ├── UsageView.tsx         # Metrics + tier usage
│   │   └── LoginView.tsx         # API key login
│   ├── types/
│   │   ├── agent.ts              # Agent, AgentStatus types
│   │   ├── handle.ts             # Handle, HandleMetadata types
│   │   ├── message.ts            # MessageEvent, FeedItem types
│   │   └── tier.ts               # Tier, Usage types
│   └── utils/
│       ├── formatters.ts         # Date, handle, bytes formatters
│       └── constants.ts          # API base URL, WS URL, tier limits
```

---

## Visual Design

### Color Palette

Dark theme only. This is a developer tool. No light mode for MVP.

```
Background:       #0a0a0f   (near-black, slight blue tint)
Surface:          #12121a   (card backgrounds)
Surface elevated: #1a1a26   (hover states, dropdowns)
Border:           #2a2a3e   (subtle borders)
Primary:          #6366f1   (indigo — interactive elements, CTAs)
Primary hover:    #4f46e5
Success:          #22c55e   (green — online, delivered)
Warning:          #f59e0b   (amber — stale, warning)
Error:            #ef4444   (red — offline, error, revoked)
Text primary:     #f1f5f9   (near-white)
Text secondary:   #94a3b8   (muted)
Text tertiary:    #475569   (very muted, timestamps)
Handle color:     #a78bfa   (purple — handles are visually distinct)
```

### Typography

```
Font family: Inter (Google Fonts, loaded in index.html)
Monospace:   JetBrains Mono (for handles, code, hashes)
```

Handles always render in monospace, purple (`#a78bfa`), truncated with a copy button. Never display a raw hash without truncation — show first 12 chars + `...` and full on hover.

### Spacing & Layout

- 4px base unit, Tailwind scale throughout
- Sidebar: 240px fixed width on desktop, collapsible on narrow screens
- Main content: fluid, min 600px
- Cards: `rounded-xl`, subtle shadow, `border border-[#2a2a3e]`
- No hard page reloads — everything updates in place via WebSocket or optimistic UI

---

## Views

### 1. Login View (`/login`)

Shown when no valid session exists.

**Layout:** Centered card on full dark background.

**Elements:**
- Tether logo / wordmark (top center)
- Tagline: "Agent coordination infrastructure"
- Input field: "API Key" — password type, monospace font
- Button: "Connect" — primary indigo
- Small text below: "Don't have a key? Self-host TetherLite →"
- Error state: red border + message if key is invalid

**Behavior:**
- On submit: POST `/v1/auth/session` with API key
- On success: store session token in memory (NOT localStorage — security), redirect to Network view
- Session token sent as `Authorization: Bearer {token}` on all subsequent requests

---

### 2. Network View (`/`) — Default view

The centerpiece. Split layout: agent graph left (60%), message feed right (40%).

#### Agent Graph (React Flow)

Displays all registered agents as nodes in a force-directed layout.

**Agent Node (`AgentNode.tsx`):**
```
┌─────────────────────┐
│  ●  claude          │  ← status dot (green=online, grey=offline, amber=idle)
│     @my-laptop      │  ← agent identity
│     3 msgs today    │  ← message count
└─────────────────────┘
```

- Online agents: full opacity, glowing status dot (CSS box-shadow animation)
- Offline agents: 40% opacity, grey dot
- Node click: opens agent detail panel (slide-in from right)

**Message Edge (`MessageEdge.tsx`):**
- When a handle is routed between two agents, an animated edge appears
- Edge animation: traveling dot along the path (CSS/Framer Motion)
- Edge fades out after 3 seconds if no further messages
- Edge thickness: scales with message frequency

**Controls (bottom left of graph):**
- Zoom in / zoom out / fit view buttons
- "Local only" / "All agents" toggle (for Tether Cloud — shows cross-machine agents)

**Agent Detail Panel (slide-in):**
- Agent name, ID, registration date
- Online/offline status + last seen
- API key associated (masked: `tk_live_••••••abc123`)
- Message stats: sent today, received today, total
- Button: Revoke key (with confirmation dialog)

#### Message Feed (right panel)

Real-time scrolling log of handle routing events. New items slide in from top.

**Feed Item (`FeedItem.tsx`):**
```
14:32:07  codex → claude    h&l_messages_9cf1e6...  [D-248]
14:31:55  claude → codex    h&l_messages_89d0d2...  [D-248]
14:28:01  claude → codex    h&l_messages_284b95...  [D-204]
```

- Timestamp: `HH:MM:SS`, text-tertiary
- From → To: agent names, text-secondary
- Handle: monospace, purple, truncated, copy button on hover
- Ticket ID badge: if present, small pill badge in indigo
- Click anywhere on row: opens HandleCard overlay with full metadata

**Feed controls:**
- Pause/resume button (pause freezes the feed for inspection)
- Filter by agent dropdown
- Clear feed button
- Max 200 items in DOM — virtual scroll or trim oldest

---

### 3. Handle Browser View (`/handles`)

For looking up any handle by hash.

**Layout:** Search bar top, results below.

**Search bar:**
- Full-width monospace input
- Placeholder: `h&l_messages_...`
- Searches as you type (debounced 300ms)
- Accepts partial handle (prefix search)

**Handle Card (`HandleCard.tsx`):**
```
┌──────────────────────────────────────────────────┐
│ h&l_messages_9cf1e6bf5ecd                   [copy]│
├──────────────────────────────────────────────────┤
│ Table:      messages                              │
│ From:       codex                                 │
│ To:         claude                                │
│ Created:    2026-04-17 19:05:04 UTC               │
│ Status:     open                        [●]       │
│ Ticket:     D-248                                 │
│ Tags:       brief, rcl                            │
└──────────────────────────────────────────────────┘
```

- No message body displayed — relay is blind to content, dashboard reflects that
- Status dot: green=open, amber=stale, red=expired/closed
- Tags: small pill badges
- Copy button: copies full handle to clipboard with toast confirmation

---

### 4. Key Management View (`/keys`)

**Layout:** "Issue New Key" button top right, key cards below in grid.

**Key Card (`KeyCard.tsx`):**
```
┌──────────────────────────────────────────────────┐
│ claude@my-laptop                    [Active] ●   │
├──────────────────────────────────────────────────┤
│ Key:    tk_live_••••••••••••abc123         [copy] │
│ Tier:   Indie                                     │
│ Issued: 2026-04-17                                │
│ Last used: 2 minutes ago                          │
│ Usage:  847 / 1000 messages today                 │
│         ████████░░  84%                           │
├──────────────────────────────────────────────────┤
│ [Rotate Key]              [Revoke Key]            │
└──────────────────────────────────────────────────┘
```

- Rotate: issues new key, revokes old atomically, shows new key once (with copy prompt)
- Revoke: confirmation modal ("This will immediately disconnect the agent. Continue?")
- Usage bar: color shifts amber at 80%, red at 95%
- Key value hidden by default, reveal on click, auto-hide after 30 seconds

**Issue New Key modal:**
- Agent name input
- Tier selector dropdown (Free / Indie / Team / Enterprise)
- Submit → shows key once with prominent copy prompt ("This is the only time you'll see this key")

---

### 5. Usage View (`/usage`)

Metrics and tier status.

**Top row — stat cards:**
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Messages   │  │   Agents    │  │  Avg Latency│  │  Tier       │
│   4,821     │  │     3       │  │   42ms      │  │   Indie     │
│  today      │  │  online     │  │  delivery   │  │  ████░  84% │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

**Message Volume Chart (Recharts LineChart):**
- X axis: last 24 hours (hourly) or last 7 days (daily)
- Y axis: message count
- Two lines: sent (indigo) / received (purple)
- Toggle: 24h / 7d / 30d

**Delivery Latency Chart (Recharts AreaChart):**
- P50 / P95 / P99 latency in ms
- Last 24 hours, 5-minute buckets

**Tier Usage bars:**
- Messages: used / limit
- Agents: registered / limit
- Retention: days remaining
- Upgrade CTA if approaching limits

---

## WebSocket Protocol

The dashboard opens a single persistent WebSocket connection to `/v1/ws/dashboard` on mount.

**Client → Server messages:**

```typescript
// Subscribe to specific agent's events
{ type: "subscribe", agent_id: "claude" }

// Unsubscribe
{ type: "unsubscribe", agent_id: "claude" }

// Ping (keepalive every 30s)
{ type: "ping" }
```

**Server → Client messages:**

```typescript
// Agent came online
{ type: "agent_online", agent_id: "claude", timestamp: "..." }

// Agent went offline
{ type: "agent_offline", agent_id: "claude", timestamp: "..." }

// Handle was routed
{
  type: "handle_routed",
  handle: "h&l_messages_9cf1e6bf5ecd",
  from: "codex",
  to: "claude",
  ticket_id: "D-248",
  timestamp: "2026-04-17T19:05:04Z"
}

// Handle status changed
{
  type: "handle_status",
  handle: "h&l_messages_9cf1e6bf5ecd",
  status: "read",
  timestamp: "..."
}

// Pong
{ type: "pong" }
```

**Reconnection logic (`socket.ts`):**
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, cap at 30s
- Show "Reconnecting..." banner in TopBar during disconnect
- Re-subscribe to all subscriptions on reconnect
- No message loss guarantee — on reconnect, fetch last 50 events via REST to backfill feed

---

## Cross-Platform Requirements

### Linux
- Test on: Chrome 120+, Firefox 120+
- Font rendering: Inter loads from Google Fonts CDN, fallback to `system-ui`
- No OS-specific APIs used anywhere
- Scrollbars: styled with CSS (`scrollbar-width: thin` + `scrollbar-color`)

### Windows
- Test on: Chrome 120+, Firefox 120+, Edge 120+
- No path separator assumptions anywhere in the frontend code
- Scrollbars: same CSS approach, fallback to default on older Edge
- Font: Inter from Google Fonts, same fallback chain
- WebSocket connects to `ws://localhost:PORT` or `wss://domain` — no OS differences

### Both
- Minimum viewport: 1024x768
- No horizontal scrolling at 1024px width
- All interactive elements keyboard accessible (Tab, Enter, Escape)
- No `window.alert()` or `window.confirm()` — use modal components

---

## Responsive Behavior

This is a desktop-first tool but should not break on smaller screens.

| Viewport | Behavior |
|----------|----------|
| > 1280px | Full layout, sidebar expanded |
| 1024-1280px | Full layout, sidebar slightly narrower |
| 768-1024px | Sidebar collapses to icon rail |
| < 768px | Single column, sidebar hidden behind hamburger |

---

## Performance Requirements

- **Initial load:** < 2 seconds on localhost (no CDN)
- **WebSocket message → DOM update:** < 100ms
- **Handle search response → display:** < 200ms (includes network round-trip)
- **Agent graph with 20 nodes:** smooth 60fps drag and zoom
- **Message feed:** no jank at 10 messages/second

Achieve these through:
- Vite code splitting — each view is a lazy-loaded chunk
- Zustand selectors — components only re-render on relevant state changes
- React Flow node memoization — AgentNode wrapped in `React.memo`
- Feed virtualization — max 200 DOM nodes in feed, trim oldest
- Debounced search input — 300ms

---

## Error States

Every API call and WebSocket event must have a handled error state. No unhandled promise rejections. No blank screens on failure.

| Scenario | UI Response |
|----------|-------------|
| Relay unreachable | Full-page "Cannot connect to relay" with retry button |
| WebSocket disconnect | TopBar banner "Disconnected — reconnecting..." with spinner |
| Invalid API key | Login form error "Invalid key — check and try again" |
| Handle not found | HandleCard shows "Handle not found or expired" |
| Rate limit hit | Toast notification "Rate limit reached — resets at HH:MM" |
| Key revoked mid-session | Redirect to login with message "Session ended — key was revoked" |
| Network timeout | Toast "Request timed out" with retry option |

---

## Build & Integration

### Development

```bash
cd relay/dashboard
npm install
npm run dev        # Vite dev server on :5173, proxies /v1/* to relay on :8000
```

`vite.config.ts` proxy:
```typescript
server: {
  proxy: {
    '/v1': 'http://localhost:8000',
    '/v1/ws': { target: 'ws://localhost:8000', ws: true }
  }
}
```

### Production Build

```bash
npm run build      # outputs to relay/dashboard/dist/
```

The relay's FastAPI server serves `dist/` as static files:
```python
app.mount("/dashboard", StaticFiles(directory="dashboard/dist", html=True))
```

Single command to run everything: `docker-compose up`

---

## Deliverables Checklist

- [ ] All 5 views implemented and navigable
- [ ] WebSocket connection working, feed updates in real time
- [ ] Agent graph renders with live status
- [ ] Handle browser searches and returns results
- [ ] Key management: issue, rotate, revoke all work
- [ ] Login / session flow complete
- [ ] Dark theme consistent throughout
- [ ] No TypeScript errors (`tsc --noEmit` passes clean)
- [ ] No console errors or warnings in browser DevTools
- [ ] Tested on Chrome Linux, Chrome Windows, Firefox Linux, Firefox Windows
- [ ] Responsive at 1024px viewport
- [ ] All error states handled (no blank screens)
- [ ] `npm run build` produces clean dist/ with no warnings

---

## Notes for Gemini

- The relay API is being built in parallel. Use mock data / stub API responses during development where endpoints aren't ready yet. Define the mocks in `src/api/mocks.ts` so they're easy to swap out.
- The WebSocket server may not be ready immediately — build the socket manager with a clean "not connected" state from the start.
- Handle values are always BLAKE3 hashes displayed as `h&l_{table}_{12-char prefix}`. Never attempt to decode or display the full hash inline — always truncate.
- The relay is **blind to message content**. The dashboard should never attempt to display message bodies, only metadata. If a future version adds this, it requires end-to-end decryption on the client side — that is out of scope for this document.
- Keep components small and single-responsibility. If a component file exceeds ~150 lines, split it.
- All string literals that appear in the UI go in `src/utils/constants.ts` — no hardcoded UI strings scattered through components.

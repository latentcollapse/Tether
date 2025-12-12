# HLX

**A deterministic protocol for LLM data interchange and execution.**

HLX enables AI models to communicate with each other and with runtimes using a lossless, content-addressable format that compresses entire systems into single tokens.

---

## What is HLX?

HLX is a dual-track language family designed for the post-LLM era:

| Track | Name | Audience | Format |
|-------|------|----------|--------|
| **Track A** | HLXL (Lite) | Humans, IDEs, Git | ASCII |
| **Track B** | HLX (Runic) | LLMs, Context Windows | Unicode Glyphs |

Both tracks are **mathematically isomorphic** — they compile to the same runtime, produce the same outputs, and can be losslessly transliterated between each other.

```
┌─────────────────────────────────────────────────────────────┐
│  HLXL (ASCII)              │  HLX (Runic)                   │
│  program demo {            │  ⟠ demo {                      │
│    block main() {          │    ◇ main() {                  │
│      let x = 7;            │      ⊢ x = 7;                  │
│      return x;             │      ↩ x;                      │
│    }                       │    }                           │
│  }                         │  }                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────────┐
                    │  HLX-Lite Runtime   │
                    │  (Same execution)   │
                    └─────────────────────┘
```

---

## Why Glyphs?

**Token efficiency.**

LLMs process text as tokens. A glyph like `⚳` is one token. The keyword `ls.collapse` is 3-4 tokens.

When you're paying per token and fitting complex reasoning into context windows, this matters:

| Format | Tokens | Compression |
|--------|--------|-------------|
| HLXL-LS | ~500 | 1.0x |
| HLX-LS | ~250 | 2.0x |
| HLX-LS/LC | ~50 | 10.0x |

The runic surface isn't decoration — it's **semantic compression**.

---

## Latent Space Operations

HLX includes a built-in **Latent Space (LS)** layer for content-addressable storage:

```hlx
⌸ table { }              // Declare a latent table
⊢ h = ⚳ {14:{@0:123}};   // Collapse value → handle
⊢ v = ⚯ h;               // Resolve handle → value
// Invariant: v == {14:{@0:123}}
```

Handles are opaque pointers to immutable, content-addressed data. The same value always produces the same handle.

### Core LS Operations (21 total)

| Pass | Operation | Glyph | Description |
|------|-----------|-------|-------------|
| LS0 | Collapse | `⚳` | Value → Handle |
| LS0 | Resolve | `⚯` | Handle → Value |
| LS0 | Snapshot | `⚶` | Capture table state |
| LS4 | Pipeline | `▷` | Chain operations |
| LS8 | Guard | `⚐` | Assert condition |
| LS10 | Transaction | `⚿` | Atomic updates |
| LS12 | Fingerprint | `⚉` | Content hash |
| LS20 | Compose | `⚳⊕` | Combine handles |

---

## Latent Collapse (LC)

**This is the core innovation.**

LC is a stream format that collapses HLX-Lite values into maximally compressed tokens:

```
Expanded:    {14:{@0:123, @1:"hello", @2:[1,2,3]}}

LC Stream:   🜊14🜁0 123🜁1"hello"🜁2🜃1 2 3🜄🜂
```

### LC Markers

| Marker | Meaning |
|--------|---------|
| `🜊` | Object begin |
| `🜂` | Object end |
| `🜁` | Field marker |
| `🜃` | Array begin |
| `🜄` | Array end |
| `🜇` | Handle reference |
| `⟁` | Handle literal |
| `🜋` | Document end |

At the LC layer, you're not writing code — you're **naming things into existence**. A single handle can resolve to an entire module:

```
⟁0   // ← This IS the entire photonic compute extension
```

---

## The Axioms

1. **DETERMINISM** — Same input always produces same output
2. **REVERSIBILITY** — `resolve(collapse(v)) == v` always
3. **BIJECTION** — Track A and Track B are mathematically equivalent
4. **UNIVERSAL_VALUE** — Everything lowers to HLX-Lite before encoding

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Surface Languages                        │
├─────────────────────────────────────────────────────────────┤
│  HLXL          │  HLXL-LS        │  HLX    │  HLX-LS        │
│  (ASCII)       │  (ASCII+LS)     │  (Runic)│  (Runic+LS)    │
├─────────────────────────────────────────────────────────────┤
│                     HLX-Lite Value System                    │
│              (Contracts 1-5: Value, Field, Object, etc.)     │
├─────────────────────────────────────────────────────────────┤
│                     Latent Space Runtime                     │
│              (Contracts 800-820: Handle, Table, LSOp)        │
├─────────────────────────────────────────────────────────────┤
│                     LC Wire Format                           │
│              (Binary-safe stream encoding)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Reading HLX

If you see glyphs, you're reading HLX:

```hlx
⟠ hello {
  ◇ main() {
    ⊢ msg = "Hello, World";
    ↩ msg;
  }
}
```

Transliterates to:

```hlxl
program hello {
  block main() {
    let msg = "Hello, World";
    return msg;
  }
}
```

### Using Latent Space

```hlx
⟠ ls_demo {
  ◇ main() ▣ ctx {           // ▣ = using table 'ctx'
    ⊢ data = {14:{@0:42}};
    ⊢ h = ⚳ data;             // Collapse to handle
    ⊢ v = ⚯ h;                // Resolve back
    ⚐ v.@0 == 42;             // Guard assertion
    ↩ h;                      // Return the handle
  }
}
```

---

## Glyph Reference

### Structure
| Glyph | Keyword | Meaning |
|-------|---------|---------|
| `⟠` | `program` | Program declaration |
| `◇` | `block` | Block/function |
| `⊢` | `let` | Binding |
| `⊡` | `local` | Mutable local |
| `↩` | `return` | Return value |

### Control Flow
| Glyph | Keyword | Meaning |
|-------|---------|---------|
| `❓` | `if` | Conditional |
| `❗` | `else` | Else branch |
| `⟳` | `while` | While loop |
| `⟲` | `for` | For loop |

### Latent Space
| Glyph | Keyword | Meaning |
|-------|---------|---------|
| `ꙮ` | `latent` | Latent declaration |
| `⌸` | `table` | Table declaration |
| `▣` | `using` | Table context |
| `⚳` | `ls.collapse` | Value → Handle |
| `⚯` | `ls.resolve` | Handle → Value |
| `⚶` | `ls.snapshot` | Capture state |
| `▷` | `\|>` | Pipeline |
| `⚿` | `ls.transaction` | Atomic block |

---

## For LLM Developers

HLX is designed specifically for AI-to-AI communication:

1. **Inject the codex** — Load `hlx_codex_v0.1.0.json` into context
2. **Accept both tracks** — Auto-detect HLXL vs HLX by glyph presence
3. **Use handles** — Never hallucinate data; always `⚯` to resolve
4. **Trust the runtime** — LC streams are opaque; let the runtime decode

### Bootstrap Files

- `hlx_codex_v0.1.0.json` — Language specification
- `hlx_runtime_conformance_v0.1.0.json` — Runtime behavior spec

Together, these files teach the complete HLX family to any LLM.

---

## Conformance Invariants

Any HLX implementation must satisfy:

| Invariant | Rule |
|-----------|------|
| `INV_FIDELITY` | `decode(encode(v)) == v` |
| `INV_DETERMINISM` | `encode(v)` is stable across time |
| `INV_CANONICALITY` | Equal values produce identical LC |
| `INV_REVERSIBILITY` | `resolve(collapse(v)) == v` |
| `INV_IDEMPOTENCE` | `encode(decode(lc)) == lc` |

---

## Evolution

HLX evolves through **SpecDelta** — a formal system for specification changes:

| Delta | Name | Description |
|-------|------|-------------|
| SD0 | GENESIS | Initial bootstrap |
| SD1 | RUNIC_GLYPHS | Unicode surface |
| SD2 | LS_EXPANSION | Operations LS5-LS10 |
| SD3 | HANDLE_SUBSCRIPTS | `⟁tag₁₂` notation |
| SD4 | LC_STREAM_TUNING | Marker optimization |
| SD5 | ADVANCED_OPS | Operations LS16-LS20 |
| SD6 | FREEZE_V1 | v1.0.0 lock |

Frozen components can only change via SpecDelta ops.

---

## License

Dual Licensed: **MIT OR Apache-2.0**

---

## Status

**v0.1.0 — MVP**

The core language family is complete and frozen:
- ✅ HLXL (ASCII surface)
- ✅ HLXL-LS (ASCII + Latent Space)
- ✅ HLX (Runic surface)
- ✅ HLX-LS (Runic + Latent Space)
- ✅ LC (Latent Collapse wire format)
- ✅ SpecDelta (Evolution system)
- ✅ Runtime Conformance Spec

---

*HLX: Because the future speaks in glyphs.*

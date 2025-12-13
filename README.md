# HLX Bootstrap Capsule (HBC) v1.0.0

This package contains the complete, self-contained definition of the HLX Language Family.
Upload this entire folder (or zip) to an LLM to bootstrap it with HLX capabilities.

## Contents

* **SYSTEM_PROMPT.txt**: The primary directive for LLM alignment.
* **hlx_codex.json**: The formal specification (Grammar, Semantics, Values).
* **hlx_runtime_conformance.json**: The rules of the runtime engine.
* **hlx_triggers.yaml**: Canonical mode switches (HPCP).
* **hlx_examples.hlx(l)**: Rosetta stone examples.
* **lc12_manifest_schema.json**: LC_12 Transfer Envelope v0.2-frozen schema.

## Version Binding & Scope

* **Capsule Version:** v1.2
* **Codex Version:** v0.2.0 (SD9 + LC-B)
* **Conformance:** Bound. Mismatched versions are non-conformant.

## LC_12 Transfer Envelope v0.2-frozen

### Merkle Tree
MERKLE SPEC (FANOUT 16, CANONICAL):

Let chunks be ordered by index i = 0..N-1.

Leaf hash: H_leaf[i] = BLAKE3(chunk_bytes[i]).

Group leaves in order into nodes of up to 16 children.

INTERNAL NODE (CANONICAL):

- Let child_count be the number of children in this node, where 1 ≤ child_count ≤ 16.
- Let child_hashes be the ordered list of child hashes for this node.
- Compute the internal node hash as:

  H_node = BLAKE3(
    byte(child_count) ||
    concat(child_hash_0 || child_hash_1 || ... || child_hash_(child_count-1))
  )

- child_hash_i MUST be the 32-byte BLAKE3 digest of the corresponding child.
- Children MUST be concatenated in strictly increasing child index order.
- No padding hashes are used.
- No implicit normalization of fanout is permitted.

VERIFICATION RULE:
- A receiver MUST recompute leaf hashes, rebuild the tree using this exact rule,
  and compare the resulting payload_root to the manifest.
- Any mismatch is fatal (E_ENV_PAYLOAD_HASH_MISMATCH).

### Table Ordering
TABLE ORDER KEY (CANONICAL):

Normalize handle string with Unicode NFC.

Lowercase using Unicode simple case-folding.

Strip exactly one leading literal "&h_" prefix if present; strip nothing else.

order_key = UTF-8 bytes of resulting string.

Sort ascending lexicographic by order_key bytes.

- Case folding MUST use Unicode 15.0 simple case folding as defined in
  Unicode Character Database file CaseFolding.txt.

## Exporter Requirement
EXPORTER REQUIREMENT:

Capsule integrity hash SHA256 is computed over final ZIP bytes by the exporter.

If BLAKE3 is used for any artifact hash, exporter tooling MUST include a real BLAKE3 implementation.

Acceptable reference implementations: python package "blake3" or Rust crate "blake3".

LLMs MUST NOT invent hashes; if unable to compute, output "COMPUTE_WITH_EXPORTER".

## Cold LLM Bootstrap Guide

Uploading this capsule alone is sufficient to initialize a compliant HLX node.
* No prior HLX knowledge required.
* No execution required (knowledge-only).
* Runtime authority is external (do not hallucinate execution).
* LC streams must never be hallucinated.

**Disclaimer:** This capsule is an instructional artifact, not a security boundary. Never grant this capsule higher privilege than the current session allows. Triggers require confirmation.

## Usage

1. Upload this zip to the LLM.
2. Tell the LLM: "Initialize from the HLX Bootstrap Capsule."
3. The LLM is now HLX-Native.

CAPSULE_INTEGRITY_HASH_SHA256: <github-provided-sha256>


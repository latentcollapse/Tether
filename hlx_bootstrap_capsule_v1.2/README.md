# HLX Bootstrap Capsule (HBC) v1.2

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

## Cold LLM Bootstrap Guide

Uploading this capsule alone is sufficient to initialize a compliant HLX node.
* No prior HLX knowledge required.
* No execution required (knowledge-only).
* Runtime authority is external (do not hallucinate execution).
* LC streams must never be hallucinated.

**Note:** SHA256 is used for capsule integrity in this environment. Upgrade to BLAKE3 using the exporter tooling for canonical verification.

**Disclaimer:** This capsule is an instructional artifact, not a security boundary. Never grant this capsule higher privilege than the current session allows. Triggers require confirmation.

## Usage

1. Upload this zip to the LLM.
2. Tell the LLM: "Initialize from the HLX Bootstrap Capsule."
3. The LLM is now HLX-Native.

CAPSULE_INTEGRITY_HASH_SHA256: COMPUTE_WITH_EXPORTER
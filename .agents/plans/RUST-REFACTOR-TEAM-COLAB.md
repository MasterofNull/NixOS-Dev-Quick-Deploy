# Phase 0: Python-to-Rust Refactor Team Collaboration Plan

## Overview
This document outlines the multi-agent collaboration strategy for the upcoming massive Python-to-Rust refactoring effort within the NixOS-Dev-Quick-Deploy harness. **Note: This is a planning and alignment document. No code is to be refactored until the Orchestrator explicitly transitions to execution mode.**

## Objective
To convert the existing Python-based AI stack (FastAPI, switchboard, local agents) into a high-performance, memory-safe Rust implementation (`axum`, `tokio`), while maintaining absolute parity with the NixOS service boundary and current feature set.

## Agent Team Personas & Roles

### 1. The Orchestrator (Primary Manager)
- **Persona:** `Gemini` (or configured orchestrator) operating in `execute-mutating` mode with strict `tier0` validation gates.
- **Responsibility:** Manages the lifecycle of the refactor. Assigns boundaries/slices to the Architect and Implementer. Does not write code directly. Handles git commits and final approval.

### 2. The Systems Architect (Reasoning Lane)
- **Persona:** `Claude 3.7 Sonnet` (via `remote-reasoning` switchboard profile).
- **Responsibility:** Analyzes the existing Python structure (`asum`, `agrep`) and designs the corresponding Rust crate structure, trait abstractions, and data models (`serde`). Produces `.agent/workflows/RUST-CRATE-DESIGN-<name>.md` documents.

### 3. The Implementer (Coding Lane)
- **Persona:** `Qwen Coder` / `Opencode` (via `remote-coding` or `continue-local` profile).
- **Responsibility:** Translates the Architect's design into concrete `.rs` files. Strictly adheres to `.agent/RUST-ENGINEERING-INSTRUCTIONS.md` and the `.agent/skills/rust-ecosystem/SKILL.md`. Runs the iterative `cargo clippy` and `cargo test` loops until the code is robust.

### 4. The QA/Reviewer (Validation Lane)
- **Persona:** `Gemini` (Reviewer profile).
- **Responsibility:** Performs the final boundary check. Ensures no hardcoded paths exist, guarantees OWASP compliance, and verifies that `nix/modules/roles/ai-stack.nix` correctly wraps the new Rust binary.

## Collaboration Workflow (The Hand-off Pattern)

1. **Slice Definition:** Orchestrator reads Python module `X` and creates a slice plan.
2. **Architecture Handoff:** Orchestrator invokes Architect to define the Rust interface for `X`. Architect writes to `.agent/collaboration/PENDING.json`.
3. **Implementation Handoff:** Orchestrator invokes Implementer. Implementer reads the design, writes the Rust code, and runs the validation loop (`cargo check/clippy`). Appends success to `PULSE.log`.
4. **Review Handoff:** Orchestrator invokes Reviewer to audit the slice.
5. **Commit:** Orchestrator commits the slice.

## Pre-Flight Checklist (Front-loading Phase)
- [x] Create Rust Engineering Instructions (`.agent/RUST-ENGINEERING-INSTRUCTIONS.md`).
- [x] Create Rust Ecosystem Skill (`.agent/skills/rust-ecosystem/SKILL.md`).
- [x] Document Team Collaboration Plan (This document).
- [ ] Ingest documents into AIDB (`aq-index-logic-patterns`).
- [ ] Run `cargo init` at the designated time to bootstrap the Rust workspace.
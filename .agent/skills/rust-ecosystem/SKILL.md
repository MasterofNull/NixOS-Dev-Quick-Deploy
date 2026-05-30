# Rust Ecosystem Skill

## Overview
This skill provides agents with the procedural knowledge required to interact with the Rust toolchain within the NixOS-Dev-Quick-Deploy environment. It details the required commands, validation gates, and expected outputs for refactoring and building Rust components.

## Prerequisites
- The environment must have `cargo`, `rustc`, `clippy`, and `rustfmt` available (typically provided via `nix develop` or NixOS packages).
- The agent must be operating within a Rust crate directory (a directory containing a `Cargo.toml`).

## Core Tooling Commands

### 1. Verification (Cargo Check)
**Goal:** Verify that the code compiles conceptually without producing a binary.
**Command:** `cargo check --all-targets --all-features`
**Expected Output:** No errors. Warnings are acceptable but should be reviewed.
**Agent Action on Error:** Read the compiler error closely. Rust errors are highly descriptive and often suggest the exact fix.

### 2. Linting (Clippy)
**Goal:** Ensure code adheres to Rust idioms and best practices.
**Command:** `cargo clippy --all-targets --all-features -- -D warnings`
**Expected Output:** Exits with `0`. If it fails, `clippy` has found a warning which is treated as an error (`-D warnings`).
**Agent Action on Error:** Apply the suggested fix from clippy. Often this involves borrowing correctly, removing redundant clones, or simplifying iterators.

### 3. Formatting (Rustfmt)
**Goal:** Ensure the codebase uses the canonical format.
**Command:** `cargo fmt --check` (to verify) or `cargo fmt` (to apply).
**Agent Action:** Always run `cargo fmt` after modifying a `.rs` file before proposing a commit.

### 4. Testing (Cargo Test)
**Goal:** Run unit and integration tests.
**Command:** `cargo test --all-features`
**Agent Action:** If a test fails, use `agrep` to find the test source, read the logic, and fix the invariant.

## Dependency Management
- **Adding a Dependency:** Use `cargo add <crate>`. E.g., `cargo add tokio --features full`.
- **NixOS Integration:** Remember that if adding C-library dependencies (e.g., `openssl-sys`), the `flake.nix` or corresponding `buildRustPackage` in the `nix/modules` tree must be updated to include the native library via `buildInputs` and `nativeBuildInputs`.

## Typical Workflow
1. Agent receives a Python-to-Rust conversion task.
2. Agent reads `.agent/RUST-ENGINEERING-INSTRUCTIONS.md` to establish architectural bounds.
3. Agent edits `src/*.rs` files.
4. Agent runs `cargo fmt`.
5. Agent runs `cargo clippy -- -D warnings`.
6. Agent runs `cargo test`.
7. Agent proposes commit ONLY when all three succeed.
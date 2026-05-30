# Rust Engineering & Refactoring Guidelines

## Core Objective
This document defines the canonical Rust ecosystem, idioms, and architectural standards for the AI Harness and NixOS-Dev-Quick-Deploy stack. It serves as the authoritative guide for all AI agents (Architects, Implementers, QA) involved in the Python-to-Rust refactoring effort.

## Ecosystem & Toolchain
- **Toolchain:** Stable Rust (managed via Nix flake inputs, e.g., `fenix` or `nixpkgs` stable).
- **Build System:** `cargo`. All Nix derivations must wrap `buildRustPackage`.
- **Async Runtime:** `tokio` (multi-threaded feature enabled).
- **Error Handling:** `anyhow` for application-level (binaries/executables), `thiserror` for library-level crates.
- **Serialization:** `serde` with `serde_json` and `serde_yaml`.
- **Web/API Server:** `axum` (replacing FastAPI/Flask).
- **HTTP Client:** `reqwest` (replacing `httpx` / `requests`).
- **CLI Parsing:** `clap` (derive API).
- **Logging/Tracing:** `tracing` and `tracing-subscriber` (replacing standard Python `logging`).

## Idiomatic Practices for Agents
1. **Memory Safety & Lifetimes:** Minimize `unsafe` blocks. If `unsafe` is absolutely required (e.g., FFI with C libraries), it MUST be heavily documented with `// SAFETY:` comments.
2. **Error Propagation:** Use the `?` operator extensively. Do not use `unwrap()` or `expect()` in production code unless proving invariants that the compiler cannot see.
3. **Immutability by Default:** Prefer immutable bindings (`let` over `let mut`).
4. **Pattern Matching:** Exhaustive `match` statements over extensive `if let` chains when dealing with enums.
5. **Clippy & Fmt:** Code is not complete until `cargo clippy -- -D warnings` and `cargo fmt --check` pass perfectly.

## Architecture Mapping (Python to Rust)
- **FastAPI Routes:** Map directly to `axum` routers and handlers. Use extractors for path/query/body.
- **Pydantic Models:** Map to `serde` structs with `#[derive(Serialize, Deserialize)]`.
- **Global State:** Do not use `lazy_static` unless necessary. Prefer passing state via `axum`'s `State` extractor or passing context structs explicitly.
- **Subprocesses:** Replace `subprocess.run` with `tokio::process::Command` to maintain async concurrency.

## NixOS Integration Constraints
- Binaries must be statically linked where possible, or rely explicitly on Nix store paths for dynamic libraries.
- Configuration should still be driven by `nix/modules/services/*.nix` generating configuration files or environment variables that the Rust binaries consume.

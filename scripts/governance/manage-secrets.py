#!/usr/bin/env python3
"""Declarative SOPS secrets manager for local AI-stack credentials."""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import stat
import string
import subprocess
import sys
import tempfile
from typing import Dict, List


SAFE_ALPHABET = string.ascii_letters + string.digits + "._~+=-"

SECRET_SPECS = [
    {
        "name": "aidb_api_key",
        "label": "AIDB API key",
        "kind": "token",
        "scope": "core",
        "services": "aidb",
    },
    {
        "name": "hybrid_coordinator_api_key",
        "label": "Hybrid coordinator API key",
        "kind": "token",
        "scope": "core",
        "services": "hybrid-coordinator, harness",
    },
    {
        "name": "embeddings_api_key",
        "label": "Embeddings API key",
        "kind": "token",
        "scope": "core",
        "services": "embeddings",
    },
    {
        "name": "postgres_password",
        "label": "Postgres password",
        "kind": "password",
        "scope": "core",
        "services": "postgres, aidb, hybrid-coordinator",
    },
    {
        "name": "redis_password",
        "label": "Redis password",
        "kind": "password",
        "scope": "core",
        "services": "redis",
    },
    {
        "name": "aider_wrapper_api_key",
        "label": "Aider wrapper API key",
        "kind": "token",
        "scope": "core",
        "services": "aider-wrapper",
    },
    {
        "name": "nixos_docs_api_key",
        "label": "NixOS docs API key",
        "kind": "token",
        "scope": "optional",
        "services": "nixos-docs",
    },
    {
        "name": "remote_llm_api_key",
        "label": "Remote LLM / OpenRouter API key",
        "kind": "token",
        "scope": "optional",
        "services": "switchboard remote routing",
    },
]

DEFAULT_CORE_SECRET_NAMES = [spec["name"] for spec in SECRET_SPECS if spec["scope"] == "core"]


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def run(cmd: List[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
    )


def require_command(name: str) -> None:
    if shutil.which(name):
        return
    raise SystemExit(f"Missing required command: {name}")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def available_hosts(root: Path) -> List[str]:
    hosts_dir = root / "nix" / "hosts"
    if not hosts_dir.is_dir():
        return []
    return sorted(path.name for path in hosts_dir.iterdir() if path.is_dir())


def resolve_host(root: Path, requested: str | None) -> str:
    hosts = available_hosts(root)
    if requested:
        if requested not in hosts:
            raise SystemExit(f"Unknown host '{requested}'. Available: {', '.join(hosts)}")
        return requested

    detected = socket.gethostname().split(".")[0]
    if detected in hosts:
        return detected
    if "nixos" in hosts:
        return "nixos"
    if len(hosts) == 1:
        return hosts[0]
    raise SystemExit("Unable to infer host. Pass --host explicitly.")


def resolve_primary_user() -> str:
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or getpass.getuser()


def host_paths(root: Path, host: str, primary_user: str) -> Dict[str, Path]:
    secrets_root = Path.home() / ".local" / "share" / "nixos-quick-deploy" / "secrets" / host
    return {
        "repo_root": root,
        "host_dir": root / "nix" / "hosts" / host,
        "deploy_options_local": root / "nix" / "hosts" / host / "deploy-options.local.nix",
        "secrets_root": secrets_root,
        "bundle": secrets_root / "secrets.sops.yaml",
        "sops_config": secrets_root / ".sops.yaml",
        "age_key_dir": Path.home() / ".config" / "sops" / "age",
        "age_key_file": Path.home() / ".config" / "sops" / "age" / "keys.txt",
        "backups_dir": secrets_root / "backups",
        "primary_user": Path("/home") / primary_user,
    }


def ensure_mode(path: Path, mode: int) -> None:
    current = stat.S_IMODE(path.stat().st_mode)
    if current != mode:
        path.chmod(mode)


def ensure_age_key(paths: Dict[str, Path]) -> str:
    require_command("age-keygen")
    age_key_dir = paths["age_key_dir"]
    age_key_file = paths["age_key_file"]
    age_key_dir.mkdir(parents=True, exist_ok=True)
    ensure_mode(age_key_dir, 0o700)
    if not age_key_file.exists():
        run(["age-keygen", "-o", str(age_key_file)])
    ensure_mode(age_key_file, 0o600)
    public_key = ""
    for line in age_key_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("# public key:"):
            public_key = line.split(":", 1)[1].strip()
            break
    if not public_key:
        raise SystemExit(f"Unable to read age public key from {age_key_file}")
    return public_key


def ensure_sops_config(paths: Dict[str, Path], public_key: str) -> None:
    secrets_root = paths["secrets_root"]
    secrets_root.mkdir(parents=True, exist_ok=True)
    ensure_mode(secrets_root, 0o700)
    config_path = paths["sops_config"]
    if config_path.exists():
        ensure_mode(config_path, 0o600)
        return
    content = (
        "creation_rules:\n"
        "  - path_regex: .*secrets\\.sops\\.yaml$\n"
        f"    age: >-\n      {public_key}\n"
    )
    config_path.write_text(content, encoding="utf-8")
    ensure_mode(config_path, 0o600)


def create_or_update_local_override(paths: Dict[str, Path], primary_user: str) -> None:
    target = paths["deploy_options_local"]
    target.parent.mkdir(parents=True, exist_ok=True)
    secrets_file = str(paths["bundle"])
    age_key_file = str(paths["age_key_file"])
    content = (
        "{ lib, ... }:\n"
        "{\n"
        "  mySystem.secrets.enable = lib.mkForce true;\n"
        f"  mySystem.secrets.sopsFile = lib.mkForce \"{secrets_file}\";\n"
        f"  mySystem.secrets.ageKeyFile = lib.mkForce \"{age_key_file}\";\n"
        "}\n"
    )
    target.write_text(content, encoding="utf-8")


def decrypt_bundle(paths: Dict[str, Path]) -> Dict[str, str]:
    bundle = paths["bundle"]
    if not bundle.exists():
        return {}
    require_command("sops")
    env = os.environ.copy()
    env["SOPS_AGE_KEY_FILE"] = str(paths["age_key_file"])
    result = subprocess.run(
        ["sops", "--decrypt", "--output-type", "json", str(bundle)],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"Failed to decrypt {bundle}: {result.stderr.strip()}")
    payload = json.loads(result.stdout or "{}")
    return {str(key): str(value) for key, value in payload.items()}


def backup_bundle(paths: Dict[str, Path]) -> Path | None:
    bundle = paths["bundle"]
    if not bundle.exists():
        return None
    backups_dir = paths["backups_dir"]
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backups_dir / f"{stamp}-secrets.sops.yaml"
    shutil.copy2(bundle, target)
    ensure_mode(target, 0o600)
    return target


def encrypt_bundle(paths: Dict[str, Path], payload: Dict[str, str], public_key: str) -> None:
    require_command("sops")
    paths["secrets_root"].mkdir(parents=True, exist_ok=True)
    ensure_mode(paths["secrets_root"], 0o700)
    backup_bundle(paths)
    json_payload = json.dumps(payload, sort_keys=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(json_payload)
        tmp_name = handle.name
    env = os.environ.copy()
    env["SOPS_AGE_KEY_FILE"] = str(paths["age_key_file"])
    try:
        result = subprocess.run(
            [
                "sops",
                "--encrypt",
                "--age",
                public_key,
                "--input-type",
                "json",
                "--output-type",
                "yaml",
                "--filename-override",
                "secrets.sops.yaml",
                tmp_name,
            ],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit(f"Failed to encrypt bundle: {result.stderr.strip()}")
        paths["bundle"].write_text(result.stdout, encoding="utf-8")
        ensure_mode(paths["bundle"], 0o600)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def random_secret(kind: str) -> str:
    length = 48 if kind == "token" else 32
    return "".join(secrets.choice(SAFE_ALPHABET) for _ in range(length))


def prompt_secret(label: str) -> str:
    while True:
        value = getpass.getpass(f"{label}: ").strip()
        if not value:
            print("Value cannot be empty.")
            continue
        confirm = getpass.getpass(f"Confirm {label}: ").strip()
        if value != confirm:
            print("Values did not match.")
            continue
        return value


def spec_map() -> Dict[str, dict]:
    return {spec["name"]: spec for spec in SECRET_SPECS}


def selected_specs(include_optional: bool, include_remote: bool) -> List[dict]:
    chosen = []
    for spec in SECRET_SPECS:
        if spec["scope"] == "core":
            chosen.append(spec)
        elif include_optional:
            chosen.append(spec)
        elif include_remote and spec["name"] == "remote_llm_api_key":
            chosen.append(spec)
    return chosen


def selected_secret_names(include_optional: bool, include_remote: bool) -> List[str]:
    return [spec["name"] for spec in selected_specs(include_optional, include_remote)]


def current_secret_payload(paths: Dict[str, Path]) -> Dict[str, str]:
    return decrypt_bundle(paths) if paths["bundle"].exists() else {}


def missing_secret_names(payload: Dict[str, str], *, include_optional: bool, include_remote: bool) -> List[str]:
    return [name for name in selected_secret_names(include_optional, include_remote) if not payload.get(name)]


def describe_secret_state(paths: Dict[str, Path], *, include_optional: bool, include_remote: bool) -> Dict[str, object]:
    payload = current_secret_payload(paths)
    missing = missing_secret_names(payload, include_optional=include_optional, include_remote=include_remote)
    state = {
        "bundle_exists": paths["bundle"].exists(),
        "age_key_exists": paths["age_key_file"].exists(),
        "local_override_exists": paths["deploy_options_local"].exists(),
        "payload": payload,
        "missing_secrets": missing,
    }
    state["is_ready"] = (
        state["bundle_exists"]
        and state["age_key_exists"]
        and state["local_override_exists"]
        and not missing
    )
    return state


def bootstrap_mode(args: argparse.Namespace) -> str:
    if args.mode in {"auto", "manual"}:
        return args.mode
    if not sys.stdin.isatty():
        return "auto"
    print("Select secrets input mode:")
    print("  1. Enter my own values")
    print("  2. Auto-generate secure values")
    choice = input("Choice [1/2, default 2]: ").strip() or "2"
    if choice == "1":
        return "manual"
    if choice == "2":
        return "auto"
    raise SystemExit(f"Invalid choice '{choice}'. Expected 1 or 2.")


def bootstrap_payload(args: argparse.Namespace, existing: Dict[str, str]) -> Dict[str, str]:
    payload = dict(existing)
    specs = selected_specs(args.include_optional, args.include_remote)
    mode = bootstrap_mode(args)

    if mode == "manual":
        use_shared = bool(args.shared_secret)
        shared_value = args.shared_secret
        if not use_shared and sys.stdin.isatty():
            shared_choice = input("Use one shared secret for all selected services? [y/N]: ").strip() or "N"
            use_shared = shared_choice.lower().startswith("y")
        if use_shared and not shared_value:
            shared_value = prompt_secret("Shared AI stack secret")
        for spec in specs:
            if spec["name"] in payload and payload[spec["name"]] and not args.force:
                continue
            payload[spec["name"]] = shared_value or prompt_secret(spec["label"])
        return payload

    for spec in specs:
        if spec["name"] in payload and payload[spec["name"]] and not args.force:
            continue
        payload[spec["name"]] = random_secret(spec["kind"])
    return payload


def command_status(args: argparse.Namespace) -> int:
    root = repo_root()
    host = resolve_host(root, args.host)
    primary_user = resolve_primary_user()
    paths = host_paths(root, host, primary_user)
    state = describe_secret_state(paths, include_optional=True, include_remote=True)
    payload = state["payload"]
    print(f"Host: {host}")
    print(f"Bundle: {paths['bundle']}")
    print(f"AGE key: {paths['age_key_file']}")
    print(f"Local override: {paths['deploy_options_local']}")
    print(f"Ready: {'yes' if state['is_ready'] else 'no'}")
    print("")
    for spec in SECRET_SPECS:
        present = spec["name"] in payload and bool(payload[spec["name"]])
        status = "present" if present else "missing"
        print(f"{spec['name']:<30} {status:<8} {spec['services']}")
    return 0


def command_paths(args: argparse.Namespace) -> int:
    root = repo_root()
    host = resolve_host(root, args.host)
    primary_user = resolve_primary_user()
    paths = host_paths(root, host, primary_user)
    for key in ("bundle", "sops_config", "age_key_file", "deploy_options_local", "backups_dir"):
        print(f"{key}={paths[key]}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    root = repo_root()
    host = resolve_host(root, args.host)
    primary_user = resolve_primary_user()
    paths = host_paths(root, host, primary_user)
    state = describe_secret_state(paths, include_optional=False, include_remote=False)
    problems = []
    if not state["age_key_exists"]:
        problems.append(f"Missing age key: {paths['age_key_file']}")
    if not state["bundle_exists"]:
        problems.append(f"Missing encrypted bundle: {paths['bundle']}")
    if not state["local_override_exists"]:
        problems.append(f"Missing local override: {paths['deploy_options_local']}")
    for name in state["missing_secrets"]:
        problems.append(f"Missing core secret value: {name}")
    if problems:
        for problem in problems:
            eprint(problem)
        return 1
    print("Secrets configuration is valid.")
    return 0


def command_init(args: argparse.Namespace) -> int:
    root = repo_root()
    host = resolve_host(root, args.host)
    primary_user = resolve_primary_user()
    paths = host_paths(root, host, primary_user)
    public_key = ensure_age_key(paths)
    ensure_sops_config(paths, public_key)
    create_or_update_local_override(paths, primary_user)
    payload = decrypt_bundle(paths) if paths["bundle"].exists() else {}
    updates = 0
    for spec in selected_specs(args.include_optional, args.include_remote):
        if spec["name"] in payload and payload[spec["name"]] and not args.force:
            continue
        payload[spec["name"]] = random_secret(spec["kind"])
        updates += 1
    if updates == 0:
        print("No secrets needed changes.")
        return 0
    encrypt_bundle(paths, payload, public_key)
    print(f"Initialized {updates} secret(s) in {paths['bundle']}")
    print(f"Local override ensured at {paths['deploy_options_local']}")
    return 0


def command_set(args: argparse.Namespace) -> int:
    root = repo_root()
    host = resolve_host(root, args.host)
    primary_user = resolve_primary_user()
    paths = host_paths(root, host, primary_user)
    specs = spec_map()
    if args.secret not in specs:
        raise SystemExit(f"Unknown secret '{args.secret}'. Use 'list' to inspect supported names.")
    public_key = ensure_age_key(paths)
    ensure_sops_config(paths, public_key)
    create_or_update_local_override(paths, primary_user)
    payload = decrypt_bundle(paths) if paths["bundle"].exists() else {}
    spec = specs[args.secret]
    if args.generate:
        value = random_secret(spec["kind"])
    elif args.value:
        value = args.value
    else:
        value = prompt_secret(spec["label"])
    payload[args.secret] = value
    encrypt_bundle(paths, payload, public_key)
    print(f"Updated {args.secret} in {paths['bundle']}")
    return 0


def command_bootstrap(args: argparse.Namespace) -> int:
    root = repo_root()
    host = resolve_host(root, args.host)
    primary_user = resolve_primary_user()
    paths = host_paths(root, host, primary_user)
    public_key = ensure_age_key(paths)
    ensure_sops_config(paths, public_key)
    create_or_update_local_override(paths, primary_user)
    payload = decrypt_bundle(paths) if paths["bundle"].exists() else {}
    names = selected_secret_names(args.include_optional, args.include_remote)
    if not args.force and all(payload.get(name) for name in names):
        print(f"Existing encrypted secrets already cover requested set in {paths['bundle']}")
        print(f"Local override ensured at {paths['deploy_options_local']}")
        return 0
    updated = bootstrap_payload(args, payload)
    encrypt_bundle(paths, updated, public_key)
    print(f"Bootstrapped {len(names)} secret(s) in {paths['bundle']}")
    print(f"Local override ensured at {paths['deploy_options_local']}")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    root = repo_root()
    host = resolve_host(root, args.host)
    primary_user = resolve_primary_user()
    paths = host_paths(root, host, primary_user)
    state = describe_secret_state(
        paths,
        include_optional=args.include_optional,
        include_remote=args.include_remote,
    )

    print(f"Host: {host}")
    print(f"Bundle: {paths['bundle']}")
    print(f"AGE key: {'present' if state['age_key_exists'] else 'missing'}")
    print(f"Encrypted bundle: {'present' if state['bundle_exists'] else 'missing'}")
    print(f"Local override: {'present' if state['local_override_exists'] else 'missing'}")
    print(f"Requested secret set ready: {'yes' if state['is_ready'] else 'no'}")

    if state["missing_secrets"]:
        print("")
        print("Missing secrets:")
        for name in state["missing_secrets"]:
            print(f"- {name}")

    next_steps: List[str] = []
    if not state["age_key_exists"] or not state["bundle_exists"] or not state["local_override_exists"]:
        bootstrap_cmd = "./scripts/governance/manage-secrets.sh bootstrap --host " + host
        if args.include_optional:
            bootstrap_cmd += " --include-optional"
        if args.include_remote:
            bootstrap_cmd += " --include-remote"
        next_steps.append(bootstrap_cmd)
    elif state["missing_secrets"]:
        next_steps.append("./scripts/governance/manage-secrets.sh status --host " + host)
        for name in state["missing_secrets"]:
            next_steps.append(f"./scripts/governance/manage-secrets.sh set {name} --host {host}")
    else:
        next_steps.append("./scripts/governance/manage-secrets.sh validate --host " + host)
        next_steps.append(f"./nixos-quick-deploy.sh --host {host} --profile ai-dev")

    print("")
    print("Next steps:")
    for step in next_steps:
        print(f"- {step}")

    return 0 if state["is_ready"] else 1


def command_list(_: argparse.Namespace) -> int:
    for spec in SECRET_SPECS:
        print(f"{spec['name']}\t{spec['scope']}\t{spec['services']}")
    return 0


def command_ensure_local_config(args: argparse.Namespace) -> int:
    root = repo_root()
    host = resolve_host(root, args.host)
    primary_user = resolve_primary_user()
    paths = host_paths(root, host, primary_user)
    public_key = ensure_age_key(paths)
    ensure_sops_config(paths, public_key)
    create_or_update_local_override(paths, primary_user)
    print(f"Ensured {paths['deploy_options_local']}")
    return 0


def interactive_menu(args: argparse.Namespace) -> int:
    while True:
        print("")
        print("Secrets Manager")
        print("1. status")
        print("2. init core secrets")
        print("3. set one secret")
        print("4. validate")
        print("5. show paths")
        print("6. ensure local override")
        print("7. exit")
        choice = input("Choice: ").strip()
        if choice == "1":
            command_status(args)
        elif choice == "2":
            menu_args = argparse.Namespace(**vars(args))
            menu_args.force = False
            menu_args.include_optional = False
            menu_args.include_remote = False
            command_init(menu_args)
        elif choice == "3":
            name = input("Secret name: ").strip()
            menu_args = argparse.Namespace(**vars(args))
            menu_args.secret = name
            menu_args.value = None
            menu_args.generate = False
            command_set(menu_args)
        elif choice == "4":
            command_validate(args)
        elif choice == "5":
            command_paths(args)
        elif choice == "6":
            command_ensure_local_config(args)
        elif choice == "7":
            return 0
        else:
            print("Invalid choice.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage external SOPS secrets for the AI stack.")
    parser.add_argument("--host", help="Host config name under nix/hosts/")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show presence/absence of managed secrets.")
    subparsers.add_parser("paths", help="Show key filesystem paths used by the secrets flow.")
    subparsers.add_parser("validate", help="Check that age key, bundle, and local override are usable.")
    doctor_parser = subparsers.add_parser("doctor", help="Explain readiness and recommended next steps.")
    doctor_parser.add_argument("--include-optional", action="store_true", help="Also check optional service secrets.")
    doctor_parser.add_argument("--include-remote", action="store_true", help="Also check remote_llm_api_key readiness.")
    subparsers.add_parser("list", help="List supported managed secret names.")
    subparsers.add_parser("ensure-local-config", help="Create or refresh deploy-options.local.nix wiring.")

    init_parser = subparsers.add_parser("init", help="Create or fill missing core secrets.")
    init_parser.add_argument("--force", action="store_true", help="Regenerate existing selected secrets.")
    init_parser.add_argument("--include-optional", action="store_true", help="Also generate optional service secrets.")
    init_parser.add_argument("--include-remote", action="store_true", help="Also generate remote_llm_api_key.")

    bootstrap_parser = subparsers.add_parser("bootstrap", help="Interactive or auto-generated first-time bootstrap flow.")
    bootstrap_parser.add_argument("--force", action="store_true", help="Regenerate existing selected secrets.")
    bootstrap_parser.add_argument("--include-optional", action="store_true", help="Also manage optional service secrets.")
    bootstrap_parser.add_argument("--include-remote", action="store_true", help="Also manage remote_llm_api_key.")
    bootstrap_parser.add_argument("--mode", choices=["auto", "manual"], help="Secret input mode.")
    bootstrap_parser.add_argument("--shared-secret", help="Use one shared secret value for all selected items in manual mode.")

    set_parser = subparsers.add_parser("set", help="Set or rotate a single secret.")
    set_parser.add_argument("secret", help="Managed secret name.")
    set_group = set_parser.add_mutually_exclusive_group()
    set_group.add_argument("--value", help="Value to store. Avoid shell history for real secrets.")
    set_group.add_argument("--generate", action="store_true", help="Generate a new value automatically.")

    return parser


def normalize_global_host_flag(argv: List[str]) -> List[str]:
    normalized = list(argv)
    if "--host" not in normalized:
        return normalized
    if normalized.index("--host") == 0:
        return normalized
    if normalized[0] != "--host":
        idx = normalized.index("--host")
        if idx + 1 >= len(normalized):
            raise SystemExit("--host requires a value")
        host_args = normalized[idx : idx + 2]
        del normalized[idx : idx + 2]
        normalized = host_args + normalized
    return normalized


def main() -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_global_host_flag(sys.argv[1:]))
    if not args.command:
        if sys.stdin.isatty():
            return interactive_menu(args)
        parser.print_help()
        return 2

    commands = {
        "status": command_status,
        "paths": command_paths,
        "validate": command_validate,
        "doctor": command_doctor,
        "list": command_list,
        "ensure-local-config": command_ensure_local_config,
        "init": command_init,
        "bootstrap": command_bootstrap,
        "set": command_set,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())

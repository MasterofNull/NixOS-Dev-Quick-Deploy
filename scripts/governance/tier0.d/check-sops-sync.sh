#!/usr/bin/env bash
# tier0.d/check-sops-sync.sh — verify sops secrets declared in secrets.nix exist in SOPS file.
# Catches the class of failure where a sops.secrets entry is added to Nix but the matching
# key is never added to the encrypted SOPS file, causing sops-install-secrets to fail at boot
# and taking down the entire AI stack (ai-aidb, ai-hybrid-coordinator, etc.).
set -euo pipefail

TAG="[tier0.d/check-sops-sync]"
MODE="${1:---pre-commit}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

SECRETS_NIX="nix/modules/core/secrets.nix"
OPTIONS_NIX="nix/modules/core/options.nix"

# Locate the SOPS file. Path comes from deploy-options.local.nix (gitignored).
# Try to read it; fall back to globbing common locations.
find_sops_file() {
  local local_opts="nix/hosts/hyperd/deploy-options.local.nix"
  if [[ -f "$local_opts" ]]; then
    local path
    path=$(grep -oP "sopsFile\s*=\s*lib\.mkForce\s*\"\K[^\"]+" "$local_opts" 2>/dev/null || true)
    [[ -n "$path" && -f "$path" ]] && { echo "$path"; return; }
  fi
  # fallback: glob known location
  local glob="$HOME/.local/share/nixos-quick-deploy/secrets/*/secrets.sops.yaml"
  # shellcheck disable=SC2086
  local found; found=$(ls $glob 2>/dev/null | head -1 || true)
  [[ -n "$found" ]] && { echo "$found"; return; }
  echo ""
}

SOPS_FILE=$(find_sops_file)

if [[ -z "$SOPS_FILE" ]]; then
  echo "$TAG SKIP: SOPS file not found (external secrets path — CI environment or first bootstrap)"
  exit 0
fi

if [[ ! -f "$SOPS_FILE" ]]; then
  echo "$TAG SKIP: SOPS file path $SOPS_FILE does not exist"
  exit 0
fi

# Extract top-level YAML keys from SOPS file (excluding the 'sops' metadata key).
# This check is the "full stack down" guardrail (a secrets.nix/SOPS mismatch fails
# sops-install-secrets at boot), so it MUST NOT silently degrade when the ambient
# python lacks PyYAML. Prefer PyYAML for exactness; otherwise fall back to a pure
# line parser — SOPS files are flat top-level mappings (`secret_name: ENC[...]`
# plus a `sops:` metadata block), so unindented `key:` lines are the top keys.
if python3 -c "import yaml" 2>/dev/null; then
  sops_keys=$(python3 - "$SOPS_FILE" <<'PYEOF'
import sys, yaml
with open(sys.argv[1]) as f:
    data = yaml.safe_load(f)
keys = sorted(k for k in data.keys() if k != 'sops')
for k in keys:
    print(k)
PYEOF
  )
else
  echo "$TAG NOTE: PyYAML unavailable — using yaml-free top-level key extraction"
  sops_keys=$(grep -oE '^[A-Za-z_][A-Za-z0-9_]*:' "$SOPS_FILE" | sed 's/:$//' | grep -vx 'sops' | sort -u)
fi

# Build a mapping of option attribute name → default string value from options.nix.
# e.g. "aidbApiKey" -> "aidb_api_key"
names_map=$(python3 - "$OPTIONS_NIX" <<'PYEOF'
import sys, re
with open(sys.argv[1]) as f:
    content = f.read()
# Match:  attrName = lib.mkOption { ... default = "value"; ... };
for m in re.finditer(
    r'(\w+)\s*=\s*lib\.mkOption\s*\{[^}]*?default\s*=\s*"([^"]+)"',
    content, re.DOTALL
):
    attr, val = m.group(1), m.group(2)
    print(f"{attr}={val}")
PYEOF
)

# Extract sec.names.X references from secrets.nix.
nix_attrs=$(grep -oP '"\$\{sec\.names\.\K[^}]+' "$SECRETS_NIX" | sort -u)

if [[ -z "$nix_attrs" ]]; then
  echo "$TAG PASS: no sec.names references found in secrets.nix"
  exit 0
fi

# Resolve each attribute name to its string value.
nix_keys=()
unresolved=()
while IFS= read -r attr; do
  val=$(echo "$names_map" | grep -E "^${attr}=" | cut -d= -f2 || true)
  if [[ -n "$val" ]]; then
    nix_keys+=("$val")
  else
    unresolved+=("$attr")
  fi
done <<< "$nix_attrs"

# Warn about unresolvable names (shouldn't happen with well-structured options.nix).
if [[ ${#unresolved[@]} -gt 0 ]]; then
  echo "$TAG WARN: could not resolve sec.names.${unresolved[*]} — skipping those entries"
fi

# Check every required Nix key exists in the SOPS file.
failures=()
for key in "${nix_keys[@]}"; do
  if ! echo "$sops_keys" | grep -qx "$key"; then
    failures+=("$key")
  fi
done

if [[ ${#failures[@]} -gt 0 ]]; then
  echo "$TAG FAIL: the following secrets are declared in secrets.nix but MISSING from $SOPS_FILE:" >&2
  for k in "${failures[@]}"; do
    echo "$TAG   - $k" >&2
  done
  echo "$TAG" >&2
  echo "$TAG Fix: SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt sops $SOPS_FILE" >&2
  echo "$TAG      Add the missing key(s), save, and re-run the gate." >&2
  echo "$TAG" >&2
  echo "$TAG This mismatch causes sops-install-secrets to fail at boot, leaving" >&2
  echo "$TAG /run/secrets/ absent and taking down ai-aidb + ai-hybrid-coordinator." >&2
  exit 1
fi

# Also warn if SOPS file has extra keys not declared in Nix (stale entries).
stale=()
while IFS= read -r key; do
  if ! printf '%s\n' "${nix_keys[@]}" | grep -qx "$key"; then
    stale+=("$key")
  fi
done <<< "$sops_keys"

if [[ ${#stale[@]} -gt 0 ]]; then
  echo "$TAG WARN: SOPS file has keys not declared in secrets.nix (stale/unused): ${stale[*]}"
fi

echo "$TAG PASS: SOPS file keys match secrets.nix declarations (${#nix_keys[@]} required, ${#stale[@]} stale)"
exit 0

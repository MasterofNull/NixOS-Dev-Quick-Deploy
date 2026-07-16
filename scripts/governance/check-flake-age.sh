#!/usr/bin/env bash
# check-flake-age.sh — fail closed when a locked flake input is under 48 hours old.

set -euo pipefail

readonly MIN_AGE_HOURS=48
readonly MIN_AGE_SECONDS=$((MIN_AGE_HOURS * 3600))
# JSON numbers above this boundary cannot be represented as exact integers by
# jq. Reject them before classification so no attacker-controlled timestamp is
# ever passed to Bash arithmetic.
readonly MAX_SAFE_TIMESTAMP=9007199254740991

fail() {
    printf 'RESULT status=fail code=%s\n' "$1"
    exit 1
}

printf 'TEMPORAL_SUPPLY_CHAIN_AUDIT min_age_hours=%d mode=offline\n' "$MIN_AGE_HOURS"

command -v nix >/dev/null 2>&1 || fail "dependency_unavailable_nix"
command -v jq >/dev/null 2>&1 || fail "dependency_unavailable_jq"

now=$(date +%s) || fail "clock_unavailable"
[[ "$now" =~ ^[0-9]+$ ]] || fail "clock_invalid"

# --offline is mandatory: this guard audits locally available lock metadata and
# must never fetch or refresh supply-chain state while making an admission decision.
if ! metadata=$(nix flake metadata --offline --json . 2>/dev/null); then
    fail "metadata_unavailable"
fi
[[ -n "$metadata" ]] || fail "metadata_invalid"

# Treat metadata as untrusted. Validate every timestamp-bearing locked input and
# terminal-safe input name before emitting input-derived data. A structurally valid,
# nonempty lock graph with no timestamp-bearing locked inputs (for example, a
# path-only root) is a vacuous pass (`checked=0`), not malformed.
if ! inputs=$(jq -r \
    --argjson now "$now" \
    --argjson min_age_seconds "$MIN_AGE_SECONDS" \
    --argjson max_safe_timestamp "$MAX_SAFE_TIMESTAMP" '
    .locks as $locks
    | $locks.nodes as $nodes
    | $locks.root as $root
    | if ($locks | type) != "object"
        or ($nodes | type) != "object"
        or ($nodes | length) == 0
        or ($root | type) != "string"
        or ($root | test("^[A-Za-z0-9._+-]{1,128}$") | not)
        or ($nodes | has($root) | not)
        or ($nodes[$root] | type) != "object"
        or any($nodes | to_entries[]; (.value | type) != "object")
        or any($nodes | to_entries[];
          .key != $root
          and (
            (.value | has("locked") | not)
            or .value.locked == null
            or (.value.locked | type) != "object"
          )
        )
      then error("invalid lock graph")
      else
        [$nodes | to_entries[] | select(.value.locked? != null)] as $locked_entries
        | if any($locked_entries[];
            (.key | type) != "string"
            or (.key | test("^[A-Za-z0-9._+-]{1,128}$") | not)
            or (.value.locked | type) != "object"
            or (
              (.value.locked | has("lastModified") | not)
              and (
                .value.locked.type? != "path"
                or (.value.locked.path? | type) != "string"
              )
            )
          ) then error("invalid locked input")
          else
            [$locked_entries[] | select(.value.locked | has("lastModified"))] as $entries
            | if any($entries[];
                (.value.locked.lastModified | type) != "number"
                or (.value.locked.lastModified | floor) != .value.locked.lastModified
                or .value.locked.lastModified < 0
                or .value.locked.lastModified > $max_safe_timestamp
              ) then error("invalid timestamp")
              else $entries | sort_by(.key)[]
                | .value.locked.lastModified as $modified
                | ($now - $modified) as $age_seconds
                | [
                    .key,
                    (if $modified > $now then "future"
                     elif $age_seconds < $min_age_seconds then "fresh"
                     else "aged"
                     end),
                    (($age_seconds / 3600) | floor | tostring)
                  ]
                | @tsv
              end
          end
      end
' <<<"$metadata" 2>/dev/null); then
    fail "metadata_invalid"
fi

violations=0
checked=0
while IFS=$'\t' read -r name classification age_hours; do
    [[ -n "$name" ]] || continue
    [[ "$age_hours" =~ ^-?[0-9]+$ ]] || fail "metadata_invalid"
    checked=$((checked + 1))

    if [[ "$classification" == "future" ]]; then
        printf 'FAIL input=%s code=timestamp_in_future\n' "$name"
        violations=$((violations + 1))
        continue
    fi

    if [[ "$classification" == "fresh" ]]; then
        printf 'FAIL input=%s code=input_too_fresh age_hours=%d min_age_hours=%d\n' \
            "$name" "$age_hours" "$MIN_AGE_HOURS"
        violations=$((violations + 1))
    elif [[ "$classification" == "aged" ]]; then
        printf 'PASS input=%s age_hours=%d\n' "$name" "$age_hours"
    else
        fail "metadata_invalid"
    fi
done <<<"$inputs"

if (( violations > 0 )); then
    printf 'RESULT status=fail code=temporal_policy_violation checked=%d violations=%d\n' \
        "$checked" "$violations"
    exit 1
fi

printf 'RESULT status=pass checked=%d violations=0\n' "$checked"

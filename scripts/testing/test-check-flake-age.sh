#!/usr/bin/env bash
# Focused regression tests for the offline temporal supply-chain guard.

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
guard="$repo_root/scripts/governance/check-flake-age.sh"
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT
mkdir -p "$tmp_dir/bin"

cat >"$tmp_dir/bin/nix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >"$FAKE_NIX_ARGS"
if [[ "${FAKE_NIX_EXIT:-0}" != "0" ]]; then
    exit "$FAKE_NIX_EXIT"
fi
printf '%s\n' "${FAKE_METADATA:-}"
EOF
chmod +x "$tmp_dir/bin/nix"

cat >"$tmp_dir/bin/date" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
[[ "$*" == "+%s" ]]
printf '%s\n' "$FAKE_NOW"
EOF
chmod +x "$tmp_dir/bin/date"

assert_contains() {
    local output=$1 expected=$2
    [[ "$output" == *"$expected"* ]] || {
        printf 'FAIL expected output to contain: %s\nOUTPUT:\n%s\n' "$expected" "$output" >&2
        exit 1
    }
}

assert_not_contains() {
    local output=$1 unexpected=$2
    [[ "$output" != *"$unexpected"* ]] || {
        printf 'FAIL output unexpectedly contained: %s\nOUTPUT:\n%s\n' "$unexpected" "$output" >&2
        exit 1
    }
}

run_guard() {
    local metadata=$1 fake_exit=${2:-0} test_path=${3:-"$tmp_dir/bin:$PATH"}
    set +e
    GUARD_OUTPUT=$(PATH="$test_path" \
        FAKE_NIX_ARGS="$tmp_dir/nix-args" \
        FAKE_NIX_EXIT="$fake_exit" \
        FAKE_METADATA="$metadata" \
        FAKE_NOW="$now" \
        "${BASH:-bash}" "$guard" 2>&1)
    GUARD_STATUS=$?
    set -e
}

assert_status() {
    local expected=$1
    [[ "$GUARD_STATUS" -eq "$expected" ]] || {
        printf 'FAIL expected status %s, got %s\nOUTPUT:\n%s\n' "$expected" "$GUARD_STATUS" "$GUARD_OUTPUT" >&2
        exit 1
    }
}

locked_metadata() {
    local name=$1 timestamp=$2
    printf '{"locks":{"nodes":{"root":{},"%s":{"locked":{"lastModified":%s}}},"root":"root"}}' "$name" "$timestamp"
}

bash -n "$guard"

now=$(date +%s)
exact=$((now - (48 * 3600)))
one_second_fresh=$((exact + 1))
future=$((now + 1))

run_guard "$(locked_metadata nixpkgs "$exact")"
assert_status 0
assert_contains "$GUARD_OUTPUT" "PASS input=nixpkgs age_hours=48"
assert_contains "$GUARD_OUTPUT" "RESULT status=pass checked=1 violations=0"
[[ "$(<"$tmp_dir/nix-args")" == "flake metadata --offline --json ." ]] || {
    printf 'FAIL guard did not use the exact offline metadata invocation\n' >&2
    exit 1
}

run_guard "$(locked_metadata nixpkgs "$one_second_fresh")"
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=input_too_fresh"

run_guard "$(locked_metadata nixpkgs "$future")"
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=timestamp_in_future"

for invalid_timestamp in '-1' '1.5' '"123"' 'true' '9223372036854775808'; do
    run_guard "$(locked_metadata nixpkgs "$invalid_timestamp")"
    assert_status 1
    assert_contains "$GUARD_OUTPUT" "code=metadata_invalid"
done
run_guard '{"locks":{"nodes":{"root":{},"nixpkgs":{"locked":{}}},"root":"root"}}'
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=metadata_invalid"

run_guard "$(locked_metadata nixpkgs '9007199254740991')"
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=timestamp_in_future"
run_guard "$(locked_metadata nixpkgs '9007199254740992')"
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=metadata_invalid"

run_guard "$(locked_metadata '../unsafe' "$exact")"
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=metadata_invalid"
oversized_name="a$(printf '%0128d' 0)"
run_guard "$(locked_metadata "$oversized_name" "$exact")"
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=metadata_invalid"

run_guard '{"locks":{"nodes":{"root":{"inputs":{}},"local":{"locked":{"type":"path","path":"/workspace"}}},"root":"root"}}'
assert_status 0
assert_contains "$GUARD_OUTPUT" "RESULT status=pass checked=0 violations=0"

for invalid_graph in \
    '{"locks":{"nodes":{},"root":"root"}}' \
    '{"locks":{"nodes":{"root":{}}}}' \
    '{"locks":{"nodes":{"root":{}},"root":"../unsafe"}}' \
    '{"locks":{"nodes":{"other":{}},"root":"root"}}' \
    '{"locks":{"nodes":{"root":{},"scalar":42},"root":"root"}}' \
    '{"locks":{"nodes":{"root":{},"empty":{}},"root":"root"}}' \
    '{"locks":{"nodes":{"root":{},"missing":{"original":{"type":"github"}}},"root":"root"}}' \
    '{"locks":{"nodes":{"root":{},"null-lock":{"locked":null}},"root":"root"}}'; do
    run_guard "$invalid_graph"
    assert_status 1
    assert_contains "$GUARD_OUTPUT" "code=metadata_invalid"
done

run_guard "{\"locks\":{\"nodes\":{\"root\":{},\"zeta\":{\"locked\":{\"lastModified\":$one_second_fresh}},\"alpha\":{\"locked\":{\"lastModified\":$exact}},\"middle\":{\"locked\":{\"lastModified\":$future}}},\"root\":\"root\"}}"
assert_status 1
alpha_line=$(grep -n '^PASS input=alpha ' <<<"$GUARD_OUTPUT" | cut -d: -f1)
middle_line=$(grep -n '^FAIL input=middle ' <<<"$GUARD_OUTPUT" | cut -d: -f1)
zeta_line=$(grep -n '^FAIL input=zeta ' <<<"$GUARD_OUTPUT" | cut -d: -f1)
(( alpha_line < middle_line && middle_line < zeta_line )) || {
    printf 'FAIL multi-input output is not in canonical name order\n%s\n' "$GUARD_OUTPUT" >&2
    exit 1
}
assert_contains "$GUARD_OUTPUT" "checked=3 violations=2"

run_guard '{"locks":'
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=metadata_invalid"
run_guard '' 0
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=metadata_invalid"
run_guard '' 1
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=metadata_unavailable"

bash_bin=$(command -v bash)
date_bin=$(command -v date)
jq_bin=$(command -v jq)
mkdir -p "$tmp_dir/no-nix" "$tmp_dir/no-jq"
ln -s "$bash_bin" "$tmp_dir/no-nix/bash"
ln -s "$date_bin" "$tmp_dir/no-nix/date"
ln -s "$jq_bin" "$tmp_dir/no-nix/jq"
run_guard '{"locks":{"nodes":{"root":{}},"root":"root"}}' 0 "$tmp_dir/no-nix"
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=dependency_unavailable_nix"

ln -s "$bash_bin" "$tmp_dir/no-jq/bash"
ln -s "$date_bin" "$tmp_dir/no-jq/date"
ln -s "$tmp_dir/bin/nix" "$tmp_dir/no-jq/nix"
run_guard '{"locks":{"nodes":{"root":{}},"root":"root"}}' 0 "$tmp_dir/no-jq"
assert_status 1
assert_contains "$GUARD_OUTPUT" "code=dependency_unavailable_jq"
assert_not_contains "$GUARD_OUTPUT" "command not found"

printf 'PASS test-check-flake-age\n'

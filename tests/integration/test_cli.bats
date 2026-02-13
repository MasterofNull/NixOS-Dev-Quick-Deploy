#!/usr/bin/env bats

setup() {
  ROOT_DIR="${BATS_TEST_DIRNAME}/../.."
}

@test "nixos-quick-deploy --help works" {
  run bash -c "cd '${ROOT_DIR}' && ./nixos-quick-deploy.sh --help"
  [ "$status" -eq 0 ]
}

@test "nixos-quick-deploy --list-phases includes Phase 1" {
  run bash -c "cd '${ROOT_DIR}' && ./nixos-quick-deploy.sh --list-phases"
  [ "$status" -eq 0 ]
  [[ "$output" =~ Phase[[:space:]]+1: ]]
}

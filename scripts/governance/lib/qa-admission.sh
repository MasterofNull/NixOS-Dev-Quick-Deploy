#!/usr/bin/env bash
# Machine-wide admission control for the heavy tier0 QA phase-0 step.
# Parallel worktree gate runs + local llama.cpp reviews push load high enough that
# timing-sensitive aq-qa checks (0.10.50, 0.10.66) time out; those are false failures.
# Waiting for a slot instead of failing removes the producer of the false failures.
# Usage: source this file, then `qa_admission_acquire` ... `qa_admission_release`.
# Env: AQ_TIER0_QA_SLOTS (default 1), AQ_TIER0_QA_WAIT_S (default 3600),
#      AQ_TIER0_QA_LOCK_DIR (override; tests). Lock dir is per-user and NOT
#      repo-relative, so it is shared by every worktree and aq-gate-checkout snapshot.

QA_ADMISSION_FD=""

qa_admission_dir() {
  local dir="${AQ_TIER0_QA_LOCK_DIR:-}"
  if [[ -z "${dir}" ]]; then
    if [[ -n "${XDG_RUNTIME_DIR:-}" && -d "${XDG_RUNTIME_DIR}" ]]; then
      dir="${XDG_RUNTIME_DIR}/aq-tier0-qa"
    else
      dir="/tmp/aq-tier0-qa-$(id -u)"
    fi
  fi
  mkdir -p "${dir}" && chmod 0700 "${dir}" || return 1
  # /tmp fallback: refuse a dir another user pre-created.
  [[ -O "${dir}" ]] || return 1
  printf '%s\n' "${dir}"
}

qa_admission_acquire() {
  local slots="${AQ_TIER0_QA_SLOTS:-1}" max_wait="${AQ_TIER0_QA_WAIT_S:-3600}"
  [[ "${slots}" =~ ^[1-9][0-9]*$ ]] || slots=1
  [[ "${max_wait}" =~ ^[0-9]+$ ]] || max_wait=3600
  local dir i fd start now waited=0 announced=0 holders
  dir="$(qa_admission_dir)" || { echo "[tier0] admission: cannot prepare lock dir" >&2; return 2; }
  start=$(date +%s)
  while :; do
    for ((i = 0; i < slots; i++)); do
      exec {fd}>>"${dir}/slot-${i}.lock" || return 2
      if flock -n "${fd}"; then
        : >"${dir}/slot-${i}.lock"
        printf '%s\n' "$$" >&"${fd}"
        QA_ADMISSION_FD="${fd}"
        now=$(date +%s)
        if ((announced)); then
          echo "[tier0] QA slot ${i} acquired after $((now - start))s wait" >&2
        fi
        return 0
      fi
      exec {fd}>&-
    done
    now=$(date +%s)
    waited=$((now - start))
    if ((waited >= max_wait)); then
      echo "[tier0] admission timeout: no QA slot after ${waited}s (AQ_TIER0_QA_WAIT_S=${max_wait}); not a check failure" >&2
      return 3
    fi
    if ((!announced)); then
      holders="$(cat "${dir}"/slot-*.lock 2>/dev/null | tr '\n' ' ')"
      echo "[tier0] waiting for QA slot (held by pid ${holders:-unknown}; slots=${slots}, max wait ${max_wait}s)" >&2
      announced=1
    fi
    sleep "${AQ_TIER0_QA_POLL_S:-2}"
  done
}

qa_admission_release() {
  if [[ -n "${QA_ADMISSION_FD}" ]]; then
    exec {QA_ADMISSION_FD}>&-
    QA_ADMISSION_FD=""
  fi
}

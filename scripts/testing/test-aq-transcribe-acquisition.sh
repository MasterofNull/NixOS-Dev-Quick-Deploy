#!/usr/bin/env bash
# Slice 1 (acquisition + timed transcript) tests for scripts/ai/aq-transcribe.
# Hermetic: stub yt-dlp/ffmpeg/whisper/whisper-cli/systemd-run/power-gate on a minimal PATH,
# no network, no real media. Root cause under test: a 429 caption failure (`|| true`) silently
# fell through to CPU Whisper that ran 5 h at ~10 cores (2026-11-18).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/ai/aq-transcribe"
HELPER="$ROOT/scripts/ai/lib/video_frames.py"
T="$(mktemp -d)"
[[ -n "${KEEP_T:-}" ]] || trap 'rm -rf "$T"' EXIT
fails=0; passes=0
ok() { if [[ "$2" == 1 ]]; then passes=$((passes+1)); echo "PASS $1"; else fails=$((fails+1)); echo "FAIL $1"; fi; }
eq() { [[ "$2" == "$3" ]] && ok "$1" 1 || { ok "$1 (got '$2' want '$3')" 0; }; }

# ---- hermetic tool dir ------------------------------------------------------------------
TOOLS="$T/tools"; STUBS="$T/stubs"; mkdir -p "$TOOLS" "$STUBS"
for b in bash sh env python3 sha256sum nice ionice timeout mkdir mv cp rm cat sed awk find sort head tail date \
         mktemp flock tr wc dirname basename ls touch printf sleep grep kill chmod ln stat du uniq cut true; do
  p="$(command -v "$b" 2>/dev/null)" && [[ -x "$p" ]] && ln -sf "$p" "$TOOLS/$b"
done
export LOG="$T/log"; mkdir -p "$LOG"

mk() { printf '#!/bin/sh\n%s\n' "$2" > "$STUBS/$1"; chmod +x "$STUBS/$1"; }
mk yt-dlp '
echo "$*" >> "$LOG/ytdlp.argv"
kind=media
for a; do case "$a" in --get-id) kind=id;; --dump-json) kind=meta;; --skip-download) kind=caps;; esac; done
echo "$kind" >> "$LOG/ytdlp.kinds"
cnt=$(grep -c "^$kind\$" "$LOG/ytdlp.kinds")
n=${STUB_FAIL_N:-0}
if [ "$STUB_429_ON" = "$kind" ] && [ "$cnt" -le "$n" ]; then
  echo "ERROR: HTTP Error 429: Too Many Requests" >&2; exit 1; fi
if [ "$STUB_ERR_ON" = "$kind" ]; then echo "ERROR: boom" >&2; exit 1; fi
case $kind in
 id) echo "${STUB_ID:-vid123}";;
 meta) if [ "$STUB_AVAIL" = MISSING ]; then echo "{\"id\":\"${STUB_ID:-vid123}\",\"duration\":60}"
       else echo "{\"id\":\"${STUB_ID:-vid123}\",\"duration\":60,\"availability\":\"${STUB_AVAIL:-public}\"}"; fi;;
 caps) want=--write-subs; [ "$STUB_CAPS" = auto ] && want=--write-auto-subs
       case "$STUB_CAPS" in creator|auto) case " $* " in *" $want "*)
         o=""; p=""; for a; do [ "$p" = -o ] && o=$a; p=$a; done
         d=${o%/*}; cp "$STUB_VTT" "$d/${STUB_ID:-vid123}.en.vtt";; esac;; esac;;
 media) o=""; p=""; for a; do [ "$p" = -o ] && o=$a; p=$a; done
        echo wavdata > "${o%/*}/audio.wav";;
esac'
mk ffmpeg 'echo "ffmpeg $*" >> "$LOG/ffmpeg.log"; for a; do l=$a; done; echo wav > "$l"'
mk whisper 'echo "whisper $*" >> "$LOG/whisper.log"
while [ $# -gt 0 ]; do [ "$1" = --output_dir ] && o=$2; shift; done
sleep "${STUB_WHISPER_SLEEP:-0}"
cat > "$o/audio.json" <<J
{"text":"hello world second line third line","segments":[
{"start":600.0,"end":602.0,"text":" hello world"},{"start":602.0,"end":604.01,"text":" second line"},{"start":604.01,"end":606.0,"text":" third line"}]}
J'
mk whisper-cli 'echo "whisper-cli $*" >> "$LOG/whisper.log"
while [ $# -gt 0 ]; do [ "$1" = -of ] && o=$2; shift; done
sleep "${STUB_WHISPER_SLEEP:-0}"
cat > "$o.json" <<J
{"transcription":[{"offsets":{"from":600000,"to":602000},"text":" hello world"},{"offsets":{"from":602000,"to":604010},"text":" second line"},{"offsets":{"from":604010,"to":606000},"text":" third line"}]}
J'
mk systemd-run 'echo "systemd-run $*" >> "$LOG/quota.log"; while [ "$1" != -- ]; do shift; done; shift; exec "$@"'
mk gate 'echo "gate $*" >> "$LOG/gate.log"; exit "${STUB_GATE_RC:-0}"'
mk sleepstub 'echo "$*" >> "$LOG/sleeps.log"'

cat > "$T/fixture.vtt" <<'V'
WEBVTT

00:10:00.000 --> 00:10:02.000
hello world

00:10:02.000 --> 00:10:04.000
hello world
second line

00:10:04.000 --> 00:10:04.010
hello world
second line

00:10:04.010 --> 00:10:06.000
second line
<c>third line</c>
V
printf 'fake media bytes\n' > "$T/fixture.mp4"
export STUB_VTT="$T/fixture.vtt"

# run <name> [extra env as VAR=val ...] -- args...  -> sets RC, OUTD, CACHE
n=0
run() {
  n=$((n+1)); OUTD="$T/out$n"; CACHE="${CACHE_OVERRIDE:-$T/cache}"; rm -f "$LOG"/*.argv "$LOG"/*.kinds "$LOG"/*.log 2>/dev/null
  local envs=()
  while [[ "$1" != "--" ]]; do envs+=("$1"); shift; done; shift
  RC=0
  env -i PATH="${RUN_PATH:-$STUBS:$TOOLS}" HOME="$T/home" TMPDIR="$T" LOG="$LOG" STUB_VTT="$STUB_VTT" \
    AQ_TRANSCRIBE_CACHE="$CACHE" AQ_TRANSCRIBE_POWER_GATE="${GATE:-$STUBS/gate}" AQ_TRANSCRIBE_SLEEP="$STUBS/sleepstub" \
    AQ_TRANSCRIBE_DEFER_LOG="$T/defer.jsonl" "${envs[@]}" \
    bash "$SCRIPT" "$@" --out "$OUTD" >"$T/last.out" 2>"$T/last.err" || RC=$?
}
mkdir -p "$T/home"
count() { local c; c="$(grep -c -e "$2" "$LOG/$1" 2>/dev/null)"; echo "${c:-0}"; }
called() { [[ -s "$LOG/$1" ]] && echo 1 || echo 0; }
segjson() { python3 -I -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["schema"],len(d["segments"]),d["segments"][0]["start_s"],d["segments"][-1]["end_s"])' "$1"; }
URL="https://www.youtube.com/watch?v=vid123"

# ---- 1. local VTT, no whisper/ffmpeg/yt-dlp on PATH --------------------------------------
RUN_PATH="$TOOLS" run -- "$T/fixture.mp4" --subs "$T/fixture.vtt"
eq "1 local vtt exit 0" "$RC" 0
eq "1 SOURCE creator-subtitles" "$(cat "$OUTD/SOURCE.txt")" creator-subtitles
eq "1 nonzero timestamps + rolling captions collapsed (3 segs, 600..606)" "$(segjson "$OUTD/transcript.json")" "aq-segments/1 3 600.0 606.0"
eq "1 rolling cue extends previous end to 604.01" "$(python3 -I -c 'import json,sys;print(json.load(open(sys.argv[1]))["segments"][1]["end_s"])' "$OUTD/transcript.json")" 604.01
eq "1 tags stripped" "$(grep -c '<c>' "$OUTD/transcript.txt")" 0

# adjacent VTT is picked up without --subs
cp "$T/fixture.mp4" "$T/adj.mp4"; cp "$T/fixture.vtt" "$T/adj.vtt"
RUN_PATH="$TOOLS" run -- "$T/adj.mp4"
eq "1b adjacent vtt exit 0" "$RC" 0

# ---- 2. caption-only URL preflight: no whisper on PATH ----------------------------------
mkdir -p "$T/ytonly"; ln -sf "$STUBS/yt-dlp" "$T/ytonly/yt-dlp"
RUN_PATH="$T/ytonly:$TOOLS" run STUB_CAPS=creator -- "$URL"
eq "2 captioned URL without whisper exit 0" "$RC" 0
eq "2 creator-subtitles" "$(cat "$OUTD/SOURCE.txt")" creator-subtitles
RUN_PATH="$T/ytonly:$TOOLS" run STUB_CAPS=auto STUB_ID=autoid -- "$URL"
eq "2 auto-captions fallback exit 0" "$RC" 0
eq "2 auto SOURCE" "$(cat "$OUTD/SOURCE.txt")" auto-captions
eq "2 creator tried before auto" "$(grep -c -- '--write-subs' "$LOG/ytdlp.argv")" 1
# argv hygiene: config/cookies disabled on every call
eq "2 --ignore-config on every yt-dlp call" "$(grep -vc -- '--ignore-config' "$LOG/ytdlp.argv")" 0
eq "2 --no-cookies on every call" "$(grep -vc -- '--no-cookies ' "$LOG/ytdlp.argv")" 0
eq "2 --retries 0 on every call" "$(grep -vc -- '--retries 0' "$LOG/ytdlp.argv")" 0

# ---- 3. 429 is terminal at every step; shared 3-retry budget -----------------------------
for step in meta caps media; do
  caps=creator; [[ $step == media ]] && caps=none
  run STUB_429_ON=$step STUB_FAIL_N=99 STUB_CAPS=$caps STUB_ID="r$step" -- "$URL"
  eq "3 429 on $step -> exit 4" "$RC" 4
  eq "3 429 on $step -> 3 backoffs (30 90 270)" "$(tr '\n' ' ' < "$LOG/sleeps.log")" "30 90 270 "
  eq "3 429 on $step -> 4 attempts of that call" "$(count ytdlp.kinds "^$step\$")" 4
  eq "3 429 on $step -> whisper never run" "$(called whisper.log)" 0
done
run STUB_429_ON=caps STUB_FAIL_N=99 STUB_CAPS=creator STUB_ID=r429allow -- "$URL" --allow-whisper-on-error
eq "3 429 with --allow-whisper-on-error still exit 4" "$RC" 4
eq "3 429 with --allow-whisper-on-error -> whisper never run" "$(called whisper.log)" 0
run STUB_429_ON=meta STUB_FAIL_N=2 STUB_CAPS=creator STUB_ID=sh1 -- "$URL"
eq "3 two 429s then success -> exit 0" "$RC" 0
# shared counter: metadata uses 2 retries; a 2-failure caption step then needs 2 more => budget (3) exhausted
mk yt-dlp '
echo "$*" >> "$LOG/ytdlp.argv"
kind=media
for a; do case "$a" in --get-id) kind=id;; --dump-json) kind=meta;; --skip-download) kind=caps;; esac; done
echo "$kind" >> "$LOG/ytdlp.kinds"
cnt=$(grep -c "^$kind\$" "$LOG/ytdlp.kinds")
case "$kind" in meta|caps) if [ "$cnt" -le 2 ]; then echo "HTTP Error 429: Too Many Requests" >&2; exit 1; fi;; esac
case $kind in meta) echo "{\"id\":\"shared1\",\"duration\":60,\"availability\":\"public\"}";; esac
exit 0'
run -- "$URL"
eq "3 shared budget across calls -> exit 4" "$RC" 4
eq "3 shared budget -> exactly 3 sleeps total" "$(wc -l < "$LOG/sleeps.log")" 3

# restore the full-featured yt-dlp stub by re-sourcing (rewrite same body)
mk yt-dlp '
echo "$*" >> "$LOG/ytdlp.argv"
kind=media
for a; do case "$a" in --get-id) kind=id;; --dump-json) kind=meta;; --skip-download) kind=caps;; esac; done
echo "$kind" >> "$LOG/ytdlp.kinds"
cnt=$(grep -c "^$kind\$" "$LOG/ytdlp.kinds")
n=${STUB_FAIL_N:-0}
if [ "$STUB_429_ON" = "$kind" ] && [ "$cnt" -le "$n" ]; then
  echo "ERROR: HTTP Error 429: Too Many Requests" >&2; exit 1; fi
if [ "$STUB_ERR_ON" = "$kind" ]; then echo "ERROR: boom" >&2; exit 1; fi
case $kind in
 id) echo "${STUB_ID:-vid123}";;
 meta) if [ "$STUB_AVAIL" = MISSING ]; then echo "{\"id\":\"${STUB_ID:-vid123}\",\"duration\":60}"
       else echo "{\"id\":\"${STUB_ID:-vid123}\",\"duration\":60,\"availability\":\"${STUB_AVAIL:-public}\"}"; fi;;
 caps) want=--write-subs; [ "$STUB_CAPS" = auto ] && want=--write-auto-subs
       case "$STUB_CAPS" in creator|auto) case " $* " in *" $want "*)
         o=""; p=""; for a; do [ "$p" = -o ] && o=$a; p=$a; done
         d=${o%/*}; cp "$STUB_VTT" "$d/${STUB_ID:-vid123}.en.vtt";; esac;; esac;;
 media) o=""; p=""; for a; do [ "$p" = -o ] && o=$a; p=$a; done
        echo wavdata > "${o%/*}/audio.wav";;
esac'

# ---- 4. non-429 caption error ----------------------------------------------------------
run STUB_ERR_ON=caps STUB_CAPS=none STUB_ID=err1 -- "$URL"
eq "4 non-429 caption error -> exit 1 (no silent Whisper)" "$RC" 1
eq "4 whisper not run" "$(called whisper.log)" 0
run STUB_ERR_ON=caps STUB_CAPS=none STUB_ID=err2 -- "$URL" --allow-whisper-on-error
eq "4 --allow-whisper-on-error permits Whisper on non-429 error" "$RC" 0
eq "4 whisper ran" "$(called whisper.log)" 1

# ---- 5. whisper path: gate, quota, cache reuse, both backends --------------------------
run STUB_CAPS=none STUB_ID=wh1 -- "$URL"
eq "5 no captions -> whisper exit 0" "$RC" 0
OPENAI_OUT="$OUTD"
eq "5 SOURCE whisper-asr" "$(cat "$OUTD/SOURCE.txt")" "whisper-asr(model=small)"
eq "5 whisper json normalised to aq-segments/1" "$(segjson "$OUTD/transcript.json")" "aq-segments/1 3 600.0 606.0"
eq "5 gate consulted with task + defer log" "$(grep -c -- '--task aq-transcribe-whisper --defer-log' "$LOG/gate.log")" 1
eq "5 whisper ran under systemd-run quota (CPUQuota+MemoryMax+TasksMax)" "$(grep -cE 'CPUQuota=[0-9]+% -p MemoryMax=[0-9]+ -p TasksMax=[0-9]+' "$LOG/quota.log")" 1
eq "5 media download passes a derived --max-filesize" "$(grep -cE -- '--max-filesize [0-9]+' "$LOG/ytdlp.argv")" 1
ls "$T/cache/wh1/transcript/" | grep -q 'transcript.raw.openai.json' && ok "5 raw openai json kept" 1 || ok "5 raw openai json kept" 0
[[ -f "$T/cache/wh1/stages/transcript.done" ]] && ok "5 .done written" 1 || ok "5 .done written" 0
run STUB_CAPS=none STUB_ID=wh1 -- "$URL"
eq "5 rerun cache hit: whisper not called" "$(called whisper.log)" 0
eq "5 rerun: exactly one metadata call (never cached)" "$(count ytdlp.kinds '^meta$')" 1
eq "5 rerun: no --get-id call (id comes from the metadata call)" "$(count ytdlp.argv '--get-id')" 0
eq "5 rerun: captions answered from cache" "$(count ytdlp.kinds '^caps$')" 0
eq "5 rerun cache hit: no media download" "$(count ytdlp.kinds '^media$')" 0
eq "5 rerun cache hit: gate not consulted" "$(called gate.log)" 0
mkdir -p "$T/cpponly"; ln -sf "$STUBS/whisper-cli" "$T/cpponly/whisper-cli"
for s in yt-dlp systemd-run; do ln -sf "$STUBS/$s" "$T/cpponly/$s"; done
RUN_PATH="$T/cpponly:$TOOLS" run STUB_CAPS=none STUB_ID=cpp1 -- "$URL"
eq "5 whisper-cli backend exit 0" "$RC" 0
eq "5 cpp json normalised identically (ms offsets -> s)" "$(segjson "$OUTD/transcript.json")" "aq-segments/1 3 600.0 606.0"
a="$(python3 -I -c 'import json,sys;print([(s["start_s"],s["end_s"],s["text"]) for s in json.load(open(sys.argv[1]))["segments"]])' "$OUTD/transcript.json")"
b="$(python3 -I -c 'import json,sys;print([(s["start_s"],s["end_s"],s["text"]) for s in json.load(open(sys.argv[1]))["segments"]])' "$OPENAI_OUT/transcript.json")"
eq "5 openai and cpp segments identical" "$a" "$b"
run STUB_CAPS=creator STUB_ID=force1 -- "$URL" --force-whisper
eq "5 --force-whisper skips captions" "$(count ytdlp.kinds '^caps$')" 0

# ---- 6. Whisper timeout = failure (exit 6), both backends ------------------------------
for be in whisper whisper-cli; do
  mkdir -p "$T/to-$be"; ln -sf "$STUBS/$be" "$T/to-$be/$be"
  for s in yt-dlp systemd-run; do ln -sf "$STUBS/$s" "$T/to-$be/$s"; done
  RUN_PATH="$T/to-$be:$TOOLS" run STUB_CAPS=none STUB_ID="to$be" STUB_WHISPER_SLEEP=5 AQ_TRANSCRIBE_WHISPER_BUDGET=1 -- "$URL"
  eq "6 $be timeout -> exit 6" "$RC" 6
  [[ ! -e "$OUTD/transcript.json" ]] && ok "6 $be no transcript.json in out" 1 || ok "6 $be no transcript.json in out" 0
  [[ ! -e "$T/cache/to$be/transcript" && ! -e "$T/cache/to$be/stages/transcript.done" ]] && ok "6 $be no cached transcript/.done" 1 || ok "6 $be no cached transcript/.done" 0
done
sleep 5  # let orphaned stub sleeps exit before cleanup

# ---- 7. gate fail-closed ---------------------------------------------------------------
run STUB_GATE_RC=5 STUB_CAPS=none STUB_ID=g1 -- "$URL"
eq "7 gate deferral -> exit 5" "$RC" 5
eq "7 deferral: no media/whisper" "$(( $(called whisper.log) + $(count ytdlp.kinds '^media$') ))" 0
run STUB_GATE_RC=1 STUB_CAPS=none STUB_ID=g2 -- "$URL"
eq "7 gate crash (rc 1) -> exit 5, not run" "$RC" 5
GATE=/nonexistent/gate run STUB_CAPS=none STUB_ID=g3 -- "$URL"
eq "7 missing gate -> exit 5" "$RC" 5
grep -q 'gate unavailable' "$T/last.err" && ok "7 missing gate message" 1 || ok "7 missing gate message" 0
eq "7 missing gate: whisper not run" "$(called whisper.log)" 0
mkdir -p "$T/noquota"; ln -sf "$STUBS/yt-dlp" "$T/noquota/yt-dlp"; ln -sf "$STUBS/whisper" "$T/noquota/whisper"
RUN_PATH="$T/noquota:$TOOLS" run STUB_CAPS=none STUB_ID=g4 -- "$URL"
eq "7 missing systemd-run -> exit 5" "$RC" 5
eq "7 missing systemd-run: whisper not run" "$(called whisper.log)" 0
RUN_PATH="$STUBS:$TOOLS" run STUB_GATE_RC=5 -- "$T/fixture.mp4" --force-whisper
eq "7 local whisper path gated before ffmpeg" "$(called ffmpeg.log)" 0

# ---- 8. cache fingerprint / validation -------------------------------------------------
cp "$T/fixture.mp4" "$T/c.mp4"; cp "$T/fixture.vtt" "$T/c.vtt"
hit() { python3 -I -c 'import json,sys;print(json.load(open(sys.argv[1]))["cache_hit"])' "$OUTD/run.json"; }
run -- "$T/c.mp4" --subs "$T/c.vtt"; eq "8 first run miss" "$(hit)" False
run -- "$T/c.mp4" --subs "$T/c.vtt"; eq "8 unchanged rerun hits" "$(hit)" True
eq "8 selection mode recorded" "$(python3 -I -c 'import json,sys;print(json.load(open(sys.argv[1]))["selection_mode"])' "$OUTD/run.json")" local-subs
sed -i 's/third line/third lines/' "$T/c.vtt"
run -- "$T/c.mp4" --subs "$T/c.vtt"
eq "8 editing only the VTT -> miss" "$(hit)" False
eq "8 edited VTT content used" "$(grep -c 'third lines' "$OUTD/transcript.txt")" 1
run -- "$T/c.mp4" --subs "$T/c.vtt" --lang en; eq "8 --lang change -> miss" "$(hit)" False
run -- "$T/c.mp4" --subs "$T/c.vtt" --lang en; eq "8 same lang hits" "$(hit)" True
ent="$T/cache/$(sha256sum "$T/c.mp4" | cut -c1-64)"
echo '{"schema":"aq-segments/1","segm' > "$ent/transcript/transcript.json"
run -- "$T/c.mp4" --subs "$T/c.vtt" --lang en
eq "8 truncated cached transcript.json -> redo ok" "$RC" 0
eq "8 truncated cached transcript.json -> miss" "$(hit)" False
[[ ! -e "$ent/quarantine" ]] && ok "8 corrupt stage deleted, no quarantine" 1 || ok "8 corrupt stage deleted, no quarantine" 0
mkdir -p "$ent/transcript.tmp"; echo x > "$ent/transcript.tmp/partial"
run -- "$T/c.mp4" --subs "$T/c.vtt" --lang en
eq "8 stale .tmp removed at start" "$([[ -e "$ent/transcript.tmp" ]] && echo present || echo gone)" gone

# ---- 9. public only --------------------------------------------------------------------
for av in private unlisted needs_auth MISSING; do
  run STUB_AVAIL=$av STUB_ID="pub$av" STUB_CAPS=creator -- "$URL"
  eq "9 availability=$av -> exit 2" "$RC" 2
  eq "9 availability=$av: no caption/media fetch" "$(count ytdlp.kinds '^caps$')" 0
done
run STUB_AVAIL=public STUB_ID=pubok STUB_CAPS=creator -- "$URL"; eq "9 public ok" "$RC" 0
run -- "$URL" --cookies c.txt; eq "9 --cookies rejected exit 2" "$RC" 2
run -- "$URL" --cookies-from-browser firefox; eq "9 --cookies-from-browser rejected exit 2" "$RC" 2
run -- "https://user:pw@example.com/v"; eq "9 URL userinfo rejected exit 2" "$RC" 2
run YT_DLP_OPTS=--cookies=x STUB_ID=envstrip STUB_CAPS=creator -- "$URL"; eq "9 YT_DLP_* env does not break run" "$RC" 0

# ---- 10. cache cap ---------------------------------------------------------------------
mkcache() { # <root> : three old 8 MB unprotected entries (oldest first)
  rm -rf "$1"; for i in a b c; do mkdir -p "$1/old$i"; head -c 8388608 /dev/zero > "$1/old$i/blob"; done
  touch -d '30 days ago' "$1/olda"; touch -d '20 days ago' "$1/oldb"; touch -d '10 days ago' "$1/oldc"
}
C1="$T/cap1"; mkcache "$C1"
CACHE_OVERRIDE="$C1" run AQ_TRANSCRIBE_CACHE_MAX_GB=0.02 AQ_TRANSCRIBE_RUN_BUDGET_MB=4 -- "$T/fixture.mp4" --subs "$T/fixture.vtt"
eq "10 over-cap admission prunes -> exit 0" "$RC" 0
[[ ! -e "$C1/olda" ]] && ok "10 oldest pruned first" 1 || ok "10 oldest pruned first" 0
[[ -e "$C1/oldc" ]] && ok "10 newest kept (pruning stops at cap - run budget)" 1 || ok "10 newest kept" 0
C3="$T/cap3"; rm -rf "$C3"
CACHE_OVERRIDE="$C3" run AQ_TRANSCRIBE_CACHE_MAX_GB=0.0001 -- "$T/fixture.mp4" --subs "$T/fixture.vtt"
eq "10 run budget exceeding the cap outright -> exit 7" "$RC" 7
C4="$T/cap4"; rm -rf "$C4"; mkdir -p "$T/bigout"; head -c 41943040 /dev/zero > "$T/bigout/bundle.bin"
CACHE_OVERRIDE="$C4" run AQ_TRANSCRIBE_CACHE_MAX_GB=0.02 -- "$T/fixture.mp4" --subs "$T/fixture.vtt"
eq "10 bundles (out dir, outside cache) are not counted" "$RC" 0
CACHE_OVERRIDE="$T/capb" run AQ_TRANSCRIBE_BUNDLE_MAX_MB=0 -- "$T/fixture.mp4" --subs "$T/fixture.vtt"
eq "10 bundle cap exceeded -> exit 7" "$RC" 7
# stage overrun: six 4 MB writes (each under the ulimit) exceed the cap -> stage deleted, exit 7, cache <= cap
mk whisper 'while [ $# -gt 0 ]; do [ "$1" = --output_dir ] && o=$2; shift; done
for i in 1 2 3 4 5 6; do head -c 4000000 /dev/zero > "$o/bloat$i"; done
cat > "$o/audio.json" <<J
{"segments":[{"start":0,"end":1,"text":"x"}]}
J'
C5="$T/cap5"; rm -rf "$C5"
CACHE_OVERRIDE="$C5" run AQ_TRANSCRIBE_CACHE_MAX_GB=0.02 STUB_CAPS=none STUB_ID=grow1 -- "$URL" --keep-audio
eq "10 stage overrun -> exit 7" "$RC" 7
eq "10 overrun deleted the stage outputs (cache <= cap)" "$(python3 -I -c 'import sys;sys.path.insert(0,sys.argv[1]);import video_frames as v;from pathlib import Path;print(int(v.cache_usage(Path(sys.argv[2]))<=int(0.02*2**30)))' "$ROOT/scripts/ai/lib" "$C5")" 1
# ulimit -f: one runaway writer is truncated at the per-process limit, not allowed to fill the disk
mk whisper 'while [ $# -gt 0 ]; do [ "$1" = --output_dir ] && o=$2; shift; done
head -c 60000000 /dev/zero > "$o/bloat" 2>/dev/null
stat -c %s "$o/bloat" > "$LOG/bloat.size"
cat > "$o/audio.json" <<J
{"segments":[{"start":0,"end":1,"text":"x"}]}
J'
CACHE_OVERRIDE="$T/cap6" run AQ_TRANSCRIBE_CACHE_MAX_GB=0.1 STUB_CAPS=none STUB_ID=ulim1 -- "$URL"
bs="$(cat "$LOG/bloat.size" 2>/dev/null || echo 99999999)"
[[ "$bs" -lt 60000000 && "$bs" -le $(( 107374182 / 4 + 1048576 )) ]] && ok "10 ulimit -f truncates a runaway writer ($bs B)" 1 || ok "10 ulimit -f truncates a runaway writer ($bs B)" 0

# ---- 10b. global lock, single metadata call, local exempt -------------------------------
mk whisper 'echo "whisper $*" >> "$LOG/whisper.log"
while [ $# -gt 0 ]; do [ "$1" = --output_dir ] && o=$2; shift; done
cat > "$o/audio.json" <<J
{"segments":[{"start":0,"end":1,"text":"x"}]}
J'
CL="$T/lockcache"; mkdir -p "$CL"
( flock 9; sleep 8 ) 9>"$CL/.lock" &
holder=$!; sleep 1
CACHE_OVERRIDE="$CL" run STUB_CAPS=creator STUB_ID=lk1 -- "$URL"
eq "10b second concurrent run -> exit 9 (busy)" "$RC" 9
eq "10b busy run made no yt-dlp call" "$(called ytdlp.kinds)" 0
kill "$holder" 2>/dev/null; wait "$holder" 2>/dev/null
CACHE_OVERRIDE="$CL" run STUB_CAPS=creator STUB_ID=lk1 -- "$URL"
eq "10b lock released -> run succeeds" "$RC" 0
eq "10b exactly one metadata call per URL run" "$(count ytdlp.kinds '^meta$')" 1
run -- "$T/fixture.mp4" --subs "$T/fixture.vtt"
eq "10b local fixture makes no yt-dlp call" "$(called ytdlp.kinds)" 0

# ---- 10c. host-derived limits logged in run.json; env wins --------------------------------
run AQ_TRANSCRIBE_CPU_QUOTA_PCT=300 STUB_CAPS=none STUB_ID=lim1 -- "$URL"
eq "10c env CPU quota override reaches systemd-run" "$(grep -c 'CPUQuota=300%' "$LOG/quota.log")" 1
eq "10c run.json logs source=env for the override" "$(python3 -I -c 'import json,sys;print(json.load(open(sys.argv[1]))["limits"]["cpu_quota_pct"]["source"])' "$OUTD/run.json")" env:AQ_TRANSCRIBE_CPU_QUOTA_PCT
eq "10c run.json logs derived source for the rest" "$(python3 -I -c 'import json,sys;print(json.load(open(sys.argv[1]))["limits"]["tasks_max"]["source"])' "$OUTD/run.json")" derived

# ---- 11. normaliser unit checks ---------------------------------------------------------
python3 -I - "$HELPER" <<'PY' && ok "11 normalizer unit checks" 1 || ok "11 normalizer unit checks" 0
import importlib.util, sys
spec = importlib.util.spec_from_file_location("vf", sys.argv[1]); vf = importlib.util.module_from_spec(spec); spec.loader.exec_module(vf)
openai = {"segments": [{"start": 3600.5, "end": 3602.25, "text": " Hi\x00 there"}]}
cpp = {"transcription": [{"offsets": {"from": 3600500, "to": 3602250}, "text": " Hi there"}]}
a, _ = vf.parse_whisper_json(openai); b, _ = vf.parse_whisper_json(cpp)
da, db = vf.finalize(a, "w", "en"), vf.finalize(b, "w", "en")
assert abs(da["segments"][0]["start_s"] - db["segments"][0]["start_s"]) < 0.01
assert da["segments"][0]["text"] == "Hi there" == db["segments"][0]["text"], da
assert da["segments"][0]["start_s"] == 3600.5 and da["schema"] == "aq-segments/1"
v = vf.parse_vtt("WEBVTT\n\n01:00:00.500 --> 01:00:02.250\nHi there\n")
assert v[0]["start_s"] == 3600.5 and v[0]["end_s"] == 3602.25
assert vf.fingerprint(["a=1", "subs_sha256=x"]) != vf.fingerprint(["a=1", "subs_sha256=y"])
# C6: one media-relative timeline; frame pts is shifted by format.start_time, VTT/Whisper are not.
assert vf.media_relative(606.0, 600.0) == 6.0 and vf.media_relative(6.0, 0.0) == 6.0
rolling = vf.parse_vtt("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nhello world\n\n00:00:02.000 --> 00:00:04.000\nhello world\nsecond line\n\n00:00:04.000 --> 00:00:04.010\nhello world\nsecond line\n")
whisper = vf.parse_whisper_json({"segments": [{"start": 0.0, "end": 2.0, "text": "hello world"}, {"start": 2.0, "end": 4.01, "text": "second line"}]})[0]
ra, rb = vf.finalize(rolling, "k", "en")["segments"], vf.finalize(whisper, "k", "en")["segments"]
assert [(s["text"]) for s in ra] == [s["text"] for s in rb]
assert all(abs(x["start_s"] - y["start_s"]) < 0.01 and abs(x["end_s"] - y["end_s"]) < 0.01 for x, y in zip(ra, rb)), (ra, rb)

# ---- resource_limits: host-derived defaults, env wins, floors/ceilings hold ------------------
G = 1 << 30; M = 1 << 20
small = {"ncpu": 2, "mem_total": 4 * G, "cache_total": 64 * G, "cache_free": 20 * G, "out_free": 20 * G}
big = {"ncpu": 64, "mem_total": 256 * G, "cache_total": 8000 * G, "cache_free": 4000 * G, "out_free": 4000 * G}
v = lambda d: {k: x["value"] for k, x in d.items()}
ls, lb = v(vf.resource_limits({}, small, 1800)), v(vf.resource_limits({}, big, 1800))
assert (ls["cpu_quota_pct"], ls["whisper_threads"], ls["ffmpeg_threads"], ls["tasks_max"]) == (100, 1, 1, 32), ls
assert ls["memory_max_mb"] == 1024 and ls["max_height"] == 480 and ls["whisper_factor"] == 8.0
assert ls["cache_max_bytes"] == int(10 * G * 0.1 * 6.4 / 1) or ls["cache_max_bytes"] == min(int(64 * G * 0.1), int(20 * G * 0.5))
assert (lb["cpu_quota_pct"], lb["whisper_threads"], lb["ffmpeg_threads"]) == (1600, 16, 8), lb
assert lb["memory_max_mb"] == 16384 and lb["max_height"] == 1080 and lb["whisper_factor"] == 1.0
assert lb["cache_max_bytes"] == 100 * G and lb["bundle_max_mb"] == 2048 and lb["tasks_max"] == 256
assert ls["whisper_budget_s"] > lb["whisper_budget_s"], "fewer cores -> larger time budget"
assert ls["run_budget_mb"] >= 16 and ls["backoff_schedule_s"] == [30, 90, 270] and ls["retries"] == 3
sources = {k: x["source"] for k, x in vf.resource_limits({}, small, 1800).items()}
assert set(sources.values()) == {"derived"}, sources
# env overrides win and are labelled
e = vf.resource_limits({"AQ_TRANSCRIBE_CPU_QUOTA_PCT": "50", "AQ_TRANSCRIBE_MEMORY_MAX_MB": "300", "AQ_TRANSCRIBE_WHISPER_BUDGET": "77",
                        "AQ_TRANSCRIBE_CACHE_MAX_GB": "1.5", "AQ_TRANSCRIBE_BACKOFF": "1 2", "AQ_TRANSCRIBE_MAX_HEIGHT": "360",
                        "AQ_TRANSCRIBE_BUNDLE_MAX_MB": "7", "AQ_TRANSCRIBE_FFMPEG_THREADS": "3"}, big, 1800)
assert e["cpu_quota_pct"]["value"] == 50 and e["cpu_quota_pct"]["source"].startswith("env:")
assert e["memory_max_bytes"]["value"] == 300 * M and e["whisper_budget_s"]["value"] == 77
assert e["cache_max_bytes"]["value"] == int(1.5 * G) and e["backoff_schedule_s"]["value"] == [1, 2] and e["retries"]["value"] == 2
assert e["max_height"]["value"] == 360 and e["bundle_max_mb"]["value"] == 7 and e["ffmpeg_threads"]["value"] == 3
# floors and ceilings
tiny = {"ncpu": 1, "mem_total": 512 * M, "cache_total": 2 * G, "cache_free": 1 * G, "out_free": 100 * M}
lt = v(vf.resource_limits({}, tiny, 10))
assert lt["cache_max_bytes"] == 256 * M and lt["bundle_max_mb"] == 50 and lt["whisper_budget_s"] == 300
assert lt["memory_max_mb"] == 256, lt  # floor 1 GiB, but never more than half of MemTotal
assert v(vf.resource_limits({}, big, 10**9))["whisper_budget_s"] == 14400
assert v(vf.resource_limits({}, big, -1))["whisper_budget_s"] == 14400, "unknown duration -> ceiling, never unbounded"
assert v(vf.resource_limits({"AQ_TRANSCRIBE_CACHE_MAX_CEILING_GB": "5"}, big, 1))["cache_max_bytes"] == 5 * G
pol = v(vf.resource_limits({"AQ_TRANSCRIBE_BACKOFF_BASE_S": "2", "AQ_TRANSCRIBE_BACKOFF_MULT": "5",
                            "AQ_TRANSCRIBE_EXPIRY_DAYS": "1", "AQ_TRANSCRIBE_TASKS_FLOOR": "64"}, tiny, 10))
assert pol["backoff_schedule_s"] == [2, 10, 50] and pol["expiry_days"] == 1 and pol["tasks_max"] == 64, pol
assert v(vf.resource_limits({}, big, 10))["backoff_schedule_s"] == [30, 90, 270]
try:
    vf.resource_limits({"AQ_TRANSCRIBE_TASKS_MAX": "lots"}, big, 1); raise SystemExit("invalid env accepted")
except ValueError:
    pass
PY

echo "---- $passes passed, $fails failed"
[[ $fails -eq 0 ]]

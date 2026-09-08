{
  # Profile package names only. Core packages are declared in
  # nix/modules/core/base.nix, and final package selection is deduplicated.
  # VSCodium is managed via Home Manager (nix/home/base.nix -> programs.vscodium),
  # so it must not be duplicated in system package profiles.
  ai-dev = [
    "nodejs"
    "bun"
    "typescript"
    "go"
    "cargo"
    "ruby"
    "neovim"
    "python3"
    "python312"
    "sqlite"
    "wireshark"
    "tcpdump"
    "nmap"
    "mtr"
    "traceroute"
    "sops"
    "age"
    "btrfs-progs"
    "pciutils"
    # NOTE: gpt4all is intentionally excluded from systemPackageNames because
    # recent nixpkgs revisions can evaluate but fail to build it (Qt6 private
    # target mismatch), which breaks full system deploys.
    # Declarative GPT4All install is provided via Flatpak profile data
    # (see nix/data/flatpak-profiles.nix: io.gpt4all.gpt4all).

    # ── Phase 29: MLOps lifecycle tooling (ai-dev profile only) ──────────────
    # dvc: data/model artifact versioning.
    "dvc"
    # httpie: human-friendly HTTP client for local API testing.
    "httpie"
    # BitNet benchmark prerequisites.
    "cmake"
    "clang"
    "zlib"

    # ── Domain tooling (Phase 58A+ capability expansion) ─────────────────────
    # systems-software domain: shell static analysis always available system-wide.
    "shellcheck"
    # security-systems domain: lightweight security linting always available.
    # semgrep and bandit are in the security dev shell (too large for system profile).
    "trivy"

    # ── Developer productivity CLI tools ──────────────────────────────────────
    # delta: git diff pager with syntax highlighting and side-by-side view.
    "delta"
    # fzf: fuzzy finder for shell history (Ctrl-R), file picker, pipe filtering.
    "fzf"
    # fd: fast, intuitive find replacement; used in repo scripts and agent tooling.
    "fd"
    # bat: cat with syntax highlighting, line numbers, and git integration.
    "bat"
    # tokei: fast code statistics (line counts, language breakdown).
    "tokei"
    # hyperfine: CLI benchmarking tool; useful for measuring inference latency.
    "hyperfine"
    # bottom: modern htop/system monitor with CPU/mem/disk/process views.
    "bottom"
    # tealdeer: fast tldr client — quick command reference pages.
    "tealdeer"
    # procs: modern ps replacement with color output and tree view.
    "procs"
    # dust: intuitive du replacement with visual disk usage tree.
    "dust"
    # sd: fast, simple find-and-replace (modern sed); useful for bulk edits.
    "sd"
    # xh: fast HTTP client (curl/httpie alternative) with clean output.
    "xh"
    # watchexec: run commands on file change; useful during development.
    "watchexec"

    # ── Local media transcription (offline research ingestion) ───────────────
    # Fully local, no cloud API. Pipeline: yt-dlp fetches the audio (or the
    # creator's caption track), ffmpeg extracts/normalizes audio, whisper does
    # offline ASR. Used to turn talks/videos into text agents can leverage.
    # yt-dlp: download video/audio + subtitle/caption tracks from YouTube etc.
    "yt-dlp"
    # ffmpeg: audio extraction/normalization; whisper depends on it at runtime.
    "ffmpeg"
    # openai-whisper: reference ASR; CLI `whisper` (CPU on this APU, no CUDA).
    "openai-whisper"
    # whisper-cpp: faster CPU whisper (GGML); CLI `whisper-cli`, needs a GGML model.
    "whisper-cpp"
  ];

  gaming = [
    "nodejs"
    "bun"
    "typescript"
    "go"
    "cargo"
    "ruby"
    "neovim"
    "python3"
    "sqlite"
    "btrfs-progs"
    "pciutils"
    "mangohud"
    "gamemode"
  ];

  minimal = [
    "nodejs"
    "bun"
    "typescript"
    "go"
    "cargo"
    "ruby"
    "neovim"
    "python3"
  ];

  # Golden AQ-OS Workstation: professional dev + gaming CLI toolset. NO AI-service
  # tooling here — the optional local AI stack is gated separately in the profile,
  # so this list stays clean on the AI-off golden path. Gaming apps (Steam/Proton/
  # mangohud) arrive via the gaming role, not this list.
  aqos-workstation = [
    # Languages / runtimes
    "nodejs"
    "bun"
    "typescript"
    "go"
    "cargo"
    "ruby"
    "python3"
    "python312"
    # Editors / db
    "neovim"
    "sqlite"
    # Dev + build
    "cmake"
    "clang"
    "httpie"
    # Modern CLI quality-of-life
    "hyperfine"
    "bottom"
    "tealdeer"
    "procs"
    "dust"
    "sd"
    "xh"
    "watchexec"
    # Secrets / filesystem / hardware
    "sops"
    "age"
    "btrfs-progs"
    "pciutils"
    # Networking diagnostics
    "nmap"
    "mtr"
    "traceroute"
    # General media tools (NOT AI): yt-dlp + ffmpeg only. The ML transcription
    # runners (openai-whisper / whisper-cpp) are DELIBERATELY excluded from the
    # golden base — they are AI dependencies and would violate the golden path's
    # "AI-off installs no AI deps" invariant. On the AI-on path they arrive with the
    # aiStack role (and remain in the ai-dev profile). Removing them here fixes the
    # AI-off package leak the independent review caught.
    "yt-dlp"
    "ffmpeg"
  ];
}

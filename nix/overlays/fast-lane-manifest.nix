# Split-channel packaging — fast-lane package manifest (SINGLE SOURCE OF TRUTH).
# .agents/plans/split-channel-packaging/DESIGN.md, slices sc-1/sc-2. Owner-directed
# 2026-09-11: this dev system tracks LATEST where performance/features matter
# (fast-lane, from nixpkgs-unstable) and STABLE where breakage is costly
# (everything else stays on the pinned `nixpkgs` input).
#
# Consumed by BOTH:
#   - nix/overlays/fast-lane.nix (the overlay wired once into flake.nix's mkPkgs)
#   - scripts/health/fast-lane-staleness-check.py (reads this file directly via
#     `nix eval --json --file`, so the checker never drifts from the overlay)
#
# To promote a package to the fast-lane: add its stable-era attr name to
# `active` below (+ a `renames` entry if nixpkgs-unstable renamed it). ALWAYS
# rebuild-test the promotion individually before it lands — moving an
# untested category (e.g. llama.cpp) to unstable could break the running AI
# stack. This is a one-line edit; nothing else needs to change.
{
  # ACTIVE fast-lane members (owner-approved, live now).
  active = [
    "grafana" # Build-checked vulnerability fix from unstable.
    "nmap" # Build-checked vulnerability fix from unstable.
    "antigravity" # IDE. Unstable renamed it: antigravity -> antigravity-ide (2.5.5 vs stable 1.23.2).
  ];

  # LEAF fast-lane members: the unstable build is installed where the package is
  # used directly (profile system packages), WITHOUT replacing pkgs.<name> for
  # everything that links against it. Use this for widely-depended-on libraries
  # whose global override would cascade a mass rebuild (ffmpeg: qtwebengine,
  # opencv, torchaudio, ... = 120 local derivations measured 2026-10-02;
  # pipewire: chromium, qtwebengine, webrtc, ...).
  leaf = [
    "ffmpeg" # CLI/media: stable 8.1.2 -> unstable 9.0.1 (21 closure alerts).
    "perl" # Scripting runtime (CVE-2023-31484, CVE-2023-31486)
    "pipewire" # Media pipeline vulnerability fix from unstable (CVE-2024-47537 etc.)
    "xdg-desktop-portal" # Desktop portal update matching pipewire 1.6+
  ];

  # Upstream attr renames: stable-era name (the name consumers like
  # nix/modules/core/base.nix basePackageNames actually reference) -> the
  # current attr name in nixpkgs-unstable. Only needed when unstable renamed
  # the package relative to stable.
  renames = {
    antigravity = "antigravity-ide";
  };

  # RESERVED categories — a documented promotion path, NOT active yet. Each
  # name needs its own individually rebuild-tested promotion (move it into
  # `active` above, add a `renames` entry if renamed) before it takes effect.
  # Left here so a promotion is a lookup, not a rediscovery:
  #   - llama.cpp / llama-cpp / llama-cpp-server — the performance-critical
  #     local-inference runtime. Promote only after a full local-inference
  #     smoke test (aq-qa) on the unstable build — untested breakage here
  #     takes down the whole AI stack, not just a dev tool.
  #   - other AI/agent runtimes & tools (e.g. ollama, additional local-model
  #     tooling) — evaluate per-tool.
  #   - other IDEs/editors beyond antigravity (vscode, etc.) — most already
  #     track upstream fast enough on stable; promote case-by-case.
  #   - misc fast-moving apps where latest-wins outweighs pin stability.
  reserved = [
    # "llama-cpp"
    # "ollama"
  ];
}

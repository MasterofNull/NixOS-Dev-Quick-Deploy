# Split-channel packaging fast-lane overlay
# (.agents/plans/split-channel-packaging/DESIGN.md sc-1).
#
# For each name in the curated manifest's `active` list
# (nix/overlays/fast-lane-manifest.nix — the single source of truth; edit
# THAT file to add/remove a fast-lane member, never this one), pkgs.<name>
# resolves from nixpkgs-unstable instead of the pinned stable nixpkgs,
# transparently handling upstream renames so consumers (e.g.
# nix/modules/core/base.nix basePackageNames) keep referring to the
# stable-era attr name. Everything NOT in `active` is left completely
# untouched — stays on whatever nixpkgs input the caller constructed `prev`
# from. Explicit + auditable: no blanket "use unstable for everything".
{
  # Already-imported nixpkgs-unstable pkgs set for this system, or null when
  # the flake input isn't available (falls back to stable-only, no-op).
  unstablePkgs ? null,
}: final: prev: let
  manifest = import ./fast-lane-manifest.nix;

  # Resolve one fast-lane name against nixpkgs-unstable, applying the rename
  # map. Returns null (never throws) when unstable doesn't carry it — the
  # overlay then simply omits an override and the package stays whatever it
  # already was in `prev` (mirrors base.nix's own missingPackageNames
  # silently-skip behavior; a stale/unavailable unstable pin must never
  # break evaluation).
  resolveFromUnstable = name:
    if unstablePkgs == null
    then null
    else let
      unstableName = manifest.renames.${name} or name;
    in
      if builtins.hasAttr unstableName unstablePkgs
      then unstablePkgs.${unstableName}
      else null;

  # manifest.renames only redirects the Nix ATTR (pkgs.<stable-name> ->
  # unstablePkgs.<unstable-name>). It does not help script/shell consumers
  # that invoke the bare BINARY by its stable-era name (e.g.
  # scripts/ai/aq-antigravity-inbox's `antigravity chat`, or
  # scripts/health/antigravity-health.sh's `command -v antigravity`) — once
  # upstream renames the binary too (antigravity -> antigravity-ide, 2.5.5),
  # the bare command disappears from PATH after rebuild even though
  # pkgs.antigravity still evaluates fine. Wrap the resolved package in a
  # symlinkJoin that re-exposes bin/<stableName> as a symlink alongside the
  # real bin/<unstableName>, so both names keep working. Only applied when
  # the attr was actually renamed — an active member with no rename entry
  # passes through untouched (no extra derivation, no build-time cost).
  # version/pname are carried through explicitly since symlinkJoin's
  # runCommand wrapper doesn't inherit them from the wrapped package, and
  # scripts/health/fast-lane-staleness-check.py depends on
  # `pkgs.<name>.version` still resolving post-wrap.
  wrapRenamedBinary = name: unstableName: resolved:
    if unstableName == name
    then resolved # not renamed — no wrapping needed
    else
      final.symlinkJoin {
        name = "${name}-fast-lane-${resolved.version or "unknown"}";
        paths = [resolved];
        postBuild = ''
          ln -s "$out/bin/${unstableName}" "$out/bin/${name}"
        '';
        passthru =
          (resolved.passthru or {})
          // {
            version = resolved.version or null;
            pname = resolved.pname or name;
          };
      };
in
  builtins.listToAttrs (
    builtins.filter (x: x != null) (
      map (
        name: let
          resolved = resolveFromUnstable name;
          unstableName = manifest.renames.${name} or name;
        in
          if resolved != null
          then {inherit name; value = wrapRenamedBinary name unstableName resolved;}
          else null # no override — prev's own value (if any) is unaffected
      )
      manifest.active
    )
  )

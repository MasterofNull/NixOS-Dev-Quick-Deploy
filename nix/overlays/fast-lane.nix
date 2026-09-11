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
in
  builtins.listToAttrs (
    builtins.filter (x: x != null) (
      map (
        name: let
          resolved = resolveFromUnstable name;
        in
          if resolved != null
          then {inherit name; value = resolved;}
          else null # no override — prev's own value (if any) is unaffected
      )
      manifest.active
    )
  )

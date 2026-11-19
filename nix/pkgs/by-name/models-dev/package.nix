{
  lib,
  stdenvNoCC,
  bun,
  fetchFromGitHub,
  nix-update-script,
  writableTmpDirAsHomeHook,
}: let
  pname = "models-dev";
  version = "0-unstable-2026-11-18";
  src = fetchFromGitHub {
    owner = "anomalyco";
    repo = "models.dev";
    rev = "d893237face842c5a4c918009d50c8e33b7c6523";
    hash = "sha256-5WCO6GX9UcqiHXlQ2pNpZyseBm32tRlBYGuX8NDC07c=";
  };

  node_modules = stdenvNoCC.mkDerivation {
    pname = "${pname}-node_modules";
    inherit version src;

    impureEnvVars =
      lib.fetchers.proxyImpureEnvVars
      ++ [
        "GIT_PROXY_COMMAND"
        "SOCKS_SERVER"
      ];

    nativeBuildInputs = [
      bun
      writableTmpDirAsHomeHook
    ];

    dontConfigure = true;

    buildPhase = ''
      runHook preBuild

      bun install \
        --cpu="*" \
        --frozen-lockfile \
        --ignore-scripts \
        --no-progress \
        --os="*"

      runHook postBuild
    '';

    installPhase = ''
      runHook preInstall

      mkdir -p $out
      find . -type d -name node_modules -exec cp -R --parents {} $out \;

      runHook postInstall
    '';

    # NOTE: Required else we get errors that our fixed-output derivation references store paths
    dontFixup = true;

    outputHash = "sha256-aL2kNCYF6Y4QnEvlpQ9U5Qe+K8a1J2X7BvJqE+BnRcY=";
    outputHashAlgo = "sha256";
    outputHashMode = "recursive";
  };
in
  stdenvNoCC.mkDerivation (_finalAttrs: {
    inherit
      pname
      version
      src
      node_modules
      ;

    nativeBuildInputs = [bun];

    configurePhase = ''
      runHook preConfigure

      cp -R ${node_modules}/. .

      runHook postConfigure
    '';

    buildPhase = ''
      runHook preBuild

      cd packages/web
      bun run ./script/build.ts

      runHook postBuild
    '';

    installPhase = ''
      runHook preInstall

      mkdir -p $out/dist
      cp -R ./dist $out

      runHook postInstall
    '';

    passthru.updateScript = nix-update-script {
      extraArgs = [
        "--version=branch"
        "--subpackage"
        "node_modules"
      ];
    };

    meta = {
      description = "Comprehensive open-source database of AI model specifications, pricing, and capabilities";
      homepage = "https://github.com/anomalyco/models.dev";
      license = lib.licenses.mit;
      platforms = lib.platforms.unix;
      maintainers = with lib.maintainers; [delafthi];
    };
  })

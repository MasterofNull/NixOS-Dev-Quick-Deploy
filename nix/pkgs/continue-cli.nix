{ lib, pkgs }:

pkgs.stdenvNoCC.mkDerivation rec {
  pname = "continue-cli";
  version = "1.5.45";

  src = pkgs.fetchurl {
    url = "https://registry.npmjs.org/@continuedev/cli/-/cli-${version}.tgz";
    sha256 = "0wp33iakvn960y6572h62rildjlb43v5224xvg3fr1r33r5n8z4i";
  };

  nativeBuildInputs = [ pkgs.makeWrapper ];

  unpackPhase = ''
    runHook preUnpack
    tar -xzf "$src"
    runHook postUnpack
  '';

  installPhase = ''
    runHook preInstall

    install -d "$out/bin" "$out/lib/continue-cli"
    cp -R package/dist "$out/lib/continue-cli/"
    cp package/package.json "$out/lib/continue-cli/"
    if [ -d package/media ]; then
      cp -R package/media "$out/lib/continue-cli/"
    fi

    makeWrapper ${pkgs.nodejs}/bin/node "$out/bin/cn" \
      --add-flags "$out/lib/continue-cli/dist/cn.js"

    runHook postInstall
  '';

  meta = with lib; {
    description = "Continue CLI for terminal coding assistance";
    homepage = "https://continue.dev";
    license = licenses.asl20;
    mainProgram = "cn";
    platforms = platforms.linux;
    maintainers = [ ];
  };
}

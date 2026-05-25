{
  lib,
  stdenv,
  python3,
  makeWrapper,
}:
stdenv.mkDerivation {
  pname = "agentic-tools";
  version = "1.0.0";

  src = ../../scripts/agent-tools;

  nativeBuildInputs = [makeWrapper];
  buildInputs = [python3];

  dontBuild = true;

  installPhase = ''
    mkdir -p $out/bin
    cp agrep $out/bin/agrep
    cp als $out/bin/als
    cp acat $out/bin/acat
    cp asum $out/bin/asum

    for tool in agrep als acat asum; do
      wrapProgram $out/bin/$tool --prefix PATH : ${lib.makeBinPath [python3]}
    done
  '';

  meta = with lib; {
    description = "Token-optimized CLI tools for AI agents";
    license = licenses.mit;
    platforms = platforms.linux;
  };
}

{
  lib,
  python3,
  fetchFromGitHub,
  makeWrapper,
}:
python3.pkgs.buildPythonApplication rec {
  pname = "mosaic-osint";
  version = "1.0.0-unstable-2026-10-19";

  src = fetchFromGitHub {
    owner = "Or1un";
    repo = "MOSAIC";
    rev = "0df2c04a2fefaf05b1d5aef9f75b4407662f62bc";
    sha256 = "105v4q6gbk9ck100admykpjancyih7wn3x6rqv02nlci1v88xv5v";
  };

  # MOSAIC is a script-based tool, we just need to wrap it
  format = "other";

  propagatedBuildInputs = with python3.pkgs; [
    requests
    pyyaml
    telethon
  ];

  nativeBuildInputs = [makeWrapper];

  installPhase = ''
    mkdir -p $out/bin $out/share/mosaic
    cp -r . $out/share/mosaic

    makeWrapper ${python3.interpreter} $out/bin/mosaic-osint \
      --add-flags "$out/share/mosaic/MOSAIC.py" \
      --prefix PYTHONPATH : "$PYTHONPATH"
  '';

  meta = with lib; {
    description = "Privacy-first behavioral intelligence tool for OSINT";
    homepage = "https://github.com/Or1un/MOSAIC";
    license = licenses.mit;
    mainProgram = "mosaic-osint";
  };
}

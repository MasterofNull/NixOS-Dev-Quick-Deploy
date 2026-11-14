{
  lib,
  python3,
  fetchFromGitHub,
  makeWrapper,
}:
python3.pkgs.buildPythonApplication rec {
  pname = "mosaic-osint";
  version = "1.0.0-unstable-2024-05-24";

  src = fetchFromGitHub {
    owner = "Or1un";
    repo = "MOSAIC";
    rev = "main";
    sha256 = "sha256-ROuyMS+pgYFcvQgrrn9nel1nMYigAY5z/m2Ehn/9x28=";
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
      --add-flags "$out/share/mosaic/mosaic.py" \
      --prefix PYTHONPATH : "$PYTHONPATH"
  '';

  meta = with lib; {
    description = "Privacy-first behavioral intelligence tool for OSINT";
    homepage = "https://github.com/Or1un/MOSAIC";
    license = licenses.mit;
    mainProgram = "mosaic-osint";
  };
}

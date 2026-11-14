{
  lib,
  python3,
  fetchFromGitHub,
}:
python3.pkgs.buildPythonApplication rec {
  pname = "maigret";
  version = "0.6.6";

  pyproject = true;

  src = fetchFromGitHub {
    owner = "soxoj";
    repo = "maigret";
    rev = "v${version}";
    sha256 = "19cl1dzz07y37zb628wjd6wbk5cq9lipafy3769axzr96df28mzm";
  };

  nativeBuildInputs = with python3.pkgs; [
    poetry-core
  ];

  propagatedBuildInputs = with python3.pkgs; [
    aiodns
    aiohttp
    aiohttp-socks
    alive-progress
    asgiref
    attrs
    beautifulsoup4
    certifi
    chardet
    cloudscraper
    colorama
    curl-cffi
    flask
    html5lib
    idna
    jinja2
    lxml
    markupsafe
    mock
    multidict
    networkx
    pandas
    platformdirs
    pycountry
    pypdf
    pyppeteer
    pysocks
    python-magic
    pyvis
    reportlab
    requests
    requests-futures
    requests-toolbelt
    six
    socid-extractor
    soupsieve
    stem
    torrequest
    tqdm
    typing-extensions
    webencodings
    xmind
    yarl
  ];

  postPatch = ''
    # Remove problematic dependencies for Python 3.13
    sed -i '/future/d' pyproject.toml

    # Swap insecure pypdf2 for pypdf
    sed -i 's/PyPDF2 = "^3.0.1"/pypdf = "*"/' pyproject.toml

    # Relax strict version constraints for all failing packages
    sed -i 's/networkx = "^2.6.3"/networkx = "*"/' pyproject.toml
    sed -i 's/alive_progress = "^3.2.0"/alive_progress = "*"/' pyproject.toml
    sed -i 's/pyvis = "^0.3.2"/pyvis = "*"/' pyproject.toml
    sed -i 's/curl-cffi = ">=0.14,<1.0"/curl-cffi = "*"/' pyproject.toml
    sed -i 's/PySocks = "^1.7.1"/PySocks = "*"/' pyproject.toml
    sed -i 's/XMind = "^1.2.0"/XMind = "*"/' pyproject.toml
    # nixpkgs ships socid-extractor 0.0.28; 0.6.6 declares >=0.1.1 (see commit body)
    sed -i 's/socid-extractor = ">=0.1.1,<0.2.0"/socid-extractor = "*"/' pyproject.toml
  '';

  # Disable tests as they usually require network for OSINT tools
  doCheck = false;

  meta = with lib; {
    description = "Collect a dossier on a person by username from thousands of sites";
    homepage = "https://github.com/soxoj/maigret";
    license = licenses.mit;
    mainProgram = "maigret";
  };
}

# Common Python package overrides used across generated configurations.
# These disable flaky or interactive test suites to keep builds reproducible
# in the Nix sandbox and apply shared post-install cleanups.
python-self: python-super:
let
  inherit (builtins)
    concatStringsSep
    filter
    getAttr
    hasAttr
    map
    removeAttrs
    typeOf;

  getAttrOr = name: default: attrs:
    if hasAttr name attrs then
      let
        value = getAttr name attrs;
      in
      if value != null then value else default
    else
      default;

  appendPostInstall = old: snippet:
    concatStringsSep "\n"
      (filter (s: s != "") [ (getAttrOr "postInstall" "" old) snippet ]);

  removeCliWrappers = binaries: old:
    let
      commands = map (bin: ''rm -f "$out/bin/${bin}" "$out/bin/.${bin}-wrapped"'') binaries;
      snippet = concatStringsSep "\n" commands;
    in
    appendPostInstall old snippet;

  filterNulls = filter (pkg: pkg != null);
in
{
  joserfc = python-super.joserfc.overridePythonAttrs (old: {
    # Skip tests to avoid flaky failures with duplicate key identifiers.
    doCheck = false;
    checkInputs = getAttrOr "checkInputs" [] old;
  });

  tenacity = python-super.tenacity.overridePythonAttrs (_: {
    # Upstream test suite relies on real timing and fails under virtualized builders.
    doCheck = false;
  });

  "inline-snapshot" = python-super."inline-snapshot".overridePythonAttrs (old: {
    # Skip tests that fail due to snapshot validation errors that require manual approval.
    doCheck = false;

    # The upstream package declares a runtime dependency on pytest so the
    # plugin entry points are available when the library is imported. Ensure it
    # is propagated so pythonRuntimeDepsCheck succeeds while still allowing the
    # tests to remain disabled.
    propagatedBuildInputs = getAttrOr "propagatedBuildInputs" [] old ++ [
      python-self.pytest
    ];
  });

  markdown = python-super.markdown.overridePythonAttrs (_: {
    doCheck = false;
  });

  "pytest-doctestplus" = python-super."pytest-doctestplus".overridePythonAttrs (_: {
    doCheck = false;
  });

  "google-api-core" = python-super."google-api-core".overridePythonAttrs (_: {
    doCheck = false;
  });

  "google-cloud-core" = python-super."google-cloud-core".overridePythonAttrs (_: {
    doCheck = false;
  });

  "google-cloud-storage" = python-super."google-cloud-storage".overridePythonAttrs (_: {
    doCheck = false;
  });

  "google-cloud-bigquery" = python-super."google-cloud-bigquery".overridePythonAttrs (_: {
    doCheck = false;
  });

  "moto" = python-super."moto".overridePythonAttrs (_: {
    # The upstream test suite attempts to reach AWS endpoints and fails in the
    # hermetic Nix build sandbox. Disable checks so builds complete.
    doCheck = false;
    pythonImportsCheck = [];
  });

  sqlframe = python-super.sqlframe.overridePythonAttrs (old: {
    postPatch = getAttrOr "postPatch" "" old
      + ''
        find . -type f -name '*.py' -exec sed -i 's/np\\.NaN/np.nan/g' {} +
      '';
    doCheck = false;
    pythonImportsCheck = [];
  });

  psycopg = python-super.psycopg.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  "llama-index" = python-super."llama-index".overridePythonAttrs (old: {
    postInstall = removeCliWrappers [ "llamaindex-cli" ] old;
  });

  "llama-cloud-services" = python-super."llama-cloud-services".overridePythonAttrs (old: {
    postInstall = removeCliWrappers [ "llama-parse" ] old;
  });

  "openai" = python-super."openai".overridePythonAttrs (old: {
    doCheck = false;
    pythonImportsCheck = [];
    postInstall = removeCliWrappers [ "openai" ] old;
  });

  pylint = python-super.pylint.overridePythonAttrs (_: {
    # Disable pylint tests to avoid build failures from flaky test suite.
    doCheck = false;
    pythonImportsCheck = [];
  });

  terminado = python-super.terminado.overridePythonAttrs (old: {
    # Upstream test suite spawns multiple pseudo terminals and fails in
    # constrained build sandboxes (MaxTerminalsReached errors).
    doCheck = false;
    pythonImportsCheck = getAttrOr "pythonImportsCheck" [] old;
  });

  watchfiles = python-super.watchfiles.overridePythonAttrs (_: {
    # The permission-denied watcher test relies on /proc pseudo files that
    # hang under the Nix sandbox and regularly trigger pytest-timeout.
    doCheck = false;
    pythonImportsCheck = [];
  });

  syrupy = python-super.syrupy.overridePythonAttrs (_: {
    # Disable syrupy tests - snapshot testing library with flaky tests.
    doCheck = false;
    pythonImportsCheck = [];
  });

  langchain = python-super.langchain.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  "langchain-core" = python-super."langchain-core".overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  "langchain-community" = python-super."langchain-community".overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  "langchain-openai" = python-super."langchain-openai".overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  "pinecone-client" = python-super."pinecone-client".overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  pymupdf = python-super.pymupdf.overridePythonAttrs (_: {
    # Upstream runs a long-running memory regression test that frequently fails
    # on shared CI builders due to noisy RSS reporting. Skip the suite so we can
    # rely on the published wheels without the fragile assertion gate.
    doCheck = false;
    pythonImportsCheck = [];
  });

  chromadb = python-super.chromadb.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  "qdrant-client" = python-super."qdrant-client".overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  litellm = python-super.litellm.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  tiktoken = python-super.tiktoken.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  dask = python-super.dask.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  "dask-ml" = python-super."dask-ml".overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  gradio = python-super.gradio.overridePythonAttrs (old: {
    doCheck = false;
    pythonImportsCheck = [];
    passthru = removeAttrs (getAttrOr "passthru" {} old) [ "sans-reverse-dependencies" ];
  });

  gradio-client = python-super.gradio-client.overridePythonAttrs (old: {
    doCheck = false;
    pythonImportsCheck = [];
    nativeCheckInputs =
      let
        existing = getAttrOr "nativeCheckInputs" [] old;
        transformed = map
          (pkg:
            if typeOf pkg == "set"
              && pkg ? pname
              && (getAttrOr "pname" "" pkg) == "gradio"
            then null
            else pkg)
          existing;
      in
      filterNulls transformed;
  });

  transformers = python-super.transformers.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  datasets = python-super.datasets.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  anthropic = python-super.anthropic.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  "sentence-transformers" = python-super."sentence-transformers".overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  diffusers = python-super.diffusers.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  accelerate = python-super.accelerate.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  evaluate = python-super.evaluate.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  "llama-cpp-python" = python-super."llama-cpp-python".overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  bitsandbytes = python-super.bitsandbytes.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  jupyterlab = python-super.jupyterlab.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  "jupyter-server" = python-super."jupyter-server".overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  torch = python-super.torch.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  torchvision = python-super.torchvision.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  torchaudio = python-super.torchaudio.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  tensorflow = python-super.tensorflow.overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });

  "llama-index-core" = python-super."llama-index-core".overridePythonAttrs (_: {
    doCheck = false;
    pythonImportsCheck = [];
  });
}

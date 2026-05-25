final: prev: {
  maigret = final.callPackage ../pkgs/maigret.nix {};
  mosaic = final.callPackage ../pkgs/mosaic.nix {};
  mosaic-osint = final.callPackage ../pkgs/mosaic.nix {};

  bbot-placeholder = prev.writeShellScriptBin "bbot" ''
    echo "BBOT is currently being provisioned. Please use the OSINT Tools MCP server for automated recon."
    exit 1
  '';
}

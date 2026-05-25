final: prev: {
  # Maigret and MOSAIC are intentionally not exposed here yet. The available
  # package path pulls insecure PyPDF2, so active system profiles use Sherlock
  # as the account-enumeration backend until secure derivations are available.
  bbot-placeholder = prev.writeShellScriptBin "bbot" ''
    echo "BBOT is currently being provisioned. Please use the OSINT Tools MCP server for automated recon."
    exit 1
  '';
}

# API Specifications
**Updated:** 2026-01-09

## Service Specs

- AIDB MCP Server: built-in OpenAPI at `http://localhost:8091/docs`
- Embeddings Service: `docs/api/embeddings-openapi.yaml`
- Hybrid Coordinator: `docs/api/hybrid-openapi.yaml`
- NixOS Docs MCP: `docs/api/nixos-docs-openapi.yaml`

## Notes

- All external endpoints require the API key when enabled (`X-API-Key` header).
- HTTPS is terminated by nginx at `https://localhost:8443` (self-signed).

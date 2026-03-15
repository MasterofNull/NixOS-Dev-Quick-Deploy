# MCP Signed Component Research - 2026-03-15

## Research Objective

Investigate MCP signed component specification for Batch 11.3: implement signature validation and generation for tool definitions to ensure trusted component distribution.

## Findings

### MCP Specification Status (2025-11-25)

The current MCP specification (released November 2025) **does not include signed component support**.

**Security Model:**
- Tool descriptions and annotations are considered "untrusted unless from a trusted server"
- Trust is based on server origin, not cryptographic signatures
- No specification for component signing, verification, or trust chains

**Sources:**
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [2026 MCP Roadmap](http://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/)

### 2026 Roadmap Priorities

The 2026 roadmap lists four priorities:
1. Transport scalability
2. Agent communication
3. Governance maturation
4. Enterprise readiness

**Security Work:**
- "Deeper security and authorization work" mentioned as lower priority
- No specific signed component specification planned
- Active SEPs (1932, 1933) focus on authentication federation, not component signing

### GitHub Repository Search

No results for:
- "signed components"
- "component signatures"
- "tool signing"

Within the modelcontextprotocol GitHub organization.

## Conclusion

**Batch 11.3 cannot be implemented as specified** because the MCP signed component specification does not exist.

### Recommended Actions

1. **Mark Batch 11.3 as blocked** pending upstream MCP specification
2. **Propose SEP (Spec Enhancement Proposal)** if component signing is critical for this project
3. **Implement custom signing layer** outside MCP spec as a local extension
4. **Skip Batch 11.3** and proceed with other roadmap work

### Custom Implementation Considerations

If a custom signing layer is desired, industry standards suggest:

**Signature Format:**
- JSON Web Signature (JWS) for tool definitions
- Code signing certificates (X.509) for tool implementations
- Package signing (e.g., apt/rpm style) for distribution

**Validation Flow:**
1. Tool provider signs tool JSON with private key
2. Signature embedded in tool metadata or separate .sig file
3. MCP server loads tool definition
4. Server validates signature against trusted public keys
5. Only validated tools exposed to clients

**Trust Model:**
- Trust anchors (CA certificates or explicit key pinning)
- Revocation mechanism (CRL or OCSP)
- Signature timestamp for freshness

**Implementation Scope:**
- ~200-300 lines for signature validation
- Integration into hybrid-coordinator tool loading
- Configuration for trusted signing keys
- Documentation for signing workflow

**Risk:**
- Custom implementation diverges from future MCP spec
- Maintenance burden if MCP adopts different approach
- Interoperability issues with other MCP implementations

## Research Complete

**Status:** Specification does not exist
**Recommendation:** Block Batch 11.3 pending upstream spec or user direction on custom implementation

---

**Researched by:** Claude Sonnet 4.5
**Date:** 2026-03-15
**Context:** SYSTEM-IMPROVEMENT-ROADMAP-2026-03.md Batch 11.3

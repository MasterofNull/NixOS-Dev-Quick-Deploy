# TLS/HTTPS Setup Guide

## Overview

This guide documents the TLS/HTTPS configuration for the NixOS AI Stack. The setup uses nginx as a reverse proxy with TLS termination for all AI services.

## Architecture

```
Client (HTTPS) → nginx:443 (TLS termination) → Backend Services (HTTP)
                                               ├─ aidb:8091
                                               ├─ hybrid-coordinator:8092
                                               ├─ qdrant:6333
                                               ├─ embeddings:8081
                                               └─ nixos-docs:8094
```

## TLS Configuration

### Certificate Generation

Self-signed certificates for local development:

```bash
# Generate certificates (creates localhost.crt and localhost.key)
bash scripts/generate-nginx-certs.sh

# Certificate location
ai-stack/compose/nginx/certs/
├── localhost.crt  (644 permissions)
└── localhost.key  (600 permissions)

# Certificate validity: 365 days
# Certificate features:
# - RSA 4096-bit key
# - Subject Alternative Names (SAN):
#   - DNS: localhost, *.localhost
#   - IP: 127.0.0.1, ::1
# - Modern browser compatibility
```

### nginx Configuration

Location: `ai-stack/compose/nginx/nginx.conf`

**Key Security Features:**

1. **Modern TLS Protocols**
   - TLS 1.2 and TLS 1.3 only
   - No support for deprecated TLS 1.0/1.1 or SSL

2. **Strong Cipher Suites**
   - ECDHE for forward secrecy
   - AES-GCM and ChaCha20-Poly1305
   - Following Mozilla Intermediate configuration

3. **Security Headers**
   - `Strict-Transport-Security`: Force HTTPS for 2 years
   - `X-Frame-Options`: Prevent clickjacking
   - `X-Content-Type-Options`: Prevent MIME sniffing
   - `X-XSS-Protection`: Browser XSS protection
   - `Referrer-Policy`: Privacy protection
   - `Content-Security-Policy`: XSS mitigation

4. **HTTP/2 Support**
   - Enabled for improved performance
   - Multiplexing and header compression

5. **Automatic HTTP → HTTPS Redirect**
   - All HTTP (port 80) traffic redirected to HTTPS (port 443)

### Service Endpoints

All services are accessible via HTTPS reverse proxy:

| Service | External URL | Internal Backend |
|---------|-------------|------------------|
| Open WebUI | `https://localhost:8443/` | `http://open-webui:3001` |
| AIDB MCP | `https://localhost:8443/aidb/` | `http://aidb:8091` |
| Hybrid Coordinator | `https://localhost:8443/hybrid/` | `http://hybrid-coordinator:8092` |
| Qdrant | `https://localhost:8443/qdrant/` | `http://qdrant:6333` |
| Embeddings | `https://localhost:8443/embeddings/` | `http://embeddings:8081` |
| NixOS Docs | `https://localhost:8443/nixos-docs/` | `http://nixos-docs:8094` |

## Usage

### Starting the Stack

```bash
# Start AI stack (includes nginx)
bash scripts/ai-stack-startup.sh

# Or manually start nginx
cd ai-stack/compose
podman-compose up -d nginx
```

### Testing TLS

```bash
# Test HTTPS connection
curl -k https://localhost:8443/aidb/health

# Test HTTP redirect
curl -I http://localhost:8088/

# Verify TLS configuration
openssl s_client -connect localhost:8443 -servername localhost

# Check certificate details
openssl s_client -connect localhost:8443 -showcerts | openssl x509 -noout -text
```

### Browser Access

1. **First-time Setup** (Self-signed certificates)
   - Navigate to `https://localhost:8443`
   - Browser will show security warning
   - Accept the risk/add exception (development only)

2. **Trust Certificate** (Optional, recommended)

   **Linux:**
   ```bash
   # Copy certificate to system trust store
   sudo cp ai-stack/compose/nginx/certs/localhost.crt /usr/local/share/ca-certificates/
   sudo update-ca-certificates
   ```

   **macOS:**
   ```bash
   # Add to Keychain and trust
   sudo security add-trusted-cert -d -r trustRoot \
     -k /Library/Keychains/System.keychain \
     ai-stack/compose/nginx/certs/localhost.crt
   ```

   **Windows:**
   ```powershell
   # Import certificate to Trusted Root
   certutil -addstore -f "ROOT" ai-stack\compose\nginx\certs\localhost.crt
   ```

## Certificate Renewal

### Development Certificates

Self-signed certificates expire after 365 days.

```bash
# Remove old certificates
rm ai-stack/compose/nginx/certs/localhost.crt
rm ai-stack/compose/nginx/certs/localhost.key

# Generate new certificates
bash scripts/generate-nginx-certs.sh

# Restart nginx
podman restart local-ai-nginx
```

### Production Certificates (Let's Encrypt)

For production deployments, use Let's Encrypt:

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx  # Debian/Ubuntu
sudo dnf install certbot python3-certbot-nginx  # Fedora/RHEL

# Get certificate (requires public domain)
sudo certbot --nginx -d your-domain.com

# Auto-renewal (certbot timer should be enabled by default)
sudo systemctl status certbot.timer
```

## Security Considerations

### Development vs Production

**Current Setup (Development):**
- ✅ Self-signed certificates
- ✅ Localhost-only binding
- ✅ Strong ciphers and protocols
- ✅ Security headers
- ⚠️ Certificate trust warnings

**Production Requirements:**
- [ ] Valid CA-signed certificates (Let's Encrypt)
- [ ] Public domain with DNS
- [ ] Certificate auto-renewal
- [ ] OCSP stapling
- [ ] Consider certificate pinning
- [ ] WAF/rate limiting
- [ ] DDoS protection

### Cipher Suite Rationale

We use Mozilla Intermediate configuration:
- **Forward Secrecy**: ECDHE key exchange
- **Modern Algorithms**: AES-GCM, ChaCha20-Poly1305
- **Compatibility**: Works with all modern browsers (last 5 years)
- **Security**: No weak ciphers (RC4, 3DES, MD5, etc.)

Reference: https://ssl-config.mozilla.org/#server=nginx&version=1.25&config=intermediate&openssl=3.0.0

### Security Headers Explained

1. **HSTS** (Strict-Transport-Security)
   - Forces HTTPS for all future requests (2 years)
   - Prevents protocol downgrade attacks
   - Includes subdomains and preload directive

2. **X-Frame-Options: SAMEORIGIN**
   - Prevents embedding in iframes from other domains
   - Mitigates clickjacking attacks

3. **X-Content-Type-Options: nosniff**
   - Prevents MIME type sniffing
   - Reduces XSS risk from uploaded files

4. **Content-Security-Policy**
   - Restricts resource loading
   - Mitigates XSS and injection attacks
   - May need adjustment for specific frontends

## Troubleshooting

### Certificate Errors

**Problem:** "NET::ERR_CERT_AUTHORITY_INVALID"
- **Cause:** Self-signed certificate not trusted
- **Solution:** Add exception in browser or trust certificate

**Problem:** "NET::ERR_CERT_COMMON_NAME_INVALID"
- **Cause:** Certificate doesn't match hostname
- **Solution:** Ensure accessing via `localhost` (not IP or other hostname)

### Connection Errors

**Problem:** Connection refused on port 8443
- **Check:** Is nginx container running?
  ```bash
  podman ps | grep nginx
  ```
- **Check:** Is port bound correctly?
  ```bash
  netstat -tuln | grep 8443
  ```

**Problem:** 502 Bad Gateway
- **Cause:** Backend service not running
- **Solution:** Check service health
  ```bash
  podman ps | grep local-ai
  curl http://localhost:8091/health  # Check AIDB directly
  ```

### nginx Configuration

**Test configuration without restarting:**
```bash
podman exec local-ai-nginx nginx -t
```

**View nginx logs:**
```bash
podman logs local-ai-nginx
```

**Reload configuration (without downtime):**
```bash
podman exec local-ai-nginx nginx -s reload
```

## Performance Considerations

### HTTP/2 Benefits

- **Multiplexing:** Multiple requests over single connection
- **Header Compression:** Reduced overhead
- **Server Push:** Proactive resource delivery

### Session Caching

- **Session Cache:** 10MB shared cache (stores ~40k sessions)
- **Session Timeout:** 1 day
- **Session Tickets:** Disabled (better forward secrecy)

### Timeouts

- **Proxy Timeout:** 60s (adjust for long-running AI operations)
- **Client Body Size:** 100MB (for file uploads)
- **Connection Timeouts:** 60s

## References

- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [OWASP TLS Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html)
- [nginx SSL Module Documentation](https://nginx.org/en/docs/http/ngx_http_ssl_module.html)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [HSTS Preload List](https://hstspreload.org/)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-08 | Initial TLS setup with self-signed certs | Claude Code |
| 2026-01-08 | Enhanced security headers and cipher suites | Claude Code |
| 2026-01-08 | Added HTTP/2 support | Claude Code |

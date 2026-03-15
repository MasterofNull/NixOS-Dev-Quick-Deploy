#!/usr/bin/env python3
"""
Security Audit & Hardening Framework

Comprehensive security scanning, hardening, and protection mechanisms.
Part of Phase 2 Batch 2.2: Security Audit & Hardening

Key Features:
- Automated security scanning (OWASP Top 10 checks)
- Content Security Policy (CSP) enforcement
- Rate limiting and DDoS protection
- Secrets rotation automation
- Security headers enforcement

Reference: OWASP Top 10, CWE/SANS Top 25
"""

import asyncio
import hashlib
import json
import logging
import re
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Security issue severity"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityType(Enum):
    """OWASP Top 10 vulnerability types"""
    INJECTION = "injection"  # SQL, NoSQL, Command injection
    BROKEN_AUTH = "broken_authentication"
    SENSITIVE_DATA = "sensitive_data_exposure"
    XXE = "xml_external_entities"
    BROKEN_ACCESS = "broken_access_control"
    SECURITY_MISCONFIG = "security_misconfiguration"
    XSS = "cross_site_scripting"
    INSECURE_DESER = "insecure_deserialization"
    VULN_COMPONENTS = "vulnerable_components"
    INSUFFICIENT_LOGGING = "insufficient_logging"


@dataclass
class SecurityFinding:
    """Security audit finding"""
    finding_id: str
    severity: Severity
    vuln_type: VulnerabilityType
    title: str
    description: str
    location: str  # File, endpoint, etc.
    remediation: str
    cwe_id: Optional[str] = None
    evidence: List[str] = field(default_factory=list)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    max_requests: int
    window_seconds: int
    burst_size: int = 0  # Allow brief bursts


@dataclass
class Secret:
    """Managed secret"""
    secret_id: str
    name: str
    value: str
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    rotation_days: int = 90


class SecurityScanner:
    """Automated security scanner"""

    def __init__(self):
        self.findings: List[SecurityFinding] = []
        logger.info("Security Scanner initialized")

    def scan_code(self, code_path: Path) -> List[SecurityFinding]:
        """Scan code for security issues"""
        logger.info(f"Scanning code: {code_path}")

        findings = []
        findings.extend(self._scan_injection(code_path))
        findings.extend(self._scan_secrets(code_path))
        findings.extend(self._scan_crypto(code_path))
        findings.extend(self._scan_xss(code_path))

        self.findings.extend(findings)
        logger.info(f"Found {len(findings)} potential security issues")

        return findings

    def _scan_injection(self, code_path: Path) -> List[SecurityFinding]:
        """Scan for injection vulnerabilities"""
        findings = []

        if not code_path.exists():
            return findings

        content = code_path.read_text()

        # SQL injection patterns
        sql_patterns = [
            r'execute\s*\(\s*["\'].*%s.*["\']',  # String formatting in SQL
            r'cursor\.execute\s*\(\s*f["\']',  # f-strings in SQL
            r'\.query\s*\(\s*["\'].*\+.*["\']',  # String concatenation
        ]

        for pattern in sql_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                findings.append(SecurityFinding(
                    finding_id=f"inj_{len(findings)}",
                    severity=Severity.HIGH,
                    vuln_type=VulnerabilityType.INJECTION,
                    title="Potential SQL Injection",
                    description="SQL query uses string formatting/concatenation",
                    location=f"{code_path}:{content[:match.start()].count(chr(10)) + 1}",
                    remediation="Use parameterized queries or ORM",
                    cwe_id="CWE-89",
                    evidence=[match.group()],
                ))

        # Command injection patterns
        cmd_patterns = [
            r'os\.system\s*\(',
            r'subprocess\.call\s*\(\s*["\'].*%s',
            r'subprocess\.run\s*\(\s*["\'].*\+',
        ]

        for pattern in cmd_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                findings.append(SecurityFinding(
                    finding_id=f"inj_{len(findings)}",
                    severity=Severity.CRITICAL,
                    vuln_type=VulnerabilityType.INJECTION,
                    title="Potential Command Injection",
                    description="Shell command uses user input",
                    location=f"{code_path}:{content[:match.start()].count(chr(10)) + 1}",
                    remediation="Use subprocess with list arguments, avoid shell=True",
                    cwe_id="CWE-78",
                    evidence=[match.group()],
                ))

        return findings

    def _scan_secrets(self, code_path: Path) -> List[SecurityFinding]:
        """Scan for hardcoded secrets"""
        findings = []

        if not code_path.exists():
            return findings

        content = code_path.read_text()

        # Secret patterns
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']{4,}["\']', "Hardcoded Password"),
            (r'api[_-]?key\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded API Key"),
            (r'secret\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded Secret"),
            (r'token\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded Token"),
            (r'private[_-]?key\s*=\s*["\']-----BEGIN', "Hardcoded Private Key"),
        ]

        for pattern, title in secret_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # Skip if it's a placeholder or example
                if any(x in match.group().lower() for x in ["example", "placeholder", "xxx", "your_"]):
                    continue

                findings.append(SecurityFinding(
                    finding_id=f"secret_{len(findings)}",
                    severity=Severity.CRITICAL,
                    vuln_type=VulnerabilityType.SENSITIVE_DATA,
                    title=title,
                    description="Secret credential found in code",
                    location=f"{code_path}:{content[:match.start()].count(chr(10)) + 1}",
                    remediation="Move secrets to environment variables or secret store",
                    cwe_id="CWE-798",
                    evidence=[match.group()[:50] + "..."],
                ))

        return findings

    def _scan_crypto(self, code_path: Path) -> List[SecurityFinding]:
        """Scan for weak cryptography"""
        findings = []

        if not code_path.exists():
            return findings

        content = code_path.read_text()

        # Weak crypto patterns
        weak_patterns = [
            (r'hashlib\.md5\s*\(', "MD5 Hash", "Use SHA-256 or better"),
            (r'hashlib\.sha1\s*\(', "SHA-1 Hash", "Use SHA-256 or better"),
            (r'random\.random\s*\(', "Weak Random", "Use secrets module for security"),
        ]

        for pattern, title, remediation in weak_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                findings.append(SecurityFinding(
                    finding_id=f"crypto_{len(findings)}",
                    severity=Severity.MEDIUM,
                    vuln_type=VulnerabilityType.SECURITY_MISCONFIG,
                    title=f"Weak Cryptography: {title}",
                    description="Using weak cryptographic algorithm",
                    location=f"{code_path}:{content[:match.start()].count(chr(10)) + 1}",
                    remediation=remediation,
                    cwe_id="CWE-327",
                    evidence=[match.group()],
                ))

        return findings

    def _scan_xss(self, code_path: Path) -> List[SecurityFinding]:
        """Scan for XSS vulnerabilities"""
        findings = []

        if not code_path.exists():
            return findings

        content = code_path.read_text()

        # XSS patterns (in templates, HTML generation)
        xss_patterns = [
            r'\.innerHTML\s*=\s*.*\+',
            r'document\.write\s*\(',
            r'render_template_string\s*\(',
        ]

        for pattern in xss_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                findings.append(SecurityFinding(
                    finding_id=f"xss_{len(findings)}",
                    severity=Severity.HIGH,
                    vuln_type=VulnerabilityType.XSS,
                    title="Potential XSS Vulnerability",
                    description="Unsafe HTML rendering detected",
                    location=f"{code_path}:{content[:match.start()].count(chr(10)) + 1}",
                    remediation="Use safe template rendering, escape user input",
                    cwe_id="CWE-79",
                    evidence=[match.group()],
                ))

        return findings

    def generate_report(self, output_path: Path):
        """Generate security scan report"""
        # Group findings by severity
        by_severity = defaultdict(list)
        for finding in self.findings:
            by_severity[finding.severity].append(finding)

        report = {
            "scan_date": datetime.now().isoformat(),
            "total_findings": len(self.findings),
            "by_severity": {
                severity.value: len(findings)
                for severity, findings in by_severity.items()
            },
            "findings": [
                {
                    "id": f.finding_id,
                    "severity": f.severity.value,
                    "type": f.vuln_type.value,
                    "title": f.title,
                    "description": f.description,
                    "location": f.location,
                    "remediation": f.remediation,
                    "cwe_id": f.cwe_id,
                    "evidence": f.evidence,
                }
                for f in self.findings
            ],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Security report generated: {output_path}")


class RateLimiter:
    """Rate limiting and DDoS protection"""

    def __init__(self):
        self.limits: Dict[str, RateLimitConfig] = {}
        self.request_history: Dict[str, List[float]] = defaultdict(list)
        self.blocked_ips: Dict[str, float] = {}  # IP -> unblock_time

        logger.info("Rate Limiter initialized")

    def configure_limit(self, endpoint: str, config: RateLimitConfig):
        """Configure rate limit for endpoint"""
        self.limits[endpoint] = config
        logger.info(
            f"Rate limit configured: {endpoint} -> "
            f"{config.max_requests}/{config.window_seconds}s"
        )

    def check_rate_limit(
        self,
        client_ip: str,
        endpoint: str,
    ) -> tuple[bool, Optional[str]]:
        """Check if request should be allowed"""
        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            unblock_time = self.blocked_ips[client_ip]
            if time.time() < unblock_time:
                return False, f"IP blocked until {datetime.fromtimestamp(unblock_time)}"
            else:
                del self.blocked_ips[client_ip]

        # Get rate limit config
        config = self.limits.get(endpoint)
        if not config:
            return True, None  # No limit configured

        # Get request history
        key = f"{client_ip}:{endpoint}"
        now = time.time()
        window_start = now - config.window_seconds

        # Clean old entries
        self.request_history[key] = [
            t for t in self.request_history[key]
            if t > window_start
        ]

        # Check limit
        request_count = len(self.request_history[key])

        if request_count >= config.max_requests:
            # Block IP if severely over limit
            if request_count > config.max_requests * 2:
                self.blocked_ips[client_ip] = now + 3600  # Block for 1 hour
                logger.warning(f"IP blocked for excessive requests: {client_ip}")
                return False, "IP blocked for excessive requests"

            return False, f"Rate limit exceeded: {config.max_requests}/{config.window_seconds}s"

        # Record request
        self.request_history[key].append(now)
        return True, None

    def get_stats(self) -> Dict:
        """Get rate limiting statistics"""
        return {
            "total_clients": len(self.request_history),
            "blocked_ips": len(self.blocked_ips),
            "endpoints_monitored": len(self.limits),
        }


class SecretsRotator:
    """Automated secrets rotation"""

    def __init__(self, secrets_dir: Path):
        self.secrets_dir = secrets_dir
        self.secrets_dir.mkdir(parents=True, exist_ok=True)

        self.secrets: Dict[str, Secret] = {}
        self._load_secrets()

        logger.info(f"Secrets Rotator initialized: {secrets_dir}")

    def _load_secrets(self):
        """Load existing secrets"""
        secrets_file = self.secrets_dir / "secrets.json"
        if secrets_file.exists():
            with open(secrets_file) as f:
                data = json.load(f)
                for item in data.get("secrets", []):
                    self.secrets[item["secret_id"]] = Secret(
                        secret_id=item["secret_id"],
                        name=item["name"],
                        value=item["value"],
                        created_at=datetime.fromisoformat(item["created_at"]),
                        expires_at=datetime.fromisoformat(item["expires_at"]) if item.get("expires_at") else None,
                        rotation_days=item.get("rotation_days", 90),
                    )

    def _save_secrets(self):
        """Save secrets to file"""
        secrets_file = self.secrets_dir / "secrets.json"
        data = {
            "secrets": [
                {
                    "secret_id": s.secret_id,
                    "name": s.name,
                    "value": s.value,
                    "created_at": s.created_at.isoformat(),
                    "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                    "rotation_days": s.rotation_days,
                }
                for s in self.secrets.values()
            ]
        }

        with open(secrets_file, "w") as f:
            json.dump(data, f, indent=2)

    def create_secret(
        self,
        name: str,
        rotation_days: int = 90,
        length: int = 32,
    ) -> Secret:
        """Create a new secret"""
        secret_id = f"secret_{len(self.secrets)}"

        # Generate secure random secret
        value = secrets.token_urlsafe(length)

        secret = Secret(
            secret_id=secret_id,
            name=name,
            value=value,
            rotation_days=rotation_days,
            expires_at=datetime.now() + timedelta(days=rotation_days),
        )

        self.secrets[secret_id] = secret
        self._save_secrets()

        logger.info(f"Secret created: {name} (expires in {rotation_days} days)")
        return secret

    def rotate_secret(self, secret_id: str) -> Secret:
        """Rotate a secret"""
        secret = self.secrets.get(secret_id)
        if not secret:
            raise ValueError(f"Secret {secret_id} not found")

        logger.info(f"Rotating secret: {secret.name}")

        # Generate new value
        secret.value = secrets.token_urlsafe(32)
        secret.created_at = datetime.now()
        secret.expires_at = datetime.now() + timedelta(days=secret.rotation_days)

        self._save_secrets()
        return secret

    def check_expiring_secrets(self, days_threshold: int = 7) -> List[Secret]:
        """Check for secrets expiring soon"""
        expiring = []
        threshold = datetime.now() + timedelta(days=days_threshold)

        for secret in self.secrets.values():
            if secret.expires_at and secret.expires_at < threshold:
                expiring.append(secret)

        if expiring:
            logger.warning(f"Found {len(expiring)} secrets expiring within {days_threshold} days")

        return expiring

    def auto_rotate_expired(self):
        """Automatically rotate expired secrets"""
        now = datetime.now()
        rotated_count = 0

        for secret in self.secrets.values():
            if secret.expires_at and secret.expires_at < now:
                self.rotate_secret(secret.secret_id)
                rotated_count += 1

        if rotated_count > 0:
            logger.info(f"Auto-rotated {rotated_count} expired secrets")


class SecurityHeaders:
    """Security headers middleware"""

    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get recommended security headers"""
        return {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",

            # XSS protection
            "X-Content-Type-Options": "nosniff",
            "X-XSS-Protection": "1; mode=block",

            # Content Security Policy
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            ),

            # HTTPS enforcement
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",

            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",

            # Permissions policy
            "Permissions-Policy": (
                "geolocation=(), "
                "microphone=(), "
                "camera=()"
            ),
        }


async def main():
    """Test security hardening"""
    logging.basicConfig(level=logging.INFO)

    logger.info("Security Hardening Framework Test")
    logger.info("=" * 60)

    # Test 1: Security Scanner
    logger.info("\n1. Security Scanner Test:")
    scanner = SecurityScanner()

    # Scan Python files
    scan_dirs = [
        Path("ai-stack"),
        Path("scripts/ai"),
    ]

    for scan_dir in scan_dirs:
        if scan_dir.exists():
            for py_file in scan_dir.rglob("*.py"):
                scanner.scan_code(py_file)

    # Generate report
    report_path = Path(".agents/security/scan_report.json")
    scanner.generate_report(report_path)

    logger.info(f"  Total findings: {len(scanner.findings)}")
    by_severity = defaultdict(int)
    for finding in scanner.findings:
        by_severity[finding.severity.value] += 1

    for severity, count in sorted(by_severity.items()):
        logger.info(f"    {severity}: {count}")

    # Test 2: Rate Limiter
    logger.info("\n2. Rate Limiter Test:")
    limiter = RateLimiter()

    limiter.configure_limit("/api/hints", RateLimitConfig(
        max_requests=10,
        window_seconds=60,
    ))

    # Simulate requests
    for i in range(15):
        allowed, reason = limiter.check_rate_limit("192.168.1.100", "/api/hints")
        if not allowed:
            logger.info(f"  Request {i+1}: BLOCKED - {reason}")
            break
    else:
        logger.info(f"  All requests allowed")

    stats = limiter.get_stats()
    logger.info(f"  Stats: {stats}")

    # Test 3: Secrets Rotation
    logger.info("\n3. Secrets Rotation Test:")
    secrets_dir = Path(".agents/security/secrets")
    rotator = SecretsRotator(secrets_dir)

    # Create secrets
    api_secret = rotator.create_secret("api_key", rotation_days=30)
    logger.info(f"  Created: {api_secret.name} = {api_secret.value[:16]}...")

    # Check expiring
    expiring = rotator.check_expiring_secrets(days_threshold=60)
    logger.info(f"  Expiring soon: {len(expiring)} secrets")

    # Test 4: Security Headers
    logger.info("\n4. Security Headers Test:")
    headers = SecurityHeaders.get_security_headers()
    logger.info(f"  Recommended headers: {len(headers)}")
    for header, value in headers.items():
        logger.info(f"    {header}: {value[:50]}{'...' if len(value) > 50 else ''}")


if __name__ == "__main__":
    asyncio.run(main())

"""Anti-SSRF and Domain Security Policy Enforcement for Phase 9."""

import fnmatch
import ipaddress
import logging
import socket
from urllib.parse import urlparse
from typing import Optional

logger = logging.getLogger(__name__)


class SsrfSecurityError(Exception):
    """Raised when an outgoing request violates Anti-SSRF boundaries."""
    pass


class DomainPolicyError(Exception):
    """Raised when a request violates domain whitelist/blacklist policy."""
    pass


# Specific cloud metadata and private IP networks that must never be contacted
FORBIDDEN_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918 private
    ipaddress.ip_network("172.16.0.0/12"),     # RFC 1918 private
    ipaddress.ip_network("192.168.0.0/16"),    # RFC 1918 private
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / AWS & GCP cloud metadata (169.254.169.254)
    ipaddress.ip_network("0.0.0.0/8"),         # Current network
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]


class DomainPolicy:
    """Configurable domain allowlist/denylist and resource quota rules."""

    def __init__(
        self,
        allowed_domains: Optional[list[str]] = None,
        blocked_domains: Optional[list[str]] = None,
        max_redirects: int = 5,
        max_response_bytes: int = 5_242_880,  # 5 MB
        max_extracted_chars: int = 100_000,
        timeout_seconds: float = 20.0,
    ):
        self.allowed_domains = allowed_domains
        self.blocked_domains = blocked_domains or []
        self.max_redirects = max_redirects
        self.max_response_bytes = max_response_bytes
        self.max_extracted_chars = max_extracted_chars
        self.timeout_seconds = timeout_seconds

    def is_domain_permitted(self, hostname: str) -> bool:
        """Check whether hostname passes allowlist and denylist filters."""
        host_lower = hostname.lower().strip(".")

        # Explicit blocklist check
        for pattern in self.blocked_domains:
            if fnmatch.fnmatch(host_lower, pattern.lower()) or host_lower == pattern.lower():
                return False

        # Whitelist check (if configured)
        if self.allowed_domains:
            allowed = False
            for pattern in self.allowed_domains:
                if fnmatch.fnmatch(host_lower, pattern.lower()) or host_lower == pattern.lower():
                    allowed = True
                    break
            if not allowed:
                return False

        return True


def is_ip_forbidden(ip_str: str) -> bool:
    """Check if an IP address falls within private, loopback, or cloud-metadata ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True

    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True

    for net in FORBIDDEN_NETWORKS:
        if ip in net:
            return True

    return False


def validate_url_against_ssrf(
    url: str,
    policy: Optional[DomainPolicy] = None,
) -> str:
    """
    Validate target URL against Anti-SSRF and domain policy rules.
    Performs pre-flight DNS resolution to ensure host does not resolve to private IPs.
    Returns canonical URL if valid; raises SsrfSecurityError or DomainPolicyError otherwise.
    """
    if not url or not isinstance(url, str):
        raise SsrfSecurityError("Invalid or empty URL provided.")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise SsrfSecurityError(
            f"Blocked scheme '{parsed.scheme}'. Only 'http' and 'https' protocols are permitted."
        )

    hostname = parsed.hostname
    if not hostname:
        raise SsrfSecurityError(f"Cannot parse valid hostname from URL '{url}'.")

    hostname_clean = hostname.lower().strip("[]")

    # Reject literal localhost or raw forbidden IP in URL
    if hostname_clean in ("localhost", "127.0.0.1", "::1"):
        raise SsrfSecurityError(f"Access to localhost/loopback ('{hostname}') is blocked by Anti-SSRF policy.")

    # Check if host is a literal IP address
    try:
        literal_ip = ipaddress.ip_address(hostname_clean)
        if is_ip_forbidden(str(literal_ip)):
            raise SsrfSecurityError(
                f"Access to private/internal IP '{hostname_clean}' is strictly blocked by Anti-SSRF policy."
            )
    except ValueError:
        pass  # Hostname is a domain name, proceed to DNS resolution

    # Domain allow/deny check
    if policy and not policy.is_domain_permitted(hostname_clean):
        raise DomainPolicyError(
            f"Access to domain '{hostname_clean}' is blocked by task domain policy."
        )

    # Pre-flight DNS resolution to check for DNS rebinding / private IP resolution
    try:
        addr_info = socket.getaddrinfo(hostname_clean, parsed.port or (443 if parsed.scheme == "https" else 80))
        for item in addr_info:
            sockaddr = item[4]
            resolved_ip = sockaddr[0]
            if is_ip_forbidden(resolved_ip):
                raise SsrfSecurityError(
                    f"Domain '{hostname_clean}' resolves to private/internal IP '{resolved_ip}', "
                    "which is strictly blocked by Anti-SSRF policy."
                )
    except socket.gaierror as e:
        raise SsrfSecurityError(f"DNS resolution failed for host '{hostname_clean}': {e}")

    return url

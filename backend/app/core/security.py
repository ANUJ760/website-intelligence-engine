"""Shared URL-safety and SSRF protection module.

Enforces:
- Scheme validation (http/https only)
- Credential rejection (no embedded user:pass)
- Port restrictions (allowlist, e.g. 80, 443)
- Comprehensive IP validation (rejection of loopback, RFC1918, link-local,
  multicast, CGNAT, documentation, unspecified, and IPv4-mapped IPv6)
- Pre-connection DNS resolution and validation
- Connection IP pinning to prevent DNS rebinding attacks
"""

import ipaddress
import socket
import ssl
import sys
from typing import Callable, Iterable, List, Optional, Tuple, Union
from urllib.parse import urlsplit, SplitResult

import anyio
import httpcore
from httpcore._backends.anyio import AnyIOBackend, AnyIOStream
from httpcore._exceptions import ConnectError, ConnectTimeout, map_exceptions
from httpcore import SOCKET_OPTION
import httpx

from app.config import settings


class SSRFError(ValueError):
    """Base exception for all SSRF and URL security violations."""
    pass


class InvalidSchemeError(SSRFError):
    """Raised when URL scheme is not http or https."""
    pass


class EmbeddedCredentialsError(SSRFError):
    """Raised when URL contains embedded user/password credentials."""
    pass


class DisallowedPortError(SSRFError):
    """Raised when URL port is not in the allowed list."""
    pass


class DNSResolutionError(SSRFError):
    """Raised when hostname resolution fails."""
    pass


class PrivateIPError(SSRFError):
    """Raised when a resolved IP is private, loopback, link-local, or reserved."""
    pass


# Specific ranges to explicitly block even if OS/library nuances vary
ADDITIONAL_BLOCKED_NETWORKS = [
    ipaddress.ip_network("100.64.0.0/10"),    # Carrier-Grade NAT (RFC 6598)
    ipaddress.ip_network("169.254.0.0/16"),   # IPv4 Link-Local (Cloud metadata)
    ipaddress.ip_network("192.0.0.0/24"),     # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),     # TEST-NET-1 (Documentation)
    ipaddress.ip_network("198.18.0.0/15"),    # Network Benchmark Tests (RFC 2544)
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2 (Documentation)
    ipaddress.ip_network("203.0.113.0/24"),   # TEST-NET-3 (Documentation)
    ipaddress.ip_network("240.0.0.0/4"),      # Reserved (Former Class E)
    ipaddress.ip_network("255.255.255.255/32"), # Limited Broadcast
    ipaddress.ip_network("fe80::/10"),        # IPv6 Link-Local
    ipaddress.ip_network("fc00::/7"),         # IPv6 Unique Local Address (ULA)
    ipaddress.ip_network("2001:db8::/32"),    # IPv6 Documentation
]


def is_ip_safe(ip: Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    """Check if an IP address is a safe, globally routable public address."""
    if isinstance(ip, str):
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return False
    else:
        ip_obj = ip

    # Unpack IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1 or ::ffff:10.0.0.1)
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        ip_obj = ip_obj.ipv4_mapped

    # Check standard properties
    if (
        ip_obj.is_loopback
        or ip_obj.is_private
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
        or ip_obj.is_reserved
    ):
        return False

    # Check global routability
    if not ip_obj.is_global:
        return False

    # Check against explicit blocked network definitions
    for net in ADDITIONAL_BLOCKED_NETWORKS:
        if ip_obj in net:
            return False

    return True


def validate_url_syntax(
    url: str,
    allowed_ports: Optional[List[int]] = None,
) -> SplitResult:
    """Validate URL syntax, scheme, credentials, and port without DNS resolution."""
    if not url or not isinstance(url, str):
        raise SSRFError("URL must be a non-empty string.")

    url_clean = url.strip()
    try:
        parsed = urlsplit(url_clean)
    except Exception as exc:
        raise SSRFError(f"Malformed URL: {exc}") from exc

    # 1. Scheme validation
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise InvalidSchemeError(
            f"Invalid URL scheme '{parsed.scheme}'. Only http and https are allowed."
        )

    # 2. Hostname presence
    if not parsed.hostname:
        raise SSRFError("URL must contain a valid hostname.")

    # 3. Embedded credentials check
    if parsed.username is not None or parsed.password is not None:
        raise EmbeddedCredentialsError("URLs with embedded credentials are not allowed.")

    # 4. Port check
    ports = allowed_ports if allowed_ports is not None else settings.ALLOWED_PORTS
    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80

    if port not in ports:
        raise DisallowedPortError(
            f"Port {port} is not in the allowed ports list: {ports}"
        )

    return parsed


DNSResolverType = Callable[[str, int], List[str]]


def default_dns_resolver(hostname: str, port: int) -> List[str]:
    """Resolve hostname to list of unique IP addresses using system getaddrinfo."""
    try:
        addr_info = socket.getaddrinfo(
            hostname,
            port,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise DNSResolutionError(f"Could not resolve hostname '{hostname}': {exc}") from exc

    resolved_ips = []
    for family, socktype, proto, canonname, sockaddr in addr_info:
        ip = sockaddr[0]
        if ip not in resolved_ips:
            resolved_ips.append(ip)

    if not resolved_ips:
        raise DNSResolutionError(f"No IP addresses found for hostname '{hostname}'.")

    return resolved_ips


def resolve_and_validate_hostname(
    hostname: str,
    port: int,
    resolver: Optional[DNSResolverType] = None,
) -> List[str]:
    """Resolve hostname and assert that ALL resolved IP addresses are safe.
    
    If any resolved IP address is private or non-routable, reject the entire destination.
    """
    resolve_fn = resolver or default_dns_resolver
    resolved_ips = resolve_fn(hostname, port)

    for ip_str in resolved_ips:
        if not is_ip_safe(ip_str):
            raise PrivateIPError(
                f"Hostname '{hostname}' resolved to prohibited/non-public IP: {ip_str}"
            )

    return resolved_ips


def validate_url(
    url: str,
    allowed_ports: Optional[List[int]] = None,
    resolver: Optional[DNSResolverType] = None,
) -> Tuple[str, str]:
    """Fully validate a URL and return (normalized_url, pinned_ip).
    
    Resolves DNS once and validates all IPs. Returns the first safe IP to pin connections to.
    """
    parsed = validate_url_syntax(url, allowed_ports)
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    
    resolved_ips = resolve_and_validate_hostname(parsed.hostname, port, resolver)
    pinned_ip = resolved_ips[0]

    return url.strip(), pinned_ip


class PinnedAnyIOBackend(AnyIOBackend):
    """AnyIO backend that connects to a pinned IP address instead of resolving host anew."""

    def __init__(self, pinned_ip: str):
        self.pinned_ip = pinned_ip

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Iterable[SOCKET_OPTION]] = None,
    ) -> AnyIOStream:
        # Connect directly to the pre-validated pinned IP, preventing DNS rebinding
        return await super().connect_tcp(
            host=self.pinned_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class PinnedTransport(httpx.AsyncHTTPTransport):
    """Custom HTTPX transport that pins TCP connections to a specific, validated IP address.
    
    Maintains original Host header and TLS SNI / certificate verification for the target hostname.
    """

    def __init__(self, pinned_ip: str, verify: Union[ssl.SSLContext, str, bool] = True, **kwargs):
        super().__init__(verify=verify, **kwargs)
        # Replace the connection pool with one using the PinnedAnyIOBackend
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            network_backend=PinnedAnyIOBackend(pinned_ip),
            retries=0,
        )

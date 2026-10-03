"""Tests for URL safety, SSRF validation, and IP pinning."""

import pytest
from app.core.security import (
    is_ip_safe,
    validate_url_syntax,
    validate_url,
    resolve_and_validate_hostname,
    SSRFError,
    InvalidSchemeError,
    EmbeddedCredentialsError,
    DisallowedPortError,
    PrivateIPError,
    DNSResolutionError,
)


def test_is_ip_safe_with_private_ips():
    disallowed = [
        "127.0.0.1",
        "127.0.1.1",
        "10.0.0.1",
        "10.254.254.1",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.0.1",
        "192.168.1.100",
        "169.254.169.254",  # AWS/GCP/Azure metadata
        "169.254.1.1",
        "0.0.0.0",
        "255.255.255.255",
        "100.64.0.1",       # Carrier Grade NAT
        "192.0.2.1",        # TEST-NET-1
        "198.51.100.1",     # TEST-NET-2
        "203.0.113.1",      # TEST-NET-3
        "224.0.0.1",        # Multicast
        "240.0.0.1",        # Reserved
        "::1",              # IPv6 loopback
        "::",               # IPv6 unspecified
        "fe80::1",          # IPv6 link-local
        "fc00::1",          # IPv6 ULA
        "fd12:3456:789a::1",
        "::ffff:127.0.0.1", # IPv4-mapped IPv6 loopback
        "::ffff:10.0.0.1",  # IPv4-mapped IPv6 private
        "::ffff:169.254.169.254",
    ]
    for ip in disallowed:
        assert not is_ip_safe(ip), f"IP {ip} should be rejected as unsafe"


def test_is_ip_safe_with_public_ips():
    allowed = [
        "8.8.8.8",
        "1.1.1.1",
        "93.184.215.14",
        "142.250.190.46",
        "2606:2800:220:1:248:1893:25c8:1946",
    ]
    for ip in allowed:
        assert is_ip_safe(ip), f"IP {ip} should be accepted as safe"


def test_scheme_validation():
    # Valid schemes
    validate_url_syntax("http://example.com")
    validate_url_syntax("https://example.com")

    # Invalid schemes
    invalid_schemes = [
        "file:///etc/passwd",
        "ftp://example.com/file.txt",
        "gopher://example.com",
        "data:text/plain;base64,SGVsbG8=",
        "javascript:alert(1)",
        "ssh://example.com",
    ]
    for url in invalid_schemes:
        with pytest.raises(InvalidSchemeError):
            validate_url_syntax(url)


def test_credentials_rejection():
    with pytest.raises(EmbeddedCredentialsError):
        validate_url_syntax("http://user:pass@example.com")
    with pytest.raises(EmbeddedCredentialsError):
        validate_url_syntax("https://admin:@example.com/login")


def test_disallowed_ports():
    # Ports 80 and 443 are allowed by default
    validate_url_syntax("http://example.com:80")
    validate_url_syntax("https://example.com:443")

    # Other ports rejected
    disallowed_urls = [
        "http://example.com:22",
        "http://example.com:8080",
        "http://example.com:3000",
        "http://example.com:6379",
    ]
    for url in disallowed_urls:
        with pytest.raises(DisallowedPortError):
            validate_url_syntax(url)


def test_hostname_resolving_to_private_ip():
    def mock_private_resolver(hostname: str, port: int):
        return ["192.168.1.50"]

    with pytest.raises(PrivateIPError):
        resolve_and_validate_hostname("internal.corp", 80, resolver=mock_private_resolver)


def test_hostname_resolving_to_mixed_ips():
    # If ANY resolved IP is private, destination is rejected
    def mock_mixed_resolver(hostname: str, port: int):
        return ["93.184.215.14", "10.0.0.1"]

    with pytest.raises(PrivateIPError):
        resolve_and_validate_hostname("sneaky.com", 80, resolver=mock_mixed_resolver)


def test_unusual_ip_encodings():
    # Decimal 2130706433 resolves to 127.0.0.1
    with pytest.raises(PrivateIPError):
        validate_url("http://2130706433")

    # Localhost resolves to loopback
    with pytest.raises(PrivateIPError):
        validate_url("http://localhost")


def test_dns_rebinding_pinning():
    # Resolver returns public IP
    calls = []
    def mock_resolver(hostname: str, port: int):
        calls.append(hostname)
        return ["93.184.215.14"]

    normalized, pinned_ip = validate_url("https://example.com/test", resolver=mock_resolver)
    assert normalized == "https://example.com/test"
    assert pinned_ip == "93.184.215.14"
    assert len(calls) == 1

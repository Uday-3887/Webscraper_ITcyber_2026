from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedURL:
    url: str
    hostname: str
    addresses: tuple[str, ...]


BLOCKED_HOSTNAMES = {
    'localhost', 'localhost.localdomain', 'metadata.google.internal',
    'metadata', 'instance-data',
}


def _is_blocked_ip(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text.split('%')[0])
    return any((
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    ))


@lru_cache(maxsize=512)
def resolve_public_addresses(hostname: str) -> tuple[str, ...]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError(f'Domain could not be resolved: {hostname}') from exc
    addresses = tuple(sorted({info[4][0] for info in infos}))
    if not addresses:
        raise UnsafeURLError('Domain did not resolve to an IP address.')
    for address in addresses:
        if _is_blocked_ip(address):
            raise UnsafeURLError('Private, local, reserved, or link-local network addresses are blocked.')
    return addresses


def validate_url(url: str, *, resolve_dns: bool = True) -> ValidatedURL:
    value = (url or '').strip()
    if not value:
        raise UnsafeURLError('Website URL is required.')
    if len(value) > 2048:
        raise UnsafeURLError('Website URL is too long.')

    parsed = urlparse(value)
    if parsed.scheme.lower() not in {'http', 'https'}:
        raise UnsafeURLError('Only http:// and https:// URLs are allowed.')
    if parsed.username or parsed.password:
        raise UnsafeURLError('URLs containing usernames or passwords are not allowed.')
    if not parsed.hostname:
        raise UnsafeURLError('A valid hostname is required.')

    hostname = parsed.hostname.rstrip('.').lower()
    if hostname in BLOCKED_HOSTNAMES or hostname.endswith('.localhost'):
        raise UnsafeURLError('Localhost and metadata endpoints are blocked.')

    try:
        if _is_blocked_ip(hostname):
            raise UnsafeURLError('Private or local IP addresses are blocked.')
    except ValueError:
        pass

    addresses = resolve_public_addresses(hostname) if resolve_dns else tuple()
    return ValidatedURL(url=value, hostname=hostname, addresses=addresses)


def is_safe_browser_request(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme in {'data', 'blob', 'about'}:
        return True
    try:
        validate_url(url, resolve_dns=True)
        return True
    except (UnsafeURLError, ValueError):
        return False

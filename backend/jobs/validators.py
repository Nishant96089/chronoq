"""
SSRF protection for job target URLs.

chronoq executes user-supplied URLs on a schedule from inside the deployment's
network, which is a textbook SSRF surface: without guards, a job could be
pointed at the cloud metadata endpoint (169.254.169.254), localhost, or an
internal admin panel. validate_public_url rejects anything that isn't plain
http(s) to a public host, resolving the host first so that a public hostname
pointing at a private address is caught too.
"""

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


class UnsafeTargetURLError(ValueError):
    """Raised when a target URL must not be reached (bad scheme or private IP)."""


def _is_disallowed_ip(ip_str: str) -> bool:
    """True if the address is anything other than a routable public host."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        # Unparseable (e.g. scoped IPv6) -> refuse, fail safe.
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local  # 169.254.0.0/16, incl. cloud metadata 169.254.169.254
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_url(url: str) -> None:
    """
    Raise UnsafeTargetURLError unless `url` is http(s) to a public host.

    Resolves the host to every address it maps to (v4 + v6) and rejects if ANY
    is non-public, so split-horizon / rebinding tricks don't slip through a
    single lookup.
    """
    parsed = urlparse(url)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeTargetURLError(f"URL scheme must be http or https, not '{parsed.scheme}'.")

    host = parsed.hostname
    if not host:
        raise UnsafeTargetURLError("URL has no host.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise UnsafeTargetURLError(f"Could not resolve host '{host}'.") from e

    for info in infos:
        ip_str = info[4][0]
        if _is_disallowed_ip(ip_str):
            raise UnsafeTargetURLError(
                f"URL host '{host}' resolves to a non-public address ({ip_str})."
            )

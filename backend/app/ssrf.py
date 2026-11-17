# SPDX-License-Identifier: AGPL-3.0-or-later
"""SSRF-safe outbound fetch for URLs we do not fully control (e.g. provider result URLs).

Rules: https only (http optional), default ports only, resolve-then-connect to a vetted
public IP (no DNS rebinding window), no automatic redirects (each hop re-validated),
response size cap.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx


class UnsafeURLError(ValueError):
    pass


ALLOWED_PORTS = {"https": 443, "http": 80}


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_link_local)


async def resolve_public_ip(host: str) -> str:
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        if not _is_public(literal):
            raise UnsafeURLError("address not allowed")
        return str(literal)
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError("cannot resolve host") from exc
    ips = {ipaddress.ip_address(info[4][0]) for info in infos}
    # Every resolved address must be public, otherwise refuse (prevents mixed-record tricks).
    if not ips or not all(_is_public(ip) for ip in ips):
        raise UnsafeURLError("address not allowed")
    return str(sorted(ips, key=lambda i: i.version)[0])


def validate_url(url: str, allow_http: bool = False) -> tuple[str, str, int]:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    allowed = {"https", "http"} if allow_http else {"https"}
    if scheme not in allowed:
        raise UnsafeURLError("scheme not allowed")
    if parts.username or parts.password:
        raise UnsafeURLError("credentials in URL not allowed")
    host = parts.hostname
    if not host:
        raise UnsafeURLError("missing host")
    port = parts.port or ALLOWED_PORTS[scheme]
    if port != ALLOWED_PORTS[scheme]:
        raise UnsafeURLError("port not allowed")
    return scheme, host, port


async def safe_get(
    url: str,
    *,
    max_bytes: int,
    request_timeout: float = 30.0,
    max_redirects: int = 3,
    allow_http: bool = False,
    headers: dict[str, str] | None = None,
) -> tuple[bytes, str]:
    """GET a URL safely. Returns (body, content-type header)."""
    current = url
    async with httpx.AsyncClient(timeout=request_timeout, follow_redirects=False) as client:
        for _ in range(max_redirects + 1):
            scheme, host, port = validate_url(current, allow_http)
            ip = await resolve_public_ip(host)
            parts = urlsplit(current)
            ip_host = f"[{ip}]" if ":" in ip else ip
            pinned = urlunsplit((scheme, f"{ip_host}:{port}", parts.path or "/", parts.query, ""))
            req_headers = {"Host": host, **(headers or {})}
            async with client.stream(
                "GET", pinned, headers=req_headers, extensions={"sni_hostname": host}
            ) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise UnsafeURLError("redirect without location")
                    current = urljoin(current, location)
                    continue
                resp.raise_for_status()
                declared = resp.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise UnsafeURLError("response too large")
                body = bytearray()
                async for chunk in resp.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise UnsafeURLError("response too large")
                return bytes(body), resp.headers.get("content-type", "")
    raise UnsafeURLError("too many redirects")

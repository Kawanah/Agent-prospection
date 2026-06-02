"""Garde-fous réseau pour les appels HTTP sortants."""

import ipaddress
import socket
import urllib.parse

MAX_REDIRECTS = 5
_BLOCKED_HOSTNAMES = {"localhost"}


def validate_public_http_url(url: str) -> str:
    """Valide une URL cible et bloque les destinations réseau internes."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL non autorisée")

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in _BLOCKED_HOSTNAMES:
        raise ValueError("Hôte local non autorisé")

    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Résolution DNS impossible") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("Adresse réseau interne non autorisée")

    return urllib.parse.urlunparse(parsed)

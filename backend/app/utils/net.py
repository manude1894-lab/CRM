"""The caller's network address. Behind Railway's proxy, request.client is the proxy; the proxy puts the real address
in X-Real-IP / X-Forwarded-For. The right-most X-Forwarded-For entry is the one the proxy itself added (anything to
its left was sent by the caller and can be made up), so that one is used."""
from typing import Optional

from fastapi import Request


def client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    real = (request.headers.get("x-real-ip") or "").strip()
    if real:
        return real
    forwarded = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",") if p.strip()]
    if forwarded:
        return forwarded[-1]
    return request.client.host if request.client else None

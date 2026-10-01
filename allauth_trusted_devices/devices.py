"""Cookie and database bookkeeping for trusted devices."""

import hashlib
import secrets

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from allauth_trusted_devices.app_settings import app_settings
from allauth_trusted_devices.models import TrustedDevice

# Set on the request when a cookie must be written; TrustedDeviceMiddleware writes it.
PENDING_COOKIE_ATTR = "_trusted_device_token"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_token(request: HttpRequest) -> str | None:
    pending = getattr(request, PENDING_COOKIE_ATTR, None)
    if pending:
        return pending
    token = request.COOKIES.get(app_settings.COOKIE_NAME)
    # Ignore anything that is not shaped like a token we issued.
    if token and 20 <= len(token) <= 100:
        return token
    return None


def _client_ip(request: HttpRequest) -> str | None:
    from allauth_trusted_devices.adapter import get_adapter

    return get_adapter().get_client_ip(request)


def _user_agent(request: HttpRequest) -> str:
    return request.META.get("HTTP_USER_AGENT", "")[:1000]


def get_trusted_device(request: HttpRequest, user) -> TrustedDevice | None:
    token = get_token(request)
    if not token or user is None or user.pk is None:
        return None
    return TrustedDevice.objects.active().filter(user=user, token_hash=hash_token(token)).first()


def touch(request: HttpRequest, device: TrustedDevice) -> None:
    device.last_used_at = timezone.now()
    device.last_ip_address = _client_ip(request)
    device.save(update_fields=["last_used_at", "last_ip_address"])
    # Re-issue the cookie so a device in regular use does not expire.
    setattr(request, PENDING_COOKIE_ATTR, get_token(request))


def trust_device(request: HttpRequest, user) -> TrustedDevice:
    """Register the current browser for ``user`` and queue the cookie.

    The browser keeps its existing token when it has one, so another user's trust on the same
    browser stays valid.
    """
    token = get_token(request) or secrets.token_urlsafe(32)
    ip = _client_ip(request)
    device, created = TrustedDevice.objects.get_or_create(
        user=user,
        token_hash=hash_token(token),
        defaults={"user_agent": _user_agent(request), "ip_address": ip, "last_ip_address": ip},
    )
    if not created:
        # A removed browser that passed the new-device check again: trust it again.
        device.revoked_at = None
        device.user_agent = _user_agent(request)
        device.last_ip_address = ip
        device.last_used_at = timezone.now()
        device.save(update_fields=["revoked_at", "user_agent", "last_ip_address", "last_used_at"])
    setattr(request, PENDING_COOKIE_ATTR, token)
    return device


def set_cookie(response: HttpResponse, token: str) -> None:
    response.set_cookie(
        app_settings.COOKIE_NAME,
        token,
        max_age=app_settings.COOKIE_AGE,
        domain=app_settings.COOKIE_DOMAIN,
        path=app_settings.COOKIE_PATH,
        secure=app_settings.COOKIE_SECURE,
        httponly=True,
        samesite=app_settings.COOKIE_SAMESITE,
    )


def is_current_device(request: HttpRequest, device: TrustedDevice) -> bool:
    token = get_token(request)
    return bool(token) and secrets.compare_digest(device.token_hash, hash_token(token))


def revoke(device: TrustedDevice) -> None:
    device.revoked_at = timezone.now()
    device.save(update_fields=["revoked_at"])


def revoke_other_devices(request: HttpRequest, user) -> int:
    devices = TrustedDevice.objects.active().filter(user=user)
    token = get_token(request)
    if token:
        devices = devices.exclude(token_hash=hash_token(token))
    return devices.update(revoked_at=timezone.now())

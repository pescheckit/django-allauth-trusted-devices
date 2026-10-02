"""Cookie and database bookkeeping for trusted devices."""

import hashlib
import secrets

from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from allauth_trusted_devices.app_settings import app_settings
from allauth_trusted_devices.models import TrustedDevice

# Set on the request when a cookie must be written; TrustedDeviceMiddleware writes it.
PENDING_COOKIE_ATTR = "_trusted_device_token"
# Session key holding the TrustedDevice the session signed in with. TrustedDeviceMiddleware logs the
# session out once that device is removed. Django keeps session data across login (cycle_key).
SESSION_DEVICE_KEY = "allauth_trusted_devices_device_id"


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
    bind_session(request, device)


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
    bind_session(request, device)
    return device


def bind_session(request: HttpRequest, device: TrustedDevice) -> None:
    """Remember in the session which device it belongs to, so removing the device ends it."""
    session = getattr(request, "session", None)
    if session is not None:
        session[SESSION_DEVICE_KEY] = device.pk


def session_device_removed(request: HttpRequest) -> bool:
    """Whether this session signed in with a device that has been removed since."""
    device_id = request.session.get(SESSION_DEVICE_KEY)
    if device_id is None:
        return False
    return not TrustedDevice.objects.active().filter(pk=device_id, user_id=request.user.pk).exists()


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

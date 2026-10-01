from allauth.account.adapter import get_adapter as get_account_adapter
from allauth.account.authentication import get_authentication_records
from allauth.account.models import EmailAddress
from allauth.utils import build_absolute_uri
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.module_loading import import_string

from allauth_trusted_devices.app_settings import MODE_OFF, MODES, app_settings
from allauth_trusted_devices.utils import describe_user_agent

# Some allauth flows (social login) record the authentication just before the Login object is
# created, so a record slightly older than the login still belongs to it.
RECORD_CLOCK_SKEW = 60


class DefaultTrustedDevicesAdapter:
    """Override this (``TRUSTED_DEVICES_ADAPTER``) to change policy per user or organisation."""

    def get_mode(self, request: HttpRequest, user) -> str:
        """``off``, ``notify`` or ``confirm`` for this user. Defaults to ``TRUSTED_DEVICES_MODE``."""
        mode = app_settings.MODE
        return mode if mode in MODES else MODE_OFF

    def trust_first_device_silently(self, request: HttpRequest, user) -> bool:
        """Whether to trust this device without email or code because the user has none yet.

        Controlled by ``TRUSTED_DEVICES_SILENT_FIRST_DEVICE``, so that installing the package on an
        existing site does not email every user on their next sign-in.
        """
        from allauth_trusted_devices.models import TrustedDevice

        return app_settings.SILENT_FIRST_DEVICE and not TrustedDevice.objects.filter(user=user).exists()

    def get_login_methods(self, request: HttpRequest, login) -> set[str]:
        """The allauth authentication methods used during this login attempt."""
        since = login.initiated_at - RECORD_CLOCK_SKEW
        return {record.get("method") for record in get_authentication_records(request) if record.get("at", 0) >= since}

    def requires_confirmation(self, request: HttpRequest, login) -> bool:
        """Whether a new device must be confirmed by code, given the mode is ``confirm``."""
        return not (self.get_login_methods(request, login) & set(app_settings.SKIP_CONFIRM_METHODS))

    def get_email(self, user) -> str | None:
        return EmailAddress.objects.get_primary_email(user) or getattr(user, "email", None) or None

    def get_client_ip(self, request: HttpRequest) -> str | None:
        try:
            return get_account_adapter(request).get_client_ip(request)
        except PermissionDenied:
            return None

    def generate_code(self) -> str:
        return get_account_adapter().generate_login_code()

    def get_mail_context(self, request: HttpRequest, user, **extra) -> dict:
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        try:
            devices_url = build_absolute_uri(request, reverse("trusted_devices_list"))
        except NoReverseMatch:
            devices_url = None
        context = {
            "user": user,
            "ip": self.get_client_ip(request),
            "user_agent": user_agent,
            "device": describe_user_agent(user_agent),
            "timestamp": timezone.now(),
            "devices_url": devices_url,
        }
        context.update(extra)
        return context

    def send_mail(self, request: HttpRequest, template_prefix: str, email: str, context: dict) -> None:
        """Delegates to the allauth account adapter, so a project's email setup applies."""
        get_account_adapter(request).send_mail(template_prefix, email, context)

    def send_new_device_mail(self, request: HttpRequest, user) -> None:
        email = self.get_email(user)
        if email:
            context = self.get_mail_context(request, user)
            self.send_mail(request, "allauth_trusted_devices/email/new_device", email, context)

    def send_confirmation_code_mail(self, request: HttpRequest, user, email: str, code: str) -> None:
        context = self.get_mail_context(request, user, code=code)
        self.send_mail(request, "allauth_trusted_devices/email/confirm_device", email, context)


def get_adapter() -> DefaultTrustedDevicesAdapter:
    return import_string(app_settings.ADAPTER)()


class TrustedDevicesAccountAdapterMixin:
    """Mix into your ``ACCOUNT_ADAPTER`` to add the trusted-device stage after allauth's own."""

    def get_login_stages(self):
        stages = list(super().get_login_stages())
        stages.append("allauth_trusted_devices.stages.TrustedDeviceStage")
        return stages

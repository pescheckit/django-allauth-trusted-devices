"""Settings, all prefixed with ``TRUSTED_DEVICES_``. Read lazily so tests can override them."""

from datetime import timedelta

from django.conf import settings

MODE_OFF = "off"
MODE_NOTIFY = "notify"
MODE_CONFIRM = "confirm"
MODES = (MODE_OFF, MODE_NOTIFY, MODE_CONFIRM)


class AppSettings:
    prefix = "TRUSTED_DEVICES_"

    def _setting(self, name, default):
        return getattr(settings, self.prefix + name, default)

    @property
    def ADAPTER(self) -> str:
        return self._setting("ADAPTER", "allauth_trusted_devices.adapter.DefaultTrustedDevicesAdapter")

    @property
    def MODE(self) -> str:
        """``notify``: email on a new device. ``confirm``: require an emailed code. ``off``: do nothing."""
        return self._setting("MODE", MODE_NOTIFY)

    @property
    def SKIP_CONFIRM_METHODS(self) -> list[str]:
        """allauth authentication methods that already prove possession of a second factor.

        A login that used one of these in ``confirm`` mode is not asked for an extra code; the
        device is registered and the user is notified instead. ``mfa`` covers TOTP, WebAuthn and
        recovery codes, ``code`` covers allauth's login-by-code. Add ``socialaccount`` to trust
        the identity provider.
        """
        return self._setting("SKIP_CONFIRM_METHODS", ["mfa", "code"])

    @property
    def SILENT_FIRST_DEVICE(self) -> bool:
        """Trust a user's first device without email or code (any mode).

        Meant for rolling the package out on a site with existing users. It also covers a user who
        removed all their devices, so leave it off where that matters more than a quiet rollout.
        """
        return self._setting("SILENT_FIRST_DEVICE", False)

    @property
    def NOTIFY_AFTER_SKIPPED_CONFIRM(self) -> bool:
        return self._setting("NOTIFY_AFTER_SKIPPED_CONFIRM", True)

    @property
    def REVOKE_ON_PASSWORD_CHANGE(self) -> bool:
        """Forget all other devices when the password is changed, set or reset."""
        return self._setting("REVOKE_ON_PASSWORD_CHANGE", True)

    @property
    def CODE_TIMEOUT(self) -> int:
        return self._setting("CODE_TIMEOUT", 15 * 60)

    @property
    def CODE_MAX_ATTEMPTS(self) -> int:
        return self._setting("CODE_MAX_ATTEMPTS", 3)

    @property
    def CODE_MAX_RESEND_COUNT(self) -> int:
        return self._setting("CODE_MAX_RESEND_COUNT", 1)

    @property
    def COOKIE_NAME(self) -> str:
        return self._setting("COOKIE_NAME", "trusted_device")

    @property
    def COOKIE_AGE(self) -> timedelta:
        age = self._setting("COOKIE_AGE", timedelta(days=365))
        if not isinstance(age, timedelta):
            age = timedelta(seconds=age)
        return age

    @property
    def COOKIE_DOMAIN(self):
        return self._setting("COOKIE_DOMAIN", settings.SESSION_COOKIE_DOMAIN)

    @property
    def COOKIE_PATH(self) -> str:
        return self._setting("COOKIE_PATH", settings.SESSION_COOKIE_PATH)

    @property
    def COOKIE_SECURE(self) -> bool:
        return self._setting("COOKIE_SECURE", settings.SESSION_COOKIE_SECURE)

    @property
    def COOKIE_SAMESITE(self):
        return self._setting("COOKIE_SAMESITE", "Lax")


app_settings = AppSettings()

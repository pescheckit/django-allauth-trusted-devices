from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TrustedDevicesConfig(AppConfig):
    name = "allauth_trusted_devices"
    verbose_name = _("Trusted devices")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from allauth_trusted_devices import checks, receivers  # noqa: F401

from allauth.account.adapter import get_adapter as get_account_adapter
from django.conf import settings
from django.core.checks import Warning, register

STAGE_PATH = "allauth_trusted_devices.stages.TrustedDeviceStage"
MIDDLEWARE_PATH = "allauth_trusted_devices.middleware.TrustedDeviceMiddleware"


@register()
def check_setup(app_configs, **kwargs):
    errors = []
    if MIDDLEWARE_PATH not in settings.MIDDLEWARE:
        errors.append(
            Warning(
                f"{MIDDLEWARE_PATH} is not in MIDDLEWARE; device cookies will never be set.",
                id="allauth_trusted_devices.W001",
            )
        )
    try:
        stages = get_account_adapter().get_login_stages()
    except Exception:  # noqa: BLE001 - a broken adapter is reported by allauth itself
        stages = []
    if STAGE_PATH not in stages:
        errors.append(
            Warning(
                f"{STAGE_PATH} is not returned by your ACCOUNT_ADAPTER.get_login_stages().",
                hint="Add allauth_trusted_devices.adapter.TrustedDevicesAccountAdapterMixin to your account adapter.",
                id="allauth_trusted_devices.W002",
            )
        )
    return errors

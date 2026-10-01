from allauth.account.signals import password_changed, password_reset, password_set
from django.dispatch import receiver

from allauth_trusted_devices.app_settings import app_settings
from allauth_trusted_devices.devices import revoke_other_devices


@receiver(password_changed)
@receiver(password_set)
@receiver(password_reset)
def revoke_devices_on_password_change(sender, request, user, **kwargs):
    if app_settings.REVOKE_ON_PASSWORD_CHANGE:
        revoke_other_devices(request, user)

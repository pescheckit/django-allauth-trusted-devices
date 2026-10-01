import logging

from allauth.account.stages import LoginStage
from allauth.core.internal.httpkit import headed_redirect_response, is_headless_request

from allauth_trusted_devices import devices
from allauth_trusted_devices.adapter import get_adapter
from allauth_trusted_devices.app_settings import MODE_CONFIRM, MODE_NOTIFY, MODE_OFF, app_settings
from allauth_trusted_devices.flows import DeviceConfirmation

logger = logging.getLogger(__name__)


class TrustedDeviceStage(LoginStage):
    """Runs after allauth's own stages, so the user has passed every other check by now."""

    key = "trusted_device"
    urlname = "trusted_devices_confirm"

    def handle(self):
        user = self.login.user
        if user is None or is_headless_request(self.request):
            # Headless clients have no cookie jar we can rely on and no page to show.
            return None, True
        adapter = get_adapter()
        mode = adapter.get_mode(self.request, user)
        if mode == MODE_OFF:
            return None, True

        device = devices.get_trusted_device(self.request, user)
        if device:
            devices.touch(self.request, device)
            return None, True

        if mode == MODE_CONFIRM and adapter.requires_confirmation(self.request, self.login):
            email = adapter.get_email(user)
            if not email:
                logger.warning("Cannot confirm new device for user %s: no email address", user.pk)
                return headed_redirect_response("account_login"), False
            DeviceConfirmation.initiate(self, email)
            return headed_redirect_response(self.urlname), True

        devices.trust_device(self.request, user)
        if mode == MODE_NOTIFY or app_settings.NOTIFY_AFTER_SKIPPED_CONFIRM:
            adapter.send_new_device_mail(self.request, user)
        return None, True

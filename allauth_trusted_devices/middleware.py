from allauth_trusted_devices.devices import PENDING_COOKIE_ATTR, set_cookie


class TrustedDeviceMiddleware:
    """Writes the device cookie queued during login. Login stages have no response to set it on."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        token = getattr(request, PENDING_COOKIE_ATTR, None)
        if token:
            set_cookie(response, token)
        return response

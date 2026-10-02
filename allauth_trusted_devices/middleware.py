from django.contrib.auth import logout

from allauth_trusted_devices.devices import PENDING_COOKIE_ATTR, session_device_removed, set_cookie


class TrustedDeviceMiddleware:
    """Ends sessions of removed devices and writes the device cookie queued during login.

    Must come after ``AuthenticationMiddleware``. Login stages have no response to set the cookie
    on, so the stage queues it on the request and this middleware writes it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and session_device_removed(request):
            # The user removed this device (or changed the password elsewhere): sign it out now,
            # not only on its next sign-in.
            logout(request)
        response = self.get_response(request)
        token = getattr(request, PENDING_COOKIE_ATTR, None)
        if token:
            set_cookie(response, token)
        return response

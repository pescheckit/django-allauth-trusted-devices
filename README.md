# django-allauth-trusted-devices

New-device sign-in protection for [django-allauth](https://allauth.org).

Each browser a user signs in from gets a long-lived cookie. When a user signs in from a browser that
is not on their list yet, this package either:

- **notify**: lets them in and emails them "new sign-in from Firefox on Linux, IP ..., at ...", or
- **confirm**: holds the login and emails a code they must enter before the device is trusted.

It plugs into allauth's own login stages, so it runs after the password, social login, email
verification and MFA steps, and works with any allauth setup. It is the Django counterpart of
packages like Laravel's `authentication-log` and Symfony's `auth-log-bundle`.

## How it fits with MFA

MFA is the stronger second factor; this package is not a replacement for it. In `confirm` mode a
login that already passed MFA (TOTP, WebAuthn, recovery code) or allauth's login-by-code is not asked
for another code: the device is trusted and the user gets the notification email. Users without
MFA get the email code. So nobody is challenged twice, and every new device shows up in the inbox.

## Requirements

- Python 3.10+
- Django 4.2+
- django-allauth 65.10+ (`<66`: the package uses allauth's login-stage internals)

## Installation

```bash
pip install django-allauth-trusted-devices
```

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "allauth",
    "allauth.account",
    "allauth_trusted_devices",
]

MIDDLEWARE = [
    # ...
    "allauth.account.middleware.AccountMiddleware",
    "allauth_trusted_devices.middleware.TrustedDeviceMiddleware",
]

ACCOUNT_ADAPTER = "myproject.adapter.AccountAdapter"
TRUSTED_DEVICES_MODE = "notify"  # or "confirm"
```

```python
# myproject/adapter.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth_trusted_devices.adapter import TrustedDevicesAccountAdapterMixin


class AccountAdapter(TrustedDevicesAccountAdapterMixin, DefaultAccountAdapter):
    pass
```

```python
# urls.py
urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("accounts/devices/", include("allauth_trusted_devices.urls")),
]
```

```bash
python manage.py migrate
```

`manage.py check` warns when the middleware or the login stage is missing.

## Settings

| Setting | Default | |
|---|---|---|
| `TRUSTED_DEVICES_MODE` | `"notify"` | `"off"`, `"notify"` or `"confirm"` |
| `TRUSTED_DEVICES_SKIP_CONFIRM_METHODS` | `["mfa", "code"]` | allauth authentication methods that count as a second factor in `confirm` mode. Add `"socialaccount"` to trust the identity provider. |
| `TRUSTED_DEVICES_NOTIFY_AFTER_SKIPPED_CONFIRM` | `True` | Still send the new-device email when `confirm` mode skipped the code. |
| `TRUSTED_DEVICES_REVOKE_ON_PASSWORD_CHANGE` | `True` | Forget all other devices when the password is changed, set or reset. |
| `TRUSTED_DEVICES_CODE_TIMEOUT` | `900` | Seconds a confirmation code stays valid. |
| `TRUSTED_DEVICES_CODE_MAX_ATTEMPTS` | `3` | Wrong codes before the login is dropped. |
| `TRUSTED_DEVICES_CODE_MAX_RESEND_COUNT` | `1` | |
| `TRUSTED_DEVICES_COOKIE_NAME` | `"trusted_device"` | |
| `TRUSTED_DEVICES_COOKIE_AGE` | 365 days | Renewed on every sign-in from the device. |
| `TRUSTED_DEVICES_COOKIE_DOMAIN`, `_PATH`, `_SECURE` | session cookie settings | The cookie is always `HttpOnly`. |
| `TRUSTED_DEVICES_COOKIE_SAMESITE` | `"Lax"` | |
| `TRUSTED_DEVICES_ADAPTER` | `DefaultTrustedDevicesAdapter` | See below. |

## Customising per user or organisation

Subclass the adapter and point `TRUSTED_DEVICES_ADAPTER` at it:

```python
from allauth_trusted_devices.adapter import DefaultTrustedDevicesAdapter


class TrustedDevicesAdapter(DefaultTrustedDevicesAdapter):
    def get_mode(self, request, user):
        if user.organisation.require_device_confirmation:
            return "confirm"
        return "notify"
```

Other hooks: `requires_confirmation()`, `get_email()`, `get_client_ip()`, `generate_code()`,
`get_mail_context()`, `send_mail()`, `send_new_device_mail()` and `send_confirmation_code_mail()`.

## Emails

Mails go through your allauth account adapter's `send_mail()`, so they use whatever email setup
your project already has. The template prefixes are:

- `allauth_trusted_devices/email/new_device`
- `allauth_trusted_devices/email/confirm_device`

Both receive `user`, `device` ("Firefox on Linux"), `user_agent`, `ip`, `timestamp` and
`devices_url`; the confirmation mail also gets `code`. Override `*_subject.txt`, `*_message.txt`
and optionally `*_message.html` like any allauth email.

## Pages

- `trusted_devices_confirm`: the code entry page, built on allauth's `account/base_confirm_code.html`.
- `trusted_devices_list`: the user's devices with a Remove button; marks the current one.

Both use allauth's `{% element %}` tags, so they follow your allauth theme. Override
`allauth_trusted_devices/confirm.html` and `allauth_trusted_devices/device_list.html` to change them.

## How devices are identified

The cookie holds a random 256-bit token; the database stores only its SHA-256 hash, with the user
agent, the first and last IP address and timestamps. One browser keeps one token, so on a shared
computer each user gets their own trusted-device row for it. IP addresses are recorded for display
only and never decide whether a device is trusted, because they change too often. The client IP
comes from allauth's `get_client_ip()`, so `ALLAUTH_TRUSTED_PROXY_COUNT` and
`ALLAUTH_TRUSTED_CLIENT_IP_HEADER` apply.

## Limitations

- Headless (allauth.headless) logins are skipped: there is no cookie jar or page to rely on.
- A user with no email address cannot pass `confirm` mode; such a login is refused and logged.

## Translations

English and Dutch are included. Contributions for other languages are welcome.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

## License

MIT

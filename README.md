# django-allauth-trusted-devices

[![CI](https://github.com/pescheckit/django-allauth-trusted-devices/actions/workflows/ci.yml/badge.svg)](https://github.com/pescheckit/django-allauth-trusted-devices/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-allauth-trusted-devices.svg)](https://pypi.org/project/django-allauth-trusted-devices/)
[![Python](https://img.shields.io/pypi/pyversions/django-allauth-trusted-devices.svg)](https://pypi.org/project/django-allauth-trusted-devices/)

Tell users when their account is used from a device it has not seen before, or make them confirm
that device by email first. Built on [django-allauth](https://allauth.org)'s own login stages.

## Why

A leaked password should not log someone in silently. MFA is the real answer, but not every user
has it, and even with MFA people want to know when a new device signs in. Hand-rolling this on top
of `user_logged_in` gets the details wrong: it fires after the login is complete, which is too late
to ask for a code, and it does not tell you whether this login already passed MFA.

This package is one allauth login stage. It runs after the password, social login, email
verification and MFA steps, so it sees the complete picture, and it can hold the login until the
device is confirmed. It is the Django counterpart of Laravel's `authentication-log` and Symfony's
`auth-log-bundle`.

## What you get

Each browser a user signs in from gets a long-lived cookie and a row in the database. On a sign-in
from a browser the user has not used before:

- **`notify`** (default): the user is let in and gets this email:

  ```
  Subject: New sign-in to your account

  Someone just signed in to your account from a device we have not seen before:

  - Device: Firefox on Linux
  - IP address: 203.0.113.42
  - Date: Oct. 1, 2026, 9:37 a.m.

  If this was you, you can ignore this email. If it was not, change your password immediately and
  remove the device from your trusted devices.

  https://example.com/accounts/devices/
  ```

- **`confirm`**: the login is held and the user gets a code by email, which they enter before the
  device is trusted. A login that already passed MFA (TOTP, WebAuthn, recovery code) or allauth's
  login-by-code skips the code and gets the notification instead, so nobody is challenged twice.

Plus a "Trusted devices" page where users see and remove their devices, automatic removal of all
other devices when the password changes, an admin, and English and Dutch translations.

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

Link the device page from your account menu:

```django
<a href="{% url 'trusted_devices_list' %}">{% translate "Trusted devices" %}</a>
```

## Rolling out on an existing site

On the day you deploy, no user has a trusted device yet, so every user's next sign-in counts as new:
in `notify` mode everyone gets an email, in `confirm` mode everyone has to enter a code. To avoid
that, trust each user's first device silently:

```python
TRUSTED_DEVICES_SILENT_FIRST_DEVICE = True
```

The trade-off: whoever signs in first after the rollout is trusted without a word, and the same goes
for a user who removed all their devices. Turn it off again once your users have signed in, if that
matters to you more than a quiet rollout.

## Behind a proxy or load balancer

The IP address in the emails and on the device page comes from allauth's `get_client_ip()`. Behind a
reverse proxy that is the proxy, unless you tell allauth where the client IP is:

```python
ALLAUTH_TRUSTED_CLIENT_IP_HEADER = "X-Real-IP"  # a header your proxy overwrites, never one it passes through
# or
ALLAUTH_TRUSTED_PROXY_COUNT = 1  # number of proxies that append to X-Forwarded-For
```

If the emails show internal addresses (`10.x`, `172.16.x` to `172.31.x`, `192.168.x`), this is why.
The IP is display-only: whether a device is trusted depends on the cookie, never on the IP.

## Testing your project

Your existing login tests will start sending new-device emails, or stop at the code page in
`confirm` mode. Switch the package off in your test settings and test it on purpose where you want:

```python
TRUSTED_DEVICES_MODE = "off"
```

## Settings

| Setting | Default | |
|---|---|---|
| `TRUSTED_DEVICES_MODE` | `"notify"` | `"off"`, `"notify"` or `"confirm"` |
| `TRUSTED_DEVICES_SILENT_FIRST_DEVICE` | `False` | Trust a user's first device without email or code. See [Rolling out](#rolling-out-on-an-existing-site). |
| `TRUSTED_DEVICES_SKIP_CONFIRM_METHODS` | `["mfa", "code"]` | allauth authentication methods that count as a second factor in `confirm` mode. Add `"socialaccount"` to trust the identity provider. |
| `TRUSTED_DEVICES_NOTIFY_AFTER_SKIPPED_CONFIRM` | `True` | Still send the new-device email when `confirm` mode skipped the code. |
| `TRUSTED_DEVICES_REVOKE_ON_PASSWORD_CHANGE` | `True` | Forget all other devices when the password is changed, set or reset. |
| `TRUSTED_DEVICES_CODE_TIMEOUT` | `900` | Seconds a confirmation code stays valid. |
| `TRUSTED_DEVICES_CODE_MAX_ATTEMPTS` | `3` | Wrong codes before the login is dropped and the user has to sign in again. |
| `TRUSTED_DEVICES_CODE_MAX_RESEND_COUNT` | `1` | How often the user may ask for a new code during one login. |
| `TRUSTED_DEVICES_COOKIE_NAME` | `"trusted_device"` | Name of the device cookie. |
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

Other hooks: `trust_first_device_silently()`, `requires_confirmation()`, `get_email()`,
`get_client_ip()`, `generate_code()`, `get_mail_context()`, `send_mail()`, `send_new_device_mail()`
and `send_confirmation_code_mail()`.

## Emails

Mails go through your allauth account adapter's `send_mail()`, so they use whatever email setup
your project already has. The template prefixes are:

- `allauth_trusted_devices/email/new_device`
- `allauth_trusted_devices/email/confirm_device`

Both receive `user`, `device` ("Firefox on Linux"), `user_agent`, `ip`, `timestamp` and
`devices_url`; the confirmation mail also gets `code`. Override `*_subject.txt`, `*_message.txt`
and optionally `*_message.html` like any allauth email, or map the prefixes to your own templates in
your adapter's `send_mail()`.

## Pages

- `trusted_devices_confirm`: the code entry page, built on allauth's `account/base_confirm_code.html`.
- `trusted_devices_list`: the user's devices with a Remove button; marks the current one.

Both use allauth's `{% element %}` tags, so they follow your allauth theme. Override
`allauth_trusted_devices/confirm.html` and `allauth_trusted_devices/device_list.html` to change them.

## How devices are identified

The cookie holds a random 256-bit token; the database stores only its SHA-256 hash, with the user
agent, the first and last IP address and timestamps. One browser keeps one token, so on a shared
computer each user gets their own trusted-device row for it. IP addresses are recorded for display
only and never decide whether a device is trusted, because they change too often.

## Security notes

- **This is not MFA.** An emailed code is only as strong as the mailbox: whoever has the user's
  password and email gets in. Use it next to MFA, not instead of it.
- **The cookie is the device.** Anyone who copies the cookie (malware, a shared browser profile)
  counts as that device until it is removed or the password changes. The cookie is `HttpOnly`,
  `Secure` when your session cookie is, and only a hash is stored server-side.
- **Not allauth's MFA trust.** allauth's `MFA_TRUST_ENABLED` cookie only skips the TOTP prompt for
  a while. This package's cookie decides whether a sign-in counts as a new device. Both can be on.
- **Password change revokes.** Changing, setting or resetting the password removes all other devices
  (`TRUSTED_DEVICES_REVOKE_ON_PASSWORD_CHANGE`), so a device an attacker got trusted stops counting.

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

## Releasing

Bump `__version__` in `allauth_trusted_devices/__init__.py`, update `CHANGELOG.md`, then push a tag:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

CI runs the tests and publishes to PyPI through trusted publishing.

## License

MIT

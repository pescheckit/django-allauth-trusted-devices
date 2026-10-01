import re

import pytest
from allauth.account.models import EmailAddress
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    generate_totp_secret,
    hotp_value,
    yield_hotp_counters_from_time,
)
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client
from django.urls import reverse

from allauth_trusted_devices.adapter import DefaultTrustedDevicesAdapter
from allauth_trusted_devices.models import TrustedDevice

PASSWORD = "correct horse battery staple"
UA_FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
COOKIE = "trusted_device"

pytestmark = pytest.mark.django_db


def make_user(email="jane@example.com"):
    user = get_user_model().objects.create_user(username=email.split("@")[0], email=email, password=PASSWORD)
    EmailAddress.objects.create(user=user, email=email, primary=True, verified=True)
    return user


def login(client, email="jane@example.com", password=PASSWORD):
    return client.post(reverse("account_login"), {"login": email, "password": password})


def logout(client):
    # Client.logout() also drops every cookie; a real sign-out keeps the device cookie.
    client.post(reverse("account_logout"))


def is_logged_in(client):
    return "_auth_user_id" in client.session


def last_code():
    return re.search(r"^([A-Z0-9]+(?:-[A-Z0-9]+)*)$", mail.outbox[-1].body, re.M).group(1)


@pytest.fixture
def client():
    return Client(HTTP_USER_AGENT=UA_FIREFOX)


@pytest.fixture
def user():
    return make_user()


class TestNotifyMode:
    def test_first_login_registers_device_and_sends_mail(self, client, user):
        response = login(client)

        assert response.status_code == 302
        assert response["Location"] == "/done/"
        assert is_logged_in(client)
        device = TrustedDevice.objects.get(user=user)
        assert device.user_agent == UA_FIREFOX
        assert device.ip_address == "127.0.0.1"
        assert response.cookies[COOKIE]["httponly"]
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["jane@example.com"]
        assert "Firefox on Linux" in mail.outbox[0].body
        assert "127.0.0.1" in mail.outbox[0].body

    def test_known_device_gets_no_mail_and_renews_cookie(self, client, user):
        login(client)
        logout(client)
        mail.outbox.clear()

        response = login(client)

        assert is_logged_in(client)
        assert mail.outbox == []
        assert TrustedDevice.objects.filter(user=user).count() == 1
        assert COOKIE in response.cookies

    def test_other_browser_is_a_new_device(self, client, user):
        login(client)
        other = Client(HTTP_USER_AGENT=UA_FIREFOX)
        mail.outbox.clear()

        login(other)

        assert len(mail.outbox) == 1
        assert TrustedDevice.objects.filter(user=user).count() == 2

    def test_shared_browser_keeps_one_token_for_both_users(self, client, user):
        other_user = make_user("john@example.com")
        login(client)
        token = client.cookies[COOKIE].value
        logout(client)

        login(client, "john@example.com")
        logout(client)
        mail.outbox.clear()
        login(client)

        assert client.cookies[COOKIE].value == token
        assert mail.outbox == []
        assert TrustedDevice.objects.filter(user=other_user).count() == 1

    def test_forged_cookie_is_not_trusted(self, client, user):
        login(client)
        logout(client)
        client.cookies[COOKIE] = "x" * 43
        mail.outbox.clear()

        login(client)

        assert len(mail.outbox) == 1

    def test_wrong_password_does_nothing(self, client, user):
        login(client, password="wrong")

        assert not is_logged_in(client)
        assert not TrustedDevice.objects.exists()
        assert mail.outbox == []


class TestOffMode:
    def test_off_does_nothing(self, client, user, settings):
        settings.TRUSTED_DEVICES_MODE = "off"

        login(client)

        assert is_logged_in(client)
        assert not TrustedDevice.objects.exists()
        assert mail.outbox == []


@pytest.fixture
def confirm_mode(settings):
    settings.TRUSTED_DEVICES_MODE = "confirm"


@pytest.mark.usefixtures("confirm_mode")
class TestConfirmMode:
    def test_new_device_must_enter_code(self, client, user):
        response = login(client)

        assert response["Location"] == reverse("trusted_devices_confirm")
        assert not is_logged_in(client)
        assert not TrustedDevice.objects.exists()
        assert len(mail.outbox) == 1

        page = client.get(reverse("trusted_devices_confirm"))
        assert page.status_code == 200
        assert b"jane@example.com" in page.content

        response = client.post(reverse("trusted_devices_confirm"), {"code": last_code()})

        assert response["Location"] == "/done/"
        assert is_logged_in(client)
        assert TrustedDevice.objects.filter(user=user).count() == 1
        assert COOKIE in response.cookies

    def test_confirmed_device_skips_code_next_time(self, client, user):
        login(client)
        client.post(reverse("trusted_devices_confirm"), {"code": last_code()})
        logout(client)
        mail.outbox.clear()

        response = login(client)

        assert response["Location"] == "/done/"
        assert mail.outbox == []

    def test_code_accepts_lowercase_and_spaces(self, client, user):
        login(client)
        code = last_code()

        client.post(reverse("trusted_devices_confirm"), {"code": f" {code.lower().replace('-', ' ')} "})

        assert is_logged_in(client)

    def test_wrong_code_until_attempts_run_out(self, client, user, settings):
        settings.TRUSTED_DEVICES_CODE_MAX_ATTEMPTS = 2
        login(client)
        url = reverse("trusted_devices_confirm")

        first = client.post(url, {"code": "WRONG1"})
        assert first.status_code == 200
        assert not is_logged_in(client)

        second = client.post(url, {"code": "WRONG2"})
        assert second["Location"] == reverse("account_login")
        assert not is_logged_in(client)
        # The stashed login is gone: even the right code no longer works.
        assert client.post(url, {"code": last_code()})["Location"] == reverse("account_login")
        assert not is_logged_in(client)

    def test_expired_code(self, client, user, settings):
        login(client)
        settings.TRUSTED_DEVICES_CODE_TIMEOUT = -1

        response = client.post(reverse("trusted_devices_confirm"), {"code": last_code()})

        assert response["Location"] == reverse("account_login")
        assert not is_logged_in(client)

    def test_resend_replaces_code_once(self, client, user):
        login(client)
        old = last_code()
        url = reverse("trusted_devices_confirm")

        client.post(url, {"action": "resend"})
        assert len(mail.outbox) == 2
        new = last_code()
        client.post(url, {"action": "resend"})
        assert len(mail.outbox) == 2

        if old != new:
            assert client.post(url, {"code": old}).status_code == 200
        client.post(url, {"code": new})
        assert is_logged_in(client)

    def test_confirm_page_without_pending_login_redirects(self, client, user):
        response = client.get(reverse("trusted_devices_confirm"))

        assert response["Location"] == reverse("account_login")

    def test_mfa_login_skips_code_but_notifies(self, client, user):
        secret = generate_totp_secret()
        TOTP.activate(user, secret)

        response = login(client)
        assert response["Location"] == reverse("mfa_authenticate")
        counter = next(iter(yield_hotp_counters_from_time()))
        response = client.post(reverse("mfa_authenticate"), {"code": format_hotp_value(hotp_value(secret, counter))})

        assert response["Location"] == "/done/"
        assert is_logged_in(client)
        assert TrustedDevice.objects.filter(user=user).count() == 1
        assert len(mail.outbox) == 1
        assert "not seen before" in mail.outbox[0].body

    def test_user_without_email_cannot_confirm(self, client):
        get_user_model().objects.create_user(username="noemail", password=PASSWORD)

        response = client.post(reverse("account_login"), {"login": "noemail", "password": PASSWORD})

        assert response["Location"] == reverse("account_login")
        assert not is_logged_in(client)


class TestCustomAdapter:
    def test_mode_per_user(self, client, user, settings):
        settings.TRUSTED_DEVICES_ADAPTER = "tests.test_login.ConfirmForJaneAdapter"

        response = login(client)

        assert response["Location"] == reverse("trusted_devices_confirm")


class ConfirmForJaneAdapter(DefaultTrustedDevicesAdapter):
    def get_mode(self, request, user):
        return "confirm" if user.email == "jane@example.com" else "notify"


def test_mail_is_translated(user):
    from django.utils import translation

    client = Client(HTTP_USER_AGENT=UA_FIREFOX)
    with translation.override("nl"):
        login(client)

    assert mail.outbox[0].subject.endswith("Nieuwe inlog op je account")
    assert "Firefox op Linux" in mail.outbox[0].body
    assert "IP-adres: 127.0.0.1" in mail.outbox[0].body


@pytest.fixture
def silent_first(settings):
    settings.TRUSTED_DEVICES_SILENT_FIRST_DEVICE = True


@pytest.mark.usefixtures("silent_first")
class TestSilentFirstDevice:
    def test_first_device_is_trusted_without_mail(self, client, user):
        response = login(client)

        assert response["Location"] == "/done/"
        assert TrustedDevice.objects.filter(user=user).count() == 1
        assert COOKIE in response.cookies
        assert mail.outbox == []

    def test_second_device_still_notifies(self, client, user):
        login(client)
        login(Client(HTTP_USER_AGENT=UA_FIREFOX))

        assert len(mail.outbox) == 1
        assert TrustedDevice.objects.filter(user=user).count() == 2

    def test_confirm_mode_skips_code_for_first_device_only(self, client, user, settings):
        settings.TRUSTED_DEVICES_MODE = "confirm"

        assert login(client)["Location"] == "/done/"
        assert mail.outbox == []
        assert login(Client(HTTP_USER_AGENT=UA_FIREFOX))["Location"] == reverse("trusted_devices_confirm")

    def test_off_by_default(self, client, user, settings):
        del settings.TRUSTED_DEVICES_SILENT_FIRST_DEVICE

        login(client)

        assert len(mail.outbox) == 1

import pytest
from django.core.checks import run_checks
from django.test import Client
from django.urls import reverse

from allauth_trusted_devices.models import TrustedDevice
from allauth_trusted_devices.utils import describe_user_agent
from tests.test_login import PASSWORD, UA_FIREFOX, login, logout, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return make_user()


def new_client():
    return Client(HTTP_USER_AGENT=UA_FIREFOX)


class TestDeviceList:
    def test_requires_login(self):
        response = new_client().get(reverse("trusted_devices_list"))

        assert response.status_code == 302
        assert reverse("account_login") in response["Location"]

    def test_lists_own_devices_and_marks_current(self, user):
        client, other = new_client(), new_client()
        login(other)
        login(client)
        stranger = make_user("john@example.com")
        login(new_client(), "john@example.com")

        response = client.get(reverse("trusted_devices_list"))

        assert response.status_code == 200
        listed = response.context["devices"]
        assert {d.user for d in listed} == {user}
        assert [d.is_current for d in listed].count(True) == 1
        assert b"Firefox on Linux" in response.content
        assert TrustedDevice.objects.filter(user=stranger).count() == 1

    def test_remove_device(self, user):
        client, other = new_client(), new_client()
        login(other)
        login(client)
        other_device = TrustedDevice.objects.filter(user=user).order_by("created_at").first()

        response = client.post(reverse("trusted_devices_revoke", args=[other_device.pk]))

        assert response["Location"] == reverse("trusted_devices_list")
        other_device.refresh_from_db()
        assert other_device.revoked_at is not None
        assert other_device not in response.wsgi_request.user.trusted_devices.active()

    def test_cannot_remove_someone_elses_device(self, user):
        make_user("john@example.com")
        john = new_client()
        login(john, "john@example.com")
        johns_device = TrustedDevice.objects.get(user__email="john@example.com")
        client = new_client()
        login(client)

        response = client.post(reverse("trusted_devices_revoke", args=[johns_device.pk]))

        assert response.status_code == 404
        assert TrustedDevice.objects.filter(pk=johns_device.pk).exists()

    def test_remove_is_post_only(self, user):
        client = new_client()
        login(client)
        device = TrustedDevice.objects.get(user=user)

        assert client.get(reverse("trusted_devices_revoke", args=[device.pk])).status_code == 405


class TestPasswordChange:
    def test_password_change_revokes_other_devices(self, user):
        client, other = new_client(), new_client()
        login(other)
        login(client)
        assert TrustedDevice.objects.filter(user=user).count() == 2

        response = client.post(
            reverse("account_change_password"),
            {"oldpassword": PASSWORD, "password1": "another long passphrase", "password2": "another long passphrase"},
        )

        assert response.status_code == 302
        remaining = TrustedDevice.objects.active().filter(user=user)
        assert remaining.count() == 1
        assert TrustedDevice.objects.filter(user=user).count() == 2
        assert client.get(reverse("trusted_devices_list")).context["devices"][0].is_current

    def test_can_be_disabled(self, user, settings):
        settings.TRUSTED_DEVICES_REVOKE_ON_PASSWORD_CHANGE = False
        client, other = new_client(), new_client()
        login(other)
        login(client)

        client.post(
            reverse("account_change_password"),
            {"oldpassword": PASSWORD, "password1": "another long passphrase", "password2": "another long passphrase"},
        )

        assert TrustedDevice.objects.filter(user=user).count() == 2

    def test_revoked_device_is_new_again(self, user):
        from django.core import mail

        client, other = new_client(), new_client()
        login(other)
        login(client)
        client.post(
            reverse("account_change_password"),
            {"oldpassword": PASSWORD, "password1": "another long passphrase", "password2": "another long passphrase"},
        )
        logout(other)
        mail.outbox.clear()

        login(other, password="another long passphrase")

        assert len(mail.outbox) == 1


class TestChecks:
    def test_no_warnings_when_set_up(self):
        assert [m for m in run_checks() if m.id.startswith("allauth_trusted_devices")] == []

    def test_missing_middleware(self, settings):
        settings.MIDDLEWARE = [m for m in settings.MIDDLEWARE if "trusted_devices" not in m]

        ids = [m.id for m in run_checks()]

        assert "allauth_trusted_devices.W001" in ids

    def test_missing_stage(self, settings):
        settings.ACCOUNT_ADAPTER = "allauth.account.adapter.DefaultAccountAdapter"

        ids = [m.id for m in run_checks()]

        assert "allauth_trusted_devices.W002" in ids


@pytest.mark.parametrize(
    ("user_agent", "expected"),
    [
        (UA_FIREFOX, "Firefox on Linux"),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
            "Edge on Windows",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/18.0 Safari/605.1.15",
            "Safari on macOS",
        ),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "CriOS/129.0 Mobile/15E148 Safari/604.1",
            "Chrome on iOS",
        ),
        (
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0 Mobile Safari/537.36",
            "Chrome on Android",
        ),
        ("", "Unknown device"),
        ("curl/8.0", "Unknown device"),
    ],
)
def test_describe_user_agent(user_agent, expected):
    assert describe_user_agent(user_agent) == expected

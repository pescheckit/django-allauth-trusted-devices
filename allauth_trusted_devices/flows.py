import time

from allauth.account.internal.stagekit import clear_login, stash_login
from django.utils.crypto import constant_time_compare

from allauth_trusted_devices import devices
from allauth_trusted_devices.adapter import get_adapter
from allauth_trusted_devices.app_settings import app_settings


def normalize_code(code: str) -> str:
    return "".join(ch for ch in (code or "") if ch.isalnum()).upper()


class DeviceConfirmation:
    """The emailed-code challenge for a new device, kept in the stashed allauth login."""

    def __init__(self, stage):
        self.stage = stage
        self.request = stage.request
        self.state = stage.state

    @classmethod
    def initiate(cls, stage, email: str) -> "DeviceConfirmation":
        stage.state.clear()
        stage.state.update({"email": email, "failed_attempts": 0, "resend_count": 0})
        process = cls(stage)
        process.send()
        process.persist()
        return process

    @classmethod
    def resume(cls, stage) -> "DeviceConfirmation | None":
        process = cls(stage)
        if not process.state.get("code") or not process.is_valid():
            process.abort()
            return None
        return process

    @property
    def email(self) -> str:
        return self.state["email"]

    def is_valid(self) -> bool:
        return time.time() - self.state.get("at", 0) <= app_settings.CODE_TIMEOUT

    def send(self) -> None:
        code = get_adapter().generate_code()
        self.state["code"] = code
        self.state["at"] = time.time()
        get_adapter().send_confirmation_code_mail(self.request, self.stage.login.user, self.email, code)

    def persist(self) -> None:
        stash_login(self.request, self.stage.login)

    def abort(self) -> None:
        clear_login(self.request)

    def check(self, code: str) -> bool:
        expected = normalize_code(self.state.get("code", ""))
        return bool(expected) and constant_time_compare(normalize_code(code), expected)

    def record_invalid_attempt(self) -> bool:
        """Count a wrong code. Returns False, and drops the login, once attempts run out."""
        self.state["failed_attempts"] += 1
        if self.state["failed_attempts"] >= app_settings.CODE_MAX_ATTEMPTS:
            self.abort()
            return False
        self.persist()
        return True

    @property
    def can_resend(self) -> bool:
        return self.state.get("resend_count", 0) < app_settings.CODE_MAX_RESEND_COUNT

    def resend(self) -> None:
        self.state["resend_count"] += 1
        self.send()
        self.persist()

    def finish(self):
        devices.trust_device(self.request, self.stage.login.user)
        return self.stage.exit()

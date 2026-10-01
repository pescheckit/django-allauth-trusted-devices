from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class TrustedDevice(models.Model):
    """A browser a user has signed in from before.

    The browser holds a random token in a cookie; only its SHA-256 hash is stored. One browser
    keeps one token, so several users of a shared computer each get their own row for it.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trusted_devices",
        verbose_name=_("user"),
    )
    token_hash = models.CharField(_("token hash"), max_length=64, db_index=True)
    user_agent = models.TextField(_("user agent"), blank=True, default="")
    ip_address = models.GenericIPAddressField(_("first IP address"), null=True, blank=True)
    last_ip_address = models.GenericIPAddressField(_("last IP address"), null=True, blank=True)
    created_at = models.DateTimeField(_("first seen"), auto_now_add=True)
    last_used_at = models.DateTimeField(_("last seen"), auto_now_add=True)

    class Meta:
        verbose_name = _("trusted device")
        verbose_name_plural = _("trusted devices")
        ordering = ["-last_used_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "token_hash"], name="trusted_device_unique_user_token"),
        ]

    def __str__(self):
        from allauth_trusted_devices.utils import describe_user_agent

        return f"{self.user} - {describe_user_agent(self.user_agent)}"

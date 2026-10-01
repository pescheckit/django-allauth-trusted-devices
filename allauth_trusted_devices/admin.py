from django.contrib import admin

from allauth_trusted_devices.models import TrustedDevice
from allauth_trusted_devices.utils import describe_user_agent


@admin.register(TrustedDevice)
class TrustedDeviceAdmin(admin.ModelAdmin):
    list_display = ["user", "device", "last_ip_address", "last_used_at", "created_at"]
    list_select_related = ["user"]
    search_fields = ["user__email", "ip_address", "last_ip_address"]
    readonly_fields = [
        "user",
        "token_hash",
        "user_agent",
        "ip_address",
        "last_ip_address",
        "created_at",
        "last_used_at",
    ]

    @admin.display(description="device")
    def device(self, obj):
        return describe_user_agent(obj.user_agent)

    def has_add_permission(self, request):
        return False

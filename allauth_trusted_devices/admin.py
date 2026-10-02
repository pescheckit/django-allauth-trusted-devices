from django.contrib import admin

from allauth_trusted_devices import devices
from allauth_trusted_devices.models import TrustedDevice
from allauth_trusted_devices.utils import describe_user_agent


@admin.register(TrustedDevice)
class TrustedDeviceAdmin(admin.ModelAdmin):
    list_display = ["user", "device", "last_ip_address", "last_used_at", "created_at", "revoked_at"]
    list_filter = [("revoked_at", admin.EmptyFieldListFilter)]
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
        "revoked_at",
    ]

    @admin.display(description="device")
    def device(self, obj):
        return describe_user_agent(obj.user_agent)

    actions = ["revoke_devices"]

    @admin.action(description="Remove selected devices (keeps their history)")
    def revoke_devices(self, request, queryset):
        for device in queryset.active():
            devices.revoke(device)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Deleting would erase the user's device history and make their next sign-in a silent
        # "first device" again. Use the remove action; rows go when the user account is deleted.
        return False

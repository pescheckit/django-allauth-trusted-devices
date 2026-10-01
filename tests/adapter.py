from allauth.account.adapter import DefaultAccountAdapter

from allauth_trusted_devices.adapter import TrustedDevicesAccountAdapterMixin


class AccountAdapter(TrustedDevicesAccountAdapterMixin, DefaultAccountAdapter):
    pass

# Changelog

## 0.2.0 (2026-10-01)

- `TRUSTED_DEVICES_SILENT_FIRST_DEVICE_UNTIL` ends the silent-first-device rollout window. Until then
  whoever signs in first (or a user who removed all devices) is trusted silently; after it, everyone
  goes through the normal new-device check.

## 0.1.0 (2026-10-01)

- First release: `notify` and `confirm` modes as an allauth login stage, a device list with
  removal, revocation on password change, admin, English and Dutch translations.
- `TRUSTED_DEVICES_SILENT_FIRST_DEVICE` to trust a user's first device without email or code, for
  rolling out on a site with existing users.

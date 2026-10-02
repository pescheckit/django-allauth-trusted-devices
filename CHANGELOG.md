# Changelog

## 0.4.0 (2026-10-02)

- Removing a device signs that browser out on its next request (Remove button, admin action,
  password change). The session remembers which device it signed in with.
- The admin can no longer delete devices, only remove them, so the history cannot be erased.
- System check `W003`: the middleware must come after `AuthenticationMiddleware`.

## 0.3.0 (2026-10-01)

- Removing a device keeps it as history (`revoked_at`) instead of deleting it. The silent first
  device only applies to users who never had a device, so removing every device no longer makes the
  next sign-in silent. A removed browser counts as a new device again. Migration `0002`.
- Admin action "Remove selected devices".

## 0.2.0 (2026-10-01)

- `TRUSTED_DEVICES_SILENT_FIRST_DEVICE_UNTIL` ends the silent-first-device rollout window. Until then
  whoever signs in first (or a user who removed all devices) is trusted silently; after it, everyone
  goes through the normal new-device check.

## 0.1.0 (2026-10-01)

- First release: `notify` and `confirm` modes as an allauth login stage, a device list with
  removal, revocation on password change, admin, English and Dutch translations.
- `TRUSTED_DEVICES_SILENT_FIRST_DEVICE` to trust a user's first device without email or code, for
  rolling out on a site with existing users.

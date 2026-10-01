from django.urls import path

from allauth_trusted_devices import views

urlpatterns = [
    path("", views.device_list, name="trusted_devices_list"),
    path("confirm/", views.confirm, name="trusted_devices_confirm"),
    path("<int:pk>/remove/", views.revoke, name="trusted_devices_revoke"),
]

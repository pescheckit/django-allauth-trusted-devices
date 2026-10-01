from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/devices/", include("allauth_trusted_devices.urls")),
    path("done/", lambda request: HttpResponse("done")),
]

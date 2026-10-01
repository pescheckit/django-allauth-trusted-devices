from allauth.account import app_settings as account_settings
from allauth.account.internal.decorators import login_stage_required
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, TemplateView, View

from allauth_trusted_devices import devices
from allauth_trusted_devices.flows import DeviceConfirmation
from allauth_trusted_devices.forms import ConfirmDeviceForm
from allauth_trusted_devices.models import TrustedDevice
from allauth_trusted_devices.stages import TrustedDeviceStage
from allauth_trusted_devices.utils import describe_user_agent


@method_decorator(
    login_stage_required(stage=TrustedDeviceStage.key, redirect_urlname="account_login"),
    name="dispatch",
)
class ConfirmDeviceView(FormView):
    form_class = ConfirmDeviceForm
    template_name = f"allauth_trusted_devices/confirm.{account_settings.TEMPLATE_EXTENSION}"

    def dispatch(self, request, *args, **kwargs):
        self.process = DeviceConfirmation.resume(request._login_stage)
        if not self.process:
            messages.error(request, _("The confirmation code has expired. Please sign in again."))
            return HttpResponseRedirect(reverse("account_login"))
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "resend":
            if self.process.can_resend:
                self.process.resend()
                messages.success(request, _("A new code has been sent."))
            return HttpResponseRedirect(reverse("trusted_devices_confirm"))
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["process"] = self.process
        return kwargs

    def form_valid(self, form):
        return self.process.finish()

    def form_invalid(self, form):
        if self.process.record_invalid_attempt():
            return super().form_invalid(form)
        messages.error(self.request, _("Too many incorrect codes. Please sign in again."))
        return HttpResponseRedirect(reverse("account_login"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "verify_form": context["form"],
                "email": self.process.email,
                "can_resend": self.process.can_resend,
                "device": describe_user_agent(self.request.META.get("HTTP_USER_AGENT", "")),
            }
        )
        return context


@method_decorator(login_required, name="dispatch")
class DeviceListView(TemplateView):
    template_name = f"allauth_trusted_devices/device_list.{account_settings.TEMPLATE_EXTENSION}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        device_list = list(TrustedDevice.objects.active().filter(user=self.request.user))
        for device in device_list:
            device.description = describe_user_agent(device.user_agent)
            device.is_current = devices.is_current_device(self.request, device)
        context["devices"] = device_list
        return context


@method_decorator(login_required, name="dispatch")
class RevokeDeviceView(View):
    http_method_names = ["post"]

    def post(self, request, pk):
        device = get_object_or_404(TrustedDevice.objects.active(), pk=pk, user=request.user)
        devices.revoke(device)
        messages.success(request, _("The device has been removed."))
        return HttpResponseRedirect(reverse("trusted_devices_list"))


confirm = ConfirmDeviceView.as_view()
device_list = DeviceListView.as_view()
revoke = RevokeDeviceView.as_view()

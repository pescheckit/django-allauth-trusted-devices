from django import forms
from django.utils.translation import gettext_lazy as _


class ConfirmDeviceForm(forms.Form):
    code = forms.CharField(
        label=_("Code"),
        widget=forms.TextInput(attrs={"placeholder": _("Code"), "autocomplete": "one-time-code"}),
    )

    def __init__(self, *args, process=None, **kwargs):
        self.process = process
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data["code"]
        if not self.process.check(code):
            raise forms.ValidationError(_("Incorrect code."), code="incorrect_code")
        return code

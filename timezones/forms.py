import re
from zoneinfo import ZoneInfo

from django import forms
from django.core import signing
from django.utils import timezone

from .models import TimezonePreference
from .zones import timezone_choices, validate_zone

CONTEXT_SALT = "event-entry-timezone"


def entry_context(user_id, zone):
    return signing.dumps({"user": user_id, "zone": zone}, salt=CONTEXT_SALT)


class PreferenceForm(forms.ModelForm):
    class Meta:
        model = TimezonePreference
        fields = ["display_timezone"]
        labels = {"display_timezone": "Account timezone"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_timezone"] = forms.ChoiceField(
            label="Account timezone", choices=timezone_choices()
        )


class EventForm(forms.Form):
    title = forms.CharField(max_length=200)
    # Carry the rendered form's zone, so travel or another tab cannot reinterpret its input.
    context = forms.CharField(widget=forms.HiddenInput)
    occurred_at = forms.CharField(
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"})
    )

    def __init__(self, *args, user_id, **kwargs):
        self.user_id = user_id
        super().__init__(*args, **kwargs)

    def clean_context(self):
        token = self.cleaned_data["context"]
        try:
            data = signing.loads(token, salt=CONTEXT_SALT, max_age=86400)
            if data["user"] != self.user_id:
                raise ValueError
            validate_zone(data["zone"])
        except (signing.BadSignature, KeyError, TypeError, ValueError) as exc:
            raise forms.ValidationError(
                "This form expired. Reload the page and try again."
            ) from exc
        return data

    def clean(self):
        data = super().clean()
        if "context" in data and "occurred_at" in data:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?", data["occurred_at"]):
                self.add_error("occurred_at", "Enter a local date and time without a UTC offset.")
                return data
            with timezone.override(ZoneInfo(data["context"]["zone"])):
                try:
                    # Django rejects nonexistent and ambiguous DST wall times.
                    data["occurred_at"] = forms.DateTimeField().clean(data["occurred_at"])
                except forms.ValidationError as exc:
                    self.add_error("occurred_at", exc)
        return data

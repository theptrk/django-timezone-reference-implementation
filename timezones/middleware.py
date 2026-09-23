from zoneinfo import ZoneInfo

from django.utils import timezone

from .models import TimezonePreference
from .zones import resolve_zone


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.display_timezone = "UTC"
        if request.path != "/" and request.user.is_authenticated:
            request.timezone_preference, _ = TimezonePreference.objects.get_or_create(
                user=request.user
            )
            request.display_timezone = resolve_zone(request.timezone_preference)
        # Restore the prior context even on an exception; no zone leaks into the next request.
        with timezone.override(ZoneInfo(request.display_timezone)):
            return self.get_response(request)

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from timezones.models import Event, TimezonePreference
from timezones.zones import safe_zone, week_bounds


class Command(BaseCommand):
    help = "Print this week's report using the saved reporting timezone, without a browser session."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        user = get_user_model().objects.get(username=options["username"])
        preference, _ = TimezonePreference.objects.get_or_create(user=user)
        zone = safe_zone(preference.reporting_timezone)
        start, end = week_bounds(timezone.now(), zone)
        events = Event.objects.filter(user=user, occurred_at__gte=start, occurred_at__lt=end)
        self.stdout.write(f"Report timezone: {zone}; UTC interval: [{start}, {end})")
        with timezone.override(zone):
            for event in events:
                self.stdout.write(
                    f"{timezone.localtime(event.occurred_at).isoformat()} {event.title}"
                )

from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from timezones.models import Event, TimezonePreference


class Command(BaseCommand):
    help = "Create the public teaching account and seed repeatable sample events."

    @transaction.atomic
    def handle(self, *args, **options):
        user, _ = get_user_model().objects.get_or_create(username="demouser")
        if user.is_staff or user.is_superuser:
            raise CommandError("Refusing to give public demo credentials to a privileged user.")
        user.set_password("demopassword")
        user.is_active = True
        user.save()
        TimezonePreference.objects.get_or_create(
            user=user,
            defaults={"display_timezone": "America/New_York", "timezone_initialized": True},
        )
        for title, instant in [
            ("Winter standup", datetime(2026, 1, 15, 17, tzinfo=UTC)),
            ("Summer standup", datetime(2026, 7, 15, 17, tzinfo=UTC)),
            ("Near-midnight deployment", datetime(2026, 7, 16, 0, 30, tzinfo=UTC)),
        ]:
            Event.objects.get_or_create(
                user=user,
                title=title,
                occurred_at=instant,
                defaults={"original_timezone": "UTC"},
            )
        self.stdout.write("Demo ready: demouser / demopassword (non-staff).")

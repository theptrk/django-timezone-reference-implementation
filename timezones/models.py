from django.conf import settings
from django.db import models

from .zones import validate_zone


class TimezonePreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    display_timezone = models.CharField(max_length=100, default="UTC", validators=[validate_zone])
    timezone_initialized = models.BooleanField(default=False, editable=False)
    reporting_timezone = models.CharField(max_length=100, default="UTC", validators=[validate_zone])


class Event(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    occurred_at = models.DateTimeField()
    original_timezone = models.CharField(max_length=100, validators=[validate_zone])

    class Meta:
        ordering = ["-occurred_at", "-pk"]
        indexes = [models.Index(fields=["user", "occurred_at"])]

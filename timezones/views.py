import json
from datetime import UTC
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import EventForm, PreferenceForm, entry_context
from .models import Event
from .zones import (
    resolve_zone,
    timezone_choices,
    timezone_search_data,
    validate_zone,
    week_bounds,
)


@require_GET
def inspector(request):
    instant = timezone.now()
    return render(
        request,
        "timezones/inspector.html",
        {
            "default_zone": settings.TIME_ZONE,
            "use_tz": settings.USE_TZ,
            "database_vendor": connection.vendor,
            "database_zone": connection.timezone_name,
            "instant": instant.astimezone(UTC).isoformat(),
            # Show the backend's prepared value without inserting any row.
            "database_value": connection.ops.adapt_datetimefield_value(instant),
        },
    )


def page(request, event_form=None, preference_form=None, status=200):
    start, end = week_bounds(timezone.now(), request.display_timezone)
    events = Event.objects.filter(user=request.user)[:50]
    return render(
        request,
        "timezones/index.html",
        {
            "event_form": event_form
            if event_form is not None
            else EventForm(
                user_id=request.user.pk,
                initial={
                    "occurred_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
                    "context": entry_context(request.user.pk, request.display_timezone),
                },
            ),
            "preference_form": preference_form
            if preference_form is not None
            else PreferenceForm(instance=request.timezone_preference),
            "entry_zone": (
                event_form.cleaned_data.get("context", {}).get("zone", request.display_timezone)
                if event_form is not None
                else request.display_timezone
            ),
            "events": events,
            "week_start": start,
            "week_end": end,
            "timezone_groups": timezone_choices(),
            "timezone_search_data": timezone_search_data(),
        },
        status=status,
    )


@login_required
@require_GET
def index(request):
    return page(request)


@login_required
@require_POST
def preferences(request):
    form = PreferenceForm(request.POST, instance=request.timezone_preference)
    if not form.is_valid():
        return page(request, preference_form=form, status=400)
    form.save()
    request.session.pop("pending_timezone_suggestion", None)
    return redirect("index")


@login_required
@require_POST
def device_timezone(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
        zone = data.get("timezone")
        validate_zone(zone)
    except (ValueError, ValidationError):
        return JsonResponse({"error": "Send a valid IANA timezone."}, status=400)
    source = data.get("source", "browser")
    if not isinstance(source, str) or source not in {"browser", "simulation"}:
        return JsonResponse({"error": "Invalid detection source."}, status=400)
    key = "device_timezone" if source == "browser" else "simulated_timezone"
    previous = request.session.get(key)
    if source == "simulation" and previous is None:
        previous = request.session.get("device_timezone")
    request.session[key] = zone
    suggestion = None
    if previous and previous != zone:
        # A fresh transition invalidates a stale dialog. Mark offered pairs before replying.
        pending = request.session.get("pending_timezone_suggestion")
        if pending and pending["to"] != zone:
            request.session.pop("pending_timezone_suggestion", None)
        if zone != request.timezone_preference.display_timezone:
            pair = [previous, zone]
            offered = request.session.get("offered_timezone_changes", [])
            if pair not in offered:
                # Reassign so Django persists the updated list with the session.
                request.session["offered_timezone_changes"] = [*offered, pair]
                suggestion = {"id": uuid4().hex, "from": previous, "to": zone}
                request.session["pending_timezone_suggestion"] = suggestion
    return JsonResponse(
        {
            "display_timezone": resolve_zone(request.timezone_preference),
            "detected_timezone": zone,
            "source": source,
            "suggestion": suggestion,
        }
    )


@login_required
@require_POST
def timezone_suggestion(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
    except ValueError:
        return JsonResponse({"error": "Send a JSON object."}, status=400)
    pending = request.session.get("pending_timezone_suggestion")
    if not pending or data.get("id") != pending["id"]:
        return JsonResponse({"error": "This suggestion is no longer current."}, status=409)
    if data.get("action") not in ("accept", "dismiss"):
        return JsonResponse({"error": "Choose accept or dismiss."}, status=400)
    if data["action"] == "accept":
        request.timezone_preference.display_timezone = pending["to"]
        request.timezone_preference.save(update_fields=["display_timezone"])
    request.session.pop("pending_timezone_suggestion")
    return JsonResponse({"display_timezone": resolve_zone(request.timezone_preference)})


@login_required
@require_POST
def create_event(request):
    form = EventForm(request.POST, user_id=request.user.pk)
    if not form.is_valid():
        return page(request, event_form=form, status=400)
    Event.objects.create(
        user=request.user,
        title=form.cleaned_data["title"],
        occurred_at=form.cleaned_data["occurred_at"].astimezone(UTC),
        original_timezone=form.cleaned_data["context"]["zone"],
    )
    return redirect("index")


@login_required
@require_GET
def events_api(request):
    zone = request.GET.get("timezone", request.display_timezone)
    try:
        validate_zone(zone)
    except ValidationError:
        return JsonResponse({"error": "Invalid timezone."}, status=400)
    start, end = week_bounds(timezone.now(), zone)
    events = Event.objects.filter(user=request.user, occurred_at__gte=start, occurred_at__lt=end)
    return JsonResponse(
        {
            "timezone": zone,
            "start": start.isoformat(),
            "end_exclusive": end.isoformat(),
            "events": [
                {
                    "id": event.pk,
                    "title": event.title,
                    "occurred_at": event.occurred_at.astimezone(UTC).isoformat(),
                    "original_timezone": event.original_timezone,
                }
                for event in events
            ],
        }
    )

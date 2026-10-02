from datetime import UTC, datetime, timedelta
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, RequestFactory
from django.utils import timezone

from timezones.forms import EventForm, entry_context
from timezones.middleware import TimezoneMiddleware
from timezones.models import Event, TimezonePreference
from timezones.zones import week_bounds


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="traveler", password="test-password-123")


@pytest.fixture
def logged_in(client, user):
    TimezonePreference.objects.create(user=user, timezone_initialized=True)
    client.force_login(user)
    return client


def test_local_week_is_chosen_before_utc_boundaries():
    # Monday in UTC is still Sunday in Los Angeles.
    start, end = week_bounds(datetime(2026, 9, 21, 1, tzinfo=UTC), "America/Los_Angeles")
    assert start == datetime(2026, 9, 14, 7, tzinfo=UTC)
    assert end == datetime(2026, 9, 21, 7, tzinfo=UTC)


@pytest.mark.parametrize(
    "instant,hours",
    [
        (datetime(2026, 3, 8, 12, tzinfo=UTC), 167),
        (datetime(2026, 11, 1, 12, tzinfo=UTC), 169),
    ],
)
def test_dst_week_lengths(instant, hours):
    start, end = week_bounds(instant, "America/New_York")
    assert end - start == timedelta(hours=hours)


def test_fractional_offset():
    start, _ = week_bounds(datetime(2026, 9, 21, 1, tzinfo=UTC), "Asia/Kathmandu")
    assert start == datetime(2026, 9, 20, 18, 15, tzinfo=UTC)


def test_naive_week_input_rejected():
    with pytest.raises(ValueError):
        week_bounds(datetime(2026, 9, 21), "UTC")


@pytest.mark.parametrize("local", ["2026-03-08T02:30", "2026-11-01T01:30"])
def test_dst_gap_and_fold_are_rejected(local):
    form = EventForm(
        {"title": "DST", "occurred_at": local, "context": entry_context(1, "America/New_York")},
        user_id=1,
    )
    assert not form.is_valid()
    assert "occurred_at" in form.errors


def test_old_form_retains_its_zone_after_travel():
    form = EventForm(
        {
            "title": "Before flight",
            "occurred_at": "2026-08-12T10:20",
            "context": entry_context(1, "America/Los_Angeles"),
        },
        user_id=1,
    )
    with timezone.override("Asia/Tokyo"):
        assert form.is_valid(), form.errors
    assert form.cleaned_data["occurred_at"].astimezone(UTC) == datetime(
        2026, 8, 12, 17, 20, tzinfo=UTC
    )


@pytest.mark.parametrize("token", ["tampered", entry_context(2, "UTC")])
def test_form_context_is_authenticated(token):
    form = EventForm(
        {"title": "Test", "occurred_at": "2026-09-21T10:00", "context": token}, user_id=1
    )
    assert not form.is_valid()
    assert "context" in form.errors


def test_expired_form_context():
    with patch("django.core.signing.time.time", return_value=1):
        token = entry_context(1, "UTC")
    form = EventForm(
        {"title": "Test", "occurred_at": "2026-09-21T10:00", "context": token}, user_id=1
    )
    assert not form.is_valid()


def test_offset_is_not_accepted_as_local_wall_time():
    form = EventForm(
        {
            "title": "Test",
            "occurred_at": "2026-09-21T10:00+09:00",
            "context": entry_context(1, "UTC"),
        },
        user_id=1,
    )
    assert not form.is_valid()


def test_detection_preserves_profile_and_fixed_override(logged_in, user):
    pref = TimezonePreference.objects.get(user=user)
    pref.display_timezone = "Europe/London"
    pref.reporting_timezone = "America/New_York"
    pref.save()
    response = logged_in.post(
        "/device-timezone/", {"timezone": "Asia/Tokyo"}, content_type="application/json"
    )
    assert response.json()["display_timezone"] == "Europe/London"
    assert response.json()["suggestion"] is None
    pref.refresh_from_db()
    assert pref.reporting_timezone == "America/New_York"
    assert pref.display_timezone == "Europe/London"
    assert logged_in.session["device_timezone"] == "Asia/Tokyo"


def test_detection_is_per_session_but_display_uses_account(logged_in, user):
    logged_in.post("/device-timezone/", {"timezone": "Asia/Tokyo"}, content_type="application/json")
    other_device = Client()
    other_device.force_login(user)
    assert logged_in.get("/profile/").context["request"].display_timezone == "UTC"
    assert logged_in.session["device_timezone"] == "Asia/Tokyo"
    assert "device_timezone" not in other_device.session
    assert other_device.get("/profile/").context["request"].display_timezone == "UTC"


@pytest.mark.parametrize(
    "body", ["{", "[]", '{"timezone":"Invalid/Zone"}', '{"timezone":null}', '{"timezone":123}']
)
def test_bad_detection_is_400(logged_in, body):
    assert (
        logged_in.post("/device-timezone/", body, content_type="application/json").status_code
        == 400
    )
    assert "device_timezone" not in logged_in.session


def test_csrf_and_method_protection(user):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    assert client.get("/device-timezone/").status_code == 405
    assert (
        client.post(
            "/device-timezone/", {"timezone": "UTC"}, content_type="application/json"
        ).status_code
        == 403
    )


def test_login_required(client):
    assert client.get("/profile/").status_code == 302
    assert client.get("/api/events/").status_code == 302


def test_preference_validation_and_persistence(logged_in, user):
    data = {"mode": "fixed", "display_timezone": "Invalid", "reporting_timezone": "UTC"}
    assert logged_in.post("/preferences/", data).status_code == 400
    data["display_timezone"] = "Asia/Tokyo"
    assert logged_in.post("/preferences/", data).status_code == 302
    assert TimezonePreference.objects.get(user=user).display_timezone == "Asia/Tokyo"


def test_entry_storage_and_original_context(logged_in, user):
    response = logged_in.post(
        "/events/",
        {
            "title": "Lunch",
            "occurred_at": "2026-09-21T12:00",
            "context": entry_context(user.pk, "Asia/Tokyo"),
        },
    )
    assert response.status_code == 302
    event = Event.objects.get(user=user)
    assert event.occurred_at == datetime(2026, 9, 21, 3, tzinfo=UTC)
    assert event.original_timezone == "Asia/Tokyo"
    logged_in.post(
        "/device-timezone/", {"timezone": "America/Los_Angeles"}, content_type="application/json"
    )
    event.refresh_from_db()
    assert event.occurred_at == datetime(2026, 9, 21, 3, tzinfo=UTC)


def test_failed_old_form_labels_original_zone(logged_in, user):
    response = logged_in.post(
        "/events/",
        {
            "title": "Bad time",
            "occurred_at": "2026-03-08T02:30",
            "context": entry_context(user.pk, "America/New_York"),
        },
    )
    assert response.status_code == 400
    assert response.context["entry_zone"] == "America/New_York"


def test_api_week_half_open_interval_and_ownership(logged_in, user):
    start = datetime(2026, 9, 14, 7, tzinfo=UTC)
    end = datetime(2026, 9, 21, 7, tzinfo=UTC)
    other = get_user_model().objects.create_user(username="other")
    for owner, instant, title in [
        (user, start, "start"),
        (user, end, "end"),
        (other, start, "private"),
    ]:
        Event.objects.create(user=owner, occurred_at=instant, title=title, original_timezone="UTC")
    with patch("timezones.views.timezone.now", return_value=datetime(2026, 9, 21, 1, tzinfo=UTC)):
        response = logged_in.get("/api/events/?timezone=America/Los_Angeles")
    assert [e["title"] for e in response.json()["events"]] == ["start"]
    assert response.json()["events"][0]["occurred_at"].endswith("+00:00")
    assert logged_in.get("/api/events/?timezone=Invalid").status_code == 400


def test_middleware_restores_timezone_after_exception(user):
    TimezonePreference.objects.create(user=user, display_timezone="Asia/Tokyo")
    request = RequestFactory().get("/profile/")
    request.user = user
    request.session = {"device_timezone": "Asia/Tokyo"}

    def raises(request):
        assert timezone.get_current_timezone_name() == "Asia/Tokyo"
        raise RuntimeError("view failed")

    with timezone.override(ZoneInfo("Europe/London")):
        with pytest.raises(RuntimeError):
            TimezoneMiddleware(raises)(request)
        assert timezone.get_current_timezone_name() == "Europe/London"


def test_report_uses_saved_zone_without_request(user):
    TimezonePreference.objects.create(user=user, reporting_timezone="America/Los_Angeles")
    Event.objects.create(
        user=user,
        title="Sunday entry",
        original_timezone="UTC",
        occurred_at=datetime(2026, 9, 20, 23, tzinfo=UTC),
    )
    output = StringIO()
    with patch(
        "timezones.management.commands.weekly_report.timezone.now",
        return_value=datetime(2026, 9, 21, 1, tzinfo=UTC),
    ):
        call_command("weekly_report", user.username, stdout=output)
    assert "Sunday entry" in output.getvalue()
    assert "America/Los_Angeles" in output.getvalue()


@pytest.mark.django_db
def test_public_inspector_is_read_only(client):
    from django.contrib.sessions.models import Session

    response = client.get("/")
    assert response.status_code == 200
    assert response.context["default_zone"] == "UTC"
    assert response.context["database_vendor"] == "sqlite"
    assert response.context["database_zone"] == "UTC"
    assert "sessionid" not in response.cookies
    assert "csrftoken" not in response.cookies
    assert Session.objects.count() == 0
    assert TimezonePreference.objects.count() == 0
    assert Event.objects.count() == 0
    assert b"inspector.js" in response.content
    assert b'src="/static/timezone.js"' not in response.content


def test_inspector_does_not_create_logged_in_preferences(client, user):
    client.force_login(user)
    assert client.get("/").status_code == 200
    assert TimezonePreference.objects.count() == 0


@pytest.mark.django_db
def test_anonymous_cannot_save_timezone(client):
    assert (
        client.post(
            "/device-timezone/", {"timezone": "Asia/Tokyo"}, content_type="application/json"
        ).status_code
        == 302
    )
    assert client.post("/preferences/", {}).status_code == 302
    assert TimezonePreference.objects.count() == 0


def detection(client, zone, source="browser"):
    return client.post(
        "/device-timezone/", {"timezone": zone, "source": source}, content_type="application/json"
    ).json()


def decision(client, suggestion, action):
    return client.post(
        "/timezone-suggestion/",
        {"id": suggestion["id"], "action": action},
        content_type="application/json",
    )


def test_accept_changes_only_display_timezone(logged_in, user):
    detection(logged_in, "UTC")
    proposal = detection(logged_in, "Asia/Tokyo")["suggestion"]
    assert proposal["from"] == "UTC"
    assert TimezonePreference.objects.get(user=user).display_timezone == "UTC"
    assert decision(logged_in, proposal, "accept").status_code == 200
    pref = TimezonePreference.objects.get(user=user)
    assert pref.display_timezone == "Asia/Tokyo"
    assert pref.reporting_timezone == "UTC"
    assert decision(logged_in, proposal, "accept").status_code == 409


def test_decline_and_repeat_pair_never_reprompts(logged_in, user):
    detection(logged_in, "UTC")
    proposal = detection(logged_in, "Asia/Tokyo")["suggestion"]
    assert decision(logged_in, proposal, "dismiss").status_code == 200
    assert TimezonePreference.objects.get(user=user).display_timezone == "UTC"
    assert detection(logged_in, "Asia/Tokyo")["suggestion"] is None
    logged_in.get("/profile/")  # Reload doesn't reset the guard.
    assert detection(logged_in, "UTC")["suggestion"] is None
    assert detection(logged_in, "Asia/Tokyo")["suggestion"] is None
    assert detection(logged_in, "Europe/London")["suggestion"] is not None


def test_reverse_pair_is_distinct_and_stale_proposal_rejected(logged_in):
    detection(logged_in, "Europe/London")
    forward = detection(logged_in, "Asia/Tokyo")["suggestion"]
    reverse = detection(logged_in, "Europe/London")["suggestion"]
    assert reverse["to"] == "Europe/London"
    assert decision(logged_in, forward, "accept").status_code == 409
    assert decision(logged_in, reverse, "dismiss").status_code == 200


def test_simulation_does_not_change_real_detection_or_account(logged_in, user):
    detection(logged_in, "Europe/London")
    assert detection(logged_in, "Asia/Tokyo", "simulation")["suggestion"] is not None
    assert logged_in.session["device_timezone"] == "Europe/London"
    assert logged_in.session["simulated_timezone"] == "Asia/Tokyo"
    assert TimezonePreference.objects.get(user=user).display_timezone == "UTC"


def test_suggestions_are_private_to_session(logged_in, user):
    detection(logged_in, "UTC")
    proposal = detection(logged_in, "Asia/Tokyo")["suggestion"]
    other_device = Client()
    other_device.force_login(user)
    assert decision(other_device, proposal, "accept").status_code == 409
    detection(other_device, "UTC")
    assert detection(other_device, "Asia/Tokyo")["suggestion"] is not None


def test_manual_save_invalidates_popup(logged_in):
    detection(logged_in, "UTC")
    proposal = detection(logged_in, "Asia/Tokyo")["suggestion"]
    logged_in.post("/preferences/", {"display_timezone": "Europe/London"})
    assert decision(logged_in, proposal, "accept").status_code == 409


def test_suggestion_boundary_validation(logged_in, user):
    assert logged_in.get("/timezone-suggestion/").status_code == 405
    assert (
        logged_in.post("/timezone-suggestion/", "[]", content_type="application/json").status_code
        == 400
    )
    assert (
        logged_in.post(
            "/device-timezone/", {"timezone": "UTC", "source": []}, content_type="application/json"
        ).status_code
        == 400
    )
    detection(logged_in, "UTC")
    proposal = detection(logged_in, "Asia/Tokyo")["suggestion"]
    assert decision(logged_in, proposal, "bad").status_code == 400
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    assert decision(csrf_client, proposal, "accept").status_code == 403


@pytest.mark.django_db
def test_demo_seed_is_repeatable_and_nonprivileged(client):
    call_command("setup_demo")
    call_command("setup_demo")
    user = get_user_model().objects.get(username="demouser")
    assert not user.is_staff and not user.is_superuser
    assert client.login(username="demouser", password="demopassword")
    assert Event.objects.filter(user=user).count() == 3
    before = list(Event.objects.filter(user=user).values_list("occurred_at", flat=True))
    response = client.get("/profile/")
    assert b"Winter standup" in response.content
    client.post("/preferences/", {"display_timezone": "Asia/Tokyo"})
    assert list(Event.objects.filter(user=user).values_list("occurred_at", flat=True)) == before


def test_once_guard_survives_repeated_transition(logged_in):
    detection(logged_in, "UTC")
    assert detection(logged_in, "Asia/Tokyo")["suggestion"] is not None
    # Repeat the transition while retaining the session offer history.
    session = logged_in.session
    session["device_timezone"] = "UTC"
    session.save()
    assert detection(logged_in, "Asia/Tokyo")["suggestion"] is None
    assert logged_in.session["offered_timezone_changes"] == [["UTC", "Asia/Tokyo"]]


def test_first_browser_initializes_new_preference(client, user):
    client.force_login(user)
    first = detection(client, "America/Los_Angeles")
    assert first["initialized"] is True
    assert first["display_timezone"] == "America/Los_Angeles"
    assert first["suggestion"] is None
    assert detection(client, "Asia/Tokyo")["initialized"] is False
    assert TimezonePreference.objects.get(user=user).display_timezone == "America/Los_Angeles"
    other = Client()
    other.force_login(user)
    assert detection(other, "Europe/London")["display_timezone"] == "America/Los_Angeles"


def test_explicit_utc_is_not_a_placeholder(client, user):
    client.force_login(user)
    client.post("/preferences/", {"display_timezone": "UTC"})
    assert detection(client, "Asia/Tokyo")["display_timezone"] == "UTC"
    assert TimezonePreference.objects.get(user=user).timezone_initialized


def test_simulation_cannot_initialize_account(client, user):
    client.force_login(user)
    result = client.post(
        "/device-timezone/",
        {"timezone": "Asia/Tokyo", "source": "simulation"},
        content_type="application/json",
    ).json()
    assert not result["initialized"]
    assert not TimezonePreference.objects.get(user=user).timezone_initialized
    assert detection(client, "America/Los_Angeles")["initialized"]


def test_invalid_first_reading_can_be_retried(client, user):
    client.force_login(user)
    assert (
        client.post(
            "/device-timezone/", {"timezone": "Bad/Zone"}, content_type="application/json"
        ).status_code
        == 400
    )
    assert not TimezonePreference.objects.get(user=user).timezone_initialized
    assert detection(client, "UTC")["initialized"]

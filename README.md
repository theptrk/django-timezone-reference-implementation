# Django timezone reference implementation

A runnable reference for Django developers and coding agents adding timezone support to an
application. It covers UTC event storage, account timezone preferences, local datetime input,
DST validation, calendar queries, and browser timezone change suggestions.

The central policy: **store instants in UTC, display them in the user's saved IANA timezone,
and ask before changing that preference when the browser timezone changes.** Browser detection
is a suggestion, not permission to overwrite the account setting.

Built with Django 5.2, Python `zoneinfo`, SQLite, server-rendered templates, and plain JavaScript.
No frontend build step is required.

## Run the reference

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/theptrk/django-timezone-reference-implementation.git
cd django-timezone-reference-implementation
cp .env.example .env
uv sync
uv run python manage.py migrate
uv run python manage.py setup_demo
uv run python manage.py runserver
```

Open http://127.0.0.1:8000/. The homepage is an anonymous, read-only inspector with live clocks,
Django/database configuration, browser detection, and U.S. timezone comparisons.

Sign in at `/profile/` with **demouser / demopassword**. The demo account is non-staff.
`setup_demo` is repeatable: it resets the demo password, preserves existing timezone preferences,
and adds missing sample events. This public password and shared account are for teaching only.

Try the flow:

1. Save **America/Los_Angeles** as the account timezone. Compare the winter, summer, and
   near-midnight sample events. The stored instants stay the same; local times and dates change.
2. Set the simulated browser timezone to **America/Los_Angeles**, then **America/New_York**.
3. Accept the suggestion to save New York, or dismiss it to keep Los Angeles.
4. Reload or repeat that transition. The same directed pair is suppressed for the login session.

The simulator does not change the device's timezone or `Intl`. It lets you exercise travel
behavior without changing your operating system settings.

## Implementation map

Start here when adapting the code to an existing project:

| Concern | Implementation | What to carry into your app |
| --- | --- | --- |
| Settings | [config/settings.py](config/settings.py) | `USE_TZ=True`, UTC default, middleware after authentication |
| Data model | [models.py](timezones/models.py) | Aware event datetimes and saved IANA zone names |
| Zone validation | [zones.py](timezones/zones.py) | Validate names server-side; keep offset and timezone distinct |
| Request display | [middleware.py](timezones/middleware.py) | Activate the account zone and restore the previous context |
| Local datetime entry | [forms.py](timezones/forms.py) | Parse in the rendered form's zone; reject DST gaps/folds |
| Save and suggest | [views.py](timezones/views.py) | Explicit preference saves, session-scoped detection and offers |
| Browser detection | [timezone.js](static/timezone.js) | `Intl` detection, authenticated POST, accept/dismiss dialog |
| Searchable zones | [timezone-picker.js](static/timezone-picker.js) | Enhance a validated native select with local search |
| Calendar filtering | [week_bounds](timezones/zones.py) | Build local calendar boundaries, then query UTC instants |
| Background work | [weekly_report.py](timezones/management/commands/weekly_report.py) | Select a saved zone explicitly outside a request |
| Behavioral tests | [tests](timezones/tests/) | Preserve the timezone rules while adapting the UI |

## 1. Separate instants, timezone preferences, and local dates

An event that happened at a specific moment is an **instant**. `Event.occurred_at` stores that
moment through Django's timezone-aware `DateTimeField`. `Event.original_timezone` records the
zone used to interpret entry; changing display preferences never rewrites the instant.

`TimezonePreference.display_timezone` holds an IANA name such as `America/Los_Angeles`.
An offset such as `-08:00` cannot replace it: Los Angeles uses different offsets across the year.
The separate `reporting_timezone` field gives background reports a stable saved zone; the demo
profile edits only the display preference.

```python
USE_TZ = True
TIME_ZONE = "UTC"
```

SQLite has no native timezone setting. In this project Django prepares UTC values for storage
and returns aware datetimes. The inspector's database representation is a preview of that
conversion, not an inserted record.

Do not apply the instant model to every date feature. Birthdays and all-day dates often need
`DateField`; recurring appointments need local scheduling rules and a named timezone. This
reference does not implement recurring events or floating local reminders.

## 2. Apply the saved zone for each request

`TimezoneMiddleware` runs after Django's authentication middleware. For authenticated application
pages, it loads or creates the preference and wraps the response in:

```python
with timezone.override(ZoneInfo(request.display_timezone)):
    return self.get_response(request)
```

Django templates then render aware event datetimes in that zone. The context manager restores
the previous timezone, including when an exception occurs. The public inspector is deliberately
excluded from preference creation.

When adapting this middleware, choose the application routes where it belongs. Do not copy the
inspector's special-case `/` path unless your homepage needs that behavior. Streaming response
iterators run outside this override; supply an explicit timezone for deferred rendering.

## 3. Treat browser detection as session state

The authenticated page detects the browser timezone with:

```javascript
Intl.DateTimeFormat().resolvedOptions().timeZone
```

Detection runs on page load, window focus, and return to a visible tab. The server validates the
reported IANA name. A first reading establishes a baseline; an initial mismatch with the saved
account zone does **not** prompt. This implementation reacts to an observed change.

| State | Scope | Updated by |
| --- | --- | --- |
| Saved display timezone | Account | Profile save or accepted suggestion |
| `device_timezone` | Django session | Real browser detection |
| `simulated_timezone` | Django session | Demo simulation |
| `offered_timezone_changes` | Django session | First offer of a directed pair |
| `pending_timezone_suggestion` | Django session | Offer, decision, or invalidation |
| Simulator selection | Tab `sessionStorage` | Demo dropdown |

Real detection and simulation have separate baselines. The first simulated reading can start
from the real browser baseline; both sources share the same offered-pair history. Anonymous
visitors only inspect browser information locally: the homepage makes no detection POST,
creates no session or preference, and writes no browser storage.

### Why reloading does not repeat the popup

The detection endpoint remembers the new baseline and records the pair **before** returning a
suggestion. The core guard is:

```python
pair = [previous, zone]
offered = request.session.get("offered_timezone_changes", [])
if pair not in offered:
    request.session["offered_timezone_changes"] = [*offered, pair]
    # Create and return the pending suggestion.
```

Reassigning the list tells Django that session data changed. There is no separate popup-tracking
model or per-offer database query. This project uses Django's default database-backed sessions,
so session updates still use database storage.

The resulting behavior:

- **Reload:** the baseline is already the new zone; there is no new transition.
- **Dismiss or leave without answering:** the pair remains recorded and is not offered again.
- **Repeat LA → New York:** the recorded pair suppresses another offer in the same login session.
- **New York → LA:** a different pair, eligible only if LA differs from the saved account zone.
- **New login session:** fresh baseline and offer history; the first reading still does not prompt.

This is a deliberately simple session-based guard. Concurrent requests can read the same old
session state and occasionally offer a duplicate; it is not an exactly-once guarantee. For a
noncritical preference suggestion, avoiding a separate tracking model is a useful tradeoff.

### Accepting and dismissing

Both endpoints require authentication and CSRF. Acceptance sends a suggestion ID; the server
uses the target stored in the session, not a client-supplied replacement timezone. Accept saves
the preference; dismiss leaves it unchanged. Neither clears the offered-pair history.

Manual profile saves invalidate pending suggestions. Stale or cross-session IDs return `409`.
Accepting a popup reloads the page to render events in the new zone, with a warning if there are
unsaved edits. Other tabs pick up saved preferences on their next request.

This saved-account policy is a product choice. If your product should follow the device
continually, make that an explicit mode rather than silently changing the meaning of a saved
preference.

## 4. Parse local input in the zone the user saw

An HTML `datetime-local` input has no timezone. The event form includes a signed context token
containing the user ID and the zone in which the form was rendered, valid for 24 hours. If another
tab changes the account preference, submitting the old form still interprets its input in the
original zone.

`EventForm` validates that token, accepts a local datetime without an offset, and parses it with
Django's `DateTimeField` under the original timezone override. The view converts the resulting
aware value to UTC before saving.

DST creates two cases that need an explicit policy:

| Local input | Example in Los Angeles | Current behavior |
| --- | --- | --- |
| Nonexistent spring-forward time | `2026-03-08 02:30` | Validation error |
| Ambiguous fall-back time | `2026-11-01 01:30` | Validation error |

A scheduling application may instead offer the first or second occurrence of an ambiguous time.
Do not silently guess. The reference uses Django's rejection behavior for both cases.

## 5. Query calendar periods in the requested zone

A user's Monday is not necessarily Monday in UTC. `week_bounds()`:

1. Converts an aware instant into the requested zone before taking its date.
2. Constructs local Monday midnight and the next local Monday midnight.
3. Converts each boundary independently to UTC.

Queries use a half-open interval:

```python
Event.objects.filter(occurred_at__gte=start, occurred_at__lt=end)
```

DST weeks can be 167 or 169 hours, so adding 168 hours to a UTC start is not equivalent.
For rare transitions at midnight, the helper uses `ZoneInfo`'s pre-transition offset for gaps
and first occurrence for folds. Calendar boundaries have a separate policy from user-entered
datetimes, where this reference rejects gaps and folds.

The session-authenticated `GET /api/events/?timezone=America/Los_Angeles` uses the same helper.
The optional query zone affects only the query, invalid names return `400`, and returned event
timestamps include explicit UTC offsets. Unauthenticated requests redirect to login.

For background work:

```bash
uv run python manage.py weekly_report demouser
```

The command uses the saved reporting timezone without a browser or request; it prints rather
than sends email. Sample events have fixed winter/summer dates and may fall outside the current
week. The profile lists the latest 50 events across all dates so the demonstration stays useful.

## Timezone selection

Both dropdowns expose the full available catalog and support search by city, country, region,
and IANA identifier. Common U.S. zones come first, followed by territories, additional U.S.
localities, worldwide locations, and aliases. Country coverage comes from `tzdata` tables.
Do not merge zones merely because their offsets happen to match today.

[Tom Select](https://tom-select.js.org/) **2.6.2** enhances native grouped selects. Users can browse
or type; arbitrary free text cannot become a saved timezone. Django remains the validation
boundary. The account dropdown works without JavaScript, and search makes no network requests.

Assets are vendored in [static/vendor/tom-select-2.6.2](static/vendor/tom-select-2.6.2/), with the
upstream Apache-2.0 license and package integrity in `SOURCE.md`. There is no CDN or Node build.

Keep timezone rules current in your deployment. `ZoneInfo` uses system timezone data when
available, with the Python `tzdata` package as a fallback. Stored zone names do not freeze a
historical copy of those rules.

## Adapting this reference: developers and coding agents

Implement the storage and interpretation rules before copying the demonstration UI:

1. Decide which values are instants, local dates, or recurring schedules, and define the display
   policy: saved account zone or an explicit follow-device mode.
2. Add validated IANA preferences to your existing user/profile model. Preserve existing instants;
   audit naive legacy datetimes before enabling timezone support on an existing database.
3. Integrate request timezone activation, local input validation, and local calendar boundaries.
   Give jobs and API consumers an explicit timezone contract.
4. Add the picker and optional travel suggestion. Keep transient detection and offered pairs in
   the session; keep the saved preference on the account.
5. Port the relevant behavioral tests. Remove the simulator, public demo credentials, sample
   events, and inspector when they do not belong in your product.

For agents modifying this repository, preserve these invariants:

- Detection alone never saves an account preference.
- Changing display timezone never changes an existing event instant.
- The anonymous inspector remains read-only.
- DST validation and the signed form context survive UI changes.
- Repeat suppression belongs in session state, not a new tracking table.
- Server validation remains authoritative even when the picker restricts input.

This is a reference application, not a deployment template. Configure your own secrets, hosts,
HTTPS, account lifecycle, and session backend when integrating it. See
[.env.example](.env.example) for the local settings.

## Verification

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

The optional browser suite exercises the rendered UI with Chromium:

```bash
uv sync --group browser
uv run --group browser playwright install --with-deps chromium
uv run --group browser pytest
```

Tests cover UTC instants, DST gaps/folds, calendar boundaries, signed form context, user/session
isolation, invalid requests, CSRF, anonymous read-only behavior, demo setup, searchable dropdowns,
live clocks, travel suggestions, accept/dismiss, reload suppression, and stale suggestion IDs.
Without Playwright installed, browser tests are skipped.

## Related references and license

- [Django Gmail reference implementation](https://github.com/theptrk/django-gmail-reference-implementation)
- [Streaming Markdown reference implementation](https://github.com/theptrk/streaming-markdown-reference-implementation)
- [Django timezone documentation](https://docs.djangoproject.com/en/5.2/topics/i18n/timezones/)

Project code is [MIT licensed](LICENSE). Vendored Tom Select retains its own Apache-2.0 license.

# Timezone reference for coding agents

This repository is the runnable model for adding timezone support to another Django app.
Start with README.md's implementation map and docs/agent-integration.md. Read the actual code
and tests before adapting it. Preserve the target app's architecture and release workflow.

## Contracts to preserve

- Store instants as aware UTC datetimes; display in a validated saved IANA zone.
- Initialize an uninitialized account once from a valid real browser reading. Preserve existing
  preferences, including UTC. Later detection only offers an explicit accept/dismiss choice.
- Keep travel baselines, pending suggestions, and directed-pair suppression in the login session.
- Reject DST gaps and folds for local entry. Preserve signed rendered-form timezone context.
- Compute calendar boundaries locally and convert both ends independently to UTC.
- Keep the anonymous inspector read-only. Demo credentials, simulator, and seeded events belong
  only to this reference application.

## Tom Select integration

- Copy static/timezone-picker.js, static/timezone-picker.css, and the pinned vendor directory
  with its license and SOURCE.md. The adapter is an ES module; preserve its relative import.
- Render server-validated grouped native selects inside `.timezone-picker` containers, and give each select the
  `timezone-picker__native` class. Load the
  vendor CSS first, host CSS next, and timezone-picker.css last. See templates/timezones/index.html
  and static/timezone.js for wiring and the country metadata JSON.
- Keep `create: false`, native form submission, server validation, labels, keyboard navigation,
  country search, and the native fallback. Search typing must not mark a preference as changed.
- Map the host theme to the component tokens. `.theme-dark` and `[data-theme="dark"]` ancestors
  are demonstrated. The reference does not implement a global dark theme or persist theme state.
- Keep native fallback selectors restricted to `select.timezone-picker__native`: Tom Select
  copies select classes onto its wrapper. Test that the wrapper has no native padding or border.
- Keep component sizing in rem/min-height so enlarged text can grow; grid/flex hosts must allow
  shrinking (`min-width: 0`). Verify at 200% root text size on a narrow viewport.
- Keep every `.ts-*` selector under `.timezone-picker`; verify unrelated controls stay unchanged.
- Tom Select's single-select CSS includes a white gradient and a more specific focused state.
  Override the full `background`, with enough specificity for both closed and input-active states.
  A background-color override alone does not remove the gradient. Do not edit vendor assets.

## Verify changes

Use the locked environment: `uv sync --frozen --group browser`. Run `uv run pytest`,
`uv run ruff check .`, `uv run ruff format --check .`, `uv run python manage.py check`, and
`uv run python manage.py makemigrations --check --dry-run`. Browser tests require installed
Chromium (`uv run playwright install chromium`). Do not report skipped browser tests as passed.

Verify both pickers in light and dark themes, closed, focused, searching, and after a theme
change. Verify selection/save, empty simulator choice, invalid search, and native fallback.
When integrating elsewhere, run the relevant timezone behavior tests in that app too.

# Hand this reference to an implementation agent

Use this prompt with the target application's repository open:

> Use https://github.com/theptrk/django-timezone-reference-implementation as the model for
> timezone support in this application. Read its AGENTS.md, README implementation map, source,
> and behavioral tests. Inspect this application's existing timezone policy before editing it.
> Adapt the UTC storage, saved IANA preference, request activation, DST-safe local entry,
> calendar boundaries, first-browser initialization, and explicit travel-suggestion contracts
> where applicable. Preserve existing saved preferences and instants. Use the reference's
> Tom Select adapter and themeable picker stylesheet for searchable city/country/IANA selection,
> with native select fallback and server validation. Integrate with this application's own
> theme, forms, authentication, frontend loading, and deployment conventions. Port the relevant
> behavior tests; verify light and dark picker states in a browser, including focused search.
> Omit the demo account, simulator, sample events, and inspector from the product. Report the
> reference commit used, changes, verification results, and any policy differences.

The reference models behavior and integration boundaries; it is not a package to install or
an instruction to replace an application's settings. Record the commit SHA when adopting it
so later agents can compare changes against a known baseline.

## Picker files to adapt together

- `timezones/zones.py`: validated catalog, groups, and country search metadata.
- `timezones/forms.py`: native ChoiceField and server-side validation.
- `templates/timezones/index.html`: stylesheet order, labeled native selects, and metadata JSON.
- `static/timezone-picker.js`: Tom Select adapter (ES module).
- `static/timezone-picker.css`: scoped component styles and light/dark tokens.
- `static/vendor/tom-select-2.6.2/`: pinned upstream assets, license, and integrity record.
- `static/timezone.js`: initialization and its interaction with dirty-form/travel state.
- `timezones/tests/test_browser.py`: actual rendered search, keyboard, save, theme, and fallback checks.

Wrap each native select in `.timezone-picker` before enhancement and put
`class="timezone-picker__native"` on the select itself. This explicit hook works with any form
renderer; it does not depend on Django rendering a `<p>`. Restrict native fallback selectors to
`select` elements because Tom Select copies their classes to its wrapper. Supply the country metadata
as demonstrated; label-only search cannot find every country. The adapter imports its vendor
script relative to itself, so preserve the directory relationship or adapt the host bundle.
Do not copy script tags from an application that uses a different loading strategy.

The stylesheet defaults to light colors and supports a `.theme-dark` or `[data-theme="dark"]`
ancestor. A host with another theme convention can set the `--timezone-picker-*` custom
properties on the component. These hooks style the picker only; they do not implement a page
or account theme. Test the native fallback too. Keep component CSS after the vendor and host
styles, and verify computed background images as well as colors: Tom Select's white gradient
can hide a correct dark background color, including in its `input-active` state.


## Theme and size adapters

Keep the shared stylesheet unchanged in consuming applications. Load a small host adapter
last and map component tokens on the component itself (not merely an ancestor, since the
component declares defaults). Give it enough specificity to override the theme hooks:

```css
.timezone-picker.account-timezone {
  --timezone-picker-bg: var(--input-bg);
  --timezone-picker-text: var(--text-color);
  --timezone-picker-border: var(--input-border);
  --timezone-picker-focus: var(--link-color);
  --timezone-picker-selected: var(--link-color);
}
```

Map the remaining palette tokens to the host's dropdown, muted-text, and active-state colors.
Font size, line height, minimum control size, radius, and maximum width also have component
tokens. Defaults preserve the compact reference UI; an application can choose larger text
without rewriting component rules. Size tokens use rem and controls use min-height rather
than fixed height. Grid or flex parents should permit shrinking with `min-width: 0`.

The sole adapter `!important` overrides the search input width written inline by Tom Select,
letting flex distribute the available width. Other vendor resets are already provided upstream;
do not duplicate them. Keep theme, native fallback, unrelated-control isolation, and narrow
viewport/200% text checks when porting or upgrading the component.

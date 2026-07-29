# DEPRECATED — 2026-06-26

This copy of meta is deprecated. The authoritative runtime source is:

```text
plugins/meta/
```

Do not patch this directory. Do not add new capabilities here. If you need to
change the meta plugin, edit `plugins/meta/` instead.

## Migration status

- [x] `plugins/meta` has the richer `_message_from_brief()` with creative handoff fields (headline, subheadline, body_copy, body, cta_text, prompt filtering) — matching the channel ownership rule in `plugins/meta/meta.md`
- [x] No `api/` or `tests/` code references `api/plugins/meta`
- [ ] Delete this directory after verification

## Why this exists

This was the original bundled plugin location before the plugin system moved to
`./plugins` mounted as `/external_plugins`. It is kept temporarily as reference
and for any remaining test/doc dependencies.

# DEPRECATED — 2026-06-26

This copy of youtube is deprecated. The authoritative runtime source is:

```text
plugins/youtube/
```

Do not patch this directory. Do not add new capabilities here. If you need to
change the youtube plugin, edit `plugins/youtube/` instead.

## Migration status

- [x] Directories are identical — no code drift
- [x] No `api/` or `tests/` code references `api/plugins/youtube`
- [ ] Delete this directory after verification

## Why this exists

This was the original bundled plugin location before the plugin system moved to
`./plugins` mounted as `/external_plugins`. It is kept temporarily as reference
and for any remaining test/doc dependencies.

# DEPRECATED — 2026-06-26

This copy of google-drive is deprecated. The authoritative runtime source is:

```text
plugins/google-drive/
```

Do not patch this directory. Do not add new capabilities here. If you need to
change the google-drive plugin, edit `plugins/google-drive/` instead.

## Migration status

- [x] `export_file()` backported to `plugins/google-drive/drive_client.py`
- [x] `api/routers/social.py` `_load_google_drive_client()` no longer falls back to this directory
- [ ] Verify no tests import from this directory
- [ ] Verify no other `api/` code imports from this directory
- [ ] Delete this directory after verification

## Why this exists

This was the original bundled plugin location before the plugin system moved to
`./plugins` mounted as `/external_plugins`. It is kept temporarily as reference
and for any remaining test/doc dependencies.

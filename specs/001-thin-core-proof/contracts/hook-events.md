# Hook Events Contract — Deferred

**Branch**: `001-thin-core-proof` | **Date**: 2026-06-08

The hook subscription system is explicitly deferred for this MVP.

This feature implements the WordPress / VS Code / pi.dev plugin-host lifecycle only:

```text
external install root → installed/quarantined → activate per Brand → CMO manifest
```

Do not implement or expand hook event contracts as part of this feature.

Deferred hook topics:

```text
brief.before_dispatch
run.after_complete
manifest.built
plugin.activated
plugin.deactivated
filter hooks
action hooks
hook payload schemas
hook registration from channel.json
```

When hooks are needed, create a separate Spec Kit feature and produce BITE samples first.

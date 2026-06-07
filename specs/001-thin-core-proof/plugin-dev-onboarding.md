# Plugin Developer Onboarding

You are building a third-party plugin for Klaroha BOS.
This doc covers everything you need to get started.

---

## Start here: the plugin directory

All plugins live in `~/bos-plugins/`. Read its README first:

```
~/bos-plugins/README.md
```

That covers the full plugin contract: directory structure, three required files,
SDK imports, credentials, and how BOS picks up your plugin.

---

## SDK install

```bash
pip install -e /home/ubu/bos/packages/klaroha_sdk
```

Verify:
```bash
python -c "from klaroha_sdk import ChannelModule, ArtifactBlock, RunResult; print('SDK OK')"
```

Full SDK API reference: `packages/klaroha_sdk/README.md`

---

## Reference plugin

`~/bos-plugins/hello/` is a working plugin you can copy as a starting point.
It has all three required files and uses the SDK correctly.

---

## Build your plugin

1. Create a directory in `~/bos-plugins/your-plugin-name/`
2. Write `channel.json` (copy from hello, update fields)
3. Write `SKILL.md` in `capabilities/{vertical}/{domain}/{task}/`
4. Write `module.py` in the same directory as `SKILL.md`
5. Restart BOS: `docker compose restart api` (from `~/bos/`)
6. Check it loaded: `curl http://localhost:8090/api/plugins/manifest`

---

## How BOS dispatches your plugin

The CMO reads all installed `SKILL.md` files and uses its own judgment to decide
which plugin to invoke based on the user's message. You control dispatch entirely
via `SKILL.md`:

- `description` — what this plugin does (most important field)
- `triggers` — phrases that should invoke it
- `requires_intent` — intent type filter

The CMO does NOT use hardcoded routing. It reads your `SKILL.md` and decides.
Write a clear, specific description.

---

## Your plugin is independent

Your plugin repo (`~/bos-plugins/`) is separate from BOS core (`~/bos/`).
You don't have access to BOS internals and you don't need them.
You only import from `klaroha_sdk`.

BOS → fires hook events → your plugin subscribes → no coupling.

---

## Need help?

- Plugin contract: `~/bos-plugins/README.md`
- SDK API: `packages/klaroha_sdk/README.md`
- Hook events: `specs/001-thin-core-proof/contracts/hook-events.md`
- Working example: `~/bos-plugins/hello/`

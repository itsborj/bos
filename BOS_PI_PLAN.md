# BOS-Pi Fork Plan

> Agent harness for BOS CMO — fork of Pi (pi.dev), built separately, zero BOS code changes.
> Pick this up when starting the `bos-pi` repo.

---

## What This Is

A fork of the Pi agent harness (github.com/earendil-works/pi-mono) that connects to BOS's existing `/chat/stream` API as its provider. Pi handles sessions, compaction, skills discovery, RPC mode, and the TUI. BOS handles all LLM calls and capability dispatch. No code in the BOS repo changes.

Reference: OpenClaw (docs.openclaw.ai) is a prior fork of Pi — same pattern, different vertical.

---

## Deployment Model

Each org gets one cloud deployment of BOS. Pi runs bundled inside it as a service in RPC mode. Org users access BOS through a browser. The Pi CLI is optional for power users.

```
Browser → nginx → BOS web (React)
                → BOS API (FastAPI) → Pi service (RPC mode)
                                            ↓
                                      BOS /chat/stream
```

For 10,000 orgs: one BOS deployment per org (dedicated instance, not multi-tenant). Control plane handles provisioning, updates, health monitoring. BOS code stays single-tenant — the "one workspace per deployment" constraint is correct by design.

---

## BOS API Contract

The only surface area the Pi fork calls:

```
POST /chat/stream
Headers: X-API-Key: <key>
Body: {
  message: str,
  history: [{ role: "user" | "ai", text: str }],
  brand_id: str | null,
  campaign_id: str | null
}

SSE response events (data: {json}\n\n):
  { "type": "step",          "label": "..." }
  { "type": "reply",         "text": "...", "klar_action": ... }
  { "type": "module_start",  "module_id": "...", "label": "..." }
  { "type": "module_result", "module_id": "...", "run": {...} }
  { "type": "done" }
```

BOS uses custom SSE — not OpenAI-compatible. Requires `streamSimple` implementation in the provider extension.

---

## Repo Structure

```
bos-pi/
├── packages/              ← Pi monorepo (forked, rename only)
│   ├── ai/
│   ├── agent/
│   ├── tui/
│   └── bos-agent/         ← renamed from coding-agent
├── extensions/
│   └── bos-provider/
│       └── index.ts       ← entire BOS integration (see below)
├── skills/
│   └── marketing/
│       ├── email-outreach/SKILL.md
│       ├── brand-setup/SKILL.md
│       └── seo/SKILL.md
└── package.json
```

---

## Step 1 — Fork and Rename

```bash
git clone https://github.com/earendil-works/pi-mono bos-pi
cd bos-pi
npm install && npm run build
```

In `package.json` change three fields:
```json
{
  "piConfig": {
    "name": "bos",
    "configDir": ".bos"
  },
  "bin": "bos"
}
```

This renames the CLI banner, config directory (`~/.bos/`), and env var prefix. That's the full extent of the fork rename.

---

## Step 2 — BOS Provider Extension

`extensions/bos-provider/index.ts` — the entire integration:

```typescript
export default function (pi: ExtensionAPI) {

  pi.registerProvider("bos", {
    baseUrl: process.env.BOS_API_URL!,
    apiKey: "BOS_API_KEY",
    api: "custom",
    models: [{
      id: "cmo", name: "BOS CMO", reasoning: false,
      input: ["text"], cost: { input: 0, output: 0 },
      contextWindow: 128000, maxTokens: 8000
    }],

    async streamSimple(model, context, options) {
      const history = context.messages
        .filter(m => m.role === "user" || m.role === "assistant")
        .slice(0, -1)
        .map(m => ({
          role: m.role === "assistant" ? "ai" : "user",
          text: m.content[0].text
        }));

      const message = context.messages.at(-1)!.content[0].text;
      const brand_id = process.env.BOS_BRAND_ID ?? null;

      const res = await fetch(`${process.env.BOS_API_URL}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": process.env.BOS_API_KEY!
        },
        body: JSON.stringify({ message, history, brand_id }),
        signal: options.signal,
      });

      options.onEvent({ type: "content_start", contentType: "text" });

      for await (const line of sseLines(res.body!)) {
        const ev = JSON.parse(line.slice(6)); // strip "data: "
        if (ev.type === "reply")         options.onEvent({ type: "content_delta", delta: ev.text });
        if (ev.type === "step")          options.onEvent({ type: "thinking_delta", delta: `[${ev.label}]\n` });
        if (ev.type === "module_start")  options.onEvent({ type: "tool_start", name: ev.module_id, label: ev.label });
        if (ev.type === "module_result") options.onEvent({ type: "tool_end", name: ev.module_id });
        if (ev.type === "done")          break;
      }

      options.onEvent({ type: "content_end" });
      options.onEvent({ type: "done" });
    }
  });

  // inject active brand into system prompt before every call
  pi.on("before_agent_start", async (event) => {
    if (process.env.BOS_BRAND_ID)
      event.systemPrompt += `\nActive brand_id: ${process.env.BOS_BRAND_ID}`;
  });

  // /brand command to switch context mid-session
  pi.registerCommand("brand", {
    description: "Switch active brand by ID",
    handler: async (args, ctx) => {
      process.env.BOS_BRAND_ID = args.trim();
      ctx.ui.notify(`Switched to brand: ${args.trim()}`, "info");
    }
  });
}

// helper — yields "data: {...}" lines from an SSE response body
async function* sseLines(body: ReadableStream<Uint8Array>) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop()!;
    for (const line of lines)
      if (line.startsWith("data: ")) yield line;
  }
}
```

---

## Step 3 — Marketing Skills

Copy SKILL.md files from BOS's `api/capabilities/` into `bos-pi/skills/marketing/`. They already follow the Pi skill spec. Add `module_id` frontmatter to each so the CMO knows which BOS module to dispatch:

```markdown
---
name: email-outreach
description: Draft cold outreach email sequences for a brand
module_id: marketing.channel.email.outreach.cold
---
```

Skills to copy on day one (match what's installed in BOS):
- `email-outreach` — `api/capabilities/marketing/channel/email/outreach/cold/`
- `brand-setup` — `api/capabilities/onboarding/brand_setup/`
- `seo` — (wherever SEO capability lives)

Pi auto-discovers skills from `skills/` directory. No registry changes needed.

---

## Org Setup (end state)

```bash
npm install -g bos-pi

BOS_API_URL=https://acme.klaroha.com \
BOS_API_KEY=pk_... \
BOS_BRAND_ID=<uuid> \
bos
```

---

## Work Estimate

| Item | Effort |
|---|---|
| Fork + rename | 1 hour |
| `sseLines` helper | 30 min |
| `bos-provider` extension | 1–2 days |
| Marketing SKILL.md copies + `module_id` audit | 1 day |
| RPC WebSocket bridge (for web integration) | 2–3 days |
| **Total MVP** | **~1 week** |

---

## What's Not in This Repo

- BOS API (FastAPI) — lives in `bos/` repo, unchanged
- React frontend — lives in `bos/web/`, unchanged
- PostgreSQL, nginx, Docker Compose — unchanged
- Capability modules — unchanged

The only coupling is the `/chat/stream` endpoint contract documented above.

---

## Open Questions Before Starting

1. Does `/chat/stream` require auth today, or is it internal-only? (Determines whether `X-API-Key` header is already wired.)
2. What's the exact `module_id` format BOS uses internally — dot-separated path or slug? (Needed for SKILL.md frontmatter.)
3. RPC WebSocket bridge: is this needed for MVP or defer until web integration phase?

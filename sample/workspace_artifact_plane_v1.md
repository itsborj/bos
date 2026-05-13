# Workspace Artifact Plane v1 — Agreed Sample

Status: approved by human on 2026-05-13.

## Principle

CMO chat is the narrative/control surface. Workspace Artifacts are the canonical artifact plane. Stream is a mobile feed over the same artifact records.

## Sample turn — specific artifact request

User:

> Draft a Gmail outreach email for Klaroha to a small business owner.

CMO visible reply:

> I drafted a Gmail outreach email focused on the pain of juggling too many marketing tools. Review it before we send or revise it.

Chat response payload as consumed by the CMO renderer:

```json
{
  "reply": "I drafted a Gmail outreach email focused on the pain of juggling too many marketing tools. Review it before we send or revise it.",
  "artifact_refs": [
    {
      "artifact_id": "art_8f31",
      "title": "Email Draft",
      "type": "draft_artifact",
      "status": "pending_review",
      "renderer": "email_preview",
      "workspace_url": "/workspace/artifacts/art_8f31"
    }
  ]
}
```

During migration, the API may still include legacy `runs[]` for backward-compatible clients. The CMO renderer must treat `artifact_refs[]` as the chat contract and must not render the native artifact body inline.

Workspace artifact detail uses the persisted run/result as source of truth and renders the native preview there.

Mobile Stream reads the same persisted artifact and may render the native preview there too.

## Sample turn — broad sample follow-up

User:

> what can you do?

CMO visible reply:

> I can help plan campaigns, create reviewable marketing drafts, review email/reply signals, and summarize available performance data. Tell me what you want to create or check.

User:

> let me see samples

Correct CMO visible reply:

> Which sample should I create as a reviewable Workspace artifact — an email draft, an email campaign plan, or a launch plan? I won’t paste channel-native drafts inline.

Correct hidden directives: none, because the artifact type is ambiguous.

Incorrect CMO visible reply:

```text
Email Campaign Sample:
Subject: Find Your Next Motorcycle...
Body: Get ready to hit the road...

Google Ads Sample:
Headline: Dependable Mobility...
Description: Get the best motorcycles...
```

## Allowed outcomes

- CMO chat creates a short conversational reply.
- CMO chat shows a compact artifact reference/link only.
- Workspace opens the artifact by ID and owns native preview, approval, revision, dismiss, and system details.
- Stream surfaces the same artifact record as a mobile card.
- Revising creates/supersedes artifact versions instead of embedding native drafts in chat history.

## Forbidden outcomes

- Platform-native drafts/previews rendered inline inside CMO chat.
- Plugin-authored final CMO prose.
- Artifact content existing only inside a chat message.
- Mobile Stream reconstructing artifacts from chat history.
- CMO claiming send/publish/action completion before explicit approval.

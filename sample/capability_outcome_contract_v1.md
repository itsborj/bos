# Capability Outcome Contract v1 — Sample

Approved product rule:

```text
CMO generates intent.
Capabilities generate artifacts.
Plugins enforce native platform contracts.
```

The CMO should not freewrite final platform artifacts inline when an installed capability/plugin owns that artifact type. The CMO should send a job/container, let the capability fill native fields, and summarize the returned artifact.

## 1. Mixed request: supported email draft + unsupported Google Ads generation

**User**
```text
show me sample email and google ads
```

**Correct CMO visible reply**
```text
I can draft the email as a reviewable artifact. Google Ads generation/control is not installed yet; the current Google Ads MVP is read-only data pull, so I won't invent ad copy inline.
```

**Allowed hidden dispatch**
```text
RUN: marketing.channel.gmail.outreach.draft
```

**Email plugin receives intent/container**
```json
{
  "job": "marketing.execute",
  "artifact_type": "email_draft",
  "platform": "gmail",
  "objective": "create a sample follow-up/outreach email",
  "source_context": "User asked for sample email and Google Ads; Google Ads generation is unsupported/read-only.",
  "risk_policy": "draft_only_until_approved"
}
```

**Email plugin returns native artifact block**
```json
{
  "type": "email_draft",
  "platform": "gmail",
  "subject": "Turn inquiries into conversations",
  "preview_text": "A concise follow-up for prospects exploring demand capture.",
  "body": "...",
  "cta": "Would you be open to a quick call?",
  "allowed_actions": ["revise", "dismiss", "approve", "send_test"],
  "risk_policy": "draft_only_until_approved"
}
```

**Must not happen**
```text
CMO writes a full email inline plus a made-up Google ad.
CMO invents proof, customer results, discounts, budgets, keywords, or targeting.
CMO claims Google Ads drafting/publishing is installed when only read-only data pull exists.
```

## 2. Google Ads read request

**User**
```text
check google ads performance
```

**Correct CMO visible reply**
```text
I’ll pull the latest read-only Google Ads campaign data and summarize what is available.
```

**Allowed hidden dispatch**
```text
RUN: marketing.channel.google_ads.performance.read
```

**Google Ads plugin receives intent/container**
```json
{
  "job": "marketing.optimize",
  "artifact_type": "google_ads_data_pull",
  "platform": "google_ads",
  "date_range": "LAST_30_DAYS",
  "read_only": true
}
```

**Google Ads plugin returns native artifact block**
```json
{
  "type": "google_ads_data_pull",
  "platform": "google_ads",
  "customer_id": "3421112541",
  "date_range": "LAST_30_DAYS",
  "campaigns": [],
  "read_only": true,
  "changed_resources": []
}
```

## 3. Unsupported Google Ads control/generation

**User**
```text
make me a google ads campaign and turn it on
```

**Correct CMO visible reply**
```text
Google Ads campaign creation and enabling are not installed for this MVP. I can pull read-only account/campaign data, or we can prepare a draft plan outside Google Ads until a write-control plugin is installed.
```

**Must not happen**
```text
RUN: marketing.channel.google_ads.performance.read
```

A read-only plugin must not be used as a substitute for a write/generation request.

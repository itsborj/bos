---
id: internal.client_onboarding.google_business_profile
name: Google Business Profile Client Onboarding
description: Use when onboarding a new Google Business Profile client, requesting Google Business Profile access, sending a client kickoff email, sharing a Google Drive onboarding folder, requesting discovery questionnaire completion, requesting creative assets for GBP setup, or introducing the service delivery team for a GBP engagement. This is an internal/client operations workflow, not a marketing campaign or generic email sequence.
scope: atomic_workflow
status: active
allowed_from_chat: true
module_id: internal.client_onboarding.google_business_profile
related_modules:
  - internal.client_onboarding.google_business_profile
requires_intent:
  - generation
  - revision
triggers:
  - google business profile onboarding
  - gbp onboarding
  - google business profile client
  - gbp client
  - google business profile access
  - client onboarding email
  - kickoff email
  - onboarding questionnaire
excluded_triggers:
  - email sequence
  - cold email
  - drip campaign
memory_slots:
  - brand_profile
  - product_catalog
  - audience_profiles
resources:
  - template.md
  - checklist.md
  - questionnaire_template.md
related_skills:
  marketing.channel.email.outreach.sequence: Use for multi-email automated lifecycle flows, not one-off client onboarding.
  marketing.cold_email: Use for prospecting outreach before a client relationship exists.
required_context:
  - client_name
  - gbp_access_email
  - google_drive_folder_link
  - questionnaire_link
  - kickoff_call_link
  - team_members
  - signoff_name
output_contract:
  - Subject
  - Access / Logins
  - Discovery
  - Creatives / Marketing Resources
  - Team Members
quality_gates:
  - includes_gbp_access_request
  - includes_google_drive_folder
  - includes_onboarding_questionnaire
  - includes_kickoff_call
  - includes_creatives_request
  - includes_team_contacts
metadata:
  version: 1.0.0
---

# Google Business Profile Client Onboarding

This skill governs the client-facing onboarding email for a Google Business Profile service engagement.

## Operating rule

Treat this as an internal service-delivery workflow. The artifact is an email, but the business function is client onboarding. Do not route it to marketing email sequence or cold outreach skills.

## Intake

Use any provided conversation or workspace context first. Ask only for missing operational details:

1. Client/contact name.
2. GBP access email to grant access to.
3. Google Drive folder link.
4. Onboarding questionnaire link, or whether BOS should use `questionnaire_template.md` to create/share one.
5. Kickoff scheduling link or proposed time.
6. Team member names, roles, and emails.
7. Signoff name.

## Required sections

The email must include:

- Welcome / getting started.
- ACCESS / LOGINS.
- DISCOVERY, including the onboarding questionnaire.
- CREATIVES / MARKETING RESOURCES.
- TEAM MEMBERS.
- Direct close and signoff.

## Quality gates

Before returning the email, check that it:

- Requests Google Business Profile access.
- Includes or TODO-flags the access email.
- Mentions the Google Drive folder.
- Links or TODO-flags the onboarding questionnaire, using `questionnaire_template.md` as the source content if a client-specific questionnaire needs to be created.
- Mentions kickoff scheduling.
- Requests logos, promotional media, customer persona info, testimonials, and business photos/video.
- Introduces team contacts or TODO-flags missing team details.
- Uses a warm operations tone, not promotional marketing language.

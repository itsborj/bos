---
id: marketing.analytics.google_tag_manager
name: google-tag-manager
description: Google Tag Manager — containers, workspaces, tags, triggers, variables, publishing Use when the user wants to configure GTM containers, add or edit tags, set up triggers or variables, publish a GTM workspace, or audit tag firing.
scope: atomic_task
status: active
allowed_from_chat: true
module_id:
requires_intent:
  - diagnostic
  - generation
triggers:
  - google tag manager
  - gtm
  - tag manager
  - gtm container
  - gtm tags
  - gtm triggers
  - gtm variables
  - container
  - tags
  - triggers
  - variables
  - workspace
  - publish container
  - gtm audit
excluded_triggers:
  - google ads
  - google analytics
  - ga4
  - universal analytics
  - campaigns
  - ad copy
memory_slots:
  - brand_profile
quality_gates:
  - explicit_generation_or_revision_intent
  - no_visible_control_directives
metadata:
  version: 1.0.0
---

# Google Tag Manager

Manage marketing and analytics tags without editing site code: create, read, update, and delete tags, triggers, and variables; review version history and roll back; stage work in workspaces; publish container versions.

## Hierarchy

Account → Container → Workspace → Tags / Triggers / Variables. Discover accounts, then containers, then the default workspace.

## Read-oriented workflows

- **Audit existing setup**: Enumerate accounts → enumerate containers → enumerate tags, triggers, and variables.
- **Inspect a tag**: Open full tag details including parameters, conversion IDs, custom HTML content.
- **Inspect a trigger**: Open full trigger details including event filters and conditions.
- **Version history**: Enumerate published versions to see what changed when. Open a specific version for a full snapshot.
- **Check live config**: Request version id `0` for the exact currently published definition.

## Write-oriented workflows

- **Add conversion tracking**: Create a custom event trigger (e.g., `signup`) → create a Google Ads Conversion tag linked to that trigger → publish.
- **Update existing tags**: Change parameters, link new triggers, pause/unpause tags.
- **Create variables**: Add dataLayer variables, constants, or JavaScript variables for tags to reference.
- **Enable built-in variables**: Enable Click URL, Page Path, Form ID, etc. for use in triggers.
- **Create workspace**: Isolate changes in a new workspace (like a branch) before publishing.

## Publish and rollback

- **Publish**: Create a version from workspace and push live.
- **Rollback**: Re-publish a previous version to undo bad changes.

## Revert workspace drafts

- **Revert tag/trigger**: Undo workspace changes before publishing — restore to last published state.

## Key Concepts

- **Workspaces**: Draft environments. Default workspace ID varies (enumerate workspaces to find it). Changes are staged here.
- **Tag types**: `awct` (Google Ads Conversion), `ua` (Universal Analytics), `gaawc` (GA4 Config), `gaawe` (GA4 Event), `html` (Custom HTML), `img` (Custom Image).
- **Trigger types**: `customEvent`, `pageview`, `domReady`, `click`, `linkClick`, `formSubmission`, `historyChange`, `timer`, `scrollDepth`, `elementVisibility`.
- **Parameter format**: GTM API uses a specific Parameter object format: `{"type": "template", "key": "keyName", "value": "theValue"}`.
- **Consent settings**: Tags can require specific consent types before firing (GDPR compliance).
- **Version IDs**: Version id `0` refers to the live published container.

## Related Skills

- **google-ads**: For creating and managing Google Ads campaigns, keywords, and RSA ads
- **seo-audit**: For auditing website SEO which may require GTM for analytics tag verification
- **analytics-tracking**: For setting up and verifying analytics tracking through GTM

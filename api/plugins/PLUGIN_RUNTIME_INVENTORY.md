# Plugin / Core Module Runtime Inventory

**Captured:** 2026-06-08 after plugin-host MVP restart

This file records the current local runtime inventory. It is not the plugin architecture contract; for the contract, see [`PLUGIN_ARCHITECTURE_RECOMMENDATION.md`](./PLUGIN_ARCHITECTURE_RECOMMENDATION.md).

## Installed plugins

These come from the external plugin root (`/external_plugins`, host default `~/bos-plugins`) and are visible in Admin → Specialists.

### `channel.gbp-completeness`

- Name: GBP Profile Completeness
- Source: external
- Status: installed
- Activation: inactive
- Capabilities:
  - `marketing.intelligence.gbp.completeness_score`
- Requires social connection:
  - `google_business`

### `channel.hello`

- Name: Hello Pipeline Test
- Source: external
- Status: installed
- Activation: inactive
- Capabilities:
  - `marketing.channel.hello.pipeline_test`
- Requires social connection: none

## Core modules

Core/first-party modules are not plugins and should not appear in Admin → Specialists. They are available through the module registry/API when dispatchable.

### copywriting

- `copywriting.copywriting_30_second_milo_frank`
  - Name: copywriting_30_second_milo_frank
  - Capability: `marketing.copywriting`
  - Platform: `copywriting_skill`
  - Internal: `true`

### marketing

- `marketing.email.campaign_plan`
  - Name: Email Campaign Plan
  - Capability: `marketing.copywriting`

- `marketing.messaging.architecture`
  - Name: Message Architecture
  - Capability: `marketing.copywriting`

- `marketing.plan.campaign_strategy`
  - Name: Marketing Campaign Strategy Plan
  - Capability: `marketing.copywriting`

- `marketing.planning.gtm_plan`
  - Name: GTM Strategy Plan
  - Capability: `marketing.copywriting`

- `marketing.planning.strategy_workflow`
  - Name: Strategy Workflow
  - Capability: `marketing.copywriting`

### onboarding

- `onboarding.brand_guidelines`
  - Name: brand_guidelines
  - Capability: `onboarding.brand_profiling`

- `onboarding.brand_setup`
  - Name: brand_setup
  - Capability: `onboarding.brand_profiling`

### reasoning

- `reasoning.buyer_intelligence`
  - Name: Buyer Intelligence Map
  - Capability: `marketing.copywriting`

## Where to query

Plugins:

```bash
GET /plugins
```

Core module registry:

```bash
GET /verticals
GET /verticals/{vertical}/modules
GET /modules/{module_id}
```

UI locations:

- Installed plugins: Admin → Specialists
- Core modules: `/modules`

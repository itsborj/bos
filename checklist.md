# Stream Activation Checklist

Stream should be treated as inactive until every required item below is complete for the active brand/client.

## Required checklist

- [ ] **AI provider connected**
  - Required by: CMO generation, decision briefs, Stream artifact generation
  - Complete in: `/admin/providers`
  - Data source: `api.getProviders()`; passes when a provider is connected, has a platform key, or has a BYOK key.

- [ ] **Client/brand selected**
  - Required by: Brand-scoped Stream activation
  - Complete in: `/admin/brands`
  - Data source: active UI brand context.

- [ ] **Workspace configured**
  - Required by: Admin setup banner, CMO, campaign operations
  - Complete in: `/admin/getting-started` or `/admin/onboarding`
  - Data source: `api.getOnboardingStatus(brand_id).workspace_configured` plus active brand fallback.

- [ ] **Brand profile imported**
  - Required by: Admin Setup / Client Readiness
  - Complete in: `/admin/onboarding`
  - Data source: `api.getOnboardingStatus(brand_id)` plus brand voice/tone/values fallback.

- [ ] **Live campaign extracted**
  - Required by: Admin Setup brand readiness
  - Complete in: `/admin/onboarding`
  - Data source: `OnboardingStatus.live_campaign_present`.

- [ ] **Brand Creative Brief approved**
  - Required by: Stream readiness and brand-aware creative generation
  - Complete in: `/admin/brands/:brand_id?tab=brand-kit` or `/admin/onboarding`
  - Data source: `api.getLatestBrandKit('approved', brand_id)`.

- [ ] **Google Drive connected**
  - Required by: Client Readiness and image/video rendering
  - Complete in: `/admin/brands/:brand_id?tab=integrations`
  - Data source: `api.listSocialConnections(brand_id)`; passes when `platform` is `google_drive` and status is `connected` or `active`.

- [ ] **Brand Kit Drive folder selected** *(shown after Google Drive is connected)*
  - Required by: Brand Kit asset storage and media rendering
  - Complete in: `/admin/brands/:brand_id?tab=integrations`
  - Data source: `api.listDriveFolders(brand_id)`; passes when selected folder id exists and is not `root`.

- [ ] **Logo/wordmark present in selected Drive folder** *(shown after a Brand Kit Drive folder is selected)*
  - Required by: Brand Kit asset validation and branded image/video output
  - Complete in: `/admin/brands/:brand_id?tab=brand-kit`
  - Data source: `api.listDriveImages(brand_id, folder_id, 'image')`; passes when a file name matches `logo`, `wordmark`, `brandmark`, or `mark`.

- [ ] **At least one publish channel connected**
  - Required by: Client Readiness publish channels and approved artifact execution
  - Complete in: `/admin/brands/:brand_id?tab=integrations`
  - Data source: `api.listSocialConnections(brand_id)`; passes when any of `facebook`, `youtube`, `tiktok`, or `google_business` has status `connected` or `active`.

- [ ] **Gmail connected**
  - Required by: Gmail reply monitoring
  - Complete in: `/admin/brands/:brand_id?tab=integrations`
  - Data source: `api.listSocialConnections(brand_id)`; passes when `platform` is `gmail` and status is `connected` or `active`.

- [ ] **Google Calendar connected**
  - Required by: Booking Pages live availability
  - Complete in: `/admin/brands/:brand_id?tab=integrations`
  - Data source: `api.listSocialConnections(brand_id)`; passes when `platform` is `google_calendar` and status is `connected` or `active`.

- [ ] **At least one installed capability activated** *(conditional)*
  - Required by: Admin Client Readiness capability gate
  - Complete in: `/admin/modules`
  - Data source: `api.listPlugins(brand_id)`; only required when non-test installed plugins exist.

- [ ] **Active capability prerequisites configured** *(conditional)*
  - Required by: Admin Capabilities safe activation
  - Complete in: `/admin/modules`
  - Data source: active plugins from `api.listPlugins(brand_id)`; passes when active plugins have no additional credential/env/social blockers beyond direct checklist items already shown above (for example Google Drive/Gmail/Calendar blockers are not counted twice).

## Universal prerequisite rule

Any Admin surface that blocks, warns, disables a primary action, or says a feature requires setup must register the same prerequisite in `web/src/utils/streamActivationChecklist.ts` unless it is purely a one-off form validation or runtime incident. Admin → Stream Setup and any future readiness surfaces must consume this shared checklist instead of duplicating local readiness logic.

Runtime incidents such as failed runs, pending approvals, and open pending decisions should appear as operational health/attention cards, not setup prerequisites.

## UI implementation

The current checklist is rendered in `web/src/pages/admin/AdminObjectiveLoop.tsx` as **Stream Activation Checklist**. Each item displays Done/Todo state, the reason it is required, and a link to the Admin surface where the requirement is completed.

The Stream page (`web/src/pages/Stream.tsx`) does **not** disable or hide the feed based on this checklist. Setup readiness lives in Admin → Stream Setup; Stream can still show artifacts, operational update cards, or the quiet state while setup work remains.

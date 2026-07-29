import assert from 'node:assert/strict';
import test from 'node:test';
import { buildStreamActivationChecklist } from '../src/utils/streamActivationChecklist';

function checklist() {
  return buildStreamActivationChecklist({
    brandId: 'brand-1',
    brandName: 'Agency Client',
    providers: [{ connected: true } as never],
    brand: { id: 'brand-1', name: 'Agency Client', voice: 'clear', tone: 'warm', values: ['trust'] } as never,
    onboardingStatus: { brand_profile_configured: true, live_campaign_present: true } as never,
    connections: [
      { platform: 'google_drive', status: 'connected' },
      { platform: 'facebook', status: 'connected' },
      { platform: 'gmail', status: 'connected' },
      { platform: 'google_calendar', status: 'connected' },
    ] as never,
    plugins: [],
    brandKitReady: true,
    driveRootName: 'Brand Kit',
    driveLogoCount: 1,
  });
}

test('brand readiness does not require an approved social-post template', () => {
  const result = checklist();
  assert.equal(result.items.some(item => item.key === 'approved-template'), false);
  assert.equal(result.items.some(item => /social-post design template/i.test(item.label)), false);
});

test('approved creative brief and official logo are explicit readiness items', () => {
  const result = checklist();
  assert.equal(result.items.find(item => item.key === 'brand-kit')?.label, 'Brand Creative Brief approved');
  assert.equal(result.items.find(item => item.key === 'brand-kit')?.ok, true);
  assert.equal(result.items.find(item => item.key === 'brand-logo')?.ok, true);
});

test('drive child checks are not counted before Google Drive is connected', () => {
  const result = buildStreamActivationChecklist({
    brandId: 'brand-1',
    brandName: 'Agency Client',
    providers: [{ connected: true } as never],
    brand: { id: 'brand-1', name: 'Agency Client', voice: 'clear', tone: 'warm', values: ['trust'] } as never,
    onboardingStatus: { brand_profile_configured: true, live_campaign_present: true } as never,
    connections: [
      { platform: 'facebook', status: 'connected' },
      { platform: 'gmail', status: 'connected' },
      { platform: 'google_calendar', status: 'connected' },
    ] as never,
    plugins: [],
    brandKitReady: true,
    driveRootName: null,
    driveLogoCount: 0,
  });

  assert.equal(result.items.find(item => item.key === 'drive-connected')?.ok, false);
  assert.equal(result.items.some(item => item.key === 'drive-folder'), false);
  assert.equal(result.items.some(item => item.key === 'brand-logo'), false);
});

test('drive folder child check is not counted before a folder is selected', () => {
  const result = buildStreamActivationChecklist({
    brandId: 'brand-1',
    brandName: 'Agency Client',
    providers: [{ connected: true } as never],
    brand: { id: 'brand-1', name: 'Agency Client', voice: 'clear', tone: 'warm', values: ['trust'] } as never,
    onboardingStatus: { brand_profile_configured: true, live_campaign_present: true } as never,
    connections: [
      { platform: 'google_drive', status: 'connected' },
      { platform: 'facebook', status: 'connected' },
      { platform: 'gmail', status: 'connected' },
      { platform: 'google_calendar', status: 'connected' },
    ] as never,
    plugins: [],
    brandKitReady: true,
    driveRootName: null,
    driveLogoCount: 0,
  });

  assert.equal(result.items.find(item => item.key === 'drive-folder')?.ok, false);
  assert.equal(result.items.some(item => item.key === 'brand-logo'), false);
});

test('needs-reauth Drive connection gives reconnect guidance', () => {
  const result = buildStreamActivationChecklist({
    brandId: 'brand-1',
    brandName: 'Agency Client',
    providers: [{ connected: true } as never],
    brand: { id: 'brand-1', name: 'Agency Client', voice: 'clear', tone: 'warm', values: ['trust'] } as never,
    onboardingStatus: { brand_profile_configured: true, live_campaign_present: true } as never,
    connections: [
      { platform: 'google_drive', status: 'needs_reauth' },
      { platform: 'facebook', status: 'connected' },
      { platform: 'gmail', status: 'connected' },
      { platform: 'google_calendar', status: 'connected' },
    ] as never,
    plugins: [],
    brandKitReady: true,
    driveRootName: null,
    driveLogoCount: 0,
  });

  assert.match(result.items.find(item => item.key === 'drive-connected')?.detail || '', /Reconnect Google Drive/);
});

test('capability prerequisites do not duplicate direct Google Drive blockers', () => {
  const result = buildStreamActivationChecklist({
    brandId: 'brand-1',
    brandName: 'Agency Client',
    providers: [{ connected: true } as never],
    brand: { id: 'brand-1', name: 'Agency Client', voice: 'clear', tone: 'warm', values: ['trust'] } as never,
    onboardingStatus: { brand_profile_configured: true, live_campaign_present: true } as never,
    connections: [
      { platform: 'facebook', status: 'connected' },
      { platform: 'gmail', status: 'connected' },
      { platform: 'google_calendar', status: 'connected' },
    ] as never,
    plugins: [{
      plugin_id: 'postcraft',
      name: 'Postcraft',
      status: 'installed',
      credentials_configured: false,
      missing_vars: [],
      requires_social_connection: ['google_drive'],
      activation_by_brand: [{ brand_id: 'brand-1', status: 'active' }],
    } as never],
    brandKitReady: true,
    driveRootName: null,
    driveLogoCount: 0,
  });

  assert.equal(result.items.find(item => item.key === 'drive-connected')?.ok, false);
  assert.equal(result.items.find(item => item.key === 'capability-prerequisites')?.ok, true);
});

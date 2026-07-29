const { chromium } = require('playwright');

const BASE = 'http://localhost:8090';
const API_KEY = 'bos_clicktest_20260726';

async function textContent(page, selector) {
  const el = page.locator(selector).first();
  await el.waitFor({ state: 'visible', timeout: 10000 });
  return (await el.textContent())?.trim() || '';
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
  const results = [];

  try {
    await page.addInitScript((key) => localStorage.setItem('bos_api_key', key), API_KEY);

    // 1) Brands page
    await page.goto(`${BASE}/admin/brands`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.admin-page-title');
    const brandsTitle = await textContent(page, '.admin-page-title');
    const brandsText = await page.locator('.admin-page').textContent();
    const hasFacebookInline = /Facebook\s+Klarohahq|YouTube\s+klarohahq@gmail\.com|Google Calendar\s+klarohahq@gmail\.com/s.test(brandsText || '');
    results.push({ step: 'brands-page', title: brandsTitle, hasFacebookInline });
    await page.screenshot({ path: '/home/ubu/bos/tmp/brands-page.png', fullPage: true });

    // 2) Go to Klaroha integrations from Brands
    const klarohaCard = page.locator('.admin-card').filter({ has: page.getByText('Klaroha', { exact: true }) }).first();
    await klarohaCard.getByRole('button', { name: 'Integrations' }).click();
    await page.waitForURL(/\/admin\/brands\/.+tab=integrations/);
    await page.waitForLoadState('networkidle');
    const integrationsText = await page.locator('.admin-page').textContent();
    const integrationsHasReturnText = (integrationsText || '').includes("After OAuth, you'll return here and stay on the Integrations tab.");
    const integrationsHasDrive = (integrationsText || '').includes('Google Drive');
    results.push({ step: 'brand-integrations', url: page.url(), integrationsHasReturnText, integrationsHasDrive });
    await page.screenshot({ path: '/home/ubu/bos/tmp/klaroha-integrations.png', fullPage: true });

    // 3) Client Readiness page
    await page.goto(`${BASE}/admin/client-readiness`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.admin-page-title');
    const readinessTitle = await textContent(page, '.admin-page-title');
    const row = page.locator('tbody tr').filter({ has: page.getByText('Klaroha', { exact: true }) }).first();
    const rowText = (await row.textContent()) || '';
    const nextActionButton = row.getByRole('button').last();
    const nextActionLabel = ((await nextActionButton.textContent()) || '').trim();
    await nextActionButton.click();
    await page.waitForLoadState('networkidle');
    results.push({ step: 'client-readiness', title: readinessTitle, rowText: rowText.replace(/\s+/g, ' ').trim(), nextActionLabel, nextUrl: page.url() });
    await page.screenshot({ path: '/home/ubu/bos/tmp/client-readiness-next.png', fullPage: true });

    // 4) Setup / Getting Started page
    await page.goto(`${BASE}/admin/getting-started`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.admin-page-title');
    const setupTitle = await textContent(page, '.admin-page-title');
    const setupText = await page.locator('.admin-page').textContent();
    const setupHasChecklist = /Brand readiness|AI provider|Brand Creative Brief approved|Google Drive connected/.test(setupText || '');
    results.push({ step: 'getting-started', title: setupTitle, setupHasChecklist });
    await page.screenshot({ path: '/home/ubu/bos/tmp/getting-started.png', fullPage: true });

    // 5) Objective loop page uses same checklist
    await page.goto(`${BASE}/admin/stream-setup`, { waitUntil: 'networkidle' });
    await page.waitForSelector('.admin-page-title');
    const loopTitle = await textContent(page, '.admin-page-title');
    const loopText = await page.locator('.admin-page').textContent();
    const loopHasChecklist = /Brand profile imported|Brand Creative Brief approved|Google Drive connected|At least one publish channel connected/.test(loopText || '');
    results.push({ step: 'objective-loop', title: loopTitle, loopHasChecklist });
    await page.screenshot({ path: '/home/ubu/bos/tmp/objective-loop.png', fullPage: true });

    console.log(JSON.stringify({ ok: true, results }, null, 2));
  } catch (error) {
    console.error(JSON.stringify({ ok: false, error: String(error), results }, null, 2));
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();

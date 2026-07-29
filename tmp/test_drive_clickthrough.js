const { chromium } = require('playwright');

const API_KEY = 'change-me-before-deploying';
const BRAND_ID = '10967e2e-bfd2-4687-a150-d01a9f0d6617';
const BRAND_NAME = 'Golden Gate Memorial';

async function testOnboarding() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await context.addInitScript(({ apiKey, returnTo }) => {
    localStorage.setItem('bos_api_key', apiKey);
    localStorage.setItem('bos_drive_return_to', returnTo);
  }, { apiKey: API_KEY, returnTo: `/admin/onboarding?brand_id=${BRAND_ID}&brand_name=${encodeURIComponent(BRAND_NAME)}` });
  const page = await context.newPage();
  await page.goto(`http://localhost:8090/admin/brands?google_drive=connected&brand_id=${BRAND_ID}&brand_name=${encodeURIComponent(BRAND_NAME)}`, { waitUntil: 'networkidle' });
  await page.waitForURL(new RegExp(`/admin/onboarding.*brand_id=${BRAND_ID}`), { timeout: 10000 });
  await page.waitForSelector('text=Choose Brand Kit folder', { timeout: 10000 });
  console.log(JSON.stringify({ test: 'onboarding', ok: true, url: page.url() }));
  await browser.close();
}

async function testBrandDetail() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await context.addInitScript(({ apiKey, returnTo }) => {
    localStorage.setItem('bos_api_key', apiKey);
    sessionStorage.setItem('bos_connect_return', returnTo);
  }, { apiKey: API_KEY, returnTo: `/admin/brands/${BRAND_ID}?tab=integrations` });
  const page = await context.newPage();
  await page.goto(`http://localhost:8090/admin/brands?google_drive=connected&brand_id=${BRAND_ID}&account=tester`, { waitUntil: 'networkidle' });
  await page.waitForURL(new RegExp(`/admin/brands/${BRAND_ID}\?tab=integrations`), { timeout: 10000 });
  const body = await page.textContent('body');
  console.log(JSON.stringify({ test: 'brand_detail', ok: /connected/i.test(body || ''), url: page.url() }));
  await browser.close();
}

(async () => {
  await testOnboarding();
  await testBrandDetail();
})();

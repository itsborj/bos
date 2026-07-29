const { chromium } = require('playwright');
const API_KEY='change-me-before-deploying';
const BRAND_ID='10967e2e-bfd2-4687-a150-d01a9f0d6617';
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext();
 await context.addInitScript(({apiKey,returnTo})=>{
  localStorage.setItem('bos_api_key',apiKey);
  sessionStorage.setItem('bos_connect_return',returnTo);
 },{apiKey:API_KEY,returnTo:`/admin/brands/${BRAND_ID}?tab=integrations`});
 const page=await context.newPage();
 page.on('console', msg => console.log('BROWSER:', msg.type(), msg.text()));
 await page.goto(`http://localhost:8090/admin/brands?google_drive=connected&brand_id=${BRAND_ID}&account=tester`);
 await page.waitForTimeout(5000);
 console.log('URL', page.url());
 console.log('BODY', (await page.textContent('body')).slice(0,1200));
 await page.screenshot({path:'tmp/debug_branddetail.png', fullPage:true});
 await browser.close();
})();

import { chromium } from 'playwright';
import fs from 'fs/promises';
import path from 'path';

const BASE = process.env.FRONTEND_URL || 'http://localhost:8090';
const API_KEY = process.env.BOS_UI_SCAN_KEY || 'change-me-before-deploying';
const OUT = path.resolve(process.env.OUT_DIR || 'web/dist');
const PAGES_DIR = path.join(OUT, 'ui-frontend-pages');

await fs.rm(PAGES_DIR, { recursive: true, force: true });
await fs.mkdir(PAGES_DIR, { recursive: true });

async function fetchText(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.text();
}

async function getAppCss() {
  const html = await fetchText(`${BASE}/`);
  const hrefs = [...html.matchAll(/<link[^>]+rel=["']stylesheet["'][^>]+href=["']([^"']+)["']/g)].map(m => m[1]);
  const css = [];
  for (const href of hrefs) {
    if (href.startsWith('http')) continue;
    css.push(`/* ${href} */\n` + await fetchText(`${BASE}${href}`));
  }
  return css.join('\n\n');
}

async function getFirstBrand() {
  try {
    const res = await fetch(`${BASE}/api/brands`, { headers: { 'X-API-Key': API_KEY } });
    if (!res.ok) return null;
    const json = await res.json();
    return json?.brands?.[0] || null;
  } catch {
    return null;
  }
}

async function getBrandKit(brandId) {
  if (!brandId) return null;
  try {
    const url = `${BASE}/api/onboarding/brand-kit/latest?status=approved&brand_id=${encodeURIComponent(brandId)}`;
    const res = await fetch(url, { headers: { 'X-API-Key': API_KEY } });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function pageHtml({ title, route, body, css, capturedAt }) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${escapeHtml(title)} · static BOS prototype</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&family=Inter:opsz,wght@14..32,300;14..32,400;14..32,500;14..32,600;14..32,700&display=swap" rel="stylesheet">
<style>${css}</style>
<style>
  html, body { min-height: 100%; }
  body { margin: 0; background: #f8f7f5; }
  .static-proto-watermark { position: fixed; right: 10px; top: 10px; z-index: 999999; font: 10px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .04em; text-transform: uppercase; color: rgba(11,61,46,.58); background: rgba(245,241,232,.92); border: 1px solid rgba(11,61,46,.16); padding: 5px 7px; pointer-events: none; }
  .static-proto-click-shield a[href^="/"] { cursor: default; }
</style>
</head>
<body class="static-proto-click-shield">
<div class="static-proto-watermark">Static prototype · ${escapeHtml(route)}</div>
${body}
<script>
  document.addEventListener('click', function(e) {
    var a = e.target.closest && e.target.closest('a[href^="/"]');
    if (!a) return;
    e.preventDefault();
    try { parent.postMessage({ type: 'bos-prototype-route', route: a.getAttribute('href') }, '*'); } catch (_) {}
  }, true);
</script>
</body>
</html>`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function safeName(route, name) {
  if (name) return name;
  return route.replace(/^\//, '').replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '') || 'root';
}

const css = await getAppCss();
const brand = await getFirstBrand();
const brandId = brand?.id || null;
const brandKit = await getBrandKit(brandId);

const routes = [
  { title: 'Brand Guidelines', route: '/brand-guidelines', name: 'brand-guidelines', auth: false, group: 'Reference', static: true },
  { title: 'Auth', route: '/auth', name: 'auth', auth: false, group: 'Entry' },
  { title: 'Stream', route: '/stream', name: 'stream', auth: true, group: 'Core' },
  { title: 'CMO', route: '/cmo', name: 'cmo', auth: true, group: 'Core' },
  { title: 'Workspace', route: '/workspace', name: 'workspace', auth: true, group: 'Core' },
  { title: 'Command Centre', route: '/admin/overview', name: 'admin-overview', auth: true, group: 'Admin' },
  { title: 'Brands / Clients', route: '/admin/brands', name: 'admin-brands', auth: true, group: 'Admin' },
  ...(brandId ? [{ title: 'Brand Detail', route: `/admin/brands/${brandId}`, name: 'admin-brand-detail', auth: true, group: 'Admin' }] : []),
  { title: 'Setup & Readiness', route: '/admin/setup', name: 'admin-setup', auth: true, group: 'Admin' },
  { title: 'Onboarding', route: '/admin/onboarding', name: 'admin-onboarding', auth: true, group: 'Admin' },
  { title: 'Approvals', route: '/admin/agent-activity', name: 'admin-agent-activity', auth: true, group: 'Admin' },
  { title: 'Campaign Board', route: '/admin/campaigns', name: 'admin-campaigns', auth: true, group: 'Admin' },
  { title: 'Capabilities', route: '/admin/modules', name: 'admin-modules', auth: true, group: 'Admin' },
  { title: 'AI Providers', route: '/admin/providers', name: 'admin-providers', auth: true, group: 'Admin' },
  { title: 'Billing', route: '/admin/billing', name: 'admin-billing', auth: true, group: 'Admin' },
  { title: 'Run Logs', route: '/admin/runs', name: 'admin-runs', auth: true, group: 'Admin' },
  { title: 'Booking Pages', route: '/admin/calendar', name: 'admin-calendar', auth: true, group: 'Admin' },
  { title: 'Loop Setup', route: '/admin/objective-loop', name: 'admin-objective-loop', auth: true, group: 'Admin' },
  { title: 'Loop Flow', route: '/admin/loop-flow', name: 'admin-loop-flow', auth: true, group: 'Admin' },
  { title: 'Watchpoints', route: '/admin/watchpoints', name: 'admin-watchpoints', auth: true, group: 'Admin' },
  { title: 'Memory & Audit', route: '/admin/memory-audit', name: 'admin-memory-audit', auth: true, group: 'Admin' },
];

function extractSection(markdown, heading) {
  if (!markdown) return '';
  const re = new RegExp(`## \\d+\\. ${heading}[^\\n]*\\n([\\s\\S]*?)(?=\\n## \\d+\\.|\\n## Optional|$)`, 'i');
  return markdown.match(re)?.[1]?.trim() || '';
}

function extractTableRows(section) {
  return section
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.startsWith('|') && !line.includes('---'))
    .slice(1)
    .map(line => line.split('|').slice(1, -1).map(cell => cell.trim().replaceAll('`', '')));
}

function miniMarkdown(value) {
  return escapeHtml(value || '')
    .replace(/^\s*-\s+/gm, '• ')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

function brandGuidelinesBody() {
  const md = brandKit?.content_markdown || '';
  const colors = extractTableRows(extractSection(md, 'Color Palette'));
  const typeRows = extractTableRows(extractSection(md, 'Typography Basics'));
  const componentRows = extractTableRows(extractSection(md, 'Campaign Components')).slice(0, 8);
  const voice = extractSection(md, 'Tone of Voice');
  const overview = extractTableRows(extractSection(md, 'Campaign Brand Kit Overview'));
  const brandName = brand?.name || 'Klaroha';
  return `<main class="brand-kit-page">
    <section class="brand-hero">
      <div class="eyebrow">Database source · approved campaign brand kit</div>
      <h1>${escapeHtml(brandKit?.title || `${brandName} — Campaign Brand Kit`)}</h1>
      <p>${escapeHtml(brand?.voice || 'clear and practical')} · ${escapeHtml(brand?.tone || 'authoritative')} · values: ${(brand?.values || ['clarity','precision','results']).map(escapeHtml).join(', ')}</p>
      <div class="source-row"><span>Brand id <code>${escapeHtml(brandId || 'n/a')}</code></span><span>Status <code>${escapeHtml(brandKit?.status || 'unavailable')}</code></span><span>Approved <code>${escapeHtml(brandKit?.approved_at || 'n/a')}</code></span></div>
    </section>
    <section class="spec-grid">
      <article class="spec-card wide"><h2>Product promise</h2><div class="kv-grid">${overview.map(([k,v]) => `<div><b>${escapeHtml(k)}</b><span>${escapeHtml(v)}</span></div>`).join('')}</div></article>
      <article class="spec-card wide"><h2>Color palette from DB</h2><div class="swatches">${colors.map(([token, hex, usage]) => `<div class="swatch"><i style="background:${escapeHtml(hex)}"></i><b>${escapeHtml(token)}</b><code>${escapeHtml(hex)}</code><span>${escapeHtml(usage)}</span></div>`).join('')}</div></article>
      <article class="spec-card"><h2>Typography</h2>${typeRows.map(([token, rec, usage]) => `<p><b>${escapeHtml(token)}</b><br><code>${escapeHtml(rec)}</code><br><span>${escapeHtml(usage)}</span></p>`).join('')}</article>
      <article class="spec-card"><h2>Voice & CTA rules</h2><p>${miniMarkdown(voice).slice(0, 2200)}</p></article>
      <article class="spec-card wide"><h2>Campaign components</h2><table>${componentRows.map(([token, purpose, rules, examples]) => `<tr><td><code>${escapeHtml(token)}</code></td><td>${escapeHtml(purpose)}</td><td>${escapeHtml(rules)}</td><td>${escapeHtml(examples)}</td></tr>`).join('')}</table></article>
      <article class="spec-card wide"><h2>Product UI reference note</h2><p>This prototype intentionally keeps the current product shell seen at <code>http://localhost:3000/ui-current.html</code>: racing green <code>#0B3D2E</code>, warm gold <code>#826D40</code>, ivory surfaces, Manrope + Inter, and 2px rectangular controls. The DB campaign kit above is preserved as the content/marketing source of truth; the product UI tokens remain the active app shell until those systems are explicitly reconciled.</p></article>
    </section>
  </main>`;
}

const brandKitCss = `
.brand-kit-page{min-height:100vh;background:#F8F7F5;color:#0B3D2E;font-family:Inter,system-ui,sans-serif;padding:42px 48px 64px}.brand-hero{background:#0A2820;color:#F5F1E8;border:1px solid rgba(216,190,138,.28);padding:34px 36px;margin:0 auto 18px;max-width:1180px}.brand-hero .eyebrow{font-size:11px;font-weight:900;letter-spacing:.16em;text-transform:uppercase;color:#D8BE8A}.brand-hero h1{font-family:Manrope,system-ui,sans-serif;font-size:42px;letter-spacing:-.045em;margin:10px 0 8px}.brand-hero p{color:rgba(245,241,232,.82);margin:0}.source-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}.source-row span{font-size:11px;border:1px solid rgba(216,190,138,.28);padding:6px 8px}.spec-grid{max-width:1180px;margin:0 auto;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.spec-card{background:#fff;border:1px solid rgba(11,61,46,.15);padding:20px}.spec-card.wide{grid-column:1/-1}.spec-card h2{font-family:Manrope,system-ui,sans-serif;font-size:20px;margin:0 0 14px;letter-spacing:-.02em}.kv-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.kv-grid div{border-top:1px solid rgba(11,61,46,.12);padding-top:9px}.kv-grid b{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:#826D40}.kv-grid span{font-size:14px}.swatches{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.swatch{border:1px solid rgba(11,61,46,.12);padding:10px;min-height:130px}.swatch i{display:block;height:34px;border:1px solid rgba(0,0,0,.08);margin-bottom:9px}.swatch b,.swatch code,.swatch span{display:block}.swatch b{font-size:12px}.swatch code{font-size:11px;color:#826D40;margin:2px 0 5px}.swatch span,.spec-card p{font-size:13px;color:#2C4A3E;line-height:1.55}.spec-card table{width:100%;border-collapse:collapse;font-size:12px}.spec-card td{border-top:1px solid rgba(11,61,46,.12);padding:9px;vertical-align:top}@media(max-width:900px){.brand-kit-page{padding:18px}.spec-grid,.kv-grid,.swatches{grid-template-columns:1fr}.spec-card.wide{grid-column:auto}}
`;

const browser = await chromium.launch({ headless: true });
const results = [];

for (const r of routes) {
  if (r.static && r.name === 'brand-guidelines') {
    const file = `${r.name}.html`;
    await fs.writeFile(path.join(PAGES_DIR, file), pageHtml({ title: r.title, route: r.route, body: brandGuidelinesBody(), css: `${css}\n${brandKitCss}` }));
    results.push({ ...r, file: `ui-frontend-pages/${file}`, status: 200, failed: [] });
    console.log(`wrote ${file} from DB brand guidelines`);
    continue;
  }
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const failed = [];
  page.on('response', res => { if (res.status() >= 400) failed.push(`${res.status()} ${res.url()}`); });
  page.on('pageerror', err => failed.push(`pageerror ${err.message}`));
  if (r.auth) {
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.evaluate((key) => localStorage.setItem('bos_api_key', key), API_KEY);
  }
  const url = `${BASE}${r.route}`;
  const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 }).catch(e => {
    failed.push(`goto ${e.message}`);
    return null;
  });
  await page.waitForTimeout(900);
  await page.evaluate(() => {
    document.querySelectorAll('video').forEach((video) => {
      const src = video.currentSrc || video.getAttribute('src') || video.querySelector('source')?.getAttribute('src') || '';
      const box = document.createElement('div');
      box.className = 'static-video-placeholder';
      box.textContent = src ? `Video artifact placeholder · ${src.split('/').pop()}` : 'Video artifact placeholder';
      box.setAttribute('style', video.getAttribute('style') || '');
      box.style.minHeight = box.style.minHeight || '180px';
      box.style.display = 'flex';
      box.style.alignItems = 'center';
      box.style.justifyContent = 'center';
      box.style.background = '#eef0f1';
      box.style.color = '#9aa3aa';
      box.style.fontSize = '13px';
      box.style.border = '1px solid #d7dde0';
      video.replaceWith(box);
    });
    document.querySelectorAll('audio, source').forEach((el) => el.removeAttribute('src'));
  });
  const body = await page.evaluate(() => document.body.innerHTML);
  const file = `${safeName(r.route, r.name)}.html`;
  await fs.writeFile(path.join(PAGES_DIR, file), pageHtml({ title: r.title, route: r.route, body, css, capturedAt: new Date().toISOString() }));
  results.push({ ...r, file: `ui-frontend-pages/${file}`, status: response?.status?.() ?? null, failed: [...new Set(failed)] });
  await context.close();
  console.log(`wrote ${file} from ${r.route}`);
}

await browser.close();
await fs.writeFile(path.join(PAGES_DIR, 'manifest.json'), JSON.stringify({ base: BASE, generated_at: new Date().toISOString(), routes: results }, null, 2));

const byGroup = results.reduce((acc, r) => { (acc[r.group] ||= []).push(r); return acc; }, {});
const navHtml = Object.entries(byGroup).map(([group, items]) => `
  <section class="nav-section"><div class="nav-label">${escapeHtml(group)}</div>
  ${items.map((r, idx) => `<button class="nav-item${r.name === 'stream' ? ' active' : ''}" data-file="${escapeHtml(r.file)}" data-route="${escapeHtml(r.route)}"><span>${escapeHtml(r.title)}</span><code>${escapeHtml(r.route)}</code></button>`).join('\n')}
  </section>`).join('\n');

const index = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>BOS UI Frontend Static Prototype</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600;14..32,700&display=swap" rel="stylesheet">
<style>
:root{--green:#0B3D2E;--green2:#0A2820;--gold:#826D40;--ivory:#F5F1E8;--line:rgba(11,61,46,.16);--muted:#4A6B5C;--bg:#f8f7f5;--font:'Inter',system-ui,sans-serif;--display:'Manrope',system-ui,sans-serif}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--green);font-family:var(--font);height:100vh;overflow:hidden}.shell{display:grid;grid-template-columns:310px minmax(0,1fr);height:100vh}.side{background:#fff;border-right:1px solid var(--line);display:flex;flex-direction:column;min-height:0}.brand{padding:22px 20px 18px;border-bottom:1px solid var(--line)}.kicker{font-size:10px;font-weight:900;letter-spacing:.18em;text-transform:uppercase;color:var(--gold)}h1{font-family:var(--display);font-size:25px;letter-spacing:-.04em;line-height:1.05;margin:8px 0 8px}.sub{font-size:12px;line-height:1.45;color:var(--muted);margin:0}.nav{padding:12px;overflow:auto}.nav-section{margin-bottom:16px}.nav-label{font-size:10px;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);padding:8px 8px}.nav-item{display:block;width:100%;text-align:left;border:1px solid transparent;background:transparent;color:var(--green);padding:10px 9px;border-radius:2px;cursor:pointer;font:inherit;margin-bottom:3px}.nav-item:hover{background:rgba(11,61,46,.04)}.nav-item.active{background:#C8E8D8;border-color:#8ABDA5}.nav-item span{display:block;font-size:13px;font-weight:800}.nav-item code{display:block;font-size:10px;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.main{display:flex;flex-direction:column;min-width:0}.top{height:44px;background:#fff;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px;padding:0 14px}.route{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:var(--muted)}.open{margin-left:auto;color:var(--green);font-size:12px;text-decoration:none;border:1px solid var(--line);padding:5px 9px;background:#fff;border-radius:2px}.frame-wrap{flex:1;min-height:0;padding:18px;background:#dfe3df}.frame{width:100%;height:100%;border:1px solid var(--line);background:#fff;box-shadow:0 14px 46px rgba(8,11,13,.10)}.meta{padding:12px 20px;border-top:1px solid var(--line);font-size:11px;color:var(--muted)}@media(max-width:900px){body{overflow:auto}.shell{display:block;height:auto}.side{height:auto}.main{height:80vh}.frame-wrap{padding:8px}}
</style>
</head>
<body>
<div class="shell">
  <aside class="side"><div class="brand"><div class="kicker">Static HTML prototype</div><h1>BOS current frontend</h1><p class="sub">Frozen DOM snapshots converted from the live React app at <b>${escapeHtml(BASE)}</b>. Visual grammar checked against <code>localhost:3000/ui-current.html</code>; brand content comes from the approved Klaroha kit in the database.</p></div><nav class="nav">${navHtml}</nav><div class="meta">Generated from live pages. Source route map: <code>web/src/App.tsx</code>. Brand kit: <code>${escapeHtml(brandKit?.id || 'unavailable')}</code>.</div></aside>
  <main class="main"><div class="top"><strong id="title">Stream</strong><span class="route" id="route">/stream</span><a class="open" id="open" href="ui-frontend-pages/stream.html" target="_blank">Open page ↗</a></div><div class="frame-wrap"><iframe class="frame" id="frame" src="ui-frontend-pages/stream.html"></iframe></div></main>
</div>
<script>
const buttons=[...document.querySelectorAll('.nav-item')];
const frame=document.getElementById('frame'); const routeEl=document.getElementById('route'); const titleEl=document.getElementById('title'); const openEl=document.getElementById('open');
function select(btn){buttons.forEach(b=>b.classList.remove('active')); btn.classList.add('active'); frame.src=btn.dataset.file; routeEl.textContent=btn.dataset.route; titleEl.textContent=btn.querySelector('span').textContent; openEl.href=btn.dataset.file;}
buttons.forEach(btn=>btn.addEventListener('click',()=>select(btn)));
window.addEventListener('message', e => { if(!e.data || e.data.type !== 'bos-prototype-route') return; const btn = buttons.find(b => b.dataset.route === e.data.route || e.data.route.startsWith(b.dataset.route + '/')); if(btn) select(btn); });
</script>
</body>
</html>`;

await fs.writeFile(path.join(OUT, 'ui-frontend.html'), index);

// Keep a versionable source copy outside web/dist/ (dist is ignored and can be
// overwritten by Docker/Vite builds). The live copy is still written to dist so
// it can be served immediately by the nginx frontend container.
const SOURCE_OUT = path.resolve(process.env.SOURCE_OUT || 'web/ui-frontend-static');
if (process.env.SOURCE_COPY !== '0' && SOURCE_OUT !== OUT) {
  await fs.rm(SOURCE_OUT, { recursive: true, force: true });
  await fs.mkdir(SOURCE_OUT, { recursive: true });
  await fs.copyFile(path.join(OUT, 'ui-frontend.html'), path.join(SOURCE_OUT, 'ui-frontend.html'));
  await fs.cp(PAGES_DIR, path.join(SOURCE_OUT, 'ui-frontend-pages'), { recursive: true });
}

console.log(`\nWrote ${path.join(OUT, 'ui-frontend.html')} and ${results.length} static pages in ${PAGES_DIR}`);
if (process.env.SOURCE_COPY !== '0') console.log(`Source copy: ${SOURCE_OUT}`);

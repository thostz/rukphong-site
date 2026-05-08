// ─────────────────────────────────────────────────────────────
//  Rukphong Dashboard — GitHub Pages Config
//  Update GS_URL after deploying your Google Apps Script
// ─────────────────────────────────────────────────────────────

const GS_URL = 'YOUR_APPS_SCRIPT_URL_HERE';

// ── API Helpers ───────────────────────────────────────────────

async function gsGet(action, params = {}) {
  if (!GS_URL || GS_URL.includes('YOUR_APPS')) {
    console.warn('GS_URL not configured in docs/config.js');
    return { ok: false, data: [] };
  }
  try {
    const url = new URL(GS_URL);
    url.searchParams.set('action', action);
    Object.entries(params).forEach(([k, v]) => { if (v) url.searchParams.set(k, v); });
    const r = await fetch(url.toString(), { redirect: 'follow' });
    return await r.json();
  } catch (e) {
    console.error('gsGet error:', e);
    return { ok: false, data: [] };
  }
}

async function gsPost(action, record) {
  if (!GS_URL || GS_URL.includes('YOUR_APPS')) return { ok: false };
  try {
    const r = await fetch(GS_URL, {
      method: 'POST',
      // text/plain avoids CORS preflight — Apps Script still receives JSON
      body: JSON.stringify({ action, record }),
      redirect: 'follow',
    });
    return await r.json();
  } catch (e) {
    console.error('gsPost error:', e);
    return { ok: false };
  }
}

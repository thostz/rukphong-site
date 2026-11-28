/**
 * Rukphong LINE Webhook Proxy — Cloudflare Worker
 *
 * 1. ตอบ LINE ด้วย 200 OK ทันที (ไม่มี cold start)
 * 2. Forward body ไป Apps Script ใน background
 *
 * Environment Variables (Settings → Variables):
 *   GS_URL  = https://script.google.com/macros/s/.../exec
 */

export default {
  async fetch(request, env, ctx) {

    // ── CORS preflight ──────────────────────────────────────────
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        },
      });
    }

    // ── GET: health check ───────────────────────────────────────
    if (request.method === 'GET') {
      return new Response(JSON.stringify({ ok: true, service: 'LINE proxy' }), {
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // ── POST: LINE webhook ──────────────────────────────────────
    if (request.method === 'POST') {
      const body = await request.text();

      // Forward to Apps Script in background (non-blocking)
      const gsUrl = env.GS_URL;
      if (gsUrl) {
        const forward = fetch(gsUrl, {
          method: 'POST',
          body,
          headers: { 'Content-Type': 'text/plain' },
          redirect: 'follow',
        }).catch(() => {});  // ignore errors — LINE already got 200

        // ctx.waitUntil ให้ Worker ทำงานต่อจนส่งต่อเสร็จ แม้ตอบ LINE ไปแล้ว
        // (ถ้าไม่ใช้ การส่งต่ออาจถูกตัดทิ้งหลังตอบ ทำให้ข้อความบางข้อความไม่ถึง Apps Script)
        ctx.waitUntil(forward);
      }

      // Return 200 immediately — before Apps Script responds
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return new Response('Method not allowed', { status: 405 });
  },
};

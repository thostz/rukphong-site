# rukphong-site

แดชบอร์ดส่วนตัว: รายจ่าย งาน โน้ต การลงทุน + LINE Bot

```
LINE ──► Cloudflare Worker (cloudflare-worker/worker.js) ──► Google Apps Script (google-apps-script/Code.gs) ──► Google Sheet
                                                                        ▲
เว็บ / PWA (docs/, GitHub Pages) ─────────────────────────────────────┘
```

- **เว็บ:** https://thostz.github.io/rukphong-site/ (ไฟล์ใน `docs/`)
- **Backend:** `google-apps-script/Code.gs` — วางใน Apps Script แล้ว Deploy เป็น Web app (Execute as: Me, Who has access: Anyone)
  - Script Properties: `SPREADSHEET_ID`, `LINE_TOKEN`, `GEMINI_API_KEY`
  - แก้โค้ดแล้วต้อง Deploy → Manage deployments → Edit → **New version** (URL เดิมไม่เปลี่ยน)
- **URL ของ Apps Script:** ตั้งใน `docs/config.js` (`GS_URL`)
- **LINE:** Webhook URL ชี้ไปที่ Cloudflare Worker (ตั้ง `GS_URL` ใน Worker) หรือชี้ตรงไป Apps Script
- **เมนู LINE (ไม่บังคับ):** `python setup_rich_menu.py` (ดู `.env.example`)

# LINE Bot + Google Sheets — คู่มือ Setup

## สิ่งที่ต้องเตรียม
- Python 3.11+
- บัญชี LINE Developers
- บัญชี Google (สำหรับ Sheets + Service Account)
- URL สาธารณะแบบ HTTPS (ใช้ ngrok ในช่วง development ได้)

---

## ขั้นตอนที่ 1 — ติดตั้ง Python dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## ขั้นตอนที่ 2 — สร้าง LINE Bot

1. ไปที่ [LINE Developers Console](https://developers.line.biz/console/)
2. สร้าง **Provider** ใหม่ (ถ้ายังไม่มี)
3. สร้าง **Channel** ประเภท **Messaging API**
4. ใน tab **Basic settings** → คัดลอก **Channel secret**
5. ใน tab **Messaging API** → สร้าง **Channel access token (long-lived)** แล้วคัดลอก
6. ตั้งค่า Webhook URL เป็น `https://[your-domain]/webhook`
7. เปิด **Use webhook** และปิด **Auto-reply messages**

---

## ขั้นตอนที่ 3 — สร้าง Google Service Account

1. ไปที่ [Google Cloud Console](https://console.cloud.google.com/)
2. สร้าง Project ใหม่ (หรือใช้ project เดิม)
3. เปิด **Google Sheets API**:
   - ไปที่ APIs & Services → Library → ค้นหา "Google Sheets API" → Enable
4. สร้าง Service Account:
   - IAM & Admin → Service Accounts → Create Service Account
   - ตั้งชื่อ เช่น `linebot-sheets`
   - ข้ามส่วน Role และ User access
5. คลิก Service Account ที่สร้าง → tab **Keys** → Add Key → JSON
6. บันทึกไฟล์ JSON ที่ดาวน์โหลดมาเป็น `credentials.json` ในโฟลเดอร์นี้

---

## ขั้นตอนที่ 4 — สร้างและแชร์ Google Sheet

1. สร้าง Google Sheet ใหม่ที่ [sheets.google.com](https://sheets.google.com)
2. คัดลอก **Spreadsheet ID** จาก URL:
   ```
   https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit
   ```
3. คลิก **Share** → ใส่ email ของ Service Account (ดูใน credentials.json ช่อง `client_email`) → ให้สิทธิ์ **Editor**

---

## ขั้นตอนที่ 5 — ตั้งค่า Environment Variables

```bash
cp .env.example .env
```

เปิดไฟล์ `.env` แล้วใส่ค่า:
```
LINE_CHANNEL_SECRET=xxxx
LINE_CHANNEL_ACCESS_TOKEN=xxxx
SPREADSHEET_ID=xxxx
```

---

## ขั้นตอนที่ 6 — รัน Server (Local + ngrok)

**Terminal 1 — รัน Bot:**
```bash
python app.py
```

**Terminal 2 — เปิด ngrok:**
```bash
# ติดตั้ง ngrok ก่อน: https://ngrok.com/download
ngrok http 5000
```

คัดลอก HTTPS URL จาก ngrok เช่น `https://xxxx.ngrok-free.app`
แล้วใส่ใน LINE Console เป็น Webhook URL:
```
https://xxxx.ngrok-free.app/webhook
```

---

## วิธีใช้ Bot

| พิมพ์ | ผลลัพธ์ |
|-------|---------|
| `จ่าย` | เริ่มบันทึกรายจ่าย (ถามทีละขั้น) |
| `จ่าย 150` | เริ่มบันทึกรายจ่าย 150 บาท |
| `150` | เริ่มบันทึกรายจ่าย 150 บาท (ตัวเลขเปล่า) |
| `งาน` | เริ่มบันทึกงาน |
| `งาน เขียน report` | บันทึกงานชื่อ "เขียน report" |
| `รายจ่ายล่าสุด` | ดูรายจ่าย 5 รายการล่าสุด |
| `งานล่าสุด` | ดูงาน 5 รายการล่าสุด |
| `สรุปรายจ่าย` | ดูยอดรวมแยกหมวดหมู่ |
| `ยกเลิก` | ยกเลิกการกรอกข้อมูล |
| `ช่วยเหลือ` | แสดงเมนูทั้งหมด |

---

## Deploy บน Cloud (ตัวเลือก)

### Render.com (ฟรี)
1. Push โค้ดขึ้น GitHub
2. สร้าง Web Service ใหม่บน [render.com](https://render.com)
3. Start command: `gunicorn app:app`
4. ใส่ Environment Variables ใน Render dashboard
5. อัปโหลด `credentials.json` เป็น Secret File

### Railway.app (ฟรี $5/เดือน)
1. เชื่อม GitHub repo
2. ใส่ Environment Variables
3. Deploy อัตโนมัติ

---

## โครงสร้างไฟล์

```
Line/
├── app.py                    # Flask webhook server
├── handlers/
│   ├── conversation.py       # State machine สำหรับ multi-step chat
│   └── message_handler.py    # Route คำสั่ง → handler
├── services/
│   └── sheets_service.py     # Google Sheets API
├── credentials.json          # Google Service Account key (ไม่ commit!)
├── .env                      # Environment variables (ไม่ commit!)
├── requirements.txt
└── SETUP.md
```

---

## โครงสร้าง Google Sheet

**Sheet "รายจ่าย"**
| วันที่ | จำนวนเงิน (บาท) | หมวดหมู่ | หมายเหตุ | บันทึกโดย |
|--------|----------------|---------|---------|---------|

**Sheet "งาน"**
| วันที่ | งาน/Task | สถานะ | หมายเหตุ | บันทึกโดย |
|--------|---------|-------|---------|---------|

ข้อมูลจะถูกสร้าง Sheet อัตโนมัติเมื่อบันทึกครั้งแรก

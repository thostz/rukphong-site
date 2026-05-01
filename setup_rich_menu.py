"""
สร้าง Rich Menu ภาพด้านล่าง LINE Chat
รัน:  python setup_rich_menu.py
"""
import os
import json
import glob
import requests
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
HEADERS_JSON = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# ── ขนาดภาพ Rich Menu (2 แถว 3 คอลัมน์) ─────────────────────────────────────
W, H = 2500, 843
COLS, ROWS = 3, 2
CW, CH = W // COLS, H // ROWS  # 833 x 421

ITEMS = [
    {"emoji": "💰", "label": "บันทึกรายจ่าย", "text": "จ่าย",           "bg": "#1A9B9F", "fg": "#FFFFFF"},
    {"emoji": "📋", "label": "บันทึกงาน",     "text": "งาน",            "bg": "#4A7ADB", "fg": "#FFFFFF"},
    {"emoji": "🕐", "label": "รายจ่ายล่าสุด", "text": "รายจ่ายล่าสุด", "bg": "#E07B54", "fg": "#FFFFFF"},
    {"emoji": "🕐", "label": "งานล่าสุด",     "text": "งานล่าสุด",     "bg": "#6B5EA8", "fg": "#FFFFFF"},
    {"emoji": "📊", "label": "สรุปรายจ่าย",   "text": "สรุปรายจ่าย",  "bg": "#C0392B", "fg": "#FFFFFF"},
    {"emoji": "❓", "label": "ช่วยเหลือ",     "text": "ช่วยเหลือ",    "bg": "#555555", "fg": "#FFFFFF"},
]

ICON_MAP = {
    "บันทึกรายจ่าย": "💰",
    "บันทึกงาน":     "📋",
    "รายจ่ายล่าสุด": "📂",
    "งานล่าสุด":     "📂",
    "สรุปรายจ่าย":   "📊",
    "ช่วยเหลือ":     "❓",
}


def find_thai_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/THSarabunNew.ttf",
        "C:/Windows/Fonts/thsarabunnew.ttf",
        "C:/Windows/Fonts/Tahoma.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_icon(draw: ImageDraw.Draw, kind: str, cx: int, cy: int, size: int, color: str):
    """วาดไอคอนแต่ละแบบด้วย PIL shapes"""
    s = size // 2
    w = max(8, size // 12)

    if kind == "money":
        # เหรียญ: วงกลมพร้อมตัว ฿
        draw.ellipse([cx - s, cy - s, cx + s, cy + s], outline=color, width=w)
        draw.ellipse([cx - s + w*2, cy - s + w*2, cx + s - w*2, cy + s - w*2], outline=color, width=w//2)

    elif kind == "task":
        # คลิปบอร์ด: สี่เหลี่ยมมีเส้น
        pad = size // 5
        draw.rectangle([cx - s + pad, cy - s, cx + s - pad, cy + s], outline=color, width=w)
        for ly in [cy - s//2, cy, cy + s//2]:
            draw.line([cx - s//2, ly, cx + s//2, ly], fill=color, width=w//2)

    elif kind == "list_expense":
        # รายการ: 3 เส้นแนวนอน + จุด
        for j, ly in enumerate([cy - s//2, cy, cy + s//2]):
            draw.ellipse([cx - s + 10, ly - w, cx - s + 10 + w*2, ly + w], fill=color)
            draw.line([cx - s//2 + 10, ly, cx + s, ly], fill=color, width=w//2)

    elif kind == "list_work":
        # งาน: checkmark list
        for j, ly in enumerate([cy - s//2, cy, cy + s//2]):
            bx = cx - s + 10
            draw.rectangle([bx, ly - w*2, bx + w*3, ly + w*2], outline=color, width=max(4, w//2))
            if j == 0:  # เฉพาะตัวแรก check
                draw.line([bx, ly, bx + w, ly + w*2, bx + w*3, ly - w], fill=color, width=max(4, w//2))
            draw.line([cx - s//2 + 20, ly, cx + s, ly], fill=color, width=w//2)

    elif kind == "chart":
        # แท่งกราฟ
        bar_w = size // 5
        heights = [s // 2, s, s * 3 // 4]
        for j, bh in enumerate(heights):
            bx = cx - s + j * (bar_w + size // 8) + size // 10
            draw.rectangle([bx, cy + s - bh, bx + bar_w, cy + s], fill=color)
        draw.line([cx - s, cy + s, cx + s, cy + s], fill=color, width=w)

    elif kind == "help":
        # วงกลม + เครื่องหมาย ?
        draw.ellipse([cx - s, cy - s, cx + s, cy + s], outline=color, width=w)
        # ก้าน ?
        draw.arc([cx - s//2, cy - s//2 + w, cx + s//2, cy + w], start=220, end=350, fill=color, width=w)
        draw.arc([cx - s//2, cy - s//2, cx + s//2, cy], start=200, end=360, fill=color, width=w)
        draw.line([cx, cy + w, cx, cy + s//2], fill=color, width=w)
        draw.ellipse([cx - w, cy + s//2 + w, cx + w, cy + s//2 + w*3], fill=color)


ICON_KINDS = ["money", "task", "list_expense", "list_work", "chart", "help"]


def make_image(out_path: str = "rich_menu.png"):
    img = Image.new("RGB", (W, H), "#EEEEEE")
    draw = ImageDraw.Draw(img)

    font_label = find_thai_font(76)
    font_small = find_thai_font(52)

    for i, item in enumerate(ITEMS):
        col = i % COLS
        row = i // COLS
        x0, y0 = col * CW, row * CH
        x1, y1 = x0 + CW - 3, y0 + CH - 3

        # พื้นหลัง gradient-like (สองสี)
        draw.rectangle([x0 + 2, y0 + 2, x1, y1], fill=item["bg"], outline="#FFFFFF", width=6)

        cx = x0 + CW // 2
        cy = y0 + CH // 2

        # ไอคอน (วาดด้วย shapes)
        icon_size = CH // 3
        draw_icon(draw, ICON_KINDS[i], cx, cy - icon_size // 2, icon_size, "#FFFFFF")

        # ชื่อเมนู
        draw.text((cx, cy + icon_size), item["label"], font=font_label,
                  fill=item["fg"], anchor="mm", stroke_width=0)

    img.save(out_path, "PNG", optimize=True)
    print(f"OK image saved: {out_path}")
    return out_path


def delete_old_menus():
    res = requests.get("https://api.line.me/v2/bot/richmenu/list", headers={"Authorization": f"Bearer {TOKEN}"})
    menus = res.json().get("richmenus", [])
    for m in menus:
        requests.delete(f"https://api.line.me/v2/bot/richmenu/{m['richMenuId']}",
                        headers={"Authorization": f"Bearer {TOKEN}"})
    if menus:
        print(f"🗑️  ลบ rich menu เดิม {len(menus)} รายการ")


def create_menu() -> str:
    areas = []
    for i, item in enumerate(ITEMS):
        col = i % COLS
        row = i // COLS
        areas.append({
            "bounds": {"x": col * CW, "y": row * CH, "width": CW, "height": CH},
            "action": {"type": "message", "text": item["text"]},
        })

    body = {
        "size": {"width": W, "height": H},
        "selected": True,
        "name": "Main Menu",
        "chatBarText": "เมนู 📋",
        "areas": areas,
    }
    res = requests.post(
        "https://api.line.me/v2/bot/richmenu",
        headers=HEADERS_JSON,
        data=json.dumps(body),
    )
    if res.status_code != 200:
        raise RuntimeError(f"Create menu failed: {res.text}")
    menu_id = res.json()["richMenuId"]
    print(f"✅ สร้าง Rich Menu: {menu_id}")
    return menu_id


def upload_image(menu_id: str, img_path: str):
    with open(img_path, "rb") as f:
        res = requests.post(
            f"https://api-data.line.me/v2/bot/richmenu/{menu_id}/content",
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "image/png"},
            data=f.read(),
        )
    if res.status_code != 200:
        raise RuntimeError(f"Upload image failed: {res.text}")
    print("✅ อัปโหลดภาพสำเร็จ")


def set_default(menu_id: str):
    res = requests.post(
        f"https://api.line.me/v2/bot/user/all/richmenu/{menu_id}",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    if res.status_code != 200:
        raise RuntimeError(f"Set default failed: {res.text}")
    print("✅ ตั้งเป็น Default Rich Menu สำเร็จ")


if __name__ == "__main__":
    print("🚀 เริ่ม setup Rich Menu...\n")
    delete_old_menus()
    img_path = make_image()
    menu_id = create_menu()
    upload_image(menu_id, img_path)
    set_default(menu_id)
    print("\n🎉 Rich Menu พร้อมใช้งานแล้ว! เปิด LINE แล้วดูเมนูด้านล่างได้เลย")

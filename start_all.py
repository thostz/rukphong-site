"""
start_all.py  —  รัน ngrok → อัปเดต LINE webhook อัตโนมัติ → รัน Flask
"""
import os
import sys
import time
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv()

LINE_TOKEN   = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
NGROK_TOKEN  = os.environ.get("NGROK_AUTHTOKEN", "")
PORT         = int(os.environ.get("PORT", 5000))
NGROK_API    = "http://localhost:4040/api/tunnels"
LINE_WEBHOOK = "https://api.line.me/v2/bot/channel/webhook/endpoint"


def kill_old_ngrok():
    subprocess.run(
        ["taskkill", "/F", "/IM", "ngrok.exe"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(1)


def start_ngrok():
    cmd = ["ngrok", "http", str(PORT), "--log", "stdout"]
    if NGROK_TOKEN:
        cmd += ["--authtoken", NGROK_TOKEN]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def get_ngrok_url(retries=15, delay=2) -> str:
    for i in range(retries):
        try:
            tunnels = requests.get(NGROK_API, timeout=3).json().get("tunnels", [])
            for t in tunnels:
                if t.get("proto") == "https":
                    return t["public_url"]
        except Exception:
            pass
        print(f"  รอ ngrok... ({i+1}/{retries})", flush=True)
        time.sleep(delay)
    raise RuntimeError("ไม่สามารถเชื่อมต่อ ngrok ได้ ตรวจสอบ NGROK_AUTHTOKEN")


def update_line_webhook(public_url: str):
    webhook_url = f"{public_url}/webhook"
    resp = requests.put(
        LINE_WEBHOOK,
        headers={
            "Authorization": f"Bearer {LINE_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"endpoint": webhook_url},
        timeout=10,
    )
    if resp.status_code == 200:
        print(f"  ✓ LINE Webhook อัปเดตแล้ว: {webhook_url}")
    else:
        print(f"  ✗ อัปเดต Webhook ล้มเหลว: {resp.status_code} {resp.text}")


def main():
    print("=" * 52)
    print("  LINE Bot Auto-Start")
    print("=" * 52)

    print("\n[1/3] หยุด ngrok เก่า (ถ้ามี)...")
    kill_old_ngrok()

    print(f"[2/3] เริ่ม ngrok tunnel → port {PORT}...")
    start_ngrok()

    public_url = get_ngrok_url()
    print(f"\n  ngrok URL: {public_url}")
    print(f"  Profile  : {public_url}/rukphong")

    update_line_webhook(public_url)

    print(f"\n[3/3] เริ่ม Flask...\n")
    print("=" * 52)

    python = sys.executable
    os.execv(python, [python, "app.py"])


if __name__ == "__main__":
    main()

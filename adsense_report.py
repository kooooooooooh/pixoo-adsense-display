import base64
import time
import traceback
from pathlib import Path
from typing import Optional, Any, Dict

import requests
from PIL import Image, ImageDraw, ImageFont

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

DEBUG = True

SCOPES = ["https://www.googleapis.com/auth/adsense.readonly"]

# ===== Configuration =====
PIXOO_IP = "<pixooのipアドレス>"  # Replace with your Pixoo IP address
UPDATE_SECONDS = 30 * 60

RANGE_TODAY = "TODAY"
RANGE_WEEK = "LAST_7_DAYS"
RANGE_MONTH = "LAST_30_DAYS"
# =========================

HERE = Path(__file__).resolve().parent
CLIENT_SECRET = HERE / "client_secret.json"  # Adjust if your filename differs
TOKEN_FILE = HERE / "token.json"

PIXOO_URL = f"http://{PIXOO_IP}/post"

FONT_FILE = HERE / "PressStart2P-Regular.ttf"

# ---------------- AdSense ----------------
def get_adsense_service():
    creds: Optional[Credentials] = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("adsense", "v2", credentials=creds)

def pick_account_name(service):
    resp = service.accounts().list(pageSize=50).execute()
    accounts = resp.get("accounts", [])
    if not accounts:
        raise RuntimeError("No AdSense accounts found.")
    return accounts[0]["name"]

def get_total(service, account_name, date_range) -> float:
    report = service.accounts().reports().generate(
        account=account_name,
        dateRange=date_range,
        metrics=["ESTIMATED_EARNINGS"],
    ).execute()

    totals = report.get("totals")
    if not totals:
        return 0.0

    if isinstance(totals, dict):
        return float(totals["cells"][0]["value"])

    if isinstance(totals, list):
        return float(totals[0]["cells"][0]["value"])

    return 0.0

# ---------------- Pixoo ----------------
def pixoo_post(payload: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(PIXOO_URL, json=payload, timeout=5)
    r.raise_for_status()
    return r.json()

def pixoo_get_http_gif_id() -> int:
    data = pixoo_post({"Command": "Draw/GetHttpGifId"})
    pic_id = data.get("PicID") or data.get("PicId") or data.get("picId")
    try:
        return int(pic_id)
    except Exception:
        return 1

def pixoo_send_http_gif(picdata_b64: str):
    pic_id = pixoo_get_http_gif_id()
    payload: Dict[str, Any] = {
        "Command": "Draw/SendHttpGif",
        "PicNum": 1,
        "PicID": pic_id,
        "PicOffset": 0,
        "PicSpeed": 100,
        "PicWidth": 64,
        "PicData": picdata_b64,
    }
    pixoo_post(payload)

def pixoo_text(text_id: int, x: int, y: int, text: str):
    payload = {
        "Command": "Draw/SendHttpText",
        "TextId": text_id,
        "x": x,
        "y": y,
        "dir": 0,
        "font": 4,
        "TextWidth": 64,
        "speed": 0,
        "TextString": text,
        "color": "#FFFFFF",
        "align": 1,
    }
    pixoo_post(payload)

def format_money(v: float) -> str:
    return f"{int(round(v))}"

# ---------------- Pixel Background (Icon Version Restored) ----------------
def _load_font(size: int):
    try:
        if FONT_FILE.exists():
            return ImageFont.truetype(str(FONT_FILE), size)
    except Exception:
        pass
    return ImageFont.load_default()

def _draw_bg(dr: ImageDraw.ImageDraw):
    for y in range(64):
        for x in range(64):
            base = 10
            if ((x // 4) + (y // 4)) % 2 == 0:
                base = 12
            dr.point((x, y), fill=(base, base, base))
    dr.rectangle([0, 0, 63, 63], outline=(70, 70, 70))
    dr.rectangle([2, 2, 61, 61], outline=(30, 30, 30))

def _draw_icon_clock(dr: ImageDraw.ImageDraw, x: int, y: int):
    outline = (160, 220, 255)
    fill = (30, 60, 70)
    dr.rectangle([x, y, x + 7, y + 7], outline=outline, fill=fill)
    dr.point((x + 4, y + 4), fill=outline)
    dr.point((x + 4, y + 3), fill=outline)
    dr.point((x + 5, y + 4), fill=outline)

def _draw_icon_calendar(dr: ImageDraw.ImageDraw, x: int, y: int):
    outline = (220, 220, 220)
    fill = (70, 70, 70)
    top = (120, 160, 255)
    dr.rectangle([x, y + 1, x + 7, y + 7], outline=outline, fill=fill)
    dr.rectangle([x, y + 1, x + 7, y + 2], fill=top)

def _draw_icon_coin(dr: ImageDraw.ImageDraw, x: int, y: int):
    """8x8 round coin sprite (fills the existing 8x8 slot; no coordinate changes)."""
    edge = (120, 90, 0)         # dark gold edge
    face = (255, 210, 0)        # gold face
    hi = (255, 240, 150)        # highlight

    # 8x8 pattern (top-left at x, y):
    # ..####..
    # .######.
    # ##****##
    # ##*+**##
    # ##****##
    # ##****##
    # .######.
    # ..####..
    pattern = [
        "..####..",
        ".######.",
        "##****##",
        "##*+**##",
        "##****##",
        "##****##",
        ".######.",
        "..####..",
    ]

    for py, row in enumerate(pattern):
        for px, ch in enumerate(row):
            if ch == ".":
                continue
            if ch == "#":
                color = edge
            elif ch == "*":
                color = face
            else:  # '+'
                color = hi
            dr.point((x + px, y + py), fill=color)

def render_background_picdata() -> str:
    im = Image.new("RGB", (64, 64), (0, 0, 0))
    dr = ImageDraw.Draw(im)

    _draw_bg(dr)

    f_title = _load_font(8)
    f_row = _load_font(7)

    blue = (120, 180, 255)

    dr.text((6, 2), "SITE", font=f_title, fill=blue)
    dr.text((6, 11), "REVENUE", font=f_title, fill=blue)

    dr.line([6, 22, 57, 22], fill=(60, 60, 60))

    # Icons + labels (changed from TD to 1D only)
    _draw_icon_clock(dr, 6, 26)
    _draw_icon_calendar(dr, 6, 38)
    _draw_icon_coin(dr, 6, 51)

    dr.text((16, 24), "1D", font=f_row, fill=(220, 220, 220))
    dr.text((16, 37), "7D", font=f_row, fill=(220, 220, 220))
    dr.text((16, 49), "30D", font=f_row, fill=(220, 220, 220))

    return base64.b64encode(im.tobytes()).decode("ascii")

BACKGROUND_PICDATA = render_background_picdata()

# ---------------- Main Loop ----------------
def main():
    service = get_adsense_service()
    account = pick_account_name(service)

    while True:
        try:
            today = get_total(service, account, RANGE_TODAY)
            week = get_total(service, account, RANGE_WEEK)
            month = get_total(service, account, RANGE_MONTH)

            pixoo_send_http_gif(BACKGROUND_PICDATA)
            time.sleep(0.2)  # Insert a short delay to ensure the background is applied before sending text

            x_val = 38            

            pixoo_text(11, x_val, 22, format_money(today))
            pixoo_text(12, x_val, 34, format_money(week))
            pixoo_text(13, x_val, 46, format_money(month))

        except Exception as e:
            print("Update failed:", repr(e))
            traceback.print_exc()

        time.sleep(UPDATE_SECONDS)

if __name__ == "__main__":
    main()

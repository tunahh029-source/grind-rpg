"""Mở app Streamlit như một người dùng thật để app không bị "ngủ" vì không có truy cập.

- Nếu app đang chạy: chờ app tải xong, giữ phiên mở vài giây rồi thoát.
- Nếu app đang ngủ: bấm nút "Yes, get this app back up!" rồi chờ app chạy lại.
- Thoát với mã 1 (workflow báo lỗi) nếu sau TOTAL_TIMEOUT giây app vẫn chưa lên.
"""
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "https://grind-rpg.streamlit.app/")
READY_TEXT = "From the ordinary to flee"  # tiêu đề sidebar, chỉ hiện khi app đã tải xong dữ liệu
WAKE_BUTTON = re.compile(r"get this app back up", re.IGNORECASE)
TOTAL_TIMEOUT = 240  # giây
HOLD_SECONDS = 20  # giữ phiên mở thêm để Streamlit ghi nhận lượt truy cập


def app_ready(page):
    for frame in page.frames:  # app Streamlit Cloud có thể nằm trong iframe
        try:
            if frame.get_by_text(READY_TEXT).first.is_visible():
                return True
        except Exception:
            pass
    return False


def find_wake_button(page):
    for frame in page.frames:
        try:
            btn = frame.get_by_role("button", name=WAKE_BUTTON).first
            if btn.is_visible():
                return btn
        except Exception:
            pass
    return None


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            deadline = time.time() + TOTAL_TIMEOUT
            woke = False
            while time.time() < deadline:
                if app_ready(page):
                    print("✅ App đang chạy" + (" (vừa được đánh thức)" if woke else ""))
                    time.sleep(HOLD_SECONDS)
                    return 0
                if not woke:
                    btn = find_wake_button(page)
                    if btn is not None:
                        print("😴 App đang ngủ → bấm nút đánh thức")
                        btn.click()
                        woke = True
                time.sleep(3)
            print("❌ Hết thời gian chờ mà app chưa lên")
            page.screenshot(path="debug.png", full_page=True)
            return 1
        finally:
            browser.close()


if __name__ == "__main__":
    sys.exit(main())

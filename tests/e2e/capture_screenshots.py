from playwright.sync_api import sync_playwright
import os

def capture_screenshots():
    # スクリーンショットの保存先ディレクトリを作成
    screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "..", "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)
    
    # ダミーアプリの絶対パスを取得 (file:// スキーム用)
    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dummy-app"))
    pass_url = f"file://{app_dir}/index_pass.html"
    fail_url = f"file://{app_dir}/index_fail.html"

    print("Starting Playwright to capture screenshots...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 一般的なデスクトップのViewportを設定
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # 正常系のスクリーンショットを撮影
        print(f"Navigating to {pass_url}")
        page.goto(pass_url)
        # アニメーション等のレンダリング待ち (Flakyテスト防止のため sleep は使用しない)
        page.wait_for_load_state("networkidle")
        pass_screenshot_path = os.path.join(screenshot_dir, "pass_screenshot.png")
        page.screenshot(path=pass_screenshot_path, full_page=True)
        print(f"Saved: {pass_screenshot_path}")

        # 異常系のスクリーンショットを撮影
        print(f"Navigating to {fail_url}")
        page.goto(fail_url)
        page.wait_for_load_state("networkidle")
        fail_screenshot_path = os.path.join(screenshot_dir, "fail_screenshot.png")
        page.screenshot(path=fail_screenshot_path, full_page=True)
        print(f"Saved: {fail_screenshot_path}")

        browser.close()
        print("Screenshots captured successfully.")

if __name__ == "__main__":
    capture_screenshots()

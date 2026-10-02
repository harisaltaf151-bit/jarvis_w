"""
JARVIS Tool — Browser Agent
Controls a real browser via Selenium WebDriver.
Supports: navigate, search, click, type, screenshot, scrape, tabs.
"""

import base64
import time
from pathlib import Path


class BrowserAgent:
    """Lazy-init Selenium driver so server starts even without browser installed."""

    def __init__(self):
        self._driver = None

    # ── driver bootstrap ───────────────────────────────────────────────────────
    def _get_driver(self):
        if self._driver:
            try:
                _ = self._driver.title   # probe
                return self._driver
            except Exception:
                self._driver = None

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options

            opts = Options()
            opts.add_argument("--start-maximized")
            opts.add_argument("--disable-notifications")
            opts.add_argument("--disable-infobars")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)

            try:
                from webdriver_manager.chrome import ChromeDriverManager
                svc = Service(ChromeDriverManager().install())
                self._driver = webdriver.Chrome(service=svc, options=opts)
            except Exception:
                self._driver = webdriver.Chrome(options=opts)

        except Exception:
            try:
                from selenium import webdriver
                from selenium.webdriver.firefox.options import Options as FOptions
                opts = FOptions()
                self._driver = webdriver.Firefox(options=opts)
            except Exception as exc:
                raise RuntimeError(
                    "No browser driver found. Install Chrome + chromedriver or Firefox + geckodriver.\n"
                    "Quick fix:  pip install webdriver-manager"
                ) from exc

        return self._driver

    # ── public actions ─────────────────────────────────────────────────────────
    def navigate(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        driver = self._get_driver()
        driver.get(url)
        return f"✅ Navigated to {url} — title: {driver.title}"

    def search(self, query: str, engine: str = "google") -> str:
        engines = {
            "google":  f"https://www.google.com/search?q={_urlencode(query)}",
            "bing":    f"https://www.bing.com/search?q={_urlencode(query)}",
            "duckduckgo": f"https://duckduckgo.com/?q={_urlencode(query)}",
            "youtube": f"https://www.youtube.com/results?search_query={_urlencode(query)}",
        }
        url = engines.get(engine.lower(), engines["google"])
        return self.navigate(url)

    def get_page_text(self, url: str = "") -> dict:
        """Return visible text from current page or a given URL."""
        driver = self._get_driver()
        if url:
            self.navigate(url)
            time.sleep(1.5)
        text = driver.find_element("tag name", "body").text
        return {"url": driver.current_url, "title": driver.title, "text": text[:6000]}

    def click(self, selector: str, by: str = "css") -> str:
        """Click an element. by: css | xpath | id | text"""
        from selenium.webdriver.common.by import By
        driver = self._get_driver()
        by_map = {
            "css":   By.CSS_SELECTOR,
            "xpath": By.XPATH,
            "id":    By.ID,
            "text":  By.LINK_TEXT,
            "name":  By.NAME,
        }
        elem = driver.find_element(by_map.get(by, By.CSS_SELECTOR), selector)
        elem.click()
        return f"✅ Clicked element: {selector}"

    def type_text(self, selector: str, text: str, by: str = "css") -> str:
        """Type text into an input field."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        driver = self._get_driver()
        by_map = {"css": By.CSS_SELECTOR, "xpath": By.XPATH, "id": By.ID, "name": By.NAME}
        elem = driver.find_element(by_map.get(by, By.CSS_SELECTOR), selector)
        elem.clear()
        elem.send_keys(text)
        return f"✅ Typed into {selector}"

    def screenshot(self, save_path: str = "") -> dict:
        """Take a screenshot, return base64 and optionally save."""
        driver = self._get_driver()
        png = driver.get_screenshot_as_png()
        b64 = base64.b64encode(png).decode()
        result = {"base64": b64, "url": driver.current_url}

        if save_path:
            p = Path(save_path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(png)
            result["saved"] = str(p)

        return result

    def new_tab(self, url: str = "") -> str:
        driver = self._get_driver()
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        if url:
            return self.navigate(url)
        return "✅ Opened new tab"

    def close_tab(self) -> str:
        driver = self._get_driver()
        driver.close()
        if driver.window_handles:
            driver.switch_to.window(driver.window_handles[-1])
        return "✅ Closed tab"

    def list_tabs(self) -> list[dict]:
        driver = self._get_driver()
        current = driver.current_window_handle
        tabs = []
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            tabs.append({
                "handle":  handle,
                "title":   driver.title,
                "url":     driver.current_url,
                "active":  handle == current,
            })
        driver.switch_to.window(current)
        return tabs

    def execute_js(self, script: str) -> str:
        result = self._get_driver().execute_script(script)
        return str(result)

    def fill_form(self, fields: dict) -> str:
        """Fill multiple form fields. fields = {selector: value}"""
        for sel, val in fields.items():
            self.type_text(sel, val)
        return f"✅ Filled {len(fields)} form fields"

    def scroll(self, direction: str = "down", amount: int = 500) -> str:
        sign = 1 if direction == "down" else -1
        self._get_driver().execute_script(f"window.scrollBy(0, {sign * amount});")
        return f"✅ Scrolled {direction}"

    def back(self) -> str:
        self._get_driver().back()
        return "✅ Navigated back"

    def forward(self) -> str:
        self._get_driver().forward()
        return "✅ Navigated forward"

    def refresh(self) -> str:
        self._get_driver().refresh()
        return "✅ Page refreshed"

    def close(self) -> str:
        if self._driver:
            self._driver.quit()
            self._driver = None
        return "✅ Browser closed"


def _urlencode(s: str) -> str:
    from urllib.parse import quote_plus
    return quote_plus(s)

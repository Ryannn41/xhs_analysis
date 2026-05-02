from __future__ import annotations

from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from backend.config import (
    BROWSER_CHANNEL,
    BROWSER_EXECUTABLE_PATH,
    BROWSER_HEADLESS,
    BROWSER_TIMEOUT_MS,
    XHS_STORAGE_STATE,
    ensure_runtime_dirs,
)


def xhs_context_options(storage_state: Path | None = None) -> dict:
    context_options = {
        "viewport": {"width": 1440, "height": 1000},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "locale": "zh-CN",
    }
    if storage_state and storage_state.exists():
        context_options["storage_state"] = str(storage_state)
    return context_options


class XhsBrowser:
    def __init__(self, storage_state: Path = XHS_STORAGE_STATE):
        self.storage_state = storage_state
        self._playwright = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        if self._browser:
            return

        ensure_runtime_dirs()
        self._playwright = await async_playwright().start()
        launch_options = {
            "headless": BROWSER_HEADLESS,
            "timeout": BROWSER_TIMEOUT_MS,
        }
        if BROWSER_CHANNEL:
            launch_options["channel"] = BROWSER_CHANNEL
        if BROWSER_EXECUTABLE_PATH:
            launch_options["executable_path"] = BROWSER_EXECUTABLE_PATH

        self._browser = await self._playwright.chromium.launch(**launch_options)

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def new_context(self) -> BrowserContext:
        await self.start()
        assert self._browser is not None

        context = await self._browser.new_context(**xhs_context_options(self.storage_state))
        context.set_default_timeout(BROWSER_TIMEOUT_MS)
        return context

    async def new_page(self) -> tuple[BrowserContext, Page]:
        context = await self.new_context()
        return context, await context.new_page()

    def has_login_state(self) -> bool:
        return self.storage_state.exists()

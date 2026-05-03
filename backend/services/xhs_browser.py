from __future__ import annotations

from contextlib import suppress
from pathlib import Path

from playwright.async_api import BrowserContext, Error as PlaywrightError, Page, Playwright, async_playwright

from backend.config import (
    BROWSER_CHANNEL,
    BROWSER_EXECUTABLE_PATH,
    BROWSER_HEADLESS,
    BROWSER_TIMEOUT_MS,
    XHS_BROWSER_PROFILE_DIR,
    ensure_runtime_dirs,
)


def xhs_context_options() -> dict:
    return {
        "viewport": {"width": 1440, "height": 1000},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "locale": "zh-CN",
    }


class XhsBrowser:
    def __init__(self, profile_dir: Path = XHS_BROWSER_PROFILE_DIR):
        self.profile_dir = profile_dir
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> None:
        if self._context:
            return

        ensure_runtime_dirs()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        launch_options = {
            "headless": BROWSER_HEADLESS,
            "timeout": BROWSER_TIMEOUT_MS,
            **xhs_context_options(),
        }
        if BROWSER_CHANNEL:
            launch_options["channel"] = BROWSER_CHANNEL
        if BROWSER_EXECUTABLE_PATH:
            launch_options["executable_path"] = BROWSER_EXECUTABLE_PATH

        context = await self._playwright.chromium.launch_persistent_context(
            str(self.profile_dir),
            **launch_options,
        )
        self._context = context
        context.on("close", lambda *_: self._handle_context_close(context))
        context.set_default_timeout(BROWSER_TIMEOUT_MS)

    async def stop(self) -> None:
        context = self._context
        self._context = None
        if context:
            with suppress(PlaywrightError):
                await context.close()
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def new_page(self) -> Page:
        await self.start()
        assert self._context is not None

        try:
            return await self._context.new_page()
        except PlaywrightError as error:
            if "closed" not in str(error).lower():
                raise
            await self.stop()
            await self.start()
            assert self._context is not None
            return await self._context.new_page()

    def has_login_state(self) -> bool:
        return self.profile_dir.exists() and any(self.profile_dir.iterdir())

    def _handle_context_close(self, context: BrowserContext) -> None:
        if self._context is context:
            self._context = None

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from backend.config import (
    BROWSER_CHANNEL,
    BROWSER_EXECUTABLE_PATH,
    BROWSER_TIMEOUT_MS,
    XHS_BASE_URL,
    XHS_STORAGE_STATE,
    ensure_runtime_dirs,
)
from backend.services.xhs_browser import xhs_context_options


def storage_state_info(storage_state: Path = XHS_STORAGE_STATE) -> dict[str, Any]:
    updated_at = None
    if storage_state.exists():
        updated_at = datetime.fromtimestamp(storage_state.stat().st_mtime).isoformat(
            timespec="seconds"
        )

    return {
        "has_login_state": storage_state.exists(),
        "storage_state": str(storage_state),
        "storage_state_updated_at": updated_at,
    }


def browser_launch_options() -> dict[str, Any]:
    launch_options: dict[str, Any] = {
        "headless": False,
        "timeout": BROWSER_TIMEOUT_MS,
    }
    if BROWSER_CHANNEL:
        launch_options["channel"] = BROWSER_CHANNEL
    if BROWSER_EXECUTABLE_PATH:
        launch_options["executable_path"] = BROWSER_EXECUTABLE_PATH
    return launch_options


class XhsLoginSession:
    def __init__(self, storage_state: Path = XHS_STORAGE_STATE):
        self.storage_state = storage_state
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def is_active(self) -> bool:
        return self._browser is not None

    def status(self) -> dict[str, Any]:
        return {
            **storage_state_info(self.storage_state),
            "login_in_progress": self.is_active(),
        }

    async def start(self, url: str = XHS_BASE_URL) -> dict[str, Any]:
        if self.is_active():
            return self.status()

        ensure_runtime_dirs()
        self.storage_state.parent.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(**browser_launch_options())
        self._context = await self._browser.new_context(
            **xhs_context_options(self.storage_state)
        )
        self._context.set_default_timeout(BROWSER_TIMEOUT_MS)
        self._page = await self._context.new_page()
        await self._page.goto(url)
        return self.status()

    async def save(self) -> dict[str, Any]:
        if not self._context:
            raise RuntimeError("当前没有进行中的登录会话，请先点击开始登录。")

        if self._page:
            await self._page.wait_for_timeout(1000)
        await self._save_storage_state()
        await self.close()
        return self.status()

    async def _save_storage_state(self) -> None:
        assert self._context is not None

        try:
            await self._context.storage_state(path=str(self.storage_state), indexed_db=True)
        except TypeError:
            await self._context.storage_state(path=str(self.storage_state))

    async def close(self) -> None:
        if self._context:
            await self._context.close()
            self._context = None
            self._page = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

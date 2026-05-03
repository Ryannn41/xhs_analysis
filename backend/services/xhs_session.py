from __future__ import annotations

import json
import shutil
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Error as PlaywrightError, Page, Playwright, async_playwright

from backend.config import (
    BROWSER_CHANNEL,
    BROWSER_EXECUTABLE_PATH,
    BROWSER_TIMEOUT_MS,
    XHS_BROWSER_PROFILE_DIR,
    XHS_CURRENT_USER_FILE,
    XHS_BASE_URL,
    XHS_STORAGE_STATE,
    ensure_runtime_dirs,
)
from backend.services.xhs_browser import xhs_context_options


def profile_dir_has_state(profile_dir: Path = XHS_BROWSER_PROFILE_DIR) -> bool:
    return profile_dir.exists() and any(profile_dir.iterdir())


def storage_state_info(
    storage_state: Path = XHS_STORAGE_STATE,
    profile_dir: Path = XHS_BROWSER_PROFILE_DIR,
) -> dict[str, Any]:
    updated_at = None
    if storage_state.exists():
        updated_at = datetime.fromtimestamp(storage_state.stat().st_mtime).isoformat(
            timespec="seconds"
        )

    return {
        "has_login_state": storage_state.exists() or profile_dir_has_state(profile_dir),
        "storage_state": str(storage_state),
        "browser_profile_dir": str(profile_dir),
        "storage_state_updated_at": updated_at,
    }


def load_current_user(user_file: Path = XHS_CURRENT_USER_FILE) -> dict[str, str] | None:
    if not user_file.exists():
        return None

    try:
        data = json.loads(user_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    profile = normalize_current_user(data)
    return profile or None


def save_current_user(profile: dict[str, Any] | None, user_file: Path = XHS_CURRENT_USER_FILE) -> None:
    if not profile:
        user_file.unlink(missing_ok=True)
        return

    user_file.parent.mkdir(parents=True, exist_ok=True)
    user_file.write_text(
        json.dumps(normalize_current_user(profile), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalize_current_user(profile: dict[str, Any]) -> dict[str, str]:
    normalized = {
        "nickname": str(profile.get("nickname") or "").strip(),
        "avatar_url": str(profile.get("avatar_url") or "").strip(),
        "profile_url": str(profile.get("profile_url") or "").strip(),
        "red_id": str(profile.get("red_id") or "").strip(),
    }
    return {key: value for key, value in normalized.items() if value}


def profile_url_from_user_id(user_id: str) -> str:
    clean_user_id = user_id.strip()
    return f"{XHS_BASE_URL}/user/profile/{clean_user_id}" if clean_user_id else ""


async def read_current_user_profile(page: Page) -> dict[str, str] | None:
    try:
        await page.goto(XHS_BASE_URL, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
    except Exception:
        pass

    try:
        await page.wait_for_timeout(1500)
        data = await page.evaluate(
            """() => {
                const textOf = (element) =>
                    (element?.innerText || element?.textContent || "").trim();
                const absoluteUrl = (value) => {
                    if (!value || value.startsWith("data:") || value.startsWith("blob:")) return "";
                    try {
                        return new URL(value, window.location.origin).toString();
                    } catch {
                        return "";
                    }
                };
                const imageUrl = (element) =>
                    absoluteUrl(
                        element?.currentSrc ||
                        element?.src ||
                        element?.getAttribute?.("src") ||
                        ""
                    );
                const profilePath = (href) => {
                    const match = href.match(/\\/user\\/profile\\/([^/?#]+)/);
                    return match ? match[1] : "";
                };

                const anchors = Array.from(document.querySelectorAll('a[href*="/user/profile/"]'));
                const scoredAnchors = anchors.map((anchor, index) => {
                    const href = absoluteUrl(anchor.href || anchor.getAttribute("href") || "");
                    const text = textOf(anchor);
                    const parentText = textOf(anchor.closest("li, nav, aside, header, .side-bar, .user"));
                    let score = 0;
                    if (/我|个人|主页|Profile/i.test(`${text}\\n${parentText}`)) score += 8;
                    if (anchor.querySelector("img")) score += 4;
                    if (index < 8) score += 2;
                    return { anchor, href, text, parentText, score };
                }).filter((item) => item.href);

                scoredAnchors.sort((a, b) => b.score - a.score);
                const best = scoredAnchors[0];
                const profileUrl = best?.href || "";
                const userId = profilePath(profileUrl);

                const stateCandidates = [];
                const seen = new WeakSet();
                const walk = (value, depth = 0) => {
                    if (!value || typeof value !== "object" || seen.has(value) || depth > 6) return;
                    seen.add(value);
                    if (!Array.isArray(value)) {
                        const nickname = value.nickname || value.nickName || value.name || "";
                        const avatar =
                            value.avatar ||
                            value.avatarUrl ||
                            value.avatar_url ||
                            value.image ||
                            value.imageUrl ||
                            "";
                        const id = String(value.userId || value.user_id || value.id || "");
                        if (nickname || avatar) {
                            let score = 0;
                            if (userId && id === userId) score += 10;
                            if (nickname) score += 3;
                            if (avatar) score += 3;
                            stateCandidates.push({
                                nickname: String(nickname || ""),
                                avatar_url: absoluteUrl(String(avatar || "")),
                                red_id: String(value.redId || value.red_id || ""),
                                user_id: id,
                                score,
                            });
                        }
                    }
                    for (const item of Array.isArray(value) ? value : Object.values(value)) {
                        walk(item, depth + 1);
                    }
                };
                walk(window.__INITIAL_STATE__);
                stateCandidates.sort((a, b) => b.score - a.score);
                const stateUser = stateCandidates[0] || {};

                let avatar = "";
                let nickname = "";
                if (best?.anchor) {
                    const container = best.anchor.closest("li, nav, aside, header, .side-bar, .user") || best.anchor;
                    const img = container.querySelector("img") || best.anchor.querySelector("img");
                    avatar = imageUrl(img);
                    nickname =
                        img?.alt?.trim() ||
                        best.text
                            .split(/\\n+/)
                            .map((line) => line.trim())
                            .filter((line) => line && !/^(我|个人主页|主页)$/.test(line))[0] ||
                        "";
                }

                return {
                    nickname: stateUser.nickname || nickname,
                    avatar_url: stateUser.avatar_url || avatar,
                    profile_url: profileUrl,
                    red_id: stateUser.red_id || "",
                    user_id: userId || stateUser.user_id || "",
                };
            }"""
        )
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    profile = normalize_current_user(
        {
            **data,
            "profile_url": data.get("profile_url") or profile_url_from_user_id(str(data.get("user_id") or "")),
        }
    )
    return profile or None


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
    def __init__(
        self,
        storage_state: Path = XHS_STORAGE_STATE,
        profile_dir: Path = XHS_BROWSER_PROFILE_DIR,
    ):
        self.storage_state = storage_state
        self.profile_dir = profile_dir
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def is_active(self) -> bool:
        return self._context is not None

    def status(self) -> dict[str, Any]:
        return {
            **storage_state_info(self.storage_state, self.profile_dir),
            "current_user": load_current_user() if self.storage_state.exists() else None,
            "login_in_progress": self.is_active(),
        }

    async def start(self, url: str = XHS_BASE_URL) -> dict[str, Any]:
        if self.is_active():
            return self.status()

        ensure_runtime_dirs()
        self.storage_state.parent.mkdir(parents=True, exist_ok=True)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        context = await self._playwright.chromium.launch_persistent_context(
            str(self.profile_dir),
            **browser_launch_options(),
            **xhs_context_options(),
        )
        self._context = context
        context.on("close", lambda *_: self._handle_context_close(context))
        context.set_default_timeout(BROWSER_TIMEOUT_MS)
        self._page = await context.new_page()
        await self._page.goto(url)
        return self.status()

    async def save(self) -> dict[str, Any]:
        if not self._context:
            raise RuntimeError("当前没有进行中的登录会话，请先点击开始登录。")

        if self._page:
            await self._page.wait_for_timeout(1000)
        await self._save_storage_state()
        save_current_user(await read_current_user_profile(self._page) if self._page else None)
        await self.close()
        return self.status()

    async def clear(self) -> dict[str, Any]:
        await self.close()
        self.storage_state.unlink(missing_ok=True)
        save_current_user(None)
        if self.profile_dir.exists():
            shutil.rmtree(self.profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        return self.status()

    async def _save_storage_state(self) -> None:
        assert self._context is not None

        try:
            await self._context.storage_state(path=str(self.storage_state), indexed_db=True)
        except TypeError:
            await self._context.storage_state(path=str(self.storage_state))

    async def close(self) -> None:
        context = self._context
        self._context = None
        self._page = None
        if context:
            with suppress(PlaywrightError):
                await context.close()
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    def _handle_context_close(self, context: BrowserContext) -> None:
        if self._context is context:
            self._context = None
            self._page = None

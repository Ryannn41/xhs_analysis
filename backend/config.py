from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "XHS Analysis"


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _bundle_root()
BASE_DIR = ROOT_DIR / "backend"
if not BASE_DIR.exists():
    BASE_DIR = Path(__file__).resolve().parent


def _path_from_env(name: str, default: Path, *, base: Path = ROOT_DIR) -> Path:
    value = os.getenv(name, "").strip()
    if not value:
        return default

    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def _default_user_data_dir() -> Path | None:
    value = os.getenv("XHS_USER_DATA_DIR", "").strip()
    if value:
        return Path(value).expanduser()

    if os.getenv("XHS_DESKTOP_MODE", "").lower() not in {"1", "true", "yes"}:
        return None

    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
    if getattr(sys, "frozen", False):
        load_dotenv(Path(sys.executable).resolve().parent / ".env")
except ImportError:
    pass

USER_DATA_DIR = _default_user_data_dir()
DATA_DIR = _path_from_env("XHS_DATA_DIR", BASE_DIR / "data")
STORAGE_DIR = _path_from_env(
    "XHS_STORAGE_DIR",
    (USER_DATA_DIR / "storage") if USER_DATA_DIR else BASE_DIR / "storage",
)
CACHE_DIR = _path_from_env(
    "XHS_CACHE_DIR",
    (USER_DATA_DIR / "cache") if USER_DATA_DIR else DATA_DIR / "cache",
)
ACCOUNTS_FILE = _path_from_env("XHS_ACCOUNTS_FILE", DATA_DIR / "accounts.json")

XHS_BASE_URL = "https://www.xiaohongshu.com"
XHS_STORAGE_STATE = _path_from_env("XHS_STORAGE_STATE", STORAGE_DIR / "xhs_state.json")
XHS_CURRENT_USER_FILE = XHS_STORAGE_STATE.with_name("xhs_current_user.json")
XHS_BROWSER_PROFILE_DIR = _path_from_env(
    "XHS_BROWSER_PROFILE_DIR",
    STORAGE_DIR / "browser_profile",
)

BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "false").lower() in {
    "1",
    "true",
    "yes",
}
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "").strip() or None
BROWSER_EXECUTABLE_PATH = os.getenv("BROWSER_EXECUTABLE_PATH", "").strip() or None
BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "45000"))
# 个人页出现登录/扫码墙时，在首次读取前最长等待（毫秒），便于用户完成扫码。
PROFILE_PAGE_LOGIN_WAIT_MS = int(os.getenv("PROFILE_PAGE_LOGIN_WAIT_MS", "120000"))
PROFILE_PAGE_POLL_MS = int(os.getenv("PROFILE_PAGE_POLL_MS", "2500"))

FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
FRONTEND_ORIGIN_REGEX = os.getenv(
    "FRONTEND_ORIGIN_REGEX",
    r"^http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
)


def ensure_runtime_dirs() -> None:
    if USER_DATA_DIR:
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_DIR.exists() and os.getenv("XHS_DATA_DIR", "").strip():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    XHS_BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

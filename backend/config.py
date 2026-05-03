from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"

XHS_BASE_URL = "https://www.xiaohongshu.com"
_storage_state = Path(os.getenv("XHS_STORAGE_STATE", str(STORAGE_DIR / "xhs_state.json")))
XHS_STORAGE_STATE = _storage_state if _storage_state.is_absolute() else ROOT_DIR / _storage_state
XHS_CURRENT_USER_FILE = XHS_STORAGE_STATE.with_name("xhs_current_user.json")

BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() in {
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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

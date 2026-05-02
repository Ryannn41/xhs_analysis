from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.config import ACCOUNTS_FILE, XHS_BASE_URL


PROFILE_RE = re.compile(r"/user/profile/([^/?#]+)")
USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


@dataclass(frozen=True)
class AccountRef:
    input: str
    user_id: str
    nickname: str = ""
    profile_url: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def load_account_map(path: Path = ACCOUNTS_FILE) -> dict[str, str]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"账号映射文件必须是 JSON object：{path}")

    return {
        str(nickname).strip(): str(user_id).strip()
        for nickname, user_id in data.items()
        if str(nickname).strip() and str(user_id).strip()
    }


def resolve_account(account_input: str, account_map: dict[str, str] | None = None) -> AccountRef:
    text = account_input.strip()
    if not text:
        raise ValueError("请输入小红书昵称、user_id 或主页 URL。")

    accounts = account_map if account_map is not None else load_account_map()
    id_to_nickname = {user_id: nickname for nickname, user_id in accounts.items()}

    profile_match = PROFILE_RE.search(text)
    if profile_match:
        user_id = profile_match.group(1)
        return AccountRef(
            input=account_input,
            user_id=user_id,
            nickname=id_to_nickname.get(user_id, ""),
            profile_url=f"{XHS_BASE_URL}/user/profile/{user_id}",
        )

    if text in accounts:
        user_id = accounts[text]
        return AccountRef(
            input=account_input,
            user_id=user_id,
            nickname=text,
            profile_url=f"{XHS_BASE_URL}/user/profile/{user_id}",
        )

    user_id = text.rstrip("/").split("/")[-1]
    if USER_ID_RE.match(user_id):
        return AccountRef(
            input=account_input,
            user_id=user_id,
            nickname=id_to_nickname.get(user_id, ""),
            profile_url=f"{XHS_BASE_URL}/user/profile/{user_id}",
        )

    raise ValueError(
        "昵称只能解析 accounts.json 中已维护的账号；也可以直接输入用户主页 URL 或 user_id。"
    )

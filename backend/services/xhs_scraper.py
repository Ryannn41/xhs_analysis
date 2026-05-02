from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from backend.config import (
    BROWSER_TIMEOUT_MS,
    PROFILE_PAGE_LOGIN_WAIT_MS,
    PROFILE_PAGE_POLL_MS,
)
from backend.services.account_resolver import AccountRef
from backend.services.xhs_browser import XhsBrowser


INITIAL_STATE_RE = re.compile(r"window\.__INITIAL_STATE__=(.*?)</script>", re.S)
DEFAULT_PERIOD_DAYS = 30
MAX_PROFILE_SCROLLS = 30
SCROLL_IDLE_ROUNDS = 3
NOTE_COUNT_FIELDS = {
    "likedCount": "liked_count",
    "collectedCount": "collected_count",
    "commentCount": "comment_count",
    "shareCount": "share_count",
}


def get_nested(data: dict[str, Any], *paths: str, default: Any = "") -> Any:
    for path in paths:
        current: Any = data
        for key in path.split("."):
            if isinstance(current, list) and key.isdigit():
                index = int(key)
                if index >= len(current):
                    current = None
                    break
                current = current[index]
                continue

            if not isinstance(current, dict) or key not in current:
                current = None
                break
            current = current[key]

        if current not in (None, ""):
            return current
    return default


def parse_count(value: Any) -> int:
    if value is None:
        return 0

    text = str(value).strip().replace(",", "").rstrip("+")
    if not text:
        return 0

    multipliers = {"万": 10000, "w": 10000, "W": 10000, "k": 1000, "K": 1000}
    unit = text[-1]
    try:
        if unit in multipliers:
            return int(float(text[:-1]) * multipliers[unit])
        return int(float(text))
    except ValueError:
        return 0


def count_display(value: Any) -> str:
    return "" if value in (None, "") else str(value).strip()


def is_approximate_count(value: Any) -> bool:
    return "+" in count_display(value)


def format_time(value: Any) -> str:
    if value in (None, ""):
        return ""

    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return str(value)

    if timestamp > 10_000_000_000:
        timestamp = timestamp // 1000
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def format_time_from_note_id(note_id: Any) -> str:
    text = str(note_id or "")
    if len(text) < 8 or not re.fullmatch(r"[0-9a-fA-F]{8,}", text):
        return ""

    try:
        timestamp = int(text[:8], 16)
    except ValueError:
        return ""

    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def parse_note_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    if isinstance(value, (int, float)):
        timestamp = int(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp // 1000
        return datetime.fromtimestamp(timestamp)

    text = str(value).strip()
    if not text:
        return None

    for parser in (
        datetime.fromisoformat,
        lambda current: datetime.strptime(current, "%Y-%m-%d %H:%M:%S"),
        lambda current: datetime.strptime(current, "%Y-%m-%d"),
    ):
        try:
            return parser(text)
        except ValueError:
            continue

    return None


def normalize_period(
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    period_end = end_date or date.today()
    period_start = start_date or period_end - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
    return period_start, period_end


def flatten_notes(notes: Any) -> list[dict[str, Any]]:
    if isinstance(notes, dict):
        return [notes]
    if not isinstance(notes, list):
        return []

    flattened: list[dict[str, Any]] = []
    for item in notes:
        if isinstance(item, dict):
            flattened.append(item)
        elif isinstance(item, list):
            flattened.extend(flatten_notes(item))
    return flattened


def walk_json(data: Any) -> list[Any]:
    stack = [data]
    values: list[Any] = []
    while stack:
        current = stack.pop()
        values.append(current)
        if isinstance(current, dict):
            stack.extend(
                value for value in current.values() if isinstance(value, (dict, list))
            )
        elif isinstance(current, list):
            stack.extend(value for value in current if isinstance(value, (dict, list)))
    return values


def extract_profile_data(payloads: list[Any]) -> dict[str, Any]:
    for payload in reversed(payloads):
        for item in walk_json(payload):
            if not isinstance(item, dict):
                continue
            user_page_data = item.get("userPageData")
            if isinstance(user_page_data, dict) and user_page_data:
                return user_page_data
            if (
                isinstance(item.get("basicInfo") or item.get("basic_info"), dict)
                and isinstance(item.get("interactions"), list)
            ):
                return item
    return {}


def extract_note_items(payloads: list[Any]) -> list[dict[str, Any]]:
    note_items: list[dict[str, Any]] = []
    for payload in payloads:
        for item in walk_json(payload):
            if not isinstance(item, dict):
                continue
            note_card = item.get("noteCard")
            if isinstance(note_card, dict) and note_card.get("noteId"):
                note_items.append(item)
            elif item.get("noteId") and (
                item.get("displayTitle")
                or item.get("title")
                or isinstance(item.get("interactInfo"), dict)
            ):
                note_items.append(item)
    return note_items


def _interaction_key(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("type") or item.get("name") or "")


def _interaction_has_count(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    count = item.get("count")
    return count not in (None, "", 0)


def merge_interactions(primary: list[Any], fallback: list[Any]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for item in fallback:
        key = _interaction_key(item)
        if key and isinstance(item, dict):
            by_key[key] = dict(item)
    for item in primary:
        key = _interaction_key(item)
        if not key or not isinstance(item, dict):
            continue
        if key not in by_key:
            by_key[key] = dict(item)
        elif _interaction_has_count(item):
            by_key[key] = {**by_key[key], **item}
    return list(by_key.values())


def merge_profile_data(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    if not primary:
        return fallback
    if not fallback:
        return primary

    merged = dict(primary)
    primary_basic = primary.get("basicInfo") or primary.get("basic_info") or {}
    fallback_basic = fallback.get("basicInfo") or fallback.get("basic_info") or {}
    if isinstance(primary_basic, dict) or isinstance(fallback_basic, dict):
        merged["basicInfo"] = {
            **(fallback_basic if isinstance(fallback_basic, dict) else {}),
            **(primary_basic if isinstance(primary_basic, dict) else {}),
        }

    primary_ix = primary.get("interactions")
    fallback_ix = fallback.get("interactions")
    if isinstance(primary_ix, list) or isinstance(fallback_ix, list):
        merged["interactions"] = merge_interactions(
            primary_ix if isinstance(primary_ix, list) else [],
            fallback_ix if isinstance(fallback_ix, list) else [],
        )

    return merged


def apply_interact_counts(note_data: dict[str, Any], interact_info: dict[str, Any]) -> None:
    for source_key, target_key in NOTE_COUNT_FIELDS.items():
        display = count_display(interact_info.get(source_key))
        parsed = parse_count(display)
        note_data[f"{target_key}_display"] = display
        note_data[target_key] = parsed


def build_note_url(note_id: str, xsec_token: str = "") -> str:
    if not note_id:
        return ""

    url = f"https://www.xiaohongshu.com/explore/{note_id}"
    if not xsec_token:
        return url

    query = urlencode({"xsec_token": xsec_token, "xsec_source": "pc_user"})
    return f"{url}?{query}"


def profile_summary(user_id: str, user_info: dict[str, Any], fallback_nickname: str = "") -> dict[str, Any]:
    basic_info = get_nested(user_info, "basicInfo", "basic_info", default={})
    interactions = get_nested(user_info, "interactions", default=[])

    summary = {
        "user_id": user_id,
        "nickname": get_nested(
            user_info,
            "nickname",
            "user.nickname",
            default=fallback_nickname,
        ),
        "desc": get_nested(user_info, "desc", "user.desc", default=""),
        "red_id": "",
        "gender": "",
        "ip_location": "",
    }

    if isinstance(basic_info, dict):
        summary["nickname"] = basic_info.get("nickname") or summary["nickname"]
        summary["desc"] = basic_info.get("desc") or summary["desc"]
        summary["red_id"] = basic_info.get("redId") or basic_info.get("red_id") or ""
        summary["gender"] = basic_info.get("gender", "")
        summary["ip_location"] = (
            basic_info.get("ipLocation") or basic_info.get("ip_location") or ""
        )

    if isinstance(interactions, list):
        for item in interactions:
            if not isinstance(item, dict):
                continue
            key = item.get("type") or item.get("name")
            if key:
                summary[f"{key}_count_display"] = str(item.get("count", ""))
                summary[f"{key}_count_lower_bound"] = parse_count(item.get("count"))

    return summary


def normalize_note(item: dict[str, Any], account: dict[str, Any]) -> dict[str, Any]:
    note = item.get("noteCard") or item
    interact_info = note.get("interactInfo") or {}
    cover = note.get("cover") or {}
    cover_url = (
        cover.get("urlDefault")
        or cover.get("urlPre")
        or cover.get("url")
        or get_nested(cover, "infoList.0.url", default="")
    )
    note_id = note.get("noteId") or item.get("id") or ""
    xsec_token = note.get("xsecToken") or item.get("xsecToken") or ""

    note_data = {
        "note_id": note_id,
        "title": note.get("displayTitle") or note.get("title") or "",
        "desc": note.get("desc") or "",
        "type": note.get("type") or "",
        "time": format_time(note.get("time")) or format_time_from_note_id(note_id),
        "last_update_time": format_time(note.get("lastUpdateTime")),
        "xsec_token": xsec_token,
        "cover_url": cover_url,
        "url": build_note_url(note_id, xsec_token),
        "account_user_id": account["user_id"],
        "account_nickname": account.get("nickname", ""),
    }
    apply_interact_counts(note_data, interact_info)
    return note_data


def merge_note(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if existing.get(key) in (None, "", 0) and value not in (None, "", 0):
            existing[key] = value
        if key.endswith("_display") and value not in (None, ""):
            existing[key] = value


def parse_initial_state_from_html(html: str) -> dict[str, Any] | None:
    match = INITIAL_STATE_RE.search(html)
    if not match:
        return None

    raw_state = match.group(1).strip().replace("undefined", "null")
    return json.loads(raw_state)


def has_profile_or_notes(state: dict[str, Any]) -> bool:
    user_state = state.get("user") or {}
    return bool(user_state.get("userPageData") or user_state.get("notes"))


def _interaction_count_field_present(item: Any) -> bool:
    """互动行是否已由接口给出 count（含 0），用于区分未加载与真实为 0。"""
    if not isinstance(item, dict) or "count" not in item:
        return False
    count = item.get("count")
    return count is not None and count != ""


def profile_page_content_ready(
    response_payloads: list[Any],
    merged_state: dict[str, Any],
    dom_note_items: list[dict[str, Any]],
) -> bool:
    """在登录/扫码流程中，避免仅凭登录页 DOM 误判为已就绪。"""
    if extract_note_items(response_payloads):
        return True
    if dom_note_items:
        return True
    user_state = merged_state.get("user") or {}
    if flatten_notes(user_state.get("notes")):
        return True
    api_profile = extract_profile_data(response_payloads)
    if not isinstance(api_profile, dict) or not api_profile:
        return False
    interactions = api_profile.get("interactions")
    if isinstance(interactions, list) and any(_interaction_count_field_present(item) for item in interactions):
        return True
    return False


def merge_extracted_state(
    state: dict[str, Any] | None,
    profile_data: dict[str, Any],
    note_items: list[dict[str, Any]],
) -> dict[str, Any]:
    merged = state if isinstance(state, dict) else {}
    user_state = merged.setdefault("user", {})
    if not isinstance(user_state, dict):
        user_state = {}
        merged["user"] = user_state

    if profile_data and not user_state.get("userPageData"):
        user_state["userPageData"] = profile_data

    existing_notes = flatten_notes(user_state.get("notes"))
    if note_items:
        user_state["notes"] = existing_notes + note_items

    return merged


async def extract_dom_profile_data(page: Any) -> dict[str, Any]:
    data = await page.evaluate(
        """() => {
            const text = document.body?.innerText || "";
            const lines = text.split(/\\n+/).map((line) => line.trim()).filter(Boolean);
            const pickText = (selectors) => {
                for (const selector of selectors) {
                    const el = document.querySelector(selector);
                    const value = el?.innerText?.trim() || el?.textContent?.trim();
                    if (value) return value;
                }
                return "";
            };
            const matchValue = (regex) => {
                const match = text.match(regex);
                return match ? match[1].trim() : "";
            };
            const isCount = (value) => /^[0-9,.]+\\s*(万|w|W|k|K)?\\+?$/.test(value);
            const adjacentCount = (label) => {
                const index = lines.findIndex((line) => line === label || line.includes(label));
                if (index < 0) return "";
                for (const candidate of [lines[index - 1], lines[index + 1], lines[index + 2]]) {
                    if (candidate && isCount(candidate)) return candidate;
                }
                return "";
            };
            return {
                nickname: pickText([".user-name", ".userName", "h1"]) || lines[0] || "",
                desc: pickText([".user-desc", ".userDesc", ".desc"]),
                redId: matchValue(/小红书号[:：\\s]+([^\\n\\s]+)/),
                ipLocation: matchValue(/IP(?:属地)?[:：\\s]+([^\\n\\s]+)/),
                fans: adjacentCount("粉丝"),
                follows: adjacentCount("关注"),
                interaction: adjacentCount("获赞与收藏") || adjacentCount("获赞"),
            };
        }"""
    )
    if not isinstance(data, dict) or not any(data.values()):
        return {}

    interactions = []
    for key, source in (
        ("follows", data.get("follows")),
        ("fans", data.get("fans")),
        ("interaction", data.get("interaction")),
    ):
        if source:
            interactions.append({"type": key, "count": source})

    return {
        "basicInfo": {
            "nickname": data.get("nickname", ""),
            "desc": data.get("desc", ""),
            "redId": data.get("redId", ""),
            "ipLocation": data.get("ipLocation", ""),
        },
        "interactions": interactions,
    }


async def extract_dom_note_items(page: Any) -> list[dict[str, Any]]:
    items = await page.evaluate(
        """() => {
            const normalizeCount = (value) => (value || "").trim().replace(/^赞\\s*/, "");
            const isCount = (value) => /^[0-9,.]+\\s*(万|w|W|k|K)?\\+?$/.test(normalizeCount(value));
            const anchors = Array.from(document.querySelectorAll('a[href*="/explore/"]'));
            const seen = new Set();

            return anchors.map((anchor) => {
                const href = anchor.href;
                const idMatch = href.match(/\\/explore\\/([^/?#]+)/);
                const noteId = idMatch ? idMatch[1] : "";
                if (!noteId || seen.has(noteId)) return null;
                seen.add(noteId);

                let card = anchor;
                for (let i = 0; i < 6 && card?.parentElement; i += 1) {
                    card = card.parentElement;
                    if ((card.innerText || "").length > 20) break;
                }

                const text = card?.innerText || anchor.innerText || "";
                const lines = text.split(/\\n+/).map((line) => line.trim()).filter(Boolean);
                const title = lines.find((line) =>
                    !line.includes("赞") &&
                    !line.includes("评论") &&
                    !line.includes("收藏") &&
                    !isCount(line)
                ) || anchor.getAttribute("title") || "";
                const liked = [...lines].reverse().find((line) => isCount(line)) || "";
                const img = card?.querySelector("img") || anchor.querySelector("img");
                const url = new URL(href);

                return {
                    noteCard: {
                        noteId,
                        displayTitle: title,
                        desc: "",
                        type: "",
                        time: "",
                        xsecToken: url.searchParams.get("xsec_token") || "",
                        cover: { url: img?.currentSrc || img?.src || "" },
                        interactInfo: { likedCount: normalizeCount(liked) },
                    },
                };
            }).filter(Boolean);
        }"""
    )
    return items if isinstance(items, list) else []


async def read_initial_state(page: Any) -> dict[str, Any] | None:
    raw_state = await page.evaluate(
        """() => {
            const state = window.__INITIAL_STATE__;
            if (!state) return null;

            const seen = new WeakSet();
            const clone = (value, depth = 0) => {
                if (value === null || value === undefined) return value;
                if (typeof value === "bigint") return value.toString();
                if (typeof value !== "object") {
                    return ["function", "symbol"].includes(typeof value) ? undefined : value;
                }

                if (seen.has(value) || depth > 10) return undefined;
                seen.add(value);

                if (Array.isArray(value)) {
                    return value
                        .slice(0, 200)
                        .map((item) => clone(item, depth + 1))
                        .filter((item) => item !== undefined);
                }

                return Object.fromEntries(
                    Object.entries(value)
                        .slice(0, 200)
                        .map(([key, item]) => [key, clone(item, depth + 1)])
                        .filter(([, item]) => item !== undefined),
                );
            };

            const user = state.user || {};
            return JSON.stringify({
                user: {
                    userPageData: clone(user.userPageData),
                    notes: clone(user.notes),
                },
                note: clone(state.note),
                feed: clone(state.feed),
            });
        }"""
    )
    if raw_state:
        state = json.loads(raw_state)
        if isinstance(state, dict) and (
            has_profile_or_notes(state) or state.get("note") or state.get("feed")
        ):
            return state
    return parse_initial_state_from_html(await page.content())


def find_note_detail(state: dict[str, Any], note_id: str) -> dict[str, Any] | None:
    stack: list[Any] = [state]
    candidates: list[dict[str, Any]] = []

    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            keyed_note = current.get(note_id)
            if isinstance(keyed_note, dict):
                candidates.append(keyed_note)

            if current.get("noteId") == note_id or current.get("id") == note_id:
                candidates.append(current)

            stack.extend(
                value for value in current.values() if isinstance(value, (dict, list))
            )
        elif isinstance(current, list):
            stack.extend(value for value in current if isinstance(value, (dict, list)))

    note_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        for path in ("note", "noteCard"):
            nested_note = candidate.get(path)
            if isinstance(nested_note, dict) and isinstance(nested_note.get("interactInfo"), dict):
                note_candidates.append(nested_note)
        if isinstance(candidate.get("interactInfo"), dict):
            note_candidates.append(candidate)

    def score_note_detail(candidate: dict[str, Any]) -> int:
        interact_info = candidate.get("interactInfo") or {}
        if not isinstance(interact_info, dict):
            return 0
        return sum(
            1
            for source_key in NOTE_COUNT_FIELDS
            if count_display(interact_info.get(source_key))
        )

    return max(note_candidates, key=score_note_detail, default=None)


def needs_detail_count_enrichment(note: dict[str, Any]) -> bool:
    return any(
        not count_display(note.get(f"{field}_display"))
        or is_approximate_count(note.get(f"{field}_display"))
        for field in NOTE_COUNT_FIELDS.values()
    )


async def enrich_approximate_note_counts(page: Any, notes: list[dict[str, Any]]) -> None:
    for note in notes:
        if not note.get("url") or (
            note.get("time") and not needs_detail_count_enrichment(note)
        ):
            continue

        try:
            await page.goto(str(note["url"]), wait_until="commit")
            await page.wait_for_timeout(800)
            state = await read_initial_state(page)
        except Exception:
            continue

        detail_note = find_note_detail(state, str(note["note_id"])) if state else None
        if detail_note:
            if not note.get("time"):
                note["time"] = format_time(detail_note.get("time"))
            if not note.get("last_update_time"):
                note["last_update_time"] = format_time(detail_note.get("lastUpdateTime"))

            interact_info = detail_note.get("interactInfo") or {}
            if isinstance(interact_info, dict):
                apply_interact_counts(note, interact_info)

        if not detail_note or needs_detail_count_enrichment(note):
            await apply_dom_note_detail(page, note)


async def apply_dom_note_detail(page: Any, note: dict[str, Any]) -> None:
    detail = await page.evaluate(
        """() => {
            const text = document.body?.innerText || "";
            const timeMatch = text.match(/(20\\d{2}[-/.年]\\d{1,2}[-/.月]\\d{1,2}(?:日)?(?:\\s+\\d{1,2}:\\d{2})?)/);
            const lines = text.split(/\\n+/).map((line) => line.trim()).filter(Boolean);
            const countValuePattern = /^[0-9,.]+\\s*(万|w|W|k|K)?\\+?$/;
            const elements = Array.from(document.querySelectorAll("body *"));
            const isVisible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
            };
            const classText = (element) => {
                const className = element.className;
                if (typeof className === "string") return className;
                return className?.baseVal || "";
            };
            const elementText = (element) => (
                element.innerText ||
                element.textContent ||
                element.getAttribute("aria-label") ||
                element.getAttribute("title") ||
                element.getAttribute("placeholder") ||
                ""
            ).trim();
            const elementSignature = (element) => [
                classText(element),
                element.id || "",
                element.getAttribute("aria-label") || "",
                element.getAttribute("title") || "",
                element.getAttribute("data-v") || "",
                elementText(element),
            ].join(" ").toLowerCase();
            const countFromText = (value) => {
                const textValue = (value || "").trim();
                if (countValuePattern.test(textValue)) return textValue;
                const matches = Array.from(textValue.matchAll(/([0-9,.]+\\s*(?:万|w|W|k|K)?\\+?)/g));
                return matches.length === 1 ? matches[0][1] : "";
            };
            const extractLeadingCount = (value) => {
                const match = (value || "").trim().match(/^[:：\\s]*([0-9,.]+\\s*(?:万|w|W|k|K)?\\+?)/);
                return match ? match[1] : "";
            };
            const directCount = (element) => {
                const own = countFromText(elementText(element));
                if (own) return own;
                const descendants = Array.from(element.querySelectorAll("*"))
                    .filter((child) => isVisible(child))
                    .map((child) => countFromText(elementText(child)))
                    .filter(Boolean);
                return descendants.length === 1 ? descendants[0] : "";
            };
            const nearbyCount = (element) => {
                let current = element;
                for (let depth = 0; depth < 4 && current; depth += 1) {
                    const found = directCount(current);
                    if (found) return found;
                    current = current.parentElement;
                }

                const rect = element.getBoundingClientRect();
                const countElements = elements
                    .filter((candidate) => isVisible(candidate))
                    .map((candidate) => ({
                        text: countFromText(elementText(candidate)),
                        rect: candidate.getBoundingClientRect(),
                    }))
                    .filter((item) => item.text)
                    .filter((item) =>
                        Math.abs(item.rect.top - rect.top) < 32 &&
                        item.rect.left >= rect.left - 8 &&
                        item.rect.left < rect.left + 96
                    )
                    .sort((a, b) => Math.abs(a.rect.left - rect.left) - Math.abs(b.rect.left - rect.left));
                return countElements[0]?.text || "";
            };
            const countByKeywords = (keywords) => {
                const candidates = elements
                    .filter((element) => isVisible(element))
                    .map((element) => ({
                        element,
                        rect: element.getBoundingClientRect(),
                        signature: elementSignature(element),
                    }))
                    .filter((item) =>
                        item.rect.height <= 160 &&
                        item.rect.top > window.innerHeight * 0.45 &&
                        keywords.some((keyword) => item.signature.includes(keyword))
                    )
                    .sort((a, b) => b.rect.top - a.rect.top || a.rect.left - b.rect.left);
                for (const item of candidates) {
                    const count = nearbyCount(item.element);
                    if (count) return count;
                }
                return "";
            };
            const countsInScope = (scope) => {
                const seen = new Set();
                return Array.from(scope.querySelectorAll("*"))
                    .filter((element) => isVisible(element))
                    .map((element) => ({
                        text: elementText(element),
                        rect: element.getBoundingClientRect(),
                    }))
                    .filter((item) => countValuePattern.test(item.text))
                    .filter((item) => {
                        const key = `${item.text}:${Math.round(item.rect.left)}:${Math.round(item.rect.top)}`;
                        if (seen.has(key)) return false;
                        seen.add(key);
                        return true;
                    })
                    .sort((a, b) => a.rect.left - b.rect.left)
                    .map((item) => item.text);
            };
            const detailActionCounts = () => {
                const commentEntries = elements.filter((element) => {
                    if (!isVisible(element)) return false;
                    const textValue = elementText(element);
                    const placeholder = element.getAttribute("placeholder") || "";
                    return textValue.includes("登录后评论") || placeholder.includes("评论");
                });
                for (const entry of commentEntries) {
                    let scope = entry;
                    for (let depth = 0; depth < 5 && scope?.parentElement; depth += 1) {
                        scope = scope.parentElement;
                        const rect = scope.getBoundingClientRect();
                        if (rect.height > 0 && rect.height <= 180) {
                            const counts = countsInScope(scope);
                            if (counts.length >= 2) return counts.slice(0, 4);
                        }
                    }
                }

                return elements
                    .filter((element) => isVisible(element))
                    .map((element) => ({
                        text: elementText(element),
                        rect: element.getBoundingClientRect(),
                    }))
                    .filter((item) => countValuePattern.test(item.text) && item.rect.top > window.innerHeight * 0.55)
                    .sort((a, b) => a.rect.top - b.rect.top || a.rect.left - b.rect.left)
                    .slice(0, 4)
                    .map((item) => item.text);
            };
            const countAfter = (label) => {
                const index = lines.findIndex((line) => line === label || line.includes(label));
                if (index < 0) return "";
                const inlineCount = extractLeadingCount(lines[index].slice(lines[index].indexOf(label) + label.length));
                if (inlineCount) return inlineCount;
                for (const candidate of [lines[index + 1], lines[index - 1]]) {
                    if (candidate && countValuePattern.test(candidate)) {
                        return candidate;
                    }
                }
                return "";
            };
            const actionCounts = detailActionCounts();
            return {
                time: timeMatch ? timeMatch[1].replace(/[年月/.]/g, "-").replace("日", "") : "",
                liked: countAfter("点赞") || countAfter("赞") || countByKeywords(["like", "liked", "点赞", "赞"]) || actionCounts[0] || "",
                collected: countAfter("收藏") || countByKeywords(["collect", "collected", "collection", "star", "收藏"]) || actionCounts[1] || "",
                comment: countAfter("评论") || countByKeywords(["comment", "chat", "评论"]) || actionCounts[2] || "",
                share: countAfter("转发") || countAfter("分享") || countByKeywords(["share", "转发", "分享"]) || actionCounts[3] || "",
            };
        }"""
    )
    if not isinstance(detail, dict):
        return
    if not note.get("time") and detail.get("time"):
        note["time"] = format_time(detail["time"])
    for source_key, target_key in (
        ("liked", "liked_count"),
        ("collected", "collected_count"),
        ("comment", "comment_count"),
        ("share", "share_count"),
    ):
        display = count_display(detail.get(source_key))
        if not display:
            continue
        if note.get(f"{target_key}_display") and not is_approximate_count(note.get(f"{target_key}_display")):
            continue
        note[f"{target_key}_display"] = display
        note[target_key] = parse_count(display)


def notes_from_state(profile: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    user_state = state.get("user") or {}
    return [normalize_note(item, profile) for item in flatten_notes(user_state.get("notes"))]


def parse_profile_state(
    account: AccountRef,
    state: dict[str, Any],
    notes: list[dict[str, Any]] | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    reached_range_start: bool = True,
) -> dict[str, Any]:
    user_state = state.get("user") or {}
    user_page_data = user_state.get("userPageData") or {}
    profile = profile_summary(
        account.user_id,
        user_page_data,
        fallback_nickname=account.nickname,
    )

    all_notes = notes if notes is not None else notes_from_state(profile, state)
    filtered_notes = filter_notes_by_period(all_notes, period_start, period_end)
    return {
        "account": account.to_dict(),
        "profile": profile,
        "notes": filtered_notes,
        "stats": build_period_stats(
            profile,
            filtered_notes,
            all_notes,
            period_start,
            period_end,
            reached_range_start,
        ),
        "source": "playwright_profile_page",
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def filter_notes_by_period(
    notes: list[dict[str, Any]],
    period_start: date | None,
    period_end: date | None,
) -> list[dict[str, Any]]:
    if not period_start or not period_end:
        return notes

    filtered: list[dict[str, Any]] = []
    for note in notes:
        note_time = parse_note_datetime(note.get("time"))
        if not note_time:
            continue
        note_date = note_time.date()
        if period_start <= note_date <= period_end:
            filtered.append(note)

    return sorted(
        filtered,
        key=lambda item: parse_note_datetime(item.get("time")) or datetime.min,
        reverse=True,
    )


def build_period_stats(
    profile: dict[str, Any],
    period_notes: list[dict[str, Any]],
    scanned_notes: list[dict[str, Any]],
    period_start: date | None,
    period_end: date | None,
    reached_range_start: bool,
) -> dict[str, Any]:
    period_totals = {
        target_key: sum(int(note.get(target_key) or 0) for note in period_notes)
        for target_key in NOTE_COUNT_FIELDS.values()
    }
    return {
        "followers_display": profile.get("fans_count_display", ""),
        "followers_count": profile.get("fans_count_lower_bound", 0),
        "period_start": period_start.isoformat() if period_start else "",
        "period_end": period_end.isoformat() if period_end else "",
        "period_note_count": len(period_notes),
        "period_liked_total": period_totals["liked_count"],
        "period_collected_total": period_totals["collected_count"],
        "period_comment_total": period_totals["comment_count"],
        "period_share_total": period_totals["share_count"],
        "scanned_note_count": len(scanned_notes),
        "reached_range_start": reached_range_start,
    }


def oldest_known_note_date(notes: list[dict[str, Any]]) -> date | None:
    note_dates = [
        parsed.date()
        for note in notes
        if (parsed := parse_note_datetime(note.get("time"))) is not None
    ]
    return min(note_dates) if note_dates else None


async def collect_notes_until_period(
    page: Any,
    profile: dict[str, Any],
    initial_state: dict[str, Any],
    period_start: date,
    drain_response_tasks: Any | None = None,
    get_response_note_items: Any | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    notes_by_id: dict[str, dict[str, Any]] = {}

    def add_notes(raw_notes: list[dict[str, Any]]) -> None:
        for note in raw_notes:
            note_id = str(note.get("note_id") or "")
            if not note_id:
                continue
            if note_id in notes_by_id:
                merge_note(notes_by_id[note_id], note)
            else:
                notes_by_id[note_id] = note

    def add_state_notes(state: dict[str, Any]) -> None:
        add_notes(notes_from_state(profile, state))

    def add_response_notes() -> None:
        if not get_response_note_items:
            return
        add_notes([normalize_note(item, profile) for item in get_response_note_items()])

    async def add_dom_notes() -> None:
        add_notes([normalize_note(item, profile) for item in await extract_dom_note_items(page)])

    add_state_notes(initial_state)
    add_response_notes()
    await add_dom_notes()
    idle_rounds = 0
    reached_range_start = False

    for _ in range(MAX_PROFILE_SCROLLS):
        notes = list(notes_by_id.values())
        oldest_date = oldest_known_note_date(notes)
        if oldest_date and oldest_date < period_start:
            reached_range_start = True
            break

        before_count = len(notes_by_id)
        await page.mouse.wheel(0, 2200)
        await page.wait_for_timeout(1200)
        if drain_response_tasks:
            await drain_response_tasks()
            add_response_notes()
        await add_dom_notes()

        state = await read_initial_state(page)
        if state:
            add_state_notes(state)
            add_response_notes()
            await add_dom_notes()

        if len(notes_by_id) == before_count:
            idle_rounds += 1
            if idle_rounds >= SCROLL_IDLE_ROUNDS:
                break
        else:
            idle_rounds = 0

    notes = list(notes_by_id.values())
    oldest_date = oldest_known_note_date(notes)
    if oldest_date and oldest_date < period_start:
        reached_range_start = True
    return notes, reached_range_start


async def scrape_account_profile(
    browser: XhsBrowser,
    account: AccountRef,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    period_start, period_end = normalize_period(start_date, end_date)
    context, page = await browser.new_page()
    response_payloads: list[Any] = []
    response_tasks: set[asyncio.Task] = set()

    async def capture_response(response: Any) -> None:
        if "xiaohongshu.com" not in response.url or "/api/" not in response.url:
            return
        try:
            payload = await response.json()
        except Exception:
            return
        response_payloads.append(payload)

    def schedule_response_capture(response: Any) -> None:
        task = asyncio.create_task(capture_response(response))
        response_tasks.add(task)
        task.add_done_callback(response_tasks.discard)

    async def drain_response_tasks() -> None:
        if response_tasks:
            await asyncio.gather(*list(response_tasks), return_exceptions=True)

    def get_response_note_items() -> list[dict[str, Any]]:
        return extract_note_items(response_payloads)

    page.on("response", schedule_response_capture)
    try:
        page.set_default_navigation_timeout(BROWSER_TIMEOUT_MS)
        await page.goto(account.profile_url, wait_until="commit")
        deadline = time.monotonic() + PROFILE_PAGE_LOGIN_WAIT_MS / 1000.0
        first_poll = True
        state: dict[str, Any] | None = None
        dom_note_items: list[dict[str, Any]] = []
        while True:
            wait_ms = 1500 if first_poll else PROFILE_PAGE_POLL_MS
            first_poll = False
            await page.wait_for_timeout(wait_ms)
            await drain_response_tasks()

            raw_state = await read_initial_state(page)
            dom_profile_data = await extract_dom_profile_data(page)
            dom_note_items = await extract_dom_note_items(page)
            state = merge_extracted_state(
                raw_state,
                merge_profile_data(extract_profile_data(response_payloads), dom_profile_data),
                get_response_note_items() + dom_note_items,
            )
            if profile_page_content_ready(response_payloads, state, dom_note_items):
                break
            if time.monotonic() >= deadline:
                break

        assert state is not None
        if not has_profile_or_notes(state):
            raise RuntimeError("未能从页面读取小红书初始数据，可能被登录墙或风控拦截。")

        user_state = state.get("user") or {}
        user_page_data = user_state.get("userPageData") or {}
        profile = profile_summary(
            account.user_id,
            user_page_data,
            fallback_nickname=account.nickname,
        )
        notes, reached_range_start = await collect_notes_until_period(
            page,
            profile,
            state,
            period_start,
            drain_response_tasks,
            get_response_note_items,
        )
        await enrich_approximate_note_counts(
            page,
            filter_notes_by_period(notes, period_start, period_end),
        )
        result = parse_profile_state(
            account,
            state,
            notes=notes,
            period_start=period_start,
            period_end=period_end,
            reached_range_start=reached_range_start,
        )
        if not result["notes"] and not result["stats"]["followers_display"]:
            raise RuntimeError("未能读取账号资料或笔记，可能页面结构变化、登录态失效或触发风控。")
        return result
    finally:
        await context.close()

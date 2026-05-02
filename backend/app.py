from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.config import (
    FRONTEND_ORIGIN_REGEX,
    FRONTEND_ORIGINS,
    ensure_runtime_dirs,
)
from backend.services.account_resolver import load_account_map, resolve_account
from backend.services.cache import JsonCache
from backend.services.xhs_browser import XhsBrowser
from backend.services.xhs_scraper import scrape_account_profile
from backend.services.xhs_session import XhsLoginSession


browser = XhsBrowser()
cache = JsonCache()
login_session = XhsLoginSession()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_runtime_dirs()
    yield
    await login_session.close()
    await browser.stop()


app = FastAPI(title="XHS Analysis API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_origin_regex=FRONTEND_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AccountRequest(BaseModel):
    account: str = Field(..., min_length=1, description="昵称、user_id 或小红书主页 URL")
    refresh: bool = Field(False, description="跳过缓存并重新抓取")
    start_date: date | None = Field(None, description="统计开始日期")
    end_date: date | None = Field(None, description="统计结束日期")


class LoginStartRequest(BaseModel):
    url: str | None = Field(None, description="登录入口 URL")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        **login_session.status(),
    }


@app.get("/api/xhs/session")
async def session_status() -> dict[str, Any]:
    return login_session.status()


@app.post("/api/xhs/session/login/start")
async def start_login(payload: LoginStartRequest | None = None) -> dict[str, Any]:
    try:
        if payload and payload.url:
            return await login_session.start(payload.url)
        return await login_session.start()
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/xhs/session/login/screenshot")
async def login_screenshot() -> Response:
    try:
        image = await login_session.screenshot()
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/xhs/session/login/save")
async def save_login() -> dict[str, Any]:
    try:
        status = await login_session.save()
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    await browser.stop()
    return status


@app.get("/api/accounts")
async def list_accounts() -> dict[str, str]:
    return load_account_map()


@app.post("/api/accounts/resolve")
async def resolve_account_api(payload: AccountRequest) -> dict[str, str]:
    try:
        return resolve_account(payload.account).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/xhs/profile")
async def profile(payload: AccountRequest) -> dict[str, Any]:
    try:
        account = resolve_account(payload.account)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if payload.start_date and payload.end_date and payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    start_date = payload.start_date.isoformat() if payload.start_date else ""
    end_date = payload.end_date.isoformat() if payload.end_date else ""
    cache_key = f"profile:v2:{account.user_id}:{start_date}:{end_date}"
    if not payload.refresh:
        cached = cache.get(cache_key)
        if cached:
            return {**cached, "cached": True}

    try:
        result = await scrape_account_profile(
            browser,
            account,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    cache.set(cache_key, result)
    return {**result, "cached": False}

from __future__ import annotations

import argparse
import asyncio

from backend.config import XHS_BASE_URL
from backend.services.xhs_session import XhsLoginSession


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="打开小红书并保存 Playwright 登录态。")
    parser.add_argument(
        "--url",
        default=XHS_BASE_URL,
        help=f"登录入口 URL，默认：{XHS_BASE_URL}",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    session = XhsLoginSession()
    try:
        await session.start(args.url)
        print("请在打开的浏览器中完成小红书登录。")
        await asyncio.to_thread(input, "登录完成后回到终端按回车保存登录态...")

        status = await session.save()
    finally:
        await session.close()

    print(f"登录态已保存到：{status['storage_state']}")


if __name__ == "__main__":
    asyncio.run(main())

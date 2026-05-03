from __future__ import annotations

import os

import uvicorn

from backend.app import app


def main() -> None:
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.getenv("BACKEND_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()

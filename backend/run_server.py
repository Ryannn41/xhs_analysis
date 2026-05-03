from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(
        "backend.app:app",
        host=host,
        port=port,
        log_level=os.getenv("BACKEND_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()

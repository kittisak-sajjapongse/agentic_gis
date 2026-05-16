from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="04_hand_off API", version="0.1.0")

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return app


app = create_app()


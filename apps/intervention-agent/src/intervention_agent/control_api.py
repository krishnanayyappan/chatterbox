from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_control_api(db_path: str | None = None) -> FastAPI:
    database = db_path or os.getenv("INTERVENTION_DB", "data/intervention.sqlite3")
    app = FastAPI(title="Quiet Agent Control API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"ok": Path(database).exists()}

    @app.get("/evaluations")
    def evaluations(limit: int = 40) -> list[dict]:
        if not Path(database).exists():
            return []
        connection = sqlite3.connect(f"file:{Path(database).as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """SELECT eval_id, ts, channel, in_thread, trigger, arm_selected,
                   arm_before_downgrade, confidence, reason, suppressed_by, posted, outcome
                   FROM evaluations ORDER BY rowid DESC LIMIT ?""",
                (min(max(limit, 1), 100),),
            ).fetchall()
            return [{**dict(row), "in_thread": bool(row["in_thread"]), "posted": bool(row["posted"]), "outcome": json.loads(row["outcome"])} for row in rows]
        finally:
            connection.close()

    return app


def run_control_api() -> None:
    import uvicorn

    uvicorn.run(create_control_api(), host="127.0.0.1", port=int(os.getenv("CONTROL_API_PORT", "8765")), log_level="warning")

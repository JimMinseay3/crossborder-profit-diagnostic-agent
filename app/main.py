import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .agent import run
from .models import RunRecord, RunRequest
from .storage import RunStore

BASE_DIR = Path(__file__).resolve().parents[1]


def _load_local_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env(BASE_DIR / ".env")
database_path = Path(os.getenv("DATABASE_PATH", ".data/agent.db"))
if not database_path.is_absolute():
    database_path = BASE_DIR / database_path
store = RunStore(database_path)
app = FastAPI(title="利润异常诊断 Agent", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"title": app.title})


@app.get("/health")
def health():
    return {"status": "ok", "agent": "profit-diagnostic", "provider": os.getenv("MODEL_PROVIDER", "mock")}


@app.get("/api/examples")
def examples():
    return [
        {"id": path.name, "label": path.stem}
        for path in sorted((BASE_DIR / "samples").iterdir())
        if path.is_file()
    ]


@app.post("/api/runs", response_model=RunRecord)
def create_run(payload: RunRequest):
    try:
        outcome = run(payload, BASE_DIR)
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record = RunRecord(
        run_id=str(uuid4()),
        status="completed",
        created_at=datetime.now(timezone.utc).isoformat(),
        run_mode="offline" if outcome["model_provider"] != "openai" else "model-enhanced",
        **outcome,
    )
    store.save(record)
    return record


@app.get("/api/runs", response_model=list[RunRecord])
def list_runs():
    return store.list()


@app.get("/api/runs/{run_id}", response_model=RunRecord)
def get_run(run_id: str):
    record = store.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="运行记录不存在。")
    return record


@app.get("/api/runs/{run_id}/export")
def export_run(run_id: str):
    record = store.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="运行记录不存在。")
    return JSONResponse(
        record.model_dump(mode="json"),
        headers={"Content-Disposition": f'attachment; filename="{run_id}.json"'},
    )

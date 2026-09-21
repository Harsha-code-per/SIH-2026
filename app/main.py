"""Sovereign AI Workbench -- API surface.

Everything the UI needs, and nothing it does not: route a request, stream the
agent trace, prove containment.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .router import Router
from .egress import EgressMonitor

ROOT = Path(__file__).resolve().parent.parent
UPLOADS = ROOT / "data" / "uploads"
OUT = ROOT / "data" / "out"
MODE = os.environ.get("MODE", "prototype")

router = Router(mode=MODE)
monitor = EgressMonitor(allowlist=router.mode_cfg.get("egress_allow") or [], mode=MODE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await monitor.start()
    yield


app = FastAPI(title="Sovereign AI Workbench", lifespan=lifespan)


@app.get("/api/status")
async def status():
    return {
        "mode": MODE,
        "endpoint": router.mode_cfg["endpoint"],
        "egress": monitor.snapshot(),
        "models": [
            {"id": m["id"], "tier": m["tier"], "caps": m["caps"],
             "name": router.resolve(m), "why": m["why"]}
            for m in router.models
        ],
        "rules": [{"name": r["name"], "why": r["why"]} for r in router.routing_rules],
    }


@app.post("/api/registry/reload")
async def reload_registry():
    """Re-read models.yaml. This is the 'add a model without redesign' proof."""
    before = {m["id"] for m in router.models}
    router.reload()
    after = {m["id"] for m in router.models}
    return {"added": sorted(after - before), "removed": sorted(before - after),
            "models": sorted(after)}


@app.post("/api/route")
async def preview_route(prompt: str = Form(...), has_image: bool = Form(False)):
    """Routing decision without executing it -- used by the UI's router panel."""
    return router.route(prompt, has_image=has_image).as_dict()


@app.post("/api/tripwire")
async def tripwire(target: str = Form("https://api.openai.com/v1/models")):
    return await monitor.tripwire(target)


@app.get("/api/egress/stream")
async def egress_stream():
    """Live tail of observed outbound traffic."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    monitor.subscribers.add(q)

    async def gen():
        try:
            yield f"data: {json.dumps({'type': 'snapshot', **monitor.snapshot()})}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps({'type': 'egress', **ev.as_dict()})}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            monitor.subscribers.discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    UPLOADS.mkdir(parents=True, exist_ok=True)
    dest = UPLOADS / Path(file.filename or "upload.bin").name
    dest.write_bytes(await file.read())
    return {"path": str(dest.relative_to(ROOT)), "bytes": dest.stat().st_size}


@app.get("/api/download/{name}")
async def download(name: str):
    p = OUT / Path(name).name
    if not p.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(p, filename=p.name)


app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")

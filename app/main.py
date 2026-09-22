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

from . import audit
from .agent import Agent
from .egress import EgressMonitor
from .kb import KB
from .llm import LLM, load_dotenv
from .router import Router

ROOT = Path(__file__).resolve().parent.parent
UPLOADS = ROOT / "data" / "uploads"
OUT = ROOT / "data" / "out"
MODE = os.environ.get("MODE", "prototype")

load_dotenv(ROOT / ".env")
router = Router(mode=MODE)
monitor = EgressMonitor(allowlist=router.mode_cfg.get("egress_allow") or [], mode=MODE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await monitor.start()
    # A fresh clone has documents but no index. Build it rather than serving an
    # empty knowledge base, which would make every task ungrounded on first run.
    if not KB.load() and any((ROOT / "data" / "kb").glob("*.md")):
        stats = await asyncio.to_thread(KB.build)
        audit.record("kb.built_on_startup", **stats)
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
             "name": router.resolve(m), "why": m["why"],
             "max_tokens": m.get("max_tokens")}
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
    r = await monitor.tripwire(target)
    audit.record("tripwire", **r)
    return r


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


@app.post("/api/run")
async def run(prompt: str = Form(...), has_image: bool = Form(False)):
    """Execute a task, streaming every step as it happens.

    The trace is the product as much as the answer is: an engineer approving a
    note needs to see which SOP clause was retrieved and what was computed, not
    just the conclusion.
    """
    q: asyncio.Queue = asyncio.Queue()
    audit.record("task.received", prompt=prompt[:500], mode=MODE)

    async def gen():
        # Steps are emitted from the event-loop thread, so queue them directly.
        # Going through call_soon_threadsafe would schedule them *after* the
        # sentinel that drive() puts in synchronously, and a fast run would
        # stream its result with no visible trace at all.
        agent = Agent(router, LLM(router), on_step=q.put_nowait)

        async def drive():
            try:
                return await agent.run(prompt, has_image=has_image)
            finally:
                q.put_nowait(None)

        task = asyncio.create_task(drive())
        while True:
            item = await q.get()
            if item is None:
                break
            d = item.as_dict()
            audit.record(f"step.{d.pop('kind')}", **d)
            yield f"data: {json.dumps({'type': 'step', **item.as_dict()}, default=str)}\n\n"
        try:
            final = await task
        except Exception as e:
            audit.record("task.failed", error=f"{type(e).__name__}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': f'{type(e).__name__}: {e}'})}\n\n"
            return
        audit.record("task.completed", verdict=final.get("verdict"),
                     model=final["decision"].get("model_name"),
                     deliverables=[d["path"] for d in final["deliverables"]])
        yield f"data: {json.dumps({'type': 'final', **final}, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.post("/api/kb/build")
async def kb_build():
    stats = await asyncio.to_thread(KB.build)
    audit.record("kb.rebuilt", **stats)
    return stats


@app.get("/api/kb/search")
async def kb_search(q: str, k: int = 6):
    if KB.vectors is None:
        KB.load()
    return {"query": q, "passages": KB.search(q, k=k)}


@app.get("/api/kb/documents")
async def kb_documents():
    if KB.vectors is None:
        KB.load()
    docs: dict[str, int] = {}
    for c in KB.chunks:
        docs[c.doc] = docs.get(c.doc, 0) + 1
    return {"chunks": len(KB.chunks),
            "documents": [{"name": d, "chunks": n} for d, n in sorted(docs.items())]}


@app.get("/api/audit")
async def audit_log(n: int = 150):
    return {"entries": audit.tail(n)}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    UPLOADS.mkdir(parents=True, exist_ok=True)
    dest = UPLOADS / Path(file.filename or "upload.bin").name
    dest.write_bytes(await file.read())
    audit.record("upload", name=dest.name, bytes=dest.stat().st_size)
    return {"path": str(dest.relative_to(ROOT)), "bytes": dest.stat().st_size}


@app.get("/api/download/{name}")
async def download(name: str):
    p = OUT / Path(name).name
    if not p.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(p, filename=p.name)


app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")

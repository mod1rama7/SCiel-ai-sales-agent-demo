import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import database
from app.core.agent import run_agent

app = FastAPI(title="AI Sales Agent — بيت القهوة")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PRODUCTS: list = json.loads(Path("data/products.json").read_text(encoding="utf-8"))
_sessions: dict[str, list] = {}

database.init_db()

app.mount("/demo", StaticFiles(directory="demo", html=True), name="demo")


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class StatusUpdate(BaseModel):
    status: str


VALID_STATUSES = {"pending", "confirmed", "delivered", "cancelled"}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/demo/index.html")


@app.post("/chat")
def chat(req: ChatRequest):
    import traceback
    history = _sessions.get(req.session_id, [])
    message = req.message if req.message != "__init__" else "مرحباً"
    try:
        reply, new_history = run_agent(message, history, PRODUCTS)
        _sessions[req.session_id] = new_history
        return {"reply": reply}
    except Exception as e:
        traceback.print_exc()
        return {"reply": None, "error": str(e)}


@app.get("/api/products")
def get_products():
    return PRODUCTS


@app.get("/api/orders")
def get_orders():
    return database.get_orders()


@app.get("/api/stats")
def get_stats():
    return database.get_stats()


@app.put("/api/orders/{order_id}/status")
def update_status(order_id: int, body: StatusUpdate):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of {VALID_STATUSES}")
    database.update_order_status(order_id, body.status)
    return {"success": True}

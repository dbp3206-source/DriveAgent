"""Isolated UI fixture server: no DB, secrets, model, Google access or real writes.

Run with uvicorn on 127.0.0.1:8002 only. This serves the REAL frontend build with
explicitly labelled synthetic API data; it does not prove Google integration.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()
state = "pending"
proposals = [
    {"id": "qa-doc", "kind": "document", "document": {
        "title": "Mẫu QA — kế hoạch ôn tập", "blocks": [
            {"text": "Tuần 1: ôn tập và tự kiểm tra. Đây là dữ liệu giả lập.", "style": "NORMAL_TEXT"}
        ],
    }},
    {"id": "qa-sheet", "kind": "spreadsheet", "spreadsheet": {
        "title": "Mẫu QA — chi tiêu", "tabs": [{
            "title": "Dữ liệu minh họa", "headers": ["Mục", "Số tiền"],
            "rows": [["Sách", 120], ["Xe buýt", 30]],
            "chart": {"title": "Chi tiêu minh họa", "kind": "COLUMN", "label_column": 0, "value_column": 1},
        }],
    }},
]


@app.get("/api/auth/status")
def auth():
    return {"authenticated": True, "user": {
        "id": "qa", "email": "qa@example.invalid", "display_name": "QA — dữ liệu giả lập",
        "role": "owner", "scopes": [], "avatar_url": None,
    }}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/chat/sessions")
def sessions():
    return [{"id": "qa-session", "title": "KIỂM THỬ UI GIẢ LẬP", "updated_at": "2026-09-08T00:00:00Z"}]


@app.get("/api/chat/sessions/qa-session/messages")
def messages():
    return [{"id": "qa-message", "role": "assistant", "content": "KIỂM THỬ GIẢ LẬP — không tạo file Google thật.",
             "trace": [], "citations": [], "proposals": proposals, "created_at": "2026-09-08T00:00:00Z"}]


@app.post("/api/creation/proposals/{proposal_id}/prepare")
def prepare(proposal_id: str):
    return {"data": {"operation_id": proposal_id, "digest": "qa-only", "state": state}}


@app.get("/api/{kind}/operations/{operation_id}")
def status(kind: str, operation_id: str):
    return {"state": state, "result": None}


@app.post("/api/{kind}/approve")
def approve(kind: str):
    global state
    state = "succeeded"
    return {"data": {"verified": False}}


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "frontend/dist", html=True))

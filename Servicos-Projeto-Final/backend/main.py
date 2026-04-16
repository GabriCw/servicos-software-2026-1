import json
import os
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent import agent

sessions: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[STARTUP] provider={os.getenv('LLM_PROVIDER')} model={os.getenv('LLM_MODEL')}")
    yield


app = FastAPI(title="ViajaFácil API", lifespan=lifespan)


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    used_historical: bool


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        history = sessions.get(req.session_id, [])
        print(f"[CHAT] session={req.session_id[:8]}... | msg={req.message!r}")
        result = await agent.run(req.message, message_history=history)
        sessions[req.session_id] = result.all_messages()
        print(f"[CHAT] resposta gerada | histórico_sessão={len(sessions[req.session_id])} msgs")

        used_historical = False
        for msg in result.new_messages():
            for part in getattr(msg, "parts", []):
                content = getattr(part, "content", "")
                if isinstance(content, str) and '"used_historical": true' in content:
                    used_historical = True

        return ChatResponse(reply=result.output, used_historical=used_historical)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

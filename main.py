from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, select, func
from datetime import datetime, timezone, timedelta
import os
import time
import httpx

app = FastAPI(title="ALLaM Chat")

# ── Database ───────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./chat.db")
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Conversation(Base):
    __tablename__ = "conversations"
    id            = Column(Integer, primary_key=True)
    prompt        = Column(Text)
    response      = Column(Text)
    response_time = Column(Float)   # seconds
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ── HuggingFace config ─────────────────────────────────────
HF_TOKEN  = os.getenv("HF_TOKEN", "")
HF_MODEL  = "humain-ai/ALLaM-7B-Instruct-preview"
HF_URL    = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

# ── Request models ─────────────────────────────────────────
class ChatRequest(BaseModel):
    prompt: str

# ── Routes ─────────────────────────────────────────────────
@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": req.prompt,
        "parameters": {
            "max_new_tokens": 512,
            "temperature": 0.7,
            "return_full_text": False,
        }
    }

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(HF_URL, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"ALLaM API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    elapsed = round(time.time() - start, 2)

    # extract text from response
    if isinstance(data, list) and data:
        response_text = data[0].get("generated_text", "").strip()
    else:
        response_text = str(data)

    # save to database
    async with AsyncSessionLocal() as session:
        entry = Conversation(
            prompt=req.prompt,
            response=response_text,
            response_time=elapsed,
        )
        session.add(entry)
        await session.commit()

    return {
        "response":      response_text,
        "response_time": elapsed,
    }

@app.get("/api/history")
async def history():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Conversation).order_by(Conversation.created_at.desc()).limit(50)
        )
        rows = result.scalars().all()
    return {
        "history": [
            {
                "id":            r.id,
                "prompt":        r.prompt,
                "response":      r.response,
                "response_time": r.response_time,
                "created_at":    r.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for r in rows
        ]
    }

@app.get("/api/insights")
async def insights():
    now      = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    async with AsyncSessionLocal() as session:
        # total conversations
        total_result = await session.execute(select(func.count(Conversation.id)))
        total = total_result.scalar() or 0

        # average response time
        avg_result = await session.execute(select(func.avg(Conversation.response_time)))
        avg_time = round(avg_result.scalar() or 0, 2)

        # fastest response
        fast_result = await session.execute(select(func.min(Conversation.response_time)))
        fastest = round(fast_result.scalar() or 0, 2)

        # conversations this week
        week_result = await session.execute(
            select(func.count(Conversation.id)).where(Conversation.created_at >= week_ago)
        )
        this_week = week_result.scalar() or 0

        # usage per day this week
        daily_result = await session.execute(
            select(
                func.date(Conversation.created_at).label("day"),
                func.count(Conversation.id).label("count")
            )
            .where(Conversation.created_at >= week_ago)
            .group_by(func.date(Conversation.created_at))
            .order_by(func.date(Conversation.created_at))
        )
        daily = [{"day": str(r.day), "count": r.count} for r in daily_result.fetchall()]

        # recent prompts (last 5)
        recent_result = await session.execute(
            select(Conversation.prompt, Conversation.created_at)
            .order_by(Conversation.created_at.desc())
            .limit(5)
        )
        recent_prompts = [
            {"prompt": r.prompt[:60] + "..." if len(r.prompt) > 60 else r.prompt,
             "time": r.created_at.strftime("%H:%M")}
            for r in recent_result.fetchall()
        ]

    return {
        "total":          total,
        "avg_time":       avg_time,
        "fastest":        fastest,
        "this_week":      this_week,
        "daily":          daily,
        "recent_prompts": recent_prompts,
    }

app.mount("/static", StaticFiles(directory="static"), name="static")
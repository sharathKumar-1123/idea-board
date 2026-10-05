import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .db import Base, engine, get_session
from .models import Idea

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("idea-board")


def wait_for_db(retries: int = 10, delay: float = 3.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as exc:
            log.warning("database not ready (attempt %d/%d): %s", attempt, retries, exc)
            if attempt == retries:
                raise
            time.sleep(delay)


@asynccontextmanager
async def lifespan(_: FastAPI):
    wait_for_db()
    Base.metadata.create_all(engine)
    log.info("database ready")
    yield


app = FastAPI(title="Idea Board API", lifespan=lifespan)

SessionDep = Annotated[Session, Depends(get_session)]
IdeaContent = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class IdeaIn(BaseModel):
    content: IdeaContent


class IdeaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    created_at: datetime


@app.get("/health")
@app.get("/api/health")
def health(session: SessionDep) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        log.error("health check failed: %s", exc)
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok"}


@app.get("/api/ideas", response_model=list[IdeaOut])
def list_ideas(session: SessionDep) -> list[Idea]:
    return list(session.scalars(select(Idea).order_by(Idea.created_at.desc(), Idea.id.desc())))


@app.post("/api/ideas", response_model=IdeaOut, status_code=201)
def create_idea(payload: IdeaIn, session: SessionDep) -> Idea:
    idea = Idea(content=payload.content)
    session.add(idea)
    session.commit()
    session.refresh(idea)
    return idea

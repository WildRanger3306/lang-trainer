from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.cards import card_view
from app.db import connect
from app.progress import save_grade
from app.repository import fetch_candidates, fetch_filter_options
from app.session import SESSION_SIZE, SessionFilter, pick_cards
from app.store import SessionStore

ROOT = Path(__file__).resolve().parents[1]
COOKIE = "train_session"

app = FastAPI(title="lang-trainer")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))
store = SessionStore()


def _format_duration(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    if minutes == 0:
        return f"{secs} с"
    return f"{minutes} мин {secs} с"


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def filter_page(request: Request, error: str | None = None) -> HTMLResponse:
    with connect() as conn:
        options = fetch_filter_options(conn)
    return templates.TemplateResponse(
        request,
        "filter.html",
        {
            "error": error,
            "options": options,
            "language": "en",
            "selected_textbooks": [],
            "selected_topics": [],
            "selected_levels": [],
        },
    )


@app.post("/start")
def start_session(
    language: str = Form(...),
    textbook: list[str] | None = Form(default=None),
    topic: list[str] | None = Form(default=None),
    level: list[str] | None = Form(default=None),
) -> RedirectResponse:
    try:
        flt = SessionFilter(
            language=language,
            textbooks=tuple(textbook or ()),
            topics=tuple(topic or ()),
            levels=tuple(level or ()),
        )
    except ValueError:
        return RedirectResponse("/?error=Выберите+язык", status_code=303)

    with connect() as conn:
        pool = fetch_candidates(conn, flt)
        picked = pick_cards(pool, flt.size, random.Random())

    if not picked:
        return RedirectResponse("/?error=Нет+карточек+по+фильтру", status_code=303)

    token = store.create(picked)
    response = RedirectResponse("/train", status_code=303)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax")
    return response


@app.get("/train", response_class=HTMLResponse, response_model=None)
def train_page(request: Request) -> HTMLResponse | RedirectResponse:
    session = store.get(request.cookies.get(COOKIE))
    if session is None:
        return RedirectResponse("/", status_code=303)
    if session.done:
        return RedirectResponse("/done", status_code=303)
    card = session.current
    assert card is not None
    return templates.TemplateResponse(
        request,
        "train.html",
        {
            "view": card_view(card),
            "number": session.number,
            "total": session.total,
        },
    )


@app.post("/grade")
def grade_card(request: Request, remembered: str = Form(...)) -> RedirectResponse:
    session = store.get(request.cookies.get(COOKIE))
    if session is None or session.current is None:
        return RedirectResponse("/", status_code=303)

    card = session.current
    knew = remembered == "1"
    with connect() as conn:
        save_grade(conn, card, knew)

    if knew:
        session.known += 1
    else:
        session.unknown += 1
    session.index += 1
    if session.done:
        session.finished_at = datetime.now()
        return RedirectResponse("/done", status_code=303)
    return RedirectResponse("/train", status_code=303)


@app.post("/finish")
def finish_session(request: Request) -> RedirectResponse:
    session = store.get(request.cookies.get(COOKIE))
    if session is None:
        return RedirectResponse("/", status_code=303)
    session.finish()
    return RedirectResponse("/done", status_code=303)


@app.get("/done", response_class=HTMLResponse, response_model=None)
def done_page(request: Request) -> HTMLResponse | RedirectResponse:
    session = store.get(request.cookies.get(COOKIE))
    if session is None or not session.done:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "done.html",
        {
            "known": session.known,
            "unknown": session.unknown,
            "total": session.answered,
            "started_at": session.started_at.strftime("%d.%m.%Y %H:%M"),
            "duration": _format_duration(session.duration_seconds),
        },
    )


@app.get("/session")
def create_session_json(
    language: str,
    textbook: list[str] | None = Query(default=None),
    topic: list[str] | None = Query(default=None),
    level: list[str] | None = Query(default=None),
    seed: int | None = None,
    size: int = SESSION_SIZE,
) -> dict:
    try:
        flt = SessionFilter(
            language=language,
            textbooks=tuple(textbook or ()),
            topics=tuple(topic or ()),
            levels=tuple(level or ()),
            size=size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rng = random.Random(seed)
    with connect() as conn:
        pool = fetch_candidates(conn, flt)
        picked = pick_cards(pool, flt.size, rng)

    return {
        "filter": {
            "language": flt.language,
            "textbooks": list(flt.textbooks),
            "topics": list(flt.topics),
            "levels": list(flt.levels),
        },
        "pool_size": len(pool),
        "cards": [
            {
                "entry_id": card.entry_id,
                "direction": card.direction,
                "language": card.language,
                "form": card.form,
                "part_of_speech": card.part_of_speech,
                "part_of_speech_code": card.part_of_speech_code,
                "transcription": card.transcription,
                "gender": card.gender,
                "translations": list(card.translations),
                "streak": card.streak,
                "weight": card.weight,
            }
            for card in picked
        ],
    }

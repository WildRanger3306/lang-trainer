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
from app.progress import count_introduced_today, save_assessment, save_grade
from app.queue import build_assessment_cards, build_session_cards
from app.repository import fetch_filter_options, fetch_queue_preview
from app.scheduler import ASSESS_BATCH, ASSESS_KNOW_INTERVAL, ASSESS_VERDICTS, new_per_day, preferred_direction
from app.session import SessionFilter
from app.stats import build_language_summary
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


def _parse_filter(
    language: str,
    textbook: list[str] | None,
    topic: list[str] | None,
    level: list[str] | None,
) -> SessionFilter | RedirectResponse:
    try:
        return SessionFilter(
            language=language,
            textbooks=tuple(textbook or ()),
            topics=tuple(topic or ()),
            levels=tuple(level or ()),
        )
    except ValueError:
        return RedirectResponse("/?error=Выберите+язык", status_code=303)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def filter_page(request: Request, error: str | None = None) -> HTMLResponse:
    language = request.query_params.get("language") or "en"
    if language not in ("en", "fr"):
        language = "en"
    with connect() as conn:
        options = fetch_filter_options(conn)
        preview = fetch_queue_preview(conn, SessionFilter(language=language))
    return templates.TemplateResponse(
        request,
        "filter.html",
        {
            "error": error,
            "options": options,
            "language": language,
            "selected_textbooks": [],
            "selected_topics": [],
            "selected_levels": [],
            "preview": preview,
            "new_per_day": new_per_day(language),
            "preferred_direction": preferred_direction(language),
            "assess_batch": ASSESS_BATCH,
            "assess_know_interval": ASSESS_KNOW_INTERVAL,
        },
    )


@app.post("/start")
def start_session(
    language: str = Form(...),
    textbook: list[str] | None = Form(default=None),
    topic: list[str] | None = Form(default=None),
    level: list[str] | None = Form(default=None),
) -> RedirectResponse:
    flt = _parse_filter(language, textbook, topic, level)
    if isinstance(flt, RedirectResponse):
        return flt

    with connect() as conn:
        picked, due_n, new_n = build_session_cards(conn, flt, random.Random())

    if not picked:
        return RedirectResponse(
            f"/?language={language}&error=Нет+карточек+на+сегодня",
            status_code=303,
        )

    token = store.create(picked, mode="train", due_at_start=due_n, new_at_start=new_n)
    response = RedirectResponse("/train", status_code=303)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax")
    return response


@app.post("/assess/start")
def start_assessment(
    language: str = Form(...),
    textbook: list[str] | None = Form(default=None),
    topic: list[str] | None = Form(default=None),
    level: list[str] | None = Form(default=None),
) -> RedirectResponse:
    flt = _parse_filter(language, textbook, topic, level)
    if isinstance(flt, RedirectResponse):
        return flt

    with connect() as conn:
        picked, unassessed = build_assessment_cards(conn, flt, random.Random())

    if not picked:
        return RedirectResponse(
            f"/?language={language}&error=Нет+неоценённых+карточек",
            status_code=303,
        )

    token = store.create(
        picked,
        mode="assess",
        unassessed_at_start=unassessed,
    )
    response = RedirectResponse("/assess", status_code=303)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax")
    return response


@app.get("/train", response_class=HTMLResponse, response_model=None)
def train_page(request: Request) -> HTMLResponse | RedirectResponse:
    session = store.get(request.cookies.get(COOKIE))
    if session is None:
        return RedirectResponse("/", status_code=303)
    if session.mode != "train":
        return RedirectResponse("/assess", status_code=303)
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
            "is_new": card.is_new,
        },
    )


@app.get("/assess", response_class=HTMLResponse, response_model=None)
def assess_page(request: Request) -> HTMLResponse | RedirectResponse:
    session = store.get(request.cookies.get(COOKIE))
    if session is None:
        return RedirectResponse("/", status_code=303)
    if session.mode != "assess":
        return RedirectResponse("/train", status_code=303)
    if session.done:
        return RedirectResponse("/done", status_code=303)
    card = session.current
    assert card is not None
    return templates.TemplateResponse(
        request,
        "assess.html",
        {
            "view": card_view(card),
            "number": session.number,
            "total": session.total,
            "know_interval": ASSESS_KNOW_INTERVAL,
        },
    )


@app.post("/grade")
def grade_card(request: Request, remembered: str = Form(...)) -> RedirectResponse:
    session = store.get(request.cookies.get(COOKIE))
    if session is None or session.current is None or session.mode != "train":
        return RedirectResponse("/", status_code=303)

    card = session.current
    knew = remembered == "1"
    with connect() as conn:
        save_grade(conn, card, knew)

    if knew:
        session.known += 1
        session.index += 1
    else:
        session.unknown += 1
        session.index += 1
        # Again: show again later in this session; due is tomorrow in DB.
        from dataclasses import replace

        session.requeue(replace(card, is_new=False))

    if session.done:
        session.finished_at = datetime.now()
        return RedirectResponse("/done", status_code=303)
    return RedirectResponse("/train", status_code=303)


@app.post("/assess/grade")
def grade_assessment(request: Request, verdict: str = Form(...)) -> RedirectResponse:
    session = store.get(request.cookies.get(COOKIE))
    if session is None or session.current is None or session.mode != "assess":
        return RedirectResponse("/", status_code=303)
    if verdict not in ASSESS_VERDICTS:
        return RedirectResponse("/assess", status_code=303)

    card = session.current
    with connect() as conn:
        save_assessment(conn, card, verdict)

    if verdict == "know":
        session.known += 1
    elif verdict == "doubt":
        session.doubt += 1
    else:
        session.unknown += 1
    session.index += 1

    if session.done:
        session.finished_at = datetime.now()
        return RedirectResponse("/done", status_code=303)
    return RedirectResponse("/assess", status_code=303)


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
            "mode": session.mode,
            "known": session.known,
            "doubt": session.doubt,
            "unknown": session.unknown,
            "total": session.answered,
            "started_at": session.started_at.strftime("%d.%m.%Y %H:%M"),
            "duration": _format_duration(session.duration_seconds),
        },
    )


@app.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request, language: str = "en") -> HTMLResponse:
    if language not in ("en", "fr"):
        language = "en"
    with connect() as conn:
        summary = build_language_summary(conn, language)
    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "language": language,
            "summary": summary,
            "new_per_day": new_per_day(language),
            "preferred_direction": preferred_direction(language),
        },
    )


@app.get("/session")
def create_session_json(
    language: str,
    textbook: list[str] | None = Query(default=None),
    topic: list[str] | None = Query(default=None),
    level: list[str] | None = Query(default=None),
    seed: int | None = None,
) -> dict:
    try:
        flt = SessionFilter(
            language=language,
            textbooks=tuple(textbook or ()),
            topics=tuple(topic or ()),
            levels=tuple(level or ()),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rng = random.Random(seed)
    with connect() as conn:
        picked, due_n, new_n = build_session_cards(conn, flt, rng)
        introduced = count_introduced_today(conn, flt.language)

    return {
        "filter": {
            "language": flt.language,
            "textbooks": list(flt.textbooks),
            "topics": list(flt.topics),
            "levels": list(flt.levels),
        },
        "due_count": due_n,
        "new_in_session": new_n,
        "introduced_today": introduced,
        "new_per_day": new_per_day(flt.language),
        "preferred_direction": preferred_direction(flt.language),
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
                "is_new": card.is_new,
                "due_on": card.due_on.isoformat() if card.due_on else None,
                "interval_days": card.interval_days,
                "ease": card.ease,
            }
            for card in picked
        ],
    }

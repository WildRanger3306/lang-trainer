from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import AuthStore
from app.cards import card_view
from app.coach import coach_message, days_since_activity
from app.db import connect
from app.load_limits import get_new_per_day
from app.progress import count_introduced_today, save_assessment, save_grade
from app.queue import build_assessment_cards, build_session_cards
from app.repository import fetch_filter_options, fetch_queue_preview, fetch_textbook_banks
from app.scheduler import ASSESS_BATCH, ASSESS_KNOW_INTERVAL, ASSESS_VERDICTS, preferred_direction
from app.session import SessionFilter
from app.stats import (
    advise_load,
    build_language_summary,
    fetch_corpus_stats,
    fetch_load_stats,
    fetch_performance_stats,
    refresh_adaptive_load,
)
from app.store import SessionStore
from app.user_filters import (
    filter_summary,
    get_last_language,
    get_user_filter,
    save_user_filter,
    set_last_language,
)
from app.users import User, authenticate, get_user_by_id

ROOT = Path(__file__).resolve().parents[1]
COOKIE = "train_session"
AUTH_COOKIE = "auth_session"

app = FastAPI(title="lang-trainer")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))


def _asset(path: str) -> str:
    """Static URL with an mtime version so browsers never reuse a stale copy."""
    try:
        version = int((ROOT / "static" / path).stat().st_mtime)
    except OSError:
        version = 0
    return f"/static/{path}?v={version}"


templates.env.globals["asset"] = _asset
store = SessionStore()
auth_store = AuthStore()


def _format_duration(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    if minutes == 0:
        return f"{secs} с"
    return f"{minutes} мин {secs} с"


def _current_user(request: Request) -> User | None:
    session = auth_store.get(request.cookies.get(AUTH_COOKIE))
    if session is None:
        return None
    with connect() as conn:
        fresh = get_user_by_id(conn, session.user.id)
    return fresh or session.user


def _require_user(request: Request) -> User | RedirectResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return user


def _resolve_language(request: Request, user: User, conn) -> str:
    language = request.query_params.get("language")
    if language not in ("en", "fr"):
        language = get_last_language(conn, user.id) or "en"
    if language not in ("en", "fr"):
        language = "en"
    set_last_language(conn, user.id, language)
    return language


def _nav(user: User | None) -> dict:
    return {"user": user}


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/login", response_class=HTMLResponse, response_model=None)
def login_page(request: Request, error: str | None = None) -> HTMLResponse | RedirectResponse:
    if _current_user(request) is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": error},
    )


@app.post("/login")
def login_submit(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    with connect() as conn:
        user = authenticate(conn, login, password)
    if user is None:
        return RedirectResponse("/login?error=Неверный+логин+или+пароль", status_code=303)
    token = auth_store.create(user)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(AUTH_COOKIE, token, httponly=True, samesite="lax")
    return response


@app.post("/logout")
def logout(request: Request) -> RedirectResponse:
    auth_store.destroy(request.cookies.get(AUTH_COOKIE))
    store.destroy(request.cookies.get(COOKIE))
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(AUTH_COOKIE)
    response.delete_cookie(COOKIE)
    return response


@app.get("/", response_class=HTMLResponse, response_model=None)
def filter_page(request: Request, error: str | None = None) -> HTMLResponse | RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    with connect() as conn:
        language = _resolve_language(request, user, conn)
        adapt = refresh_adaptive_load(conn, user.id, language)
        flt = get_user_filter(conn, user.id, language)
        preview = fetch_queue_preview(conn, flt, user.id)
        daily_new = get_new_per_day(conn, user.id, language)
        load = fetch_load_stats(conn, user.id, language, new_per_day=daily_new)
        performance = fetch_performance_stats(conn, user.id, language)
        corpus = fetch_corpus_stats(conn, user.id, language)
        advice = advise_load(corpus, load, performance, language=language)
        since = days_since_activity(conn, user.id, language)
        coach = coach_message(
            user,
            language=language,
            load=load,
            advice=advice,
            performance=performance,
            days_since_active=since,
            adapt_note=adapt.note,
            # Same scope as chips below the text (active filter), not whole language.
            queue_due=preview.due_count,
            queue_new_left=preview.new_remaining_today,
        )
    return templates.TemplateResponse(
        request,
        "filter.html",
        {
            **_nav(user),
            "error": error,
            "language": language,
            "filter_label": filter_summary(flt),
            "preview": preview,
            "new_per_day": daily_new,
            "preferred_direction": preferred_direction(language),
            "assess_batch": ASSESS_BATCH,
            "assess_know_interval": ASSESS_KNOW_INTERVAL,
            "coach": coach,
        },
    )


@app.get("/filters", response_class=HTMLResponse, response_model=None)
def filters_page(
    request: Request, saved: str | None = None
) -> HTMLResponse | RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    with connect() as conn:
        language = _resolve_language(request, user, conn)
        options = fetch_filter_options(conn, language)
        flt = get_user_filter(conn, user.id, language)
    return templates.TemplateResponse(
        request,
        "filters.html",
        {
            **_nav(user),
            "language": language,
            "options": options,
            "selected_textbooks": list(flt.textbooks),
            "selected_topics": list(flt.topics),
            "saved": saved == "1",
        },
    )


@app.post("/filters")
def filters_save(
    request: Request,
    language: str = Form(...),
    textbook: list[str] | None = Form(default=None),
    topic: list[str] | None = Form(default=None),
) -> RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if language not in ("en", "fr"):
        return RedirectResponse("/filters?error=1", status_code=303)
    with connect() as conn:
        save_user_filter(
            conn,
            user.id,
            language,
            textbook or [],
            topic or [],
        )
        set_last_language(conn, user.id, language)
    return RedirectResponse(
        f"/filters?language={language}&saved=1", status_code=303
    )


@app.post("/start")
def start_session(
    request: Request,
    language: str = Form(...),
) -> RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if language not in ("en", "fr"):
        return RedirectResponse("/?error=Выберите+язык", status_code=303)

    with connect() as conn:
        set_last_language(conn, user.id, language)
        refresh_adaptive_load(conn, user.id, language)
        flt = get_user_filter(conn, user.id, language)
        picked, due_n, new_n = build_session_cards(conn, flt, user.id, random.Random())

    if not picked:
        return RedirectResponse(
            f"/?language={language}&error=Нет+карточек+на+сегодня",
            status_code=303,
        )

    token = store.create(
        picked, user_id=user.id, mode="train", due_at_start=due_n, new_at_start=new_n
    )
    response = RedirectResponse("/train", status_code=303)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax")
    return response


@app.post("/assess/start")
def start_assessment(
    request: Request,
    language: str = Form(...),
) -> RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if language not in ("en", "fr"):
        return RedirectResponse("/?error=Выберите+язык", status_code=303)

    with connect() as conn:
        set_last_language(conn, user.id, language)
        flt = get_user_filter(conn, user.id, language)
        picked, unassessed = build_assessment_cards(
            conn, flt, user.id, random.Random()
        )

    if not picked:
        return RedirectResponse(
            f"/?language={language}&error=Нет+неоценённых+карточек",
            status_code=303,
        )

    token = store.create(
        picked,
        user_id=user.id,
        mode="assess",
        unassessed_at_start=unassessed,
    )
    response = RedirectResponse("/assess", status_code=303)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax")
    return response


@app.get("/train", response_class=HTMLResponse, response_model=None)
def train_page(request: Request) -> HTMLResponse | RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    session = store.get(request.cookies.get(COOKIE))
    if session is None or session.user_id != user.id:
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
            **_nav(user),
            "view": card_view(card),
            "number": session.number,
            "total": session.total,
            "is_new": card.is_new,
        },
    )


@app.get("/assess", response_class=HTMLResponse, response_model=None)
def assess_page(request: Request) -> HTMLResponse | RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    session = store.get(request.cookies.get(COOKIE))
    if session is None or session.user_id != user.id:
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
            **_nav(user),
            "view": card_view(card),
            "number": session.number,
            "total": session.total,
            "know_interval": ASSESS_KNOW_INTERVAL,
        },
    )


@app.post("/grade")
def grade_card(request: Request, rating: str = Form(...)) -> RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    session = store.get(request.cookies.get(COOKIE))
    if (
        session is None
        or session.current is None
        or session.mode != "train"
        or session.user_id != user.id
    ):
        return RedirectResponse("/", status_code=303)

    from app.scheduler import TRAIN_RATINGS

    if rating not in TRAIN_RATINGS:
        return RedirectResponse("/train", status_code=303)

    card = session.current
    with connect() as conn:
        save_grade(conn, user.id, card, rating)

    session.index += 1
    if rating == "again":
        session.again += 1
        from dataclasses import replace

        session.requeue(replace(card, is_new=False))
    elif rating == "hard":
        session.hard += 1
    elif rating == "good":
        session.good += 1
    else:
        session.easy += 1

    if session.done:
        session.finished_at = datetime.now()
        return RedirectResponse("/done", status_code=303)
    return RedirectResponse("/train", status_code=303)


@app.post("/assess/grade")
def grade_assessment(request: Request, verdict: str = Form(...)) -> RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    session = store.get(request.cookies.get(COOKIE))
    if (
        session is None
        or session.current is None
        or session.mode != "assess"
        or session.user_id != user.id
    ):
        return RedirectResponse("/", status_code=303)
    if verdict not in ASSESS_VERDICTS:
        return RedirectResponse("/assess", status_code=303)

    card = session.current
    with connect() as conn:
        save_assessment(conn, user.id, card, verdict)

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
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    session = store.get(request.cookies.get(COOKIE))
    if session is None or session.user_id != user.id:
        return RedirectResponse("/", status_code=303)
    session.finish()
    return RedirectResponse("/done", status_code=303)


@app.get("/done", response_class=HTMLResponse, response_model=None)
def done_page(request: Request) -> HTMLResponse | RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    session = store.get(request.cookies.get(COOKIE))
    if session is None or not session.done or session.user_id != user.id:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "done.html",
        {
            **_nav(user),
            "mode": session.mode,
            "known": session.known,
            "doubt": session.doubt,
            "unknown": session.unknown,
            "again": session.again,
            "hard": session.hard,
            "good": session.good,
            "easy": session.easy,
            "total": session.answered,
            "started_at": session.started_at.strftime("%d.%m.%Y %H:%M"),
            "duration": _format_duration(session.duration_seconds),
        },
    )


@app.get("/about", response_class=HTMLResponse, response_model=None)
def about_page(request: Request) -> HTMLResponse | RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    with connect() as conn:
        banks = fetch_textbook_banks(conn)
    return templates.TemplateResponse(
        request,
        "about.html",
        {**_nav(user), "banks": banks},
    )


@app.get("/stats", response_class=HTMLResponse, response_model=None)
def stats_page(
    request: Request, language: str = "en"
) -> HTMLResponse | RedirectResponse:
    user = _require_user(request)
    if isinstance(user, RedirectResponse):
        return user
    if language not in ("en", "fr"):
        language = "en"
    with connect() as conn:
        summary = build_language_summary(conn, user.id, language)
    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            **_nav(user),
            "language": language,
            "summary": summary,
            "new_per_day": summary.load.new_per_day,
            "preferred_direction": preferred_direction(language),
        },
    )


@app.get("/session")
def create_session_json(
    request: Request,
    language: str,
    textbook: list[str] | None = Query(default=None),
    topic: list[str] | None = Query(default=None),
    level: list[str] | None = Query(default=None),
    seed: int | None = None,
) -> dict:
    user = _current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="login required")
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
        refresh_adaptive_load(conn, user.id, flt.language)
        picked, due_n, new_n = build_session_cards(conn, flt, user.id, rng)
        introduced = count_introduced_today(conn, user.id, flt.language)
        daily_new = get_new_per_day(conn, user.id, flt.language)

    return {
        "filter": {
            "language": flt.language,
            "textbooks": list(flt.textbooks),
            "topics": list(flt.topics),
            "levels": list(flt.levels),
        },
        "user": user.login,
        "due_count": due_n,
        "new_in_session": new_n,
        "introduced_today": introduced,
        "new_per_day": daily_new,
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

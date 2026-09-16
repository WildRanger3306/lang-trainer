# lang-trainer

Личный веб-тренажёр. FastAPI + HTML, всё в Docker. Экраны адаптивные: телефон и компьютер.

Документы: [docs/1-intent.md](docs/1-intent.md). Решения: [docs/4-decisions.md](docs/4-decisions.md).

```bash
docker compose up --build -d
```

Настройки БД — в `.env` (`POSTGRES_*`, `DATABASE_URL` для доступа **с хоста**). В контейнерах app/backup хост БД — `db:5432` (собирается из тех же `POSTGRES_USER` / `PASSWORD` / `DB`).

Открыть http://127.0.0.1:8000 — фильтр → карточки → итог.

При первом старте, если словарь пуст, загружаются `starlight_5`–`7`, `loiseau_blue_5`/`6`, `fr_trainer`. Повторный `up` данные не затирает.

Повтор — упрощённый Anki: due + до 15 новых карточек в день на язык.

Postgres с хоста: порт 5433. Сбросить всё: `docker compose down -v`.

Сервис **backup** раз в сутки в **00:00** (TZ из `.env`, по умолчанию `Europe/Moscow`) кладёт полный `pg_dump` в `backups/lang_trainer_YYYYMMDD_HHMMSS.zip`. Старые zip старше `BACKUP_KEEP_DAYS` (по умолчанию 30) удаляются. Ручной прогон:

```bash
docker compose exec backup /scripts/docker_backup.sh
```

Тесты (нужен локальный `.venv`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python3 -m unittest discover -s tests -v
RUN_DB_TESTS=1 PYTHONPATH=. python3 -m unittest discover -s tests -v
```

# Слова из сырья

1. Скан — `raw/<учебник>/NNNN.jpg` (например `starlight_6`, `Starlight_7`, `loiseau_blue_5`, `loiseau_blue_6`).
2. JSON по модели [5-data-model.md](../5-data-model.md) — `json/<учебник>/NNNN.json`.
3. В Postgres: при пустой базе Compose грузит все `json/*/` подряд; вручную — `python3 scripts/load_entries.py docs/words/json/<учебник>` или `--append` для догрузки. Дубликаты `(язык, form, POS)` при загрузке **сливаются** в одну строку; JSON остаётся копией страниц. Разовый merge уже залитой базы: `python3 scripts/dedupe_entries.py`.

Строка английского вордлиста: `форма — /транскрипция/ — (код) — перевод`.  
Французский (L'oiseau bleu): `форма m/f` + перевод; род → поле `gender`.

Транскрипции в JSON сейчас не заполняем.

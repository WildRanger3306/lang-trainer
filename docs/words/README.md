# Слова из сырья

1. Скан — `raw/<учебник>/NNNN.jpg` (например `starlight_6`, `loiseau_blue_5`).
2. JSON по модели [5-data-model.md](../5-data-model.md) — `json/<учебник>/NNNN.json`.
3. В Postgres: при пустой базе Compose грузит `json/starlight_6/`; вручную — `python3 scripts/load_entries.py docs/words/json/<учебник>` или `--append` для догрузки.

Строка английского вордлиста: `форма — /транскрипция/ — (код) — перевод`.  
Французский (L'oiseau bleu): `форма m/f` + перевод; род → поле `gender`.

Транскрипции в JSON сейчас не заполняем.

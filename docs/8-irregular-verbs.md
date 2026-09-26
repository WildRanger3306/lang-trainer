# Неправильные глаголы (EN)

Статус: **реализовано** 2026-09-25 — [4-decisions.md §015](4-decisions.md). Код: миграция `verb_forms` + `card_direction.forms`, загрузка `en.json` в `load_entries.py`, выборка по метке в `repository.py`, карточка в `templates/_card.html`.

## Объём: школа с углублённым изучением

Цель — список уровня спецшколы (УМК Верещагина / Афанасьева, 2–11 класс) к концу основной школы: **144 глагола, A1–B2**, британский вариант (UK). Файл: [`docs/words/irregular/en.json`](words/irregular/en.json) — A1 53, A2 22, B1 28, B2 41. Сверено с таблицей Starlight 6 (103 глагола): все её глаголы в списке.

Основа — частотный список 143 глаголов с приближённым CEFR ([ENGLISH99](https://englishexplained.ru/wp_files/wp-content/uploads/2018/09/irregular-verbs-list-by-frequency-and-cefr-level.pdf)): A1 52, A2 23, B1 29, B2 39. Уровень там выведен из частотности (A1 ≈ 500 слов, A2 ≈ 1000, B1 ≈ 2500, B2 ≈ 5000), это не English Vocabulary Profile.

Правки к основе:

| Что | Глаголы | Почему |
|---|---|---|
| убрать | `strip`, `melt`, `sneak`, `dare`, `prove`, `fit`, `thrive` | в BrE спрягаются по правилу (`proved`, `fitted`, `thrived`); неправильная форма — архаизм или US |
| добавить | `sting`, `creep`, `mistake`, `spoil`, `rebuild`, `sew`, `stink` | есть в школьных таблицах (плакат «Я всё сам», 113 глаголов, — все его глаголы в списке) или уже в базе из Starlight; уровень B2 |
| добавить | `can` | есть в таблице Starlight 6; модальный, A1. Past Part. нет — в колонке, как в учебнике, `(been able to)` |
| не добавлять | `dive`, `knit`, `shave` | в базе из Starlight, но в BrE спрягаются по правилу |

Формы — британские. Где в BrE норма оба варианта (`learnt/learned`, `dreamt/dreamed`, `burnt/burned`, `spelt/spelled`, `spoilt/spoiled`), хранятся оба, `-t` первым. Формы только NAmE не берём: `got` (не `gotten`), `knelt`, `spat`, `spun`, `forbade`, `slid`. `sew` — `sewed`, `sewn/sewed`. `hang` — `hung` и вторым `hanged` («казнить», так в Starlight 6). `bear` — `borne/born`.

Сейчас в базе 62 из них (Starlight); самых частотных (`go`, `see`, `do`, `have`, `say`, `get`…) нет совсем — список их добавит.

## Источник в репозитории

Один файл `docs/words/irregular/en.json` — канон: `kind: irregular_verbs`, `variant: UK`, массив `verbs`. Каждый глагол — полноценный entry (те же поля, что в вордлистах) плюс формы:

```json
{
  "language": "en",
  "form": "go",
  "partOfSpeech": "verb",
  "transcription": "gˈəʊ",
  "translations": ["идти", "ехать"],
  "level": "A1",
  "topics": ["irr_sl6"],
  "textbooks": ["Irregular verbs"],
  "rank": 5,
  "past":           [{ "form": "went", "ipa": "wˈɛnt" }],
  "pastParticiple": [{ "form": "gone", "ipa": "gˈɒn" }]
}
```

- `rank` — позиция в частотном списке (порядок подачи новых); добавленные глаголы — 144+. Пропуски на месте убранных.
- Тип образования (`AAA` cut–cut–cut, `ABB` buy–bought–bought, `ABA` come–came–come, `ABC` go–went–gone) не хранится — вычисляется из форм, если понадобится.
- `topics` — `irr_sl6` у 103 глаголов из таблицы неправильных глаголов Starlight 6, у остальных пусто. В фильтре: учебник `Irregular verbs` + тема `irr_sl6` → карточки форм только этих 103 глаголов (учебник и темы соединяются через «И»). Режим «Непр. глаголы» фильтр не учитывает — все 144.
- `cue` — необязательная строка для лица карточки `forms`; есть у 30 глаголов с общими значениями (см. «Неоднозначность перевода»). Без `cue` на лице — `translations`.
- Метка учебника у всех — `Irregular verbs`.

## Хранение

Глагол — обычный `entry` (`verb`), формы — в таблице рядом, 1:1:

| Поле | Пример |
|---|---|
| `entry_id` | → `go` |
| `past` | `{went}` |
| `past_ipa` | `{went}` |
| `past_participle` | `{gone}` |
| `past_participle_ipa` | `{gɒn}` |
| `cue` | `NULL` (у `make` — `делать, изготавливать (торт, чай)`) |

`CHECK (cardinality(past) = cardinality(past_ipa))`, то же для причастия. Язык и транскрипция инфинитива — из `entries`.

Загрузка — тем же `load_entries.py`, после entries: глагол upsert’ится по `(en, lower(form), verb)` (переводы и метки сливаются, пустой `level` заполняется), затем пишутся формы. Отдельный шаг нельзя: полная загрузка делает `TRUNCATE entries … CASCADE`.

## Транскрипции

- Заполняет `fill_en_transcriptions.py` из `en_UK` — **только пустые** `ipa`, даже с `--overwrite`, чтобы не затереть ручные правки.
- Покрытие `en_UK` на школьном списке: 243 из 254 форм. Нет: `ate, do, have, put, rose, wear, won, learned, lead, read, tear` — вписать вручную.
- Омографы — только вручную: `read` [riːd] — `read` [red]; `lead` [liːd] (не [led]); `tear` [teə] (не [tɪə]); `wind` [waɪnd] (не [wɪnd]); `wound` [waʊnd] (не [wuːnd]).
- Вручную также пропуски `en_UK` (`leant`, `upset` и др.) и артефакты словаря: `dreamt` [drˈɛmpt] → [drˈɛmt], `arise/arose` [ɐ…] → [ər…], `hear` [hˈiə] → [hˈɪə]. `ate` — [eɪt], как в Starlight 6 (британское [ɛt] тоже норма).
- Загрузчик отказывает, если у формы пустой `ipa`.

## Карточки

- Обычные карточки `go ↔ идти` — как сейчас.
- Новое направление `forms` (значение `card_direction`): одна карточка на глагол, свой FSRS-прогресс, общий лимит новых.

### Когда выдаётся `forms`

Набор карточек entry считается **при выборке**, по фильтру сессии; тип в БД не храним. Решено 2026-09-25.

| Учебник `Irregular verbs` в фильтре | Карточки глагола со строкой форм |
|---|---|
| выбран | `foreign_to_native` + **`forms`** (`forms` заменяет `native_to_foreign`) |
| не выбран | `foreign_to_native` + `native_to_foreign`, формы — справкой на обороте |
| фильтр учебников пуст | как «не выбран» |

- Метку `Irregular verbs` несут все 144 глагола из `en.json`; 62 глагола Starlight получают её при слиянии, рядом со своим учебником. Учебники в фильтре — через ИЛИ, так что `Starlight 7` + `Irregular verbs` даёт формы и для `buy` из Starlight.
- `forms` заменяет `native_to_foreign`, потому что «читать → read, read, read» целиком покрывает «читать → read». Нагрузка на 144 глагола: 288 новых карточек вместо 432.
- Прогресс не удаляется: при выбранной метке у глагола Starlight пауза у `native_to_foreign`, без метки — у `forms`. Due-карточки вне набора просто не выбираются, как карточки вне фильтра.
- Название метки — одна константа в коде (`FORMS_TEXTBOOK`), не строка в SQL и шаблонах.
- Сделать: SQL выборки due/new ([repository.py](../app/repository.py) — сейчас `CROSS JOIN unnest(DIRECTIONS)`), явный список направлений в [stats.py](../app/stats.py), флаги в шапке карточки — как у `native_to_foreign` (`🇷🇺 → 🇬🇧`).
- Позже: новые `forms` в порядке `rank` (сначала A1), сейчас новые идут по `e.id`.

### Режим «Непр. глаголы» (§016)

Отдельная кнопка на главной (только EN): все due + все новые `forms`, вперемешку, без дневного лимита, без учёта фильтра. FSRS, 4 кнопки. Ответы — `source = verbs`: вне квоты новых, автонагрузки и сводки тренировки; прогресс карточек общий с тренировкой. Код: `build_verbs_cards` ([queue.py](../app/queue.py)), `POST /verbs/start` ([main.py](../app/main.py)).

### Справка на обороте обычной карточки

Если у entry есть формы, а `forms` в наборе нет, — на обороте `foreign_to_native` и `native_to_foreign` мелкой строкой:

```
покупать
buy — bought — bought
```

Без оценки, без прогресса, квоту новых не тратит. Видно при каждом повторе; для тренировки — метка `Irregular verbs`.

### Карточка `forms`: перевод → три формы

Как проверка в спецшколе: учитель диктует по-русски, ученик называет три формы. Выбрано 2026-09-25 из трёх вариантов (инфинитив → две формы; перевод → три формы; строка с пропуском).

**Лицо** — только русский:

```
читать
неправильный глагол · 3 формы
```

**Оборот** — три колонки, транскрипция под каждой формой. Перевод внизу не повторяем.

```
  Inf.       Past Simple    Past Part.
  read       read           read
  [rˈiːd]    [rˈɛd]         [rˈɛd]
```

- Подписи колонок: `Inf.` · `Past Simple` · `Past Part.`
- Узкий экран (решено 2026-09-26 по тесту на телефоне): до 560px — столбиком, строка на форму «подпись | форма, под ней IPA», шрифт формы ~2rem; при форме длиннее 8 букв (`understood`, `undertaken`) — чуть мельче, чтобы слово не рвалось. От 560px — три колонки.
- Второй вариант формы — мелко под основным: `learnt` / `learned`.
- Транскрипция формы, которая пишется как инфинитив, но звучит иначе (`read`), подсвечивается.
- На лице — `cue`, если есть; иначе все переводы entry через запятую (после слияния со Starlight их может быть больше).

**Неоднозначность перевода.** Значения 15 групп пересекались: `делать` (do / make), `сказать` (say / tell), `говорить` (say / speak), `держать` (keep / hold), `класть` / `ставить` (put / lay / set / bet), `учить` (learn / teach), `бросать` (throw / cast / quit) и др. Решено 2026-09-25: отдельное поле `cue` только для лица `forms` (не `translations` — туда при слиянии приезжают переводы Starlight). Правило: у каждого глагола группы есть слово, которого нет у соседей; английских подсказок не даём. Проверка: на лицах всех 144 карточек нет общего значения.

| Группа | `cue` |
|---|---|
| делать | do — делать (уроки, работу) · make — делать, изготавливать (торт, чай) |
| сказать / говорить | say — сказать (что-то) · tell — рассказать, сказать (кому-то) · speak — говорить (на языке), разговаривать |
| ехать | go — идти, ехать · drive — водить машину |
| становиться | get — получать, доставать · become — становиться (кем-то) |
| класть / ставить | put — класть, ставить (куда-то) · lay — накрывать на стол, класть (горизонтально) · set — устанавливать; заходить (о солнце) · bet — держать пари |
| держать | keep — хранить, сохранять · hold — держать (в руках) |
| бежать | run — бегать, бежать · flee — спасаться бегством |
| учить | learn — учить (сам), узнавать · teach — учить (кого-то), преподавать |
| побеждать | win — выигрывать (игру, приз) · beat — побеждать (соперника), бить |
| ударять | hit — ударять, попадать (в цель) · strike — наносить удар; бить (о часах, молнии) |
| бросать | throw — бросать, кидать · cast — отбрасывать (тень), бросать (взгляд) · quit — бросать (привычку), уходить (с работы) |
| прыгать | spring — вскакивать · leap — прыгать (далеко, высоко) |
| наклоняться | lean — опираться, прислоняться · bend — сгибать, гнуть |

## Референсы

Списки и уровни:

- [ENGLISH99: Irregular verbs by frequency and CEFR level](https://englishexplained.ru/wp_files/wp-content/uploads/2018/09/irregular-verbs-list-by-frequency-and-cefr-level.pdf) — основа, 143 глагола.
- [English Vocabulary Profile](https://www.englishprofile.org/) (Cambridge) — сверка уровней по словам.
- [A2 Key for Schools vocabulary list](https://www.cambridgeenglish.org/images/506886-a2-key-2020-vocabulary-list.pdf) — сверка A2.
- [УМК Верещагина, Афанасьева (2–11), углублённое](https://prosv.ru/umk/element/english-vereshchagina.2855.html) — ориентир объёма; готовой таблицы в открытом виде нет.
- Школьные таблицы для сверки: [nsportal: Spotlight 5](https://nsportal.ru/shkola/inostrannye-yazyki/angliiskiy-yazyk/library/2024/06/17/spisok-nepravilnyh-glagolov-dlya-5), [nsportal: Rainbow English 5](https://nsportal.ru/shkola/inostrannye-yazyki/angliiskiy-yazyk/library/2017/10/30/tablitsa-nepravilnyh-glagolov-k), [multiurok: 5–9 класс](https://multiurok.ru/files/tablitsa-nepravilnykh-glagolov-5-9-klass.html).

Формы и транскрипции (машиночитаемые):

- [monolithpl/verb.forms.dictionary](https://github.com/monolithpl/verb.forms.dictionary) — MIT; формы по Oxford ALD 9 и Longman DCE 6, CSV/JSON. Сверка форм.
- [Wiktextract](https://github.com/tatuylonen/wiktextract) / [kaikki.org](https://kaikki.org/dictionary/rawdata.html) — Wiktionary в JSONL: `forms` с тегами `past` / `past participle`, `sounds` с IPA и тегами `UK` / `US`. CC BY-SA. Для 11 пропусков `en_UK` и омографов.
- [Wikipedia: List of English irregular verbs](https://en.wikipedia.org/wiki/List_of_English_irregular_verbs) — варианты BrE / AmE, CC BY-SA.
- [ipa-dict](https://github.com/open-dict-data/ipa-dict) (`docs/words/ipa/en_UK.txt`) — основной источник IPA, уже в репозитории.

## Не делать

- три `entries` на один глагол;
- пихать `went, gone` в `translations` или в `form`;
- ломать уникальность ради форм;
- спрягалку для FR — отдельная схема: [17-fr-verbs.md](17-fr-verbs.md).

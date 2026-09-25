# Модель данных

Словарь, пользователи, прогресс карточек и лог ответов для сводки.

Единица — слово, выражение или фраза на иностранном языке плюс переводы на русский. Карточка = единица × направление. Прогресс принадлежит **пользователю**.

## Пользователь (`user`)

| Поле | Смысл |
|---|---|
| `login` | уникальный логин для входа |
| `password_hash` | hash пароля (не plaintext) |
| `display_name` | необязательно; для шапки |
| `created_at` | когда создан |

## Единица (`entry`)

| Поле | Тип | Обязательно | Смысл |
|---|---|---|---|
| `language` | `en` \| `fr` | да | изучаемый язык |
| `form` | строка | да | иностранная форма, как в источнике |
| `partOfSpeech` | см. ниже | да | часть речи для карточки |
| `partOfSpeechCode` | строка | нет | код из учебника: `n`, `adj`, `phr`… |
| `transcription` | строка \| нет | нет | IPA только у иностранной формы, без `/ /` |
| `gender` | `m` \| `f` \| нет | нет | род; для французских существительных |
| `translations` | строки, ≥ 1 | да | переводы на русский |
| `level` | `A1` \| `A2` \| `B1` \| `B2` | нет | один уровень |
| `topics` | строки | нет | метки тем |
| `textbooks` | строки | нет | метки учебников |

Глаголы — в инфинитиве. Форму не нормализуем, кроме обрезки пробелов.

В БД единица уникальна по `(language, lower(form), part_of_speech)` (индекс `uq_entries_lang_form_pos`). Один и тот же словоформ в двух учебниках — **одна** строка `entries` с несколькими метками в `entry_textbooks`. JSON в `docs/words/json/` остаётся сырьём со страниц и может содержать кросс-книжные повторы; при загрузке (`load_entries.py`) они сливаются (переводы и учебники).

`gender` заполняем из учебника (`ami m` → `m`, `maison f` → `f`). Для английского, глаголов, фраз и прочего — пусто. Пары муж/жен (`ami` / `amie`) — две отдельные единицы. Плюрал (`parents m pl`) — род в `gender`, число пока в `partOfSpeechCode` (`pl n` / как в источнике), отдельного поля числа нет.

`partOfSpeechCode` храним, чтобы не потерять различие «фраза / phrasal verb / plural noun». На карточке показываем `partOfSpeech`.

## Часть речи

Значения `partOfSpeech`: `noun`, `adjective`, `verb`, `pronoun`, `numeral`, `adverb`, `phrase`, `phrasal_verb`, `other`.

`phrase` — уточнение к требованиям («слово, выражение или фраза»): для `(phr)` писать «другое» неудобно.  
`phrasal_verb` — фразовые глаголы учебника (`phr v`).

Коды Starlight / похожих вордлистов:

- `n`, `pl n` → `noun`
- `v` → `verb`
- `phr v` → `phrasal_verb` (`phr v` остаётся в `partOfSpeechCode`)
- `adj` → `adjective`
- `adv` → `adverb`
- `pron` → `pronoun`
- `phr` → `phrase`
- `conj`, `prep`, `pp` и прочее → `other`

## Формы глагола (`verb_forms`)

Неправильные глаголы EN, 1:1 к `entries` (§015, [8-irregular-verbs.md](8-irregular-verbs.md)). Источник — `docs/words/irregular/en.json`.

| Поле | Смысл |
|---|---|
| `entry_id` | PK, → инфинитив (`verb`) |
| `past`, `past_ipa` | Past Simple и IPA, параллельные массивы (`learnt`, `learned`) |
| `past_participle`, `past_participle_ipa` | Past Participle и IPA |
| `pattern` | `AAA` / `AAB` / `ABA` / `ABB` / `ABC` |
| `rank` | место в частотном списке |
| `cue` | лицо карточки `forms`, если перевод неоднозначен |

## Карточка (`card`)

Карточка = `entry` × направление `foreign_to_native` | `native_to_foreign` | `forms`.

`forms` — перевод → три формы неправильного глагола (§015). Выдаётся только глаголам со строкой в `verb_forms` и только если в фильтре выбран учебник `Irregular verbs`; тогда заменяет `native_to_foreign`. Набор направлений считается при выборке, в БД не хранится.

Прогресс не смешивается с текстом единицы и **привязан к пользователю**. Нет строки прогресса у этого user = новая карточка.

| Поле | Смысл |
|---|---|
| `user_id` | чей прогресс |
| `due_on` | дата следующего показа |
| `interval_days` | дней до due (для сводки / горизонта) |
| `stability` | FSRS stability |
| `difficulty` | FSRS difficulty (1…10) |
| `fsrs_state` | Learning / Review / Relearning |
| `last_review` | время последнего ответа |
| `introduced_on` | день первого показа |
| `introduced_via` | `train` (квота новых), `assess` (оценка, квоту не жжёт) или `verbs` (режим «Непр. глаголы», §016, квоту не жжёт) |

PK: `(user_id, entry_id, direction)`.

Сессия: все due по фильтру + до N новых в день на язык (EN 10 / FR 20; только `introduced_via = train` этого пользователя). Внутри групп — приоритет направления по языку. Планировщик train — FSRS ([12-fsrs.md](12-fsrs.md)).

## Ответ (`card_review`)

Одна строка на каждое нажатие в тренировке или оценке. Нужна для перформанса за 7/30 дней (снимок `card_progress` этого не даёт).

| Поле | Смысл |
|---|---|
| `user_id` | кто ответил |
| `entry_id`, `direction` | какая карточка |
| `answered_at` | когда ответили (timestamp) |
| `answered_on` | календарный день ответа (для 7/30д) |
| `remembered` | не Again (train) / знаю|сомневаюсь (assess) |
| `rating` | FSRS 1–4 в train; в assess null |
| `was_new` | до ответа не было строки прогресса |
| `interval_before` | интервал до ответа (0 если новая) |
| `interval_after` | интервал после применения алгоритма |
| `source` | `train` \| `assess` \| `verbs` |

Язык для агрегатов брать из `entries`. Учебник в лог не дублируем в первой версии.

## Что не в единице

- пользователь и его прогресс;
- прогресс (`due_on`, интервал, ease) — по направлению и user, отдельно;
- лог ответов (`card_review`) — отдельно от текущего состояния карточки;
- сырой скан — рядом в `docs/words/raw/`, в единицу не копируем;
- JSON импорта (следующая волна) — те же поля `entry`.

## Связи

```mermaid
erDiagram
  User ||--|{ CardProgress : has
  User ||--|{ CardReview : has
  Entry ||--|{ Translation : has
  Entry }o--o| Level : may_have
  Entry }o--|{ Topic : tagged
  Entry }o--|{ Textbook : tagged

  User {
    string login
    string password_hash
  }

  Entry {
    string language
    string form
    string partOfSpeech
    string gender
  }
  Entry ||--|{ CardProgress : has
  Entry ||--|{ CardReview : has

  CardProgress {
    int user_id
    date due_on
    float interval_days
    float ease
    date introduced_on
  }

  CardReview {
    int user_id
    datetime answered_at
    bool remembered
    bool was_new
    float interval_before
    float interval_after
  }

  Translation {
    string text
  }
```

Тема и учебник — справочники меток: одна строка не дублируется зря, единица ссылается на несколько.

## Сырьё → JSON

Скан в `docs/words/raw/`. Извлечение — `docs/words/json/`. Как устроена пачка и что надёжно снять со страницы — [words/README.md](words/README.md).

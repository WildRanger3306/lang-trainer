# Спряжение французских глаголов (черновик)

Статус: **думать**. Зафиксировано 2026-09-25. Решено: **этап 1 — Présent и Passé composé**. Остальное открыто, записи в [4-decisions.md](4-decisions.md) ещё нет.

Аналог неправильных глаголов EN ([8-irregular-verbs.md](8-irregular-verbs.md), §015–016), но устроен иначе: у английского глагола 3 формы — одна карточка на глагол; у французского 6 лиц в каждом времени, и школа учит спряжение порциями «глагол × время».

## Что требует школа

Потолок к 9 классу — ОГЭ ([ФИПИ, навигатор: грамматика](https://doc.fipi.ru/navigator-podgotovki/navigator-oge/2020/Fran-9_3_grammatika.pdf)): изъявительное наклонение — Présent, Passé composé, Imparfait, Futur simple, Plus-que-parfait, Futur proche, Passé proche, Futur dans le passé; Conditionnel présent, Subjonctif présent, пассив (Présent).

Passé composé начинается уже в L'oiseau bleu 5 ([тест к учебнику](https://nsportal.ru/shkola/inostrannye-yazyki/frantsuzskiy-yazyk/library/2013/03/31/passe-compose-uchebnik-beregovskaya)). Раскладки грамматики LB6 по юнитам в открытом доступе нет — этапы ниже по логике курса, сверить с учебником (в `raw/` пока только словарные страницы).

| Этап | Когда | Что |
|---|---|---|
| **1** (решено) | LB6 ч. 1, 7 класс | **Présent** — таблицы; **Passé composé** — причастие + вспомогательный (`avoir` / `être`). Futur proche / Passé proche — через `aller` / `venir de`, своих форм не нужно |
| 2 | LB6 ч. 2, 8 класс | Futur simple (основы `ser-`, `aur-`, `ir-`, `fer-`, `pourr-`…), Imparfait (правило + `être → ét-`), Impératif |
| 3 | 9 класс | Conditionnel, Subjonctif présent, Plus-que-parfait — выводятся из выученного |

## Глаголы

В базе 176 уникальных глаголов FR (184 записи, LB5 / LB6 / FR Trainer), форм нет.

| Группа | В базе | Как учить |
|---|---|---|
| 3e groupe, неправильные: `être`, `avoir`, `aller`, `faire`, `prendre`, `venir`, `pouvoir`, `vouloir`, `savoir`, `dire`, `mettre`, `voir`, `lire`, `écrire`, `boire`, `partir`, `ouvrir`, `connaître`… | 41 | таблица у каждого |
| -er с изменением основы: `manger` (mangeons), `commencer` (commençons), `acheter` (achète), `appeler` (appelle), `préférer`, `envoyer`, `essayer`… | 24 | таблица у образцов (~8) |
| 2e groupe: `finir`, `choisir`, `bâtir`, `maigrir` | 4 | образец `finir` |
| -re правильные: `attendre`, `vendre`, `répondre`… | 6 | образец `attendre` |
| -er правильные | 101 | образец `parler` |

Нет в базе, нужны: `devoir`, `falloir`, `pleuvoir`, `payer`.

Оценка этапа 1: **~55 глаголов** (~45 неправильных + ~10 образцов) → ~55 карточек Présent + ~55 Passé composé.

## Карточки

Две карточки на глагол этапа 1. Лицо — **инфинитив + перевод + время** (задача — спрягать, а не вспомнить глагол; для FR приоритет и так FR→RU).

**Présent — таблица, одна оценка на всю:**

```
лицо:    être · быть · Présent

оборот:  je        suis     [ʒə sɥi]
         tu        es       [ty ɛ]
         il/elle   est      [il ɛ]
         nous      sommes   [nu sɔm]
         vous      êtes     [vuz‿ɛt]
         ils/elles sont     [il sɔ̃]
```

**Passé composé — вспомогательный + причастие:**

```
лицо:    aller · идти, ехать · Passé composé
оборот:  je suis allé(e)   [ʒə sɥiz‿ale] · вспомогательный être
```

Не делать карточку на каждую форму («nous · prendre → prenons»): 6 × времена × глаголы — сотни карточек, а в голове это одна таблица.

## Транскрипции

- `fr_FR.txt` покрывает спрягаемые формы (`suis`, `sommes`, `ont`, `vont`, `finissons`, `prennent`, `pris`, `venu`, `irai`, `serai`…).
- IPA — на **связку местоимение + форма**, иначе не слышно главного: `ils sont` [il sɔ̃] ≠ `ils ont` [ilz‿ɔ̃]; `j'ai` [ʒe]; `vous êtes` [vuz‿ɛt]. Собирать правилом: IPA местоимения + элизия `j'` перед гласной + liaison [z] у `nous / vous / ils / elles` перед гласной.
- Омографы и артефакты — вручную: `est` [ɛ] (не [ɛst] «восток»), `as` [a] (не [as] «туз»), `faisons` [fəzɔ̃] (в словаре [fɛzɔ̃]).

## Хранение (предложение)

`verb_forms` (EN) не подходит — фиксированные колонки под 3 формы.

| Таблица | Поля |
|---|---|
| `verb_conjugations` | `entry_id`, `tense`, `forms text[6]`, `ipa text[6]` — порядок je, tu, il, nous, vous, ils |
| `verb_info` | `entry_id`, `auxiliary` (`avoir` / `être`), `participle`, `group`, `model` |

Канон — `docs/words/conjugation/fr.json`, загрузка тем же `load_entries.py`.

Направления карточек: `conj_present`, `conj_passe_compose` (дальше — по одному на время). PK прогресса `(user, entry, direction)` не меняется.

Когда выдавать — как в EN: метка `Conjugaison` в фильтре тренировки + отдельная кнопка режима «Спряжение» у FR. Времена включаются по этапам.

**До привязки спряжений — чистка возвратных:** 8 пар записаны дважды (`se lever` / `lever (se)`, `se coucher` / `coucher (se)`, `s'endormir` / `endormir (s')`, `se promener` / `promener`, `se réveiller` / `réveiller`, `diriger (se)` / `diriger`, `passer (se)` / `passer`, `arrêter (s')` / `arrêter qn`). Нужна одна форма записи; иначе таблица достанется одной из пары. Возвратные спрягаются с местоимением (`je me lève`), в Passé composé — всегда `être`.

## Источники данных

| Источник | Что | Лицензия |
|---|---|---|
| [verbecc](https://github.com/bretttolbert/verbecc) (данные [Verbiste](https://manpages.debian.org/testing/verbiste/french-conjugator.1.en.html), 7000+ глаголов) | все времена, включая сложные, с правильным вспомогательным; генерация JSON | LGPL-3.0; данные Verbiste — GPL |
| [Lexique 3.83](https://lexique.org/) | все словоформы + частотность + фонетика — выбор глаголов по частоте | не проверена (сайт не открылся); по памяти CC BY-SA |
| Wiktionary / [kaikki.org](https://kaikki.org/dictionary/rawdata.html) | таблицы спряжения, IPA | CC BY-SA |
| `docs/words/ipa/fr_FR.txt` ([ipa-dict](https://github.com/open-dict-data/ipa-dict)) | IPA форм | уже в репозитории |

План: сгенерировать таблицы verbecc для ~55 глаголов → ручная сверка → IPA из `fr_FR` + правило связки.

## Открыто

- Правильные глаголы: только образцы групп (~55 карточек) или таблица у каждого из 176?
- Показывать `il/elle`, `ils/elles` или только `il` / `ils`, как в части школьных таблиц?
- Сверить этапы с грамматикой LB6 (нужно оглавление или страницы грамматики учебника).
- Как писать возвратные (`se lever` или `lever (se)`) — до чистки дублей.
- Имя метки и режима: `Conjugaison` / «Спряжение».

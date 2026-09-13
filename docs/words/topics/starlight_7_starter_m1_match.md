# Starlight 7 — матчинг Starter + Module 1 ↔ банк WL

Статус: **proposal / анализ**, JSON и БД **не менялись**.

Источники:

- Contents + страницы модулей: `docs/words/raw/Starlight_7_Book/` (с. 3–10+)
- Канон тем: [starlight_7_canon.md](starlight_7_canon.md)
- Банк: `docs/words/json/starlight_7/` = **Word List WL 1–24** (~1885 форм), `topics: []`

Правило сверки: **точное** совпадение `form` (без fuzzy). «Близко» — отдельная колонка, в «есть» не входит.

---

## Вывод

| Модуль | Связь с банком WL |
|--------|-------------------|
| **Starter** | Почти **не покрыт** алфавитным Word List. Базовый vocabulary со с. 5–6 в WL отсутствует или есть только родственные фразы. Скорее живёт в **Vocabulary Bank (VB)** / revision младших классов. |
| **Module 1** | **Хорошо покрыт** WL: jobs, character adjectives, hobbies, Check these words, phrasal *break/bring*. Слова размазаны по WL-страницам **по алфавиту**, не блоком «WL 1–3 = M1». |

**Как матчить дальше (когда будем менять данные):** не «файл WL = модуль», а `topics` из канона Contents на лексемы. Starter — отдельный заход (досканировать VB или не тащить в фильтр M1).

---

## Starter (темы Contents)

Списки — со сканов с. 5–6 + колонка Vocabulary.

### Transport — в банке 0/8

| Есть (точно) | Нет в WL |
|--------------|----------|
| — | plane, bus, underground, ferry, bike, car, motorbike, taxi |

Близко в банке: `military plane` (WL 14), `taxi driver` (WL 22).

### Places in a city — в банке 1/15

| Есть | Нет в WL |
|------|----------|
| community centre (WL 4) | block of flats, petrol station, post office, traffic lights, tunnel, bungalow, semi-detached house, road sign, hospital, cottage, library, bus stop, bus lane, detached house |

### Household chores — в банке 2/9

| Есть | Нет в WL |
|------|----------|
| iron (WL 12), dust (WL 6) | hoover, mop, rubbish, washing-up, make the bed, lay the table, take out the rubbish |

Близко: `collect rubbish` (WL 5), `pile of rubbish` (WL 17).

### Food/Drinks — в банке 0/16

| Есть | Нет в WL |
|------|----------|
| — | tomatoes, yoghurt, chicken, orange juice, cauliflower, bread, salmon, grapes, rice, lamb, milk, eggs, cherries, tuna, tea, peppers |

### Cooking methods — в банке 2/7

| Есть | Нет в WL |
|------|----------|
| beat (WL 2), melt (WL 13) | pour, add, slice, chop, stir |

### Natural disasters — в банке 4/7

| Есть | Нет в WL |
|------|----------|
| drought (WL 6), flood (WL 8), tornado (WL 22), hurricane (WL 10) | earthquake, forest fire, tsunami |

### Вне канона Contents (есть на с. 5, в фильтр модулей не брать)

- **Shopping (clothes/footwear):** blouse, shorts, sandals, boots, coats, jeans, slippers, shoes, trainers, jackets — в WL почти нет.
- **Collocations (ex. 6):** polluted waters, child labour, rescue team, medical supplies, conservation project, bus lane — точных фраз мало; есть куски вроде `polluted`, `conservation`.

---

## Module 1 Work & Play

### Jobs — в банке 18/20 (90%)

| Есть | Нет |
|------|-----|
| camp counsellor (WL 3), surgeon (WL 21), judge (WL 12), firefighter (WL 8), storm chaser (WL 20), shop assistant (WL 19), flight attendant (WL 8), police officer (WL 16), artist (WL 1), sports coach (WL 20), taxi driver (WL 22), nurse (WL 15), secretary (WL 19), smokejumper (WL 20), architect (WL 1), engineer (WL 7), pilot (WL 16), lawyer (WL 12) | accountant, vet |

### Character adjectives — 12/14 (85%)

| Есть | Нет |
|------|-----|
| brave (WL 2), organised (WL 15), creative (WL 5), caring (WL 3), patient (WL 15), polite (WL 16), dangerous (WL 5), demanding (WL 6), interesting (WL 12), well-paid (WL 24), outgoing (WL 15), reliable (WL 17) | ambitious, sociable |

### Hobbies (с. 10) — 5/5 (100%)

ghost hunting (WL 9), robot building (WL 18), tornado chasing (WL 22), metal detecting (WL 14), UFO hunting (WL 23)

### Check these words · 1a (smokejumpers) — ~19/19

tough job, beat, elite, risk, remote area, bravely, parachute, put out, duty, training, fit, fire zone, padded, face mask, helmet, backpack, drop, smokejumper — всё есть (WL разбросаны).

### Check these words · 1b (UFO hunter) — 22/24

| Есть (примеры) | Нет |
|----------------|-----|
| fascinated, strange object, meteor, military plane, curious, explanation, involve, mostly, investigate, sighting, analyse, hotspot, rooftop, hillside, record information, camcorder, telescope, device, take up, enthusiastic, patient, spot | planet, find out |

### Phrasal verbs: break, bring — 6/8

| Есть | Нет |
|------|-----|
| break into/down/out/up, bring up/about (все WL 3) | bring round, bring back |

### Applying for a job / Student jobs — 5/11 (+ близкие)

| Есть точно | Близко / нет |
|------------|----------------|
| interview (WL 12), part-time (WL 15), shift (WL 19), salary (WL 18), letter of application (WL 13) | cover letter —, CV ≈ фраза с CV (WL 8), volunteer ≈ volunteer work (WL 23), voluntourism —, full-time —, wage ≈ average wage (WL 1) |

### Sports (выборка, тема канона; полный список — дальше по модулю)

scuba diving (WL 19); нет точных: ice diving, paintball (есть paintballing WL 15), skateboarding.

---

## Предлагаемый порядок работ (когда разрешите менять)

1. **Module 1:** проставить `topics` из канона на точные формы из таблиц выше (Jobs, Character adjectives, Hobbies, Check these words, Phrasal break/bring).
2. Добить M1 со следующих страниц модуля (Sports, Student jobs, Word formation) тем же способом.
3. **Starter:** не размечать из WL вслепую — сначала решить: сканировать VB / завести отдельный мини-набор / оставить вне фильтра 7 класса.
4. После разметки — фильтр по темам / модулю в UI; уникальность формы в БД уже есть, пересечения модулей ок (1–3 темы).

Пилот разметки можно начать с одной темы, например **Hobbies** (5/5) или **Jobs** (18/20).

---

## Vocabulary Bank 1 (VB1–VB3) — анализ сканов

Файлы: `docs/words/raw/Starlight_7_Book/VB1.jpg` … `VB3.jpg`.  
Это **Vocabulary Bank 1** к Module 1 (не Starter). Starter по-прежнему не учитываем.

### Структура

| Стр. | Тема страницы | Содержание |
|------|---------------|------------|
| **VB1** | Work | 18 составных названий профессий + глаголы/коллокации (earn a living, apply, promote, fire, redundant, CV…) |
| **VB2** | Work (продолжение) | 14 профессий + пары part-time/full-time, wages/salary… + банк: perks, bonus, training, underpaid… |
| **VB3** | Sports | 22 вида спорта + пары прилагательных (thrilling/boring, challenging…) + типы Indoor/Outdoor/… |

### Объём (уник. «ядро» VB, без exercise-прилагательных как отдельных целей)

| Блок | Уник. |
|------|------:|
| Job titles VB1 ∪ VB2 | **32** (18+14, пересечений почти нет) |
| Work lexicon (коллокации / условия работы) | **~19** |
| Sports (VB3) | **22** |
| **Всего ядро VB1–3** | **~73** |

Прилагательные на VB3 (~16 в парах) — скорее практика, чем отдельный словарь модуля; часть уже есть в Character adjectives / CTW.

### Покрытие текущим банком WL (точное `form`)

Грубо по ядру:

| Блок | Exact в WL | Комментарий |
|------|------------|-------------|
| VB1 job titles | **9/18** | есть dog walker, shop assistant, flight attendant, taxi driver, police officer, camp counsellor, storm chaser, social worker, video game tester |
| VB2 job titles | **5/14** | artist, secretary, cashier, lifeguard, surgeon; нет hairdresser, librarian, tailor, miner…; biologist ≈ marine biologist |
| Work lexicon | **слабо** | part-time, salary, profession, training, experience, shift; много фраз нет как целых форм (earn a living, full-time, perks, CV…) |
| VB3 sports | **3/22** | rock climbing, windsurfing, rafting; skiing ≈ speed skiing; остальные базовые sports в WL почти не заведены |

**Итого:** VB сильно расширяет M1 по **профессиям** и даёт **спорт**, которого мало в CTW/фото-списках модуля; в алфавитном WL сейчас закрыто примерно **треть** ядра VB (лучше jobs, хуже sports).

### Как стыкуется с прежним счётом M1

| Слой | ~уник. |
|------|-------:|
| Check these words (учебник) | ~131 |
| + фото Jobs/Hobbies/Sports/Student jobs | ~171–176 |
| **+ ядро VB1–3** (минус пересечения с jobs уже на с. 7–18) | ориентир **~220–250** |

Пересечения VB ↔ страницы модуля: shop assistant, camp counsellor, flight attendant, storm chaser, taxi driver, police officer, surgeon, secretary, lifeguard, video game tester, rock climbing, windsurfing… — десяток+.

VB **не заменяет** CTW: там другие пласты (smokejumpers, UFO, freediving gear, voluntary work, PSHE…).

### Практический вывод

1. Для фильтра **Module 1** канон тем остаётся; VB1–2 → тема **Jobs** (+ Applying for a job / Student jobs), VB3 → **Sports**.
2. Чтобы M1 был полным в тренажёре, не хватает в WL многих VB-спортов и части профессий/коллокаций — либо добить JSON с VB, либо принять дыры.
3. Starter по-прежнему отдельно / не в M1.

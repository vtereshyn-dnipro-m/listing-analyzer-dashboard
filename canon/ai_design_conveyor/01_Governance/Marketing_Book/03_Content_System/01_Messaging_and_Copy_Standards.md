# 03. Content System — сообщения и copy DNIPRO-M

**Статус:** working

## Правило одного сообщения

Каждый asset должен иметь:

- одну аудиторию в конкретной рабочей ситуации;
- одну центральную идею;
- один доказуемый product angle;
- один следующий шаг или CTA.

## Базовая структура сообщения

`задача / материал / ситуация -> релевантная характеристика -> практический результат -> комплектация, совместимость или ограничение -> CTA`.

Пример формы:

`Нужно [задача]? [Инструмент / система] помогает [результат] благодаря [проверяемая характеристика]. Проверьте [совместимость / комплектность / ограничение].`

## Язык клиента

Источники для copy: reviews, Q&A, причины возвратов, customer support, search queries, интервью и комментарии. До черновика фиксируем:

- реальную формулировку задачи;
- возражение или риск ошибки;
- бытовой или профессиональный контекст;
- слова клиента для headline, proof и CTA.

## Запрещённые сокращения смысла

Не используем как самостоятельные обещания:

- «мощный» без параметра или сценария;
- «надёжный» без доказуемого факта;
- «профессиональный» без границы применения;
- «универсальный» при существующих ограничениях;
- «полный комплект», если аккумулятор, зарядка или оснастка продаются отдельно.

## Rewrite loop

1. черновик для мысли;
2. редактура для структуры;
3. проверка product truth и доказательства;
4. редактура для ясности и голоса;
5. проверка headline, CTA, страны и языка.


<!-- TALKABILITY_COPY_GATE_2026_08_29_START -->
## Talkability Gate for copy

Before approving copy for a product with a sensitive, complex or identity-risk problem, answer:

1. What makes the buyer avoid naming or discussing the problem: embarrassment, complexity, identity risk or skepticism?
2. What neutral `safe_language` can describe the problem without minimizing it or shaming the buyer?
3. Is the mechanism understandable without category jargon?
4. Does humor clarify the problem or mechanism rather than replace the product benefit?
5. Can the core idea be repeated accurately in ten seconds?
6. Is every authority or expert cue linked to named, scoped and approved evidence?

Required message sequence:

`normalize without trivializing -> direct problem statement -> simple mechanism -> condition or limitation -> proof -> next action`

Do not approve:

- humor that targets the customer;
- euphemisms so vague that the buyer cannot identify fit;
- a memorable line that omits the condition or limitation;
- `expert recommended` or similar authority language without evidence and relationship disclosure.
<!-- TALKABILITY_COPY_GATE_2026_08_29_END -->

## Brand Voice Lexicon Standard

Стандарт применяется к брендовым текстам, product copy, A+ modules, Store, баннерам, видео-скриптам, designer briefs, FAQ, публикациям и AI-generated drafts. Цель — сделать DNIPRO-M узнаваемым по языку, не жертвуя фактической точностью, уровнем уверенности и доказательностью.

Brand voice не равен “красивому стилю”. Это управляемый набор характерных слов, глаголов, переходов, конструкций, метафорических полей и ритмов, которые помогают бренду звучать последовательно и отличимо.

### Метод построения Brand Voice Lexicon

1. Собрать корпус 10–15 действительно характерных текстов бренда: тексты, которые команда считает сильными, точными и близкими DNIPRO-M.
2. Провести аудит повторений:
   - слова и устойчивые выражения;
   - глаголы действия;
   - переходы между мыслями;
   - метафорические поля;
   - ритм предложений;
   - типовые конструкции: “не X, а Y”, “от задачи к решению”, “сначала риск, потом доказательство”, “функция -> польза -> доказательство”.
3. Разделить элементы на четыре списка:
   - `Signature` — элементы, которые делают голос узнаваемым и должны использоваться осознанно;
   - `Contextual` — элементы, которые подходят только для определённых категорий, аудиторий, каналов или уровней формальности;
   - `Replace-review` — частотные, но слабые или слишком общие элементы, которые нужно пересматривать при редактуре;
   - `Avoid` — слова, конструкции и интонации, которые размывают бренд, звучат generic/AI-like или противоречат Brand Constitution.
4. Для каждого элемента указать реальный пример и правило применения.
5. После фактчека и структурной редакторской проверки выполнить отдельный voice-filter.
6. Для AI-агентов подготовить voice package:
   - 5–10 signature patterns;
   - 5–10 avoid/review patterns;
   - 2–3 эталонных фрагмента;
   - правила, где стиль не должен менять факты, scope claims или evidence status.

### Voice lists format

| List | What it contains | Required fields |
|---|---|---|
| `Signature` | Слова, глаголы, конструкции, ритмы и метафоры, которые узнаваемо выражают DNIPRO-M. | Element; real example; use rule; allowed channels; misuse risk. |
| `Contextual` | Формулировки, допустимые только в конкретном контексте. | Element; context; example; do-not-use context. |
| `Replace-review` | Слова и обороты, которые часто появляются по инерции и требуют проверки. | Weak element; replacement options; when original is still allowed. |
| `Avoid` | Generic, exaggerated, low-trust, off-brand or unsupported wording. | Avoid pattern; reason; safer alternative. |

### Voice-filter order

Voice-filter выполняется только после:

1. product truth / fact check;
2. claim/evidence status check;
3. structure and value-story editing;
4. readability and channel fit check.

Voice-filter не имеет права менять факт, SKU, комплектность, совместимость, scope claim, уровень уверенности или evidence status ради более сильного стиля.

### AI voice package

Для AI-производства текстов должен существовать компактный пакет:

```text
Brand voice objective:
Signature patterns, 5-10:
Avoid/review patterns, 5-10:
Reference excerpts, 2-3:
Preferred verbs:
Preferred transition logic:
Metaphor fields allowed:
Metaphor fields avoided:
Generic AI tone examples:
Fact/evidence protection rules:
```

AI не должен вставлять все signature elements в один текст. Узнаваемость достигается точным выбором 1–3 релевантных элементов, а не перегрузкой фирменными словами.

### QA against stylistic caricature

Текст получает риск `stylistic_caricature`, если:

- signature words вставлены слишком часто;
- метафоры звучат декоративно и не помогают смыслу;
- стиль стал сильнее фактов;
- текст начал имитировать бренд поверх generic structure;
- голос противоречит аудитории, каналу или задаче;
- AI “усилил” текст, но изменил claim scope, certainty или evidence status.

### Требования

| ID | Требование | Уровень |
|---|---|---|
| MB-MSG-BVL-R001 | Brand Voice Lexicon строится на корпусе 10–15 действительно характерных текстов бренда. | MUST |
| MB-MSG-BVL-R002 | Lexicon audit должен фиксировать повторяющиеся слова, глаголы, переходы, метафорические поля, ритм и конструкции. | MUST |
| MB-MSG-BVL-R003 | Lexicon должен иметь четыре списка: Signature, Contextual, Replace-review, Avoid. | MUST |
| MB-MSG-BVL-R004 | Каждый элемент lexicon должен иметь реальный пример и правило применения. | MUST |
| MB-MSG-BVL-R005 | Voice-filter выполняется отдельно после фактчека, claim/evidence check и структурной редакции. | MUST |
| MB-MSG-BVL-R006 | AI voice package должен включать 5–10 signature patterns, 5–10 avoid/review patterns и 2–3 reference excerpts. | MUST |
| MB-MSG-BVL-R007 | Запрещено вставлять все signature elements в один текст; использовать только релевантные элементы, которые усиливают смысл. | MUST NOT |
| MB-MSG-BVL-R008 | Стиль не должен менять факт, claim scope, certainty level, evidence status, SKU, комплектность или совместимость. | MUST NOT |
| MB-MSG-BVL-R009 | Текст должен проходить QA против stylistic caricature: перегруженного, декоративного или искусственно “фирменного” голоса. | MUST |
| MB-MSG-BVL-R010 | AI-generated text не принимается только потому, что он грамматически правильный и структурный; он должен пройти brand voice fit check. | MUST |
| MB-MSG-BVL-R011 | Voice edits должны быть traceable: что заменено, почему это ближе к DNIPRO-M, какой смысл или buyer value усилен. | SHOULD |
| MB-MSG-BVL-R012 | Ключевая метрика: доля voice edits, которые автор/brand owner принял как более точное выражение мысли, а не просто как “красивее”. | SHOULD |

### Metrics

- lexicon coverage by channel;
- share of texts with completed voice-filter;
- generic AI tone findings;
- stylistic caricature findings;
- accepted voice edits as more accurate expression of thought;
- rejected voice edits due to fact/scope/evidence distortion;
- repeated avoid-pattern rate;
- signature pattern overuse rate.

<!-- MB_MESSAGE_MEDIA_2026_09_27_START -->
## Перевірка відповідності повідомлення потребам покупця

### Призначення

Brand Message Fit визначає розрив між покупцем, якого припускає чинний текст, і передкупівельними питаннями та переконаннями, підтвердженими незалежними джерелами. Це діагностика повідомлення, а не перевірка фірмових кольорів і не заміна Product Truth. Метод адаптовано з навчального пакета Brand Message Fit, у якому автором зазначений Tim Jordan.

### Область застосування

Застосовувати перед змістовним переписуванням listing, PDP, A+, Store або landing page, коли обґрунтовується `optimize_existing` чи `replace_existing`. Для технічної правки, resize або виправлення друкарської помилки повний аудит не потрібний: зафіксувати причину незастосування. Для нового товару без чинного тексту використовувати дослідження покупця; не вигадувати вихідний текст для порівняння.

### Вхідні дані

Потрібні актуальні доступні тексти, SKU, ринок, мова, розміщення, джерела питань покупців і перелік недоступних даних. Для кожного фрагмента позначати походження: `OBSERVED`, `BRAND_MIRROR`, `RECONSTRUCTED` або `THIRD_PARTY`. Реконструкція з пошукових уривків не є повним прочитанням сторінки; дата й область джерела зберігаються.

### Правила виконання

1. Першим окремим проходом читати текст без дослідження покупця. Визначити `assumed_buyer`: що читач уже повинен знати, вміти оцінювати й вважати важливим, щоб аргументи спрацювали. Кожний висновок прив'язати до фрагмента тексту; не додавати біографію, вік чи дохід.
2. Другим проходом сформувати `evidence_buyer` з незалежних питань, пошуку, Q&A, транскриптів, спільнот та відгуків. Не шукати лише підтвердження першої версії. Ідентичні affiliate/SEO передруки не рахувати незалежними джерелами; власні відгуки після покупки не представляють усіх тих, хто не купив.
3. Для кожного збереженого переконання записати дослівну цитату, source locator, клас джерела, дату/ринок, конкуруюче переконання й область `CATEGORY` або `BRAND`. Без цитати твердження вилучається з доказової моделі покупця; окрема дослідницька гіпотеза дозволена, але не є висновком аудиту. Частота згадок не доводить поширеність у популяції.
4. До висновку перевірити достатність і незалежність доказів. Якщо текст недоступний, джерела залежні або не відповідають ринку/товару, повернути `EVIDENCE_INSUFFICIENT`; можливий явно позначений висновок про категорію, але не про конкретний бренд. Початкове правило джерела «одна поверхня тексту та два класи джерел» є орієнтиром планування, не автоматичним пропуском чи універсальною квотою.
5. Порівняти дві моделі. `gap_type` описує тип проблеми: `UNARGUED_BELIEF` — важливе питання не розкрите; `UNEVALUABLE_ARGUMENT` — доказ неможливо зрозуміло оцінити; `OVER_ARGUED` — надмірне доведення; `CROSS_SURFACE_CONTRADICTION` — суперечність матеріалів. Окреме поле `message_dimension` описує тему: `IDENTITY` — хто покупець і його задача; `OUTCOME` — очікуваний результат; `PROOF` — докази; `RISK` — ризик покупки. Це незалежні осі, не взаємозамінні класифікації; для підтвердженого розриву зазначати застосовні виміри з поясненням. Якщо вимір невідомий, зазначити `NOT_VERIFIABLE` і причину. Непідтверджений розрив не створювати заради звіту.
6. Для кожного критерію записати оцінку й обґрунтування: важливість для покупки (`centrality`), нерозкритість (`resolution`), помітність розміщення (`visibility`), підтверджене висвітлення конкурентами (`competitive`). Використовувати `HIGH`, `MEDIUM`, `LOW` або `NOT_VERIFIABLE` із причиною нестачі даних. Це якісна пріоритизація, не втрачена виручка; автоматичного переведення в 0–3 чи підсумкового бала немає. Невідоме не означає низьке або нуль. Окремий невідомий критерій не скасовує доказового розриву; недостатність доказів про покупця/бренд потребує `EVIDENCE_INSUFFICIENT` за правилом 4.
7. Перед переписуванням сформувати `preserve_candidates`: терміни й твердження, які можуть виконувати пошукову або платформну функцію. Без keyword/search-term evidence не називати їхній вплив на ранжування доведеним. Переписування дозволене як окрема наступна задача після перевірки Product Truth, query evidence, каналу та погодження; метод не забороняє копірайтинг загалом.

### Ролі та відповідальність

Content TZ Agent або маркетолог готує діагностику; рецензент перевіряє джерела та можливе підлаштування другого проходу під перший. Власник контенту обирає зміну. Копірайтер отримує принцип коригування й захищені елементи; висновки про покупця не записуються в Паспорт SKU як продуктові факти.

### Вихід і вердикти

Один документальний запис містить `scope`, `visible_surfaces`, `unavailable_surfaces`, `copy_provenance`, `assumed_buyer`, `evidence_buyer`, `belief_quotes`, `competing_beliefs`, `gap_type`, `message_dimension`, `priority_rationale` (чотири оцінки з обґрунтуваннями), `confidence`, `preserve_candidates`, `correction_principle`, `owner` і `test_ref`. Наприклад: `UNEVALUABLE_ARGUMENT` + `PROOF`; `competitive = NOT_VERIFIABLE`, якщо даних конкурентів немає. Це приклад форми, не продуктовий висновок. `EVIDENCE_INSUFFICIENT` блокує висновок про бренд, але дозволяє збір даних. Запис не є готовим JSON receipt і не дозволяє зміну або публікацію.

### Acceptance tests

- Висновок про покупця без цитати відсутній у доказовій моделі.
- Недоступна сторінка або повторення одного джерела не видаються за повне покриття.
- Для розриву є конкретний фрагмент або зафіксована відсутність на перевірених поверхнях, принцип коригування і спосіб перевірки.
- Перевірено незалежність `gap_type` і `message_dimension`; невідома оцінка збережена без вигаданого числа; недостатні докази не дають висновку про бренд. Документальний запис не проходить машинний gate замість receipt. Збережено фактологічні, пошукові й канальні обмеження; хороший fit не породжує штучну задачу переписування.

### Метрики та межі доказовості

Відстежувати покриття цитатами й походженням, частку висновків із недостатніми доказами, зв'язок виправлень із погодженими тестами. Це авторський практичний метод, а не доведений прогноз конверсії. Публічні джерела не розкривають усіх причин відмови від покупки; ефект перевіряється окремим експериментом.
<!-- MB_MESSAGE_MEDIA_2026_09_27_END -->


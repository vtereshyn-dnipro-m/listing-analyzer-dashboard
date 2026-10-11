# 03. Value Story and Visual Journey Standards

Статус: рабочий стандарт v0.1  
Область применения: Store Home, Amazon Brand Store, Brand Story, A+ content, PDP gallery, видео, баннеры, category tiles, брендовые и продуктовые визуальные модули DNIPRO-M.

## 1. Назначение стандарта

Контент DNIPRO-M должен оцениваться и проектироваться не только как набор отдельных фото, баннеров или видео, а как последовательная история ценности для покупателя.

Базовая цепочка истории:

`customer task -> product/system fit -> demonstration -> proof -> risk reduction -> choice path -> CTA`

Для инструментов, электроинструментов и DIY покупатель покупает не только продукт, а уверенность, что он сможет решить задачу правильно, безопасно и без лишнего риска. Поэтому каждый визуальный модуль должен помогать покупателю понять:

- для какой задачи это подходит;
- какой продукт, система или категория решает задачу;
- как продукт используется;
- почему обещанию можно верить;
- какие риски сняты: совместимость, комплектность, гарантия, сервис, безопасность, ограничение применения;
- какой следующий шаг нужно сделать.

## 2. Уровни обязательности

| Уровень | Значение | Как применять |
|---|---|---|
| `MUST` | Обязательное требование | Нарушение влияет на решение о публикации, если применимо к каналу и подтверждено evidence |
| `SHOULD` | Сильная рабочая практика | Обычно требует правки или письменного исключения |
| `RECOMMENDATION` | Рекомендация для улучшения | Не создает reject сама по себе |
| `HYPOTHESIS` | Проверяемое предположение | Требует A/B, аналитики или customer evidence |
| `NV` | Не проверяемо | Нельзя снижать score без данных |

## 3. Обязательный context gate

Перед созданием или аудитом набора визуального контента необходимо зафиксировать контекст.

| ID | Требование | Уровень |
|---|---|---|
| MB-VS-R001 | Для каждого контент-набора определить покупателя: DIY beginner, home user, мастер, professional или mixed audience. | MUST |
| MB-VS-R002 | Зафиксировать покупательскую задачу: что человек хочет сделать, отремонтировать, построить, улучшить или выбрать. | MUST |
| MB-VS-R003 | Зафиксировать риск покупки: цена, безопасность, совместимость, комплектность, гарантия, результат, сложность применения или доверие к бренду. | MUST |
| MB-VS-R004 | Зафиксировать цель контента: category route, product fit, education, trust, comparison, cross-sell или conversion. | MUST |
| MB-VS-R005 | Не утверждать визуальную концепцию без понимания канала: Store Home, PDP gallery, A+, Brand Story, video, paid/social, email. | MUST |

## 4. Value Story Map

Для Store, PDP gallery, A+, Brand Story, видео и баннерной серии обязательно строить `Value Story Map`.

| Этап | Вопрос покупателя | Роль визуала |
|---|---|---|
| 1. Customer task | “Это для моей задачи?” | Показать реальную задачу, материал, ситуацию применения |
| 2. Product/system fit | “Какой инструмент или система подходит?” | Показать категорию, продуктовую систему, совместимость, набор |
| 3. Demonstration | “Как это работает?” | Показать инструмент в действии, хват, масштаб, контакт с материалом |
| 4. Proof | “Почему этому можно верить?” | Показать результат, деталь качества, проверяемое доказательство |
| 5. Risk reduction | “Что если не подойдет, сломается, я ошибусь?” | Показать комплектность, ограничения, гарантию, поддержку, безопасность |
| 6. Choice path | “Куда идти дальше?” | Дать маршрут к категории, сравнению, аксессуарам, product family |
| 7. CTA | “Что сделать сейчас?” | Дать конкретное действие: shop category, compare models, view accessories, check warranty |

| ID | Требование | Уровень |
|---|---|---|
Context audit rule: for creation and approval, missing context is a process blocker. For audit of existing materials, continue the audit; affected checks receive `NV`, quality score is not reduced, verification coverage is reduced, and missing inputs are listed as required inputs.

Value Story Map scale rule: one asset requires role + buyer question + claim/mobile/text checks; 2-3 linked assets require compact sequence check; 4+ assets or Store/PDP/A+/Brand Story/video require full Value Story Map.

| MB-VS-R006 | Для каждого набора контента должна быть карта этапов истории с указанием, какие модули закрывают каждый этап. | MUST |
| MB-VS-R007 | Нельзя оценивать Store, PDP gallery, A+, Brand Story или видео только по отдельным картинкам без оценки последовательности истории. | MUST |
| MB-VS-R008 | Если этап истории отсутствует, он должен быть отмечен как story gap с указанием риска для покупателя. | MUST |
| MB-VS-R009 | Переход между соседними модулями должен быть логичным: каждый следующий модуль должен продолжать или уточнять предыдущий смысл. | SHOULD |
| MB-VS-R010 | Один модуль должен иметь один доминирующий смысл. Вторичные сообщения допускаются только если они не конкурируют с главным. | SHOULD |

## 5. Роли визуальных материалов

Каждый asset должен иметь основную роль. Если роль не определена, материал считается декоративным или stakeholder-driven и требует обоснования.

Допустимые роли:

- `identify` — идентифицирует продукт, категорию или бренд;
- `task` — показывает задачу или ситуацию применения;
- `use` — показывает использование инструмента;
- `result` — показывает результат работы;
- `detail` — показывает важную деталь, механизм, материал, качество;
- `scale` — показывает размер, хват, пропорции;
- `system` — показывает линейку, совместимость, аксессуары, экосистему;
- `proof` — подтверждает claim или обещание;
- `risk reduction` — снимает риск: гарантия, сервис, комплектность, безопасность, ограничения;
- `choice guidance` — помогает выбрать между категориями, моделями или наборами;
- `CTA/navigation` — ведет к следующему действию.

| ID | Требование | Уровень |
|---|---|---|
Visual role rule: every asset has one primary role. A secondary role is allowed only when it supports the primary role and does not create a competing interpretation.

| MB-VS-R011 | Для каждого визуального asset должна быть назначена одна основная visual role. | MUST |
| MB-VS-R012 | Визуал, headline, support copy и CTA должны поддерживать одну и ту же интерпретацию. | MUST |
| MB-VS-R013 | Нельзя использовать фото только потому, что оно “красивое” или “брендовое”, если оно не помогает buyer question, proof, risk reduction или navigation. | SHOULD |
| MB-VS-R014 | Дублирование одной роли в нескольких модулях допустимо только если каждый модуль добавляет новый смысл. | SHOULD |

## 6. Канальные модели истории

### 6.1 Store Home / Brand Store

Рекомендуемая структура:

`brand/category orientation -> customer task/category routes -> product system/range -> trust proof -> support/risk reduction -> CTA/deep links`

| ID | Требование | Уровень |
|---|---|---|
| MB-VS-R015 | Store Home должен быстро объяснять, что здесь можно выбрать или купить, а не только рассказывать о компании. | MUST |
| MB-VS-R016 | Category routes, product families или use-case routes должны быть видимы без глубокого чтения. | SHOULD |
| MB-VS-R017 | Corporate proof не должен вытеснять покупательский маршрут к категориям или продуктам. | SHOULD |
| MB-VS-R018 | Каждый CTA должен вести туда, что обещает визуал и текст. | MUST |

### 6.2 PDP gallery

Рекомендуемая структура:

`identify product -> fit/use case -> included items/kit -> demonstration -> feature/benefit -> compatibility/limitations -> proof/risk reduction`

| ID | Требование | Уровень |
|---|---|---|
| MB-VS-R019 | Галерея PDP должна ясно показывать продукт, комплектность, сценарий применения и ограничения. | MUST |
| MB-VS-R020 | Нельзя создавать ложное ожидание комплекта, аксессуаров или совместимости. | MUST |
| MB-VS-R021 | Фича должна объясняться через покупательскую пользу, а не только через технический параметр. | SHOULD |

### 6.3 A+ content

Рекомендуемая структура:

`problem/use case -> feature explanation -> comparison/system -> proof/detail -> risk reduction/support -> cross-sell`

| ID | Требование | Уровень |
|---|---|---|
| MB-VS-R022 | A+ должен помогать понять продукт и выбор, а не дублировать Brand Story. | SHOULD |
| MB-VS-R023 | Comparison/system blocks должны помогать выбрать модель, набор или аксессуар. | SHOULD |

### 6.4 Brand Story

Рекомендуемая структура:

`customer value -> brand role -> product system -> credible proof -> route to categories/products`

| ID | Требование | Уровень |
|---|---|---|
| MB-VS-R024 | Brand Story должна связывать бренд с пользой для покупателя, а не быть только биографией компании. | MUST |
| MB-VS-R025 | История бренда должна давать маршрут к продуктовой системе, категориям или задачам. | SHOULD |

### 6.5 Video

Рекомендуемая структура:

`hook -> task/context -> tool selection -> demonstration -> result/proof -> limitation/safety/support -> CTA`

| ID | Требование | Уровень |
|---|---|---|
| MB-VS-R026 | Первые секунды видео должны показывать задачу, контекст или причину смотреть дальше. | SHOULD |
| MB-VS-R027 | Демонстрация не должна создавать неподтвержденное performance claim. | MUST |
| MB-VS-R028 | Материал, условия применения, результат и ограничения должны быть понятны из видео или сопровождающего текста. | SHOULD |

## 7. Proof, trust и claims

| ID | Требование | Уровень |
|---|---|---|
| MB-VS-R029 | Каждый числовой, гарантийный, сервисный, географический, сравнительный или performance claim должен иметь evidence status. | MUST |
| MB-VS-R030 | Trust signal засчитывается только если ясно, какой риск он снижает. | MUST |
| MB-VS-R031 | Claim должен иметь понятный scope: рынок, дата, категория, продукт или источник. | MUST |
| MB-VS-R032 | Гарантия и поддержка должны быть связаны с конкретным покупательским риском: поломка, ремонт, запчасти, срок, канал обращения. | SHOULD |
| MB-VS-R033 | Нельзя использовать “глобальность”, “количество магазинов”, “количество клиентов” или “прямой производитель” как самодостаточную ценность без связи с buyer benefit. | SHOULD |

## 8. Tools / Power Tools / DIY visual requirements

| ID | Требование | Уровень |
|---|---|---|
| MB-VS-R034 | Для инструмента или DIY-контента должен быть хотя бы один визуал, показывающий реальную задачу или материал. | SHOULD |
| MB-VS-R035 | Если продукт сложен в применении, должен быть визуал использования: хват, положение, контакт с материалом, масштаб или рабочая зона. | SHOULD |
| MB-VS-R036 | For battery, corded, kit or accessory products, compatibility, included items or limitations must be shown where they affect purchase, if a claim is made or the risk is material. | MUST where applicable |
| MB-VS-R037 | Результат работы должен быть показан там, где покупательская ценность зависит от качества результата. | SHOULD |
| MB-VS-R038 | Нельзя показывать опасное или технически некорректное использование продукта. | MUST |

## 9. Mobile-first требования

Канонический источник по detailed mobile crop, safe zone, UI overlay risk and art direction: `05_Mobile_Crop_Safe_Zone_and_Art_Direction_Standards.md`. Этот раздел фиксирует только минимальные cross-reference требования.

| ID | Требование | Уровень |
|---|---|---|
| MB-VS-R039 | В мобильном кропе должны сохраняться главный объект, headline, ключевой qualifier и CTA/путь действия. | MUST |
| MB-VS-R040 | Текст, иконки, карты и схемы должны быть читаемы без зума в фактическом размере отображения. | SHOULD |
| MB-VS-R041 | Мобильная версия должна проверяться отдельно; desktop-макет не является evidence мобильной пригодности. | MUST |
| MB-VS-R042 | Если изображение содержит важный текст, он должен быть продублирован нативным текстом, alt-текстом или доступным описанием, если канал это поддерживает. | SHOULD |

## 10. Designer brief: обязательная форма задания

Для каждого нового или переделываемого модуля дизайнер должен получать не общий комментарий, а конкретное задание.

Brief должен иметь decision spine: аудитория -> гипотеза -> доказательство/evidence status -> decision metric и порог -> решение. Research, examples, references, source/supporting materials не должны перегружать основную decision spine: они размещаются на втором уровне — в приложении, раскрываемом evidence-блоке или ссылках.

```text
Module ID:
Channel:
Audience/context:
Story stage:
Buyer question:
Module role:
Visual subject:
Required elements:
Forbidden elements:
Headline:
Support line:
CTA / destination:
Claim/proof dependency:
Claim status: confirmed_fact / insight / hypothesis / unknown
Hypothesis:
Evidence and evidence status:
Decision metric and threshold:
Decision after measurement:
Experiment outcome: experiment_error / negative_result / positive_result / inconclusive
Research/examples/references/supporting materials:
Mobile crop rule:
Acceptance criteria:
Owner:
```

Claim/status notation:

- `confirmed_fact` — проверенный факт с источником или прямым подтверждением;
- `insight` — интерпретация данных, отзывов, интервью, поведения или наблюдений;
- `hypothesis` — предположение, которое требует проверки;
- `unknown` — важная зона, по которой нет достаточных данных.

Experiment outcome notation:

- `experiment_error` — тест или запуск не позволяет принять решение по гипотезе из-за ошибки метода, данных, настройки, выборки, трекинга, креатива или исполнения;
- `negative_result` — тест корректен, но гипотеза не достигла заданного порога;
- `positive_result` — тест корректен, и гипотеза достигла заданного порога;
- `inconclusive` — данных недостаточно для решения, но это не техническая ошибка.

При `experiment_error` решение по гипотезе не принимается. Нужно зафиксировать причину ошибки, какие данные можно сохранить, какое исправление требуется и когда проводится следующий запуск. Техническая ошибка не считается отрицательным результатом.

| ID | Требование | Уровень |
|---|---|---|
| MB-VS-R043 | Designer brief должен содержать decision spine: аудитория -> гипотеза -> доказательство/evidence status -> decision metric и порог -> решение. | MUST |
| MB-VS-R044 | В шаблоне brief обязательны поля Hypothesis, Evidence and evidence status, Decision metric and threshold, Decision after measurement. | MUST |
| MB-VS-R045 | Research, examples, references и source/supporting materials должны находиться на втором уровне: приложение, раскрываемый evidence-блок или ссылки, без перегрузки основной decision spine. | MUST |
| MB-VS-R046 | Для утверждений должны использоваться различимые статусы: confirmed_fact, insight, hypothesis, unknown. | MUST |
| MB-VS-R047 | Факт, инсайт и гипотеза не должны иметь одинаковую визуальную силу без подписи статуса; статус утверждения должен быть видим дизайнеру, аудитору и принимающему решение. | MUST |
| MB-VS-R048 | Исходы эксперимента должны разделяться на experiment_error, negative_result, positive_result, inconclusive; техническая ошибка не считается отрицательным результатом. | MUST |
| MB-VS-R049 | При experiment_error решение по гипотезе не принимается: фиксируются причина ошибки, сохранённые данные, исправление и следующий запуск. | MUST |

Минимальные acceptance criteria:

- buyer question answered in one scan;
- headline and visual communicate same meaning;
- CTA destination matches promise;
- no unsupported claim;
- mobile crop preserves product, headline and qualifier;
- native text/alt text covers important embedded meaning;
- module has one dominant message.


### 10.1 Narrative planning, obstacle and format adaptation

Эти правила применяются к narrative assets: Store/A+ story blocks, брендовые баннеры, видео-сценарии, campaign landing content, explainers, launch content, educational posts and long/short adaptations. Они не заменяют hook, payoff, reader promise или scanability rules. Их задача — помочь спланировать историю до draft и сохранить смысл при адаптации формата.

Six-beat narrative skeleton используется как planning skeleton, а не как обязательный буквальный шаблон текста или последовательность кадров. Допустимо менять порядок, объединять beats или начинать short-form с trigger, если сохраняются audience, trigger, importance, outcome/next action.

```text
Narrative asset ID:
Audience:
Status quo:
Routine:
Trigger:
First consequence:
Wider consequence:
Resolution:
Obstacle type: false belief / process friction / constraint / risk / trade-off
Audience evidence:
Consequence for buyer/user:
Allowed brand response:
Format adaptation: long / short / video / banner / social / A+
Function coverage after compression:
Next action/result:
```

Obstacle must be real and evidence-backed. Do not invent artificial conflict, enemy, fear, urgency, or “uncomfortable truth” only to increase engagement.

Applicability-density audit: every body block must perform one useful function — evidence, mistake, lesson, decision rule, example, or copyable action. A block that only repeats tension, emotion or generic motivation without increasing understanding or ability to act should be removed or rewritten.

Format compression map: when adapting long-form to short-form, preserve story function, not identical length or beat order. The compressed version must still answer: who needs this, what changed/triggered attention, why it matters, and what result or next action follows.

| ID | Требование | Уровень |
|---|---|---|
| MB-VS-R050 | Для narrative asset до draft должен быть заполнен six-beat planning skeleton: status quo -> routine -> trigger -> first consequence -> wider consequence -> resolution. | SHOULD |
| MB-VS-R051 | Six-beat skeleton является planning skeleton, а не обязательным буквальным шаблоном текста, кадра или порядка блоков. | MUST |
| MB-VS-R052 | Obstacle должен быть определён как конкретный false belief, process friction, constraint, risk или trade-off, который реально мешает аудитории. | MUST |
| MB-VS-R053 | Для obstacle должны быть зафиксированы audience evidence, consequence и допустимая response бренда. | MUST |
| MB-VS-R054 | Запрещено создавать искусственный conflict, fear, enemy, false urgency или misleading tension ради engagement. | MUST NOT |
| MB-VS-R055 | Applicability-density audit обязателен для body content: каждый body block должен быть evidence, mistake, lesson, decision rule, example или copyable action. | SHOULD |
| MB-VS-R056 | При review удалять или переписывать body blocks, которые повторяют tension или generic motivation, но не увеличивают понимание, доверие, выбор или способность действовать. | SHOULD |
| MB-VS-R057 | Format compression map должен сохранять audience, trigger, importance, outcome/next action; запрещено механически переносить одинаковую длину и порядок beats во все каналы. | MUST |

Acceptance criteria:

- skeleton заполнен до draft для narrative asset or reason for bypass stated;
- obstacle evidence-backed and not artificial;
- each body block has one useful applicability function;
- compressed format keeps audience, trigger, importance and outcome/next action;
- long/short/video/banner adaptations do not copy the same beat length and order mechanically;
- report does not present Pixar Pitch, F-pattern or dopamine claims as scientifically proven ranking/success factors.

Metrics:

- completed skeleton before draft;
- promise-payoff match;
- unresolved narrative gaps;
- evidence-backed obstacles;
- reader objections resolved;
- misleading tension findings;
- actionable blocks per asset;
- repeated-idea rate;
- function coverage after adaptation;
- comprehension by format;
- CTA/result clarity.

## 11. Story score

Story score считается отдельно от compliance score.

| Критерий | Оценка |
|---|---|
| Story completeness | 0-10 |
| Transition logic | 0-10 |
| Buyer relevance | 0-10 |
| Trust/proof quality | 0-10 |
| Action clarity | 0-10 |
| Channel fit | 0-10 |

Низкий story score может приводить к рекомендации `REWORK`, но `REJECT` или `NC` возможны только при нарушении применимого требования или неподтвержденном критичном claim.

## 12. Типовые story gap labels

- `missing stage` — отсутствует важный этап истории;
- `weak transition` — переход между модулями не объяснен;
- `duplicated role` — несколько модулей повторяют один смысл;
- `premature proof` — доказательство появляется до объяснения пользы;
- `stakeholder-first content` — контент важен компании, но не отвечает buyer question;
- `unsupported trust signal` — доверительный сигнал не имеет evidence;
- `dead-end story` — нет следующего действия;
- `audience mismatch` — язык/визуал не соответствует уровню покупателя;
- `value inversion` — сначала рассказываем о компании, а не о задаче покупателя;
- `channel mismatch` — модуль не соответствует роли канала;
- `proof overload` — доказательств много, но покупательская польза не ясна;
- `missing risk reducer` — не снят существенный риск покупки.

## 13. Минимальный блок отчета

Любой аудит Store, PDP gallery, A+, Brand Story, видео или баннерной серии должен включать:

1. intended customer and buying situation;
2. current value story;
3. story score;
4. Value Story Map;
5. story gaps and broken transitions;
6. Visual Role Register;
7. claims and proof register;
8. recommended new value story;
9. designer brief by module;
10. validation plan.

## Brand promise sequence for DNIPRO-M

For brand, Store, A+, PDP and banner materials, DNIPRO-M value story must check not only product benefit but the full brand promise:

```text
working task -> suitable tool/system -> proven quality -> fair price -> service after purchase -> human help -> limitation/condition -> CTA
```

Rules:

- If a material uses `direct`, `manufacturer`, `no middlemen`, or similar wording, it must connect the claim to buyer value: fair price, quality control, service, availability or risk reduction.
- If a material uses a warranty/service claim, it must be scoped by SKU, market, conditions and available infrastructure.
- If a material uses `global`, `700+ stores`, `1200+ products`, or similar scale claims, it must explain customer value, not only corporate scale.
- If a region has limitations in service, stores, clubs, repair terms or coverage, content must not create the opposite expectation.
- DNIPRO-M must not be framed as cheap, low-end, DIY-only, premium-status or ?for everyone?. The story must serve the self-employed master and/or the private-house owner with land plot.

## Brand Constitution fit in Value Story audit

Add these questions to Value Story audit:

| Question | OK / issue / NV | Comment |
|---|---|---|
| Which core customer is served: self-employed master, private-house owner, or both? |  |  |
| Does the story preserve quality, fair price, service after purchase and human help? |  |  |
| Does any corporate/trust claim translate into buyer value? |  |  |
| Are regional/service/warranty limitations respected? |  |  |
| Does the story avoid cheap/low-end/DIY-only/premium-status/for-everyone framing? |  |  |

A weak Brand Constitution fit normally creates `REWORK`, `GAP` or `NV`. It creates `REJECT` only when it also creates a critical false, misleading, legal, safety, claim, SKU, compatibility, kit-content or platform issue.

<!-- MB_MESSAGE_MEDIA_2026_09_27_START -->
## Доказова демонстрація у продуктовому відео

### Призначення та область застосування

Для відео фізичного товару з видимою дією починати із ситуації використання й питання покупця. Брендові, іміджеві або інформаційні відео можуть мати іншу логіку; причину відмінності зафіксувати в ТЗ. Не інсценувати невидиму, довготривалу чи непідтверджену користь як демонстрацію результату.

### Вхідні дані та правила виконання

Потрібні підтверджений SKU, допустимі сценарії, комплектність, референси, права, buyer evidence і канал. Для товару, що продається, використати також доступні питання, повернення та історію контенту; для нового товару відсутність цих даних не заповнювати вигаданими відгуками.

Сформувати різні кандидатні ситуації використання, а потім обрати одну ідею: хто, де, яка проблема, що робить товар і яка зміна видима. Ситуації є гіпотезами до підтвердження, а не доказом сегмента чи попиту. До зйомки перевірити, чи є видимі початковий стан, дія та результат; голос не повинен приховувати відсутність доказу.

Для демонстраційного формату перевірити: зрозумілість без звуку; наявність дії замість переліку характеристик; зрозумілу проблему; видиму розв'язку. Для перепублікації додатково перевірити зрозумілість без назви бренду. Не вимагати прибирати брендування з усіх відео. Невиконана застосовна перевірка повертає сценарій на доопрацювання; хибний claim або небезпечний сценарій не перекривається сумарною оцінкою.

### Контракт кадру та безперервність

У чинному shot list кожний кадр містить `shot_id`, роль, початковий/кінцевий стан, тривалість, дію товару, рух камери, захищені деталі SKU, контакт/опору, джерело доказу, зв'язок із сусідніми кадрами, text/audio dependency та умови відхилення. До паралельного створення кадрів зафіксувати спільні референси й continuity anchors.

Перевіряти кадри, рух усередині них і зібрану послідовність: геометрія, колір, напис, кількість деталей, насадка, масштаб, контакт, тінь, напрямок дії та flicker. Перевірки лише першого й останнього кадрів недостатньо. Дефект отримує timecode, дозволене виправлення і повторну перевірку всього відповідного фрагмента та стиків.

### Ролі та вердикти

Маркетолог/Content TZ Agent відповідає за ідею, доказ і роль кадрів. Prompt Agent та виконавець додають технічні параметри, не змінюючи стратегію, Product Truth і критерії приймання без повернення власнику ТЗ. `ANGLE_REWORK` повертає на вибір ідеї; `TEMPORAL_PRODUCT_DRIFT` або `SEQUENCE_CONTINUITY_FAIL` вимагає виправлення до випуску. Коли доступний інструмент не підтверджений, результатом може бути сценарій, а не нібито створене відео.

### Acceptance tests

- Відео з непідтвердженою насадкою не проходить як демонстрація комплекту.
- Зміна напису або форми товару посеред кадру виявляється до публікації.
- Неясний без звуку результат не отримує позитивну оцінку лише завдяки voice-over.
- Технічна адаптація не змінює погоджену ідею або порядок смислових завдань кадрів.

### Метрики та межі доказовості

Відстежувати зрозумілість демонстрації, temporal defects, повторні роботи й час на прийнятий ролик. Retention, CTR і conversion перевіряються окремо після дозволеного тесту. Поради «7–10 ситуацій», «4–6 кадрів», «30 секунд», «4/5», «4–6 секунд на кадр» і обмеження осей руху мають статус `TESTABLE_DEFAULT`, а не обов'язкової норми. Джерело — навчальний метод Product Video Strategist; кейс PW-14B не підтверджує характеристики чи ефективність інших SKU.
<!-- MB_MESSAGE_MEDIA_2026_09_27_END -->


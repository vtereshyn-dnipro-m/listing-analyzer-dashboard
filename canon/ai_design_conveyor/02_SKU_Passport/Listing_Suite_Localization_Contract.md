# Контракт локалізації Listing Suite

Версія: 1.0  
Дата: 04.10.2026  
Статус: `APPROVED_FOR_IMPLEMENTATION`; production UI flag `OFF`

## Призначення

Забезпечити стабільне перетворення `user_message_code` на зрозумілий текст без зміни machine-readable result, severity або дозволеної наступної дії.

## Область застосування

Контракт діє для повідомлень evidence delta, recreate, intake, authority, concurrency та compatibility errors. Він не локалізує canonical codes, IDs, SKU, version/SHA або назви API fields.

## Locale profile

- активні локалі першої версії: `uk-UA`, `ru-RU`;
- default і fallback locale: `uk-UA`;
- `en-US` має стан `PLANNED` і не може бути обрана UI до 100% catalog coverage;
- resolution order: user preference → organization preference → `uk-UA`.

Profile відповідає `listing_suite_locale_profile.schema.json`. Message catalog відповідає `listing_suite_message_catalog.schema.json`. Обидва артефакти versioned і мають SHA-256, обчислений із compact UTF-8 JSON зі стабільним порядком полів без власного SHA field.

## Правила виконання

1. `user_message_code`, result, reason, severity та allowed action не перекладаються.
2. Активна locale повинна мати 100% обов'язкових codes; інакше locale не активується.
3. Якщо переклад відсутній під час runtime, використовується `uk-UA`, а receipt отримує `FALLBACK_USED`.
4. Невідома або непідтримана locale також переходить на `uk-UA` із `UNSUPPORTED_LOCALE_FALLBACK`.
5. Невідомий `user_message_code` не отримує generic success: результат `CONTRACT_COMPATIBILITY_ERROR`.
6. UI не показує raw exception, stack trace, internal agent route, access token або приватний locator.
7. Зміна тексту без зміни semantics підвищує catalog version; machine code не змінюється.
8. Різні локалі мають однакові `severity` і `allowed_action` для одного code.
9. Locale selection не змінює Passport state та не запускає mutation.
10. Кожне fallback-рішення може бути зафіксоване receipt за `listing_suite_message_resolution_receipt.schema.json`.

## Acceptance tests

- `uk-UA` і `ru-RU` мають 100% required codes.
- `en-US` не входить до enabled locales.
- Default і fallback дорівнюють `uk-UA`.
- Для кожного code тексти `uk-UA` та `ru-RU` непорожні.
- Severity й allowed action задаються один раз на code, а не окремо для перекладів.
- Відсутній переклад → `FALLBACK_USED`, resolved locale `uk-UA`.
- Unsupported locale → `UNSUPPORTED_LOCALE_FALLBACK`.
- Unknown code → `CONTRACT_COMPATIBILITY_ERROR`.

## Межі доказовості

Контракт і каталог підтверджують повноту статичних UX-текстів, але не доводять rendering, truncation, typography або доступність у реалізованому UI. Feature flag залишається `OFF` до UI acceptance tests.

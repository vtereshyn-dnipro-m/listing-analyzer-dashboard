# Migration note: manifest v0.4 → v0.5

## Призначення

Версія v0.5 додає контрольоване опрацювання social-джерел, недоступних без session/login, неповних comments corpus і невизначених прав.

## Обов'язкові зміни

- Додано `access_resolution_queue` з фізичним queue artifact, структурованими blockers, human actions, states, outcomes і receipts.
- Додано `rights_clearance_queue` для `unknown/restricted` rights та окремого рішення щодо кожного requested use.
- Sources із неповним доступом обов'язково мають access queue item.
- Sources із `unknown` або `restricted` rights обов'язково мають rights queue item.
- `OPEN` має тільки `PENDING` і не має resolution receipt.
- `RESOLVED/EXCLUDED` потребує фізичного receipt і SHA-256.
- `delta_retry_source_ids` обмежує повторний запуск лише відповідними sources.
- Публічна доступність не є доказом права на `production_input`.

## Сумісність

Manifest v0.4 залишається історичним. Нові collection створюються за schema v0.5 та instruction v1.2.

# Реєстр конфігураційних рішень Listing Suite

Версія: 1.0  
Дата: 04.10.2026  
Статус: `OWNER_DECISIONS_PARTIALLY_CLOSED`

## Призначення

Не дозволити команді реалізації самостійно вигадати продуктові, policy або authority parameters. Кожне рішення закривається immutable decision receipt із decision ID, owner, approved value, effective environment/date та evidence.

## Відкриті рішення

| ID | Рішення | Власник | Потрібно до | Поведінка без рішення | Статус |
|---|---|---|---|---|---|
| `LS-CFG-001` | allowlist extensions і MIME types | Product owner + infrastructure owner | intake integration test | `INTAKE_POLICY_NOT_CONFIGURED` | `CLOSED`; `LS-CFG-001_002_Decision_Receipt.md` |
| `LS-CFG-002` | file count, single/total bytes, video duration, recursion depth | Infrastructure owner + Product owner | intake boundary test | folder snapshot flag `OFF` | `CLOSED`; `LS-CFG-001_002_Decision_Receipt.md` |
| `LS-CFG-003` | `retention_period_days` | Policy owner + Product owner | retention integration test | безстрокове зберігання | `CLOSED`; `LS-CFG-003_004_Decision_Receipt.md` |
| `LS-CFG-004` | archive review owner і legal-hold authorities | Policy owner | retention integration test | purge review недоступний | `CLOSED`; `LS-CFG-003_004_Decision_Receipt.md` |
| `LS-CFG-005` | IdP groups/users → canonical roles | Security/identity owner + Product owner | authority integration test | mutation/access denied | `CONTRACT_READY_BINDING_REQUIRED`; `LS-CFG-005_Authority_Matrix_Decision_Receipt.md` |
| `LS-CFG-006` | UI locales, fallback locale і message catalog | Product owner + localization owner | UI acceptance test | production UI flag `OFF` | `CLOSED`; `LS-CFG-006_Localization_Decision_Receipt.md` |
| `LS-CFG-007` | rollout `TEST → STAGING → PRODUCTION` | Deployment owner | activation receipt | production flags `OFF` | `OPEN` |

## Не є owner decisions

HTTP/RPC/queue transport, endpoint names, database engine, lock implementation, polling/push, telemetry vendor і retry timing у межах контрактів є implementation choices. Вони документуються у deployment manifest і не змінюють 00A.

## Closure criteria

Decision закритий лише коли визначено точне значення, owner і approver, створено versioned artifact із SHA-256, задано environment/effective date, пройдено boundary tests і deployment manifest посилається на exact artifact.

## Заборонені підміни

- Fixture values не є production defaults.
- Dev values не переносяться автоматично в production.
- Відсутність policy не заповнюється припущенням розробника.
- Product owner не визначає infrastructure limits самостійно; infrastructure owner не визначає business retention або authority.

## Межі доказовості

Реєстр показує залишкові owner decisions і fail-closed поведінку. Він не закриває рішення та не дозволяє activation.

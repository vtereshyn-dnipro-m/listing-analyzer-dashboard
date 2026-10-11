# AI Design Governance Route Mapping

## Призначення

Mapping визначає, як нормативні маршрути `R01–R41` співвідносяться з execution graph. Він не перетворює кожне правило на окремого агента або node: спочатку фіксується функція маршруту, потім — його правильна runtime-форма.

## Область застосування

Canonical зміст `R01–R41` залишається у `03_AI_Design_Content_Creation_Pipeline.md`. `AI_DESIGN_GOVERNANCE_ROUTE_MAPPING.json` додає лише graph classification, node/edge binding, owner boundary, activation rule та failure disposition.

## Класифікація

| Execution disposition | Кількість | Значення |
|---|---:|---|
| `TYPED_EDGE_ACTIVE` | 13 | Маршрут реально передає control state через наявні typed edges. |
| `NON_EXECUTABLE_GOVERNANCE` | 12 | Правило є guard для чинних nodes/edges і не повинно створювати зайвий hop. |
| `NODE_REQUIRED` | 6 | Для коректного runtime бракує спеціалізованого evidence, reducer або compiler node. |
| `OUTSIDE_CORE_RUNTIME` | 10 | Маршрут належить до PPC, analytics, experiment, promotion, listing mutation або зовнішнього surface runtime. |

## Правила виконання

### Typed execution

До execution graph безпосередньо входять `R01`, `R02`, `R03`, `R10`, `R11`, `R12`, `R14`, `R15`, `R16`, `R19`, `R21`, `R30`, `R33`.

`R30` прив'язаний до контрольованого provider call та output recording. `R33` прив'язаний до checkpoint/resume. Ці зв'язки були відсутні у першій редакції Core Edge Registry і додані у Step 3B.

### Governance без нового node

Policy guards застосовуються лише за своїм trigger. Наприклад, video packaging, creator disclosure, phrase evidence, synthetic reuse або value-to-price не створюють постійного етапу для кожного SKU. Вони додають обов'язкові поля та acceptance checks до вже активного node.

`R17` і `R18` уже прикріплені до human release edge як умовні guards. Тому Edge Registry містить 15 route references: 13 execution routes плюс два conditional policy overlays.

### Маршрути, для яких потрібні nodes

- `R04` — competitive evidence branch;
- `R07` — consumer reality evidence branch;
- `R22` — audience pretest evidence branch;
- `R29` — parallel fan-out/fan-in та conflict-preserving reducer;
- `R36` — carousel/editorial batch compiler specialization;
- `R37` — comment clustering і provenance branch.

Їх не можна активувати лише додаванням стрілки. Спочатку потрібні bounded responsibility, input/output schema, ownership, receipts та stop contract.

### Поза core runtime

`R09`, `R13`, `R20`, `R23–R26`, `R38–R40` зберігають нормативну силу, але не виконуються core content graph. Це запобігає неявному отриманню повноважень на PPC, analytics implementation, publication, listing mutation, commercial offer або post-test learning.

## Acceptance tests

```powershell
& "C:\Users\ystep\Documents\DM AMAZON\AI Design Conveyor\10_Runtime_Registry\Test-AIDesignGovernanceRouteMapping.ps1"
```

Validator перевіряє повноту `R01–R41`, унікальність classification, наявність edge/node references, узгодженість active/deferred scope, коректне виділення `R29` та відсутність core edges у зовнішніх маршрутах.

## Межі доказовості

Mapping доводить повноту нормативної класифікації. Він не створює відсутні nodes, не активує runtime і не надає external, spend або publication authority.


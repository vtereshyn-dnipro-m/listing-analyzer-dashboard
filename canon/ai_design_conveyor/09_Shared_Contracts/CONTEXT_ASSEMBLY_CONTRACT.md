# Context Assembly Contract for DM AMAZON agents

Версія: `1.2`  
Статус: `active_v1.2`  
Дата набуття чинності: 24.09.2026

## Scope

Use for active DM AMAZON agents working with SKU/Product Truth, marketplace, country, account, ASIN/category, advertising, inventory, content, localization, experiments or regulatory data. Development specifications for planned agents must declare this dependency but do not become runtime-ready through that declaration.

This contract defines the shared manifest only. Agent-specific context is a named delta; it must not create a second independent context assembly system.

## Per-request sequence

`identity/account → country/marketplace/channel → task and decision → permission-filtered sources → freshness/relevance gate → task tools → validation → model call`

## Required context manifest

- request, actor and owner;
- marketplace, country, account and ASIN/category scope;
- metric definitions, currency, time zone and reporting calendar;
- included files/rows/API results with source, version and freshness;
- known outages, attribution limits and platform caveats;
- excluded sources and reason;
- available tools, read/write boundary and approval requirement;
- context budget, unresolved ambiguity and validation status.

## Per-decision-object allocation manifest

For a request containing more than one independent question, decision or required deliverable, context assembly must prove coverage after packing, not only retrieval into the candidate pool. Record:

```yaml
context_allocation_manifest:
  assembly_id:
  context_budget_tokens:
  independent_decision_object_count:
  tokens_per_decision_object:
  decision_objects:
    - decision_object_id:
      parent_decision_object_id: null
      dependency_class: INDEPENDENT | DEPENDENT
      required_evidence_types: []
      candidate_evidence_refs: []
      packed_evidence_refs: []
      allocated_tokens:
      allocation_status: ALLOCATED | STARVED | UNRESOLVED_DEPENDENCY
      exclusion_reason:
      validation_result: PASS | FAIL
```

Each independent decision object must receive at least one relevant packed evidence item or an explicit `STARVED` status. A dependent object is not allocated as an independent sibling until its parent condition is resolved; unresolved dependency becomes `UNRESOLVED_DEPENDENCY`, not an unsupported answer. Reservations are scored against the corresponding decision object, after which remaining budget may be distributed by global relevance.

`candidate_evidence_refs` proves retrieval only. `packed_evidence_refs` proves model-visible allocation. The assembler must not infer post-pack coverage from candidate-pool recall, source count or total token utilization.

## Version-pinned dependency and receipt

Every runtime agent must load this exact canonical path and expected status `active_v1.2` before substantive work. Record:

```yaml
context_contract_receipt:
  canonical_path:
  expected_status: active_v1.2
  actual_status:
  sha256:
  read_at:
  profile:
  agent_delta_id:
  validation_result: PASS | FAIL
```

Status mismatch, missing file, unreadable path or stale SHA against the run manifest gives `CONTEXT_CONTRACT_MISMATCH`. Do not reconstruct the contract from memory. Agent-specific manifests add fields by reference to a profile; they do not repeat or weaken shared identity, scope, freshness, permissions or validation rules.

### Version transition

New runs created on or after activation of v1.2 must pin `active_v1.2`. A run already pinned to the immutable v1.1 hash may continue only through its recorded archived dependency and existing checkpoint; it must not silently read the changed canonical path. Migration to v1.2 requires a new context receipt and revalidation of the allocation manifest. This transition does not authorize a provider call, publication or scope expansion.

## Profiles and agent deltas

- `SKU_PIPELINE`: exact SKU/configuration, Product Truth/Passport version and SHA, RUN/parent binding, verifier mode, source cutoff and receipt chain. Local delta lives in 00A and the assigned SKU agent contract.
- `CONTENT_TZ`: exact SKU Product Truth projection, channel/placement, audience/job, claims/rights/safety, Marketing Book/content-standard versions, requested deliverable and human approval gates. Local delta lives in the Content TZ instruction and schemas.
- `PROMPT_COMPILATION`: approved Content TZ version/hash, hypothesis/task ID, exact SKU/variant, Product Truth snapshot, Visual Invariants, reference bindings, generation/edit contract, provider capability snapshot, QA tests and human owner. The delta may compile but cannot reinterpret the approved brief.
- `CREATIVE_PRODUCTION`: approved Prompt Package/version, exact SKU/variant and Product Truth binding, provider/model snapshot, input/reference hashes, allowed change boundary, output target, cost/run limits, lineage/checkpoint policy and review owner. The delta cannot grant publication authority.
- `CONTENT_AUDIT`: audit object, asset inventory, channel/viewport, applicable standard versions, evidence completeness, read/write boundary and report mode. Local delta lives in the auditor skill references/output contract.
- `LOCALIZATION`: source design/version, working copy, languages/locale, immutable non-text boundary, typography/RTL constraints and release owner. `creative_design_context` is this profile's delta. It must be nested under a localization context envelope containing `context_contract_receipt` and `shared_manifest_ref`; shared request/actor/owner, marketplace/country/channel, permissions, source freshness and validation status are inherited by reference and must not be independently redefined. A conflicting duplicated value returns `CONTEXT_BINDING_CONFLICT`.
- `MEDIA_COLLECTION`: exact SKU/Passport binding, human-confirmed request, visual targets, source inventory and rights, product artifact root, collection ID, tool/runtime availability and downstream-use boundary. Local delta lives in the Image Collector package.
- `EXPERIMENT`: country/market, audience/account, content cluster, objective, cohort, local time/calendar, metric definition, observation window, permissions and decision threshold. Local delta lives in the experiment contract.

Unknown profile or missing required delta returns `CONTEXT_NOT_READY`; it is not permission to infer values.

## Differential tests

- same query for two marketplaces;
- same metric for two accounts or currencies;
- current vs stale advertising/inventory extract;
- analyst role vs write-authorized operator;
- ASIN-specific vs category-level question;
- clean data vs known tracking outage.
- same multi-object request with reordered decision objects;
- candidate evidence present but one independent object receives zero packed evidence;
- independent sibling vs unresolved dependent object under the same context budget.

## Stop rules

Stop or qualify the answer if tenant/account isolation fails, metric/calendar is ambiguous, source freshness exceeds the task limit, or the required action tool is outside the actor's permission.

For multi-object requests, `STARVED`, `UNRESOLVED_DEPENDENCY` or missing allocation validation blocks a supported-status answer for the affected decision object. Other adequately supported objects may proceed if the output preserves the gap explicitly and the applicable workflow permits partial completion.

Do not copy the full central KB case here. This file is the project-specific application contract.

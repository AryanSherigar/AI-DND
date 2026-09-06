# Stripe specialist-skill research

**Research date:** 2026-09-01  
**Scope:** First-party public Stripe engineering posts, documentation, careers pages, and role descriptions.  
**Purpose:** Identify specialist Codex skills that add useful decision procedures beyond the broad `stripe-engineering` skill.

## Research and evidence boundary

- The existing [Stripe engineering practices report](./stripe-engineering-practices.md) already covers broad principles, API versioning, idempotency, online migrations, production gates, testing, staff expectations, and hiring. This report focuses on newer or more detailed evidence that changes how a specialist skill should behave.
- “Observed” means a first-party Stripe source explicitly describes the mechanism or expectation. “Adaptation” means a reusable procedure inferred from that evidence; it is not a claim about Stripe's confidential process.
- Dated engineering articles describe Stripe at publication time. Current job and careers pages are current only as accessed and can change or close.
- Firecrawl was retried through the official CLI. The CLI reached Firecrawl, but unauthenticated requests were rejected because the execution IP was classified as suspicious. Sources were therefore retrieved through read-only web search and direct requests to the same first-party Stripe URLs.

## Finding: more specialist skills are justified

Yes. The incremental evidence supports multiple narrow skills rather than making the existing persona/router much larger. Strongest new skill-worthy mechanisms:

1. Treat one canonical API schema as a release artifact; derive and validate every developer-facing surface from it.
2. Model production recovery as invariant-preserving state transitions, simulate the exact execution logic, and choose the safest reachable state when full recovery is impossible.
3. Separate data-plane replacement from ordinary service work; require production-shaped load tests, synthetic tests, explicit reliability targets, and staged deployment.
4. Turn recurring codebase migrations into durable, build-graph-aware services producing bounded, idempotent, reviewable changes.
5. Replay the same deterministic production logic against minimized historical inputs; make behavioral diffs—not merely passing tests—the review artifact.
6. Select CI tests from observed dependencies only when the selector has conservative escape hatches and a reproducible baseline.
7. Bound coding agents with isolated environments, narrow tools, deterministic gates, limited feedback loops, and human review.

## Horizon 1: API and interface review

### New observed evidence

Stripe's 2026 API pipeline article describes a single OpenAPI-centered representation feeding SDKs, CLI behavior, API reference material, code samples, changelogs, and other developer products. Before merge, automated checks validate naming, field types, backward compatibility, documentation completeness, and consumer-specific constraints such as SDK reserved words. Reviewers see schema diffs; for v2, tooling also detects accidental changes to past versions. A pre-release comparison enriches changes with downstream SDK impact and suggested changelog text. Release snapshots become canonical artifacts distributed to downstream consumers. ([How API changes flow into Stripe's developer products](https://stripe.dev/blog/how-api-changes-flow-into-stripes-developer-products), 2026-06-15)

The same article exposes important architecture trade-offs:

- A second internal representation for v2 forced generator duplication and caused some developer tools to omit v2 support. Stripe chose convergence on extensible OpenAPI rather than maintaining parallel representations.
- Artifacts vary by **surface**, **release phase**, and **API version**. Public artifacts remove private metadata and endpoints; GA, public-preview, and private-preview artifacts differ; versioned snapshots reproduce historical API shapes.
- Stripe openly records a remaining limitation: historical v1 descriptions cannot be regenerated with newly added metadata as cleanly as v2 snapshots. The report therefore distinguishes a strong current v2 mechanism from legacy v1 constraints.

### Decision-changing adaptation

An API review skill should reject “controller code plus handwritten docs” as sufficient evidence for a consequential interface. Require:

1. Canonical schema or typed contract.
2. Explicit consumer surfaces and visibility filters.
3. Lifecycle phase and version semantics.
4. Machine-checked naming, types, compatibility, documentation, and reserved-word constraints.
5. Human-reviewable semantic diff, including historical-version drift.
6. Generated or contract-checked SDK/docs/examples/changelog impact.
7. Immutable release artifact and reproducible prior versions.

Use one source of truth, but allow purpose-built extensions. “One schema” does not mean exposing identical metadata to every consumer.

### Recommended skill

**`stripe-api-contract-governance`**

- Trigger: public APIs, events, SDKs, CLI surfaces, schemas, compatibility, previews, versioned releases, contract reviews.
- Output: consumer map; contract diff; compatibility classification; generated-surface impact; release/rollback plan.
- Boundary: not a generic REST style guide; not authority to invent Stripe's internal approval chain.
- Why separate: schema propagation and lifecycle governance are deeper than ordinary code or architecture review.

## Horizon 2: production readiness and reliability

### New observed evidence: high-criticality data plane

Stripe's 2026 service-mesh account starts from a user failure budget: a failed internal request can lose a user's sale, and the published target is 99.9995% reliability. Stripe replaced Envoy only after concrete scaling and behavior risks became material. A 2024 dependency upgrade had rejected legitimate traffic in QA load testing; Stripe notes that the issue could have escaped if the test traffic had not reproduced the affected production pattern. The replacement was accepted after comparative load tests and then guarded with code review, unit, end-to-end, and synthetic tests. ([Building a data plane from scratch](https://stripe.dev/blog/building-a-data-plane-from-scratch-stripes-own-high-performance-distributed-proxy), 2026-08-26)

The architectural lesson is conditional—not “build infrastructure yourself.” Stripe explicitly accepted in-house complexity because its service mesh had become unusually large and customized, the current mechanism created incidents and rollout risk, and the replacement showed about half the CPU and roughly 50% lower latency under Stripe's deployment. The article also records a cost: shared connections required more coordination of request state across goroutines.

### New observed evidence: recovery planning

Stripe's 2026 database-fleet article replaced fragile, ordered remediation plugins with graph search over simulated infrastructure states. Current state and desired source-of-truth state are nodes; atomic operations are edges; invalid intermediate states are pruned using safety invariants such as quorum rules. The same business logic runs in simulation and durable Temporal execution through a shared context interface—“what you simulate is what you execute.” ([Graph search and state machines for auto-remediation](https://stripe.dev/blog/how-stripe-uses-graph-search-and-state-machines-to-auto-remediate-a-global-database-fleet), 2026-07-16)

Stripe evolved from breadth-first search to weighted Dijkstra search because a fully healthy state can be unreachable. The weighted search minimizes time spent in misconfigured states and returns partial remediation toward the least-degraded reachable state. Canceled workflows can be replanned from actual intermediate state. Published impact: about 30% fewer pages, 12 fewer days of unhealthy shard states annually, and no code changes for a newly onboarded layout. This is current 2026 evidence for that database platform, not a universal Stripe remediation framework.

Current Core Infrastructure hiring evidence reinforces a verification posture: launch/failover readiness using traffic replay, synthetics, failover drills, dependency analysis, CI/CD gates, and incident data; manual checklists should become repeatable global mechanisms where feasible. ([Staff Engineer, Core Infrastructure](https://stripe.com/careers/listing/staff-engineer-core-infrastructure/8070949), current listing accessed 2026-09-01)

### Decision-changing adaptation

A specialist readiness skill should distinguish three risk classes:

- **Ordinary service change:** staged rollout, telemetry, rollback, retry/idempotency, capacity checks.
- **Shared data/control plane:** explicit reliability budget, production-shaped traffic tests, dependency compatibility, synthetic coverage, priority/load-shedding behavior, incremental fleet rollout.
- **Automated remediation:** declared source of truth, atomic operations, safety invariants checked at every intermediate state, pure simulation of the same logic, durable execution, cancellation/replanning, partial-safe outcome, operator visibility.

### Recommended skills

**`stripe-critical-path-readiness`**

- Trigger: gateways, service mesh, shared databases, schedulers, identity, payment path, regional launch, failover, traffic shift.
- Output: reliability budget; critical dependency map; production-shaped validation; staged rollout and abort criteria; recovery evidence.
- Boundary: complements generic production-readiness review; invoked only when blast radius or reliability target warrants deeper gates.

**`stripe-invariant-recovery-design`**

- Trigger: auto-remediation, workflow orchestration, fleet repair, complex runbooks, cancel/resume recovery, topology migration.
- Output: state model; source of truth; transitions; invariants; simulator/executor fidelity proof; unreachable-goal policy; human override.
- Boundary: never authorizes unattended production mutation without explicit permissions and organizational controls.

## Horizon 3: online data and codebase migrations

### New observed evidence: zero-downtime data movement

Stripe's 2024 DocDB article describes a current-at-publication migration platform operating over thousands of shards. Its migration protocol:

1. Register migration intent and prepare target indexes.
2. Bulk-load a point-in-time source snapshot.
3. Replicate mutations from that time through CDC with checkpointed pause/resume.
4. Replicate bidirectionally and tag generated writes to prevent loops, preserving the option to move traffic back.
5. Compare point-in-time snapshots for completeness and correctness without consuming production query capacity.
6. Use version-gated requests to briefly fence the source, drain remaining replication, atomically change routing metadata, then rely on application retries.
7. Deregister only after success; delete source data last.

Stripe states the traffic switch took under two seconds and framed this within application retry budgets. The platform also isolated migration I/O from user query capacity and exposed replication lag. ([How Stripe's document databases supported 99.999% uptime with zero-downtime data migrations](https://stripe.dev/blog/how-stripes-document-databases-supported-99.999-uptime-with-zero-downtime-data-migrations), 2024-06-06; historical architecture snapshot)

### New observed evidence: migrations as a maintained service

Stripe's 2026 AutoJDK system computes upgrade eligibility from the live build graph, accounting for reverse dependencies, runtime caps, framework guards, source/test coordination, and pinned macros. It generates bounded PRs, behaves idempotently, can run continuously or against one package, tracks blockers and adoption, keeps multiple JDKs available during transition, and watches anticipated runtime failures for targeted rollback. ([Modern Java at Stripe](https://stripe.dev/blog/modern-java-at-stripe-language-upgrades-as-a-service), 2026-05-27)

Key shift: preserve migration machinery instead of writing a bespoke script and discarding it. Central platform policy plus CI constraints and deployable artifacts bundling their runtime reduce drift. The published results are Stripe-specific; the reusable procedure is graph-aware eligibility, bounded review units, visible blockers, gradual compatibility, runtime detection, and idempotent reruns.

### Decision-changing adaptation

Do not combine database movement and codebase modernization into one generic “migration checklist.” They share observability and rollback, but their proof obligations differ:

- Data movement needs completeness, ordering, catch-up, fencing, reversible routing, retry budgets, and delayed deletion.
- Codebase migration needs dependency-graph eligibility, bounded review units, compiler/test/toolchain evidence, merge-conflict control, adoption/blocker telemetry, and a repeatable upgrader.

### Recommended skills

**`stripe-online-data-migration`**

- Trigger: shard moves, datastore replacement, repartitioning, schema/source-of-truth cutover, CDC backfill.
- Output: migration state machine; source/target authority by phase; watermark/checkpoint; correctness comparison; fence/cutover protocol; reverse path; cleanup proof.
- Boundary: does not prescribe Stripe's DocDB design; selects mechanisms appropriate to the actual datastore.

**`stripe-codebase-migration-service`**

- Trigger: language/runtime/framework/library upgrades spanning many owners or targets.
- Output: live dependency graph; eligibility policy; bounded partitions; idempotent automation; blocker ledger; CI/runtime gates; adoption dashboard; final removal criteria.
- Boundary: use one-off codemods for genuinely one-off, bounded changes; build a service only when upgrade cost recurs or graph scale justifies it.

## Horizon 4: testing, CI, and verification

### New observed evidence: production-history replay

Stripe's 2026 replay-testing series argues that unit and integration tests cannot characterize behavior across a long-tailed real input distribution. Stripe recommends separating deterministic decision logic from transport, global state, live dependencies, and side effects; then invoking the exact same logic offline over privacy-minimized historical inputs. Reviewers receive quantified old/new diffs with explanations, not only a pass/fail signal. ([Replay testing with Apache Spark](https://stripe.dev/blog/microservice-testing-with-apache-spark), 2026-06-01; [building the replay harness](https://stripe.dev/blog/microservice-testing-with-apache-spark-part-2), 2026-06-08)

The sources add safeguards often missing from “shadow test” advice:

- Reconstruct dependency state as time-aware datasets or logged request/response pairs.
- Replace side effects with output records; do not execute them.
- Minimize, tokenize, redact, and access-control historical data and diffs.
- Keep the wrapper thin; reimplementation can drift and create false confidence.
- Include trace identifiers, intermediate values, and rule explanations so a changed result can be diagnosed.
- Preserve incident and boundary cases in a smaller golden dataset for pull requests.
- State replay limitations instead of claiming a perfect production simulation.

### New observed evidence: selective CI with reproducible evidence

Stripe's 2026 Selective Test Execution article now exposes the algorithm that was unavailable during the earlier research. It observes files opened by each test instead of relying only on static Ruby analysis; tracks generated artifacts as well as source; stores a compact file-to-test index; hashes the full file inventory to detect changes; always reruns previously failing and file-discovery tests; and records an ordered, queryable baseline so selection can be reproduced. Stripe reports roughly 5% of tests run on average, without presenting “5%” as a safe universal target. ([Selective Test Execution at Stripe](https://stripe.dev/blog/selective-test-execution-at-stripe-fast-ci-for-a-50m-line-ruby-monorepo), 2026-04-09)

### Supporting time evidence

Stripe's test-clock architecture abstracts time behind a provider, advances directly between meaningful events, excludes test-clock objects from real-time schedulers, and runs existing Billing business logic under the simulated clock. Stripe says it uses test clocks internally for new Billing features. ([Test clocks](https://stripe.com/blog/test-clocks-how-we-made-it-easier-to-test-stripe-billing-integrations), 2024-05-09; historical architecture snapshot, current product capability may evolve)

### Decision-changing adaptation

Verification depth should be selected by failure mode:

- Handwritten unit/property tests for invariants and constructed boundaries.
- Integration/contract tests for component interactions.
- Controllable time for long-horizon state transitions.
- Golden datasets for stable service-level behavior.
- Historical replay for long-tail behavior and consequential refactors/rule changes.
- End-to-end/synthetic/load/failover tests for runtime wiring and operations.
- Selective CI only when missed-test risk is measured and conservative full-run triggers exist.

### Recommended skills

**`stripe-behavioral-replay-verification`**

- Trigger: money, pricing, eligibility, billing, ranking, policy engines, migrations, AI-written high-impact refactors.
- Output: purity boundary; replay dataset contract; privacy controls; old/new diff schema; acceptance thresholds; unexplained-diff review.
- Boundary: replay complements, never replaces, unit/integration/end-to-end evidence.

**`stripe-risk-aware-ci-selection`**

- Trigger: test suites too large for full execution on every change.
- Output: dependency signal; underselection threats; generated-file handling; mandatory tests; baseline identity; reproducibility; periodic/full-run audit.
- Boundary: do not optimize CI before measuring latency/cost pain; never copy Stripe's 5% target without local evidence.

## Horizon 5: staff technical leadership and planning

### Incremental evidence

The current Core Infrastructure role makes staff planning concrete: multi-year strategy decomposed into quarterly milestones and success metrics; readiness evidence turned into reusable platform checks; risk ownership driven by incident/system data; hands-on production debugging; and asynchronous decisions across regions. ([Staff Engineer, Core Infrastructure](https://stripe.com/careers/listing/staff-engineer-core-infrastructure/8070949), current listing accessed 2026-09-01)

A Terminal Developer Productivity listing adds a useful staff-level internal-platform loop: talk directly to internal developer users, define metrics such as build time, test stability, and release velocity, translate roadmap into executable projects with clear outcomes, contribute through code/design docs/reviews, own incidents, and prefer simple, robust, scalable designs. The canonical role URL now returns 404; search-indexed localized snapshots were about five months old, so treat this as historical listing evidence, not a current opening. ([Terminal Developer Productivity listing snapshot](https://stripe.com/en-be/jobs/listing/staff-software-engineer-terminal-developer-productivity/7705412), historical snapshot accessed through search 2026-09-01)

A current generalist platform listing expects future-proof interfaces, trade-offs among business priority, user experience, and sustainable foundations, cross-team technical conversation, full-stack production debugging, and language-agnostic coding strength. It explicitly values autonomy and contribution to peers' success. ([Full Stack Engineer, Developer & End User Experience Platform](https://stripe.com/careers/listing/full-stack-engineer-developer-end-user-experience-platform/6567104), current listing accessed 2026-09-01)

### Decision-changing adaptation

A staff-planning skill should demand a mechanism, not merely a vision document:

1. Named internal/external users and observed friction.
2. Multi-year direction with near-term milestones.
3. Baseline and outcome metrics.
4. Reusable platform/default/check—not repeated persuasion.
5. Cross-team decision mechanism and explicit ownership.
6. Hands-on technical proof through code, design review, debugging, or prototypes.
7. Operational ownership and cleanup.
8. Mentorship/standards that make the capability persist beyond one leader.

### Recommended skill

**`stripe-staff-technical-planning`**

- Trigger: multi-team roadmap, platform strategy, ambiguous staff-level initiative, quarterly planning, architecture influence without authority.
- Output: user/friction evidence; strategic thesis; milestones; success/guardrail metrics; decision map; platform leverage; risk and learning plan.
- Boundary: not performance leveling or promotion scoring; public listings do not reveal Stripe's complete internal rubric.

## Horizon 6: interviews, hiring, and people expectations

### Current official boundary

Stripe's careers page currently confirms only broad stages: recruiter screen, technical or skills assessment, then team interviews; sequence and timing vary by role, level, and location. It also warns candidates that legitimate recruiters use LinkedIn or `@stripe.com`, never request payment, financial information, or login credentials, and can be verified through `careers@stripe.com`. ([Stripe Careers](https://stripe.com/careers), current-as-accessed 2026-09-01)

Current emerging-talent guidance says good ideas should not wait for seniority, describes mentorship and technically rigorous teams, and lists rolling full-time/apprenticeship hiring with academic-calendar internship timing. It does not disclose technical interview content. ([Emerging talent](https://stripe.com/careers/emerging-talent), current-as-accessed 2026-09-01)

The current generalist platform listing says its interview process is language agnostic and emphasizes collaboration, autonomy, generalist problem solving, reliable/extensible platforms, maintainable interfaces, and production debugging. This is role-specific evidence—not a company-wide interview rubric. ([Developer & End User Experience Platform role](https://stripe.com/careers/listing/full-stack-engineer-developer-end-user-experience-platform/6567104), current listing accessed 2026-09-01)

Stripe's scaling guide remains the richest first-party hiring-system source: realistic work samples; stable rubrics with behavioral anchors; interviewer training; candidate preparation; candidate-experience surveys; and feedback loops. It is undated/historical guidance and cannot establish the current private Stripe loop. ([Scaling engineering organizations](https://stripe.com/guides/atlas/scaling-eng), historical/undated, accessed 2026-09-01)

### Decision-changing adaptation

Two separate skills are possible, but evidence strength differs:

**`stripe-engineering-interview-prep`** — justified with a strict boundary.

- Trigger: Stripe engineering application or interview preparation.
- Focus: realistic coding in candidate's strongest language; interface clarity; production failure reasoning; user impact; end-to-end ownership; evidence-responsive trade-offs; collaboration stories.
- Must say: exact loop varies; do not predict questions, rounds, scoring, or current team matching beyond official pages.
- Must verify: role still open and current description before tailoring.

**`stripe-evidence-based-hiring-system`** — useful as a general hiring-design adaptation, but not as a “current Stripe interviewer” persona.

- Trigger: designing an engineering interview process, rubric, interviewer training, candidate communications, or candidate-experience measurement.
- Output: role outcomes; realistic work sample; behavioral anchors; independent evidence; interviewer calibration; candidate prep; survey/feedback loop.
- Boundary: label source historical and adaptation general; never claim current confidential Stripe practice.

## Additional cross-horizon skill: safe agentic delivery

Stripe's 2026 Minions article gives enough concrete evidence for a specialist coding-agent safety skill. Stripe describes isolated, replaceable QA devboxes without production data or arbitrary network egress; small task-relevant tool sets; directory/file-scoped rule files; blueprints combining deterministic steps with agent judgment; left-shifted local lint feedback; one bounded full-CI repair loop; and mandatory human review. ([Minions, Part 2](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2), 2026-02-19)

### Recommended skill

**`stripe-safe-agentic-delivery`**

- Trigger: autonomous or unattended code changes, batch agent work, agentic migrations, many parallel tasks.
- Output: isolated environment; permission/data boundary; scoped context and tools; deterministic mandatory steps; test/CI budget; escalation limit; human review handoff.
- Boundary: no inference that an ordinary local agent has Stripe's controls; absence of isolated QA and credential boundaries should block unattended high-impact execution.

## Priority order for skill creation

| Priority | Skill | Why now | Overlap risk |
|---:|---|---|---|
| 1 | `stripe-api-contract-governance` | New 2026 source supplies a complete review/release pipeline | Low |
| 2 | `stripe-online-data-migration` | 2024 source supplies concrete fencing, CDC, verification, reversal protocol | Medium with existing broad migration guidance |
| 3 | `stripe-behavioral-replay-verification` | New 2026 series provides distinctive test architecture and privacy constraints | Low |
| 4 | `stripe-critical-path-readiness` | New data-plane and current role evidence deepen reliability gates | Medium with current production-readiness references |
| 5 | `stripe-codebase-migration-service` | New 2026 build-graph system changes recurring-migration planning | Low |
| 6 | `stripe-invariant-recovery-design` | New 2026 state-machine pattern supports complex remediation safely | Low, but narrower trigger |
| 7 | `stripe-risk-aware-ci-selection` | Previously unavailable article body now provides implementable mechanism | Low, but only useful at large suite scale |
| 8 | `stripe-staff-technical-planning` | Useful focused planning contract | Medium with existing staff-engineer material |
| 9 | `stripe-safe-agentic-delivery` | Concrete modern evidence; useful for Codex workflows | Low |
| 10 | Interview/hiring skills | Useful, but current public evidence remains intentionally broad | High; keep conservative |

Creation recommendation: implement priorities 1–6 and 9 as independent references or thin skills. Add priority 7 only for repositories with proven CI scale pain. Keep staff/interview/hiring as focused modes or references unless repeated usage justifies separate routing.

## Source register

| Horizon | Source | Date/status | New decision value |
|---|---|---|---|
| API | [How API changes flow into Stripe's developer products](https://stripe.dev/blog/how-api-changes-flow-into-stripes-developer-products) | 2026-06-15 | Canonical schema pipeline, validation, semantic diffs, historical snapshots, downstream propagation |
| Reliability | [Building a data plane from scratch](https://stripe.dev/blog/building-a-data-plane-from-scratch-stripes-own-high-performance-distributed-proxy) | 2026-08-26 | Explicit reliability target, production-shaped QA load risk, comparative acceptance evidence |
| Recovery | [Graph search and state machines for auto-remediation](https://stripe.dev/blog/how-stripe-uses-graph-search-and-state-machines-to-auto-remediate-a-global-database-fleet) | 2026-07-16 | Invariant-preserving search, simulator/executor parity, partial remediation, replan after cancellation |
| Data migration | [DocDB zero-downtime migrations](https://stripe.dev/blog/how-stripes-document-databases-supported-99.999-uptime-with-zero-downtime-data-migrations) | 2024-06-06; historical snapshot | CDC/checkpoints, bidirectional reversal path, snapshot verification, version-gated fence/cutover |
| Code migration | [Modern Java at Stripe](https://stripe.dev/blog/modern-java-at-stripe-language-upgrades-as-a-service) | 2026-05-27 | Live build-graph eligibility, bounded idempotent PRs, blocker telemetry, targeted runtime rollback |
| Replay testing | [Apache Spark replay, Part 1](https://stripe.dev/blog/microservice-testing-with-apache-spark) | 2026-06-01 | Historical distribution as executable test asset; privacy-minimized behavioral diffs |
| Replay testing | [Apache Spark replay, Part 2](https://stripe.dev/blog/microservice-testing-with-apache-spark-part-2) | 2026-06-08 | Same logic online/offline; dependency state as data; explainable diffs; explicit fidelity limits |
| CI | [Selective Test Execution](https://stripe.dev/blog/selective-test-execution-at-stripe-fast-ci-for-a-50m-line-ruby-monorepo) | 2026-04-09 | Observed dependencies, mandatory-test escape hatches, generated files, reproducible baseline |
| Time testing | [Test clocks](https://stripe.com/blog/test-clocks-how-we-made-it-easier-to-test-stripe-billing-integrations) | 2024-05-09; historical snapshot | Time-provider seam, event-directed advancement, real-scheduler isolation |
| Agent safety | [Minions, Part 2](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2) | 2026-02-19 | Isolation, scoped tools/rules, deterministic gates, bounded CI loops, human review |
| Staff/reliability | [Staff Engineer, Core Infrastructure](https://stripe.com/careers/listing/staff-engineer-core-infrastructure/8070949) | Current listing accessed 2026-09-01 | Evidence-based launch/failover readiness and milestone-driven multi-year strategy |
| Staff/internal platform | [Terminal Developer Productivity](https://stripe.com/en-be/jobs/listing/staff-software-engineer-terminal-developer-productivity/7705412) | Historical search snapshot; canonical listing now 404 | Developer-user discovery, DX metrics, operational ownership, simple robust design |
| General expectations | [Developer & End User Experience Platform](https://stripe.com/careers/listing/full-stack-engineer-developer-end-user-experience-platform/6567104) | Current listing accessed 2026-09-01 | Language-agnostic coding, future-proof interfaces, sustainable trade-offs, peer success |
| Hiring | [Stripe Careers](https://stripe.com/careers) | Current-as-accessed 2026-09-01 | Only authoritative broad stages and recruiter-authentication guidance |
| Early career | [Emerging talent](https://stripe.com/careers/emerging-talent) | Current-as-accessed 2026-09-01 | Agency regardless of tenure, mentorship, rolling/application timing |
| Hiring system | [Scaling engineering organizations](https://stripe.com/guides/atlas/scaling-eng) | Undated/historical; accessed 2026-09-01 | Realistic work samples, anchored rubrics, interviewer training, candidate feedback loop |

## Remaining gaps

- No public current Stripe engineering level matrix, promotion rubric, or complete staff/senior-staff scope framework.
- No authoritative current technical-interview question set, round-by-round loop, scoring guide, or interviewer calibration procedure. Third-party interview reports should not fill this gap in a Stripe-branded skill.
- No complete current internal API approval, architecture-review, incident-command, postmortem, on-call, capacity-planning, or deployment-promotion process.
- No published miss-rate audit or false-negative measurement for Selective Test Execution. A derived skill must require local selector validation rather than treating Stripe's “without sacrificing safety” statement as a portable guarantee.
- Replay articles explain architecture and limitations, but not universal acceptance thresholds. Teams must define materiality and escalation thresholds from their own invariants.
- The automated-remediation article gives high-level safety invariants, but not authorization, audit, access-control, or emergency-stop implementation details. Those controls remain mandatory design questions.
- Some 2026 mechanisms are highly specific to Stripe scale. Skills must include a “simplest sufficient mechanism” check so small systems do not imitate fleet-scale machinery without evidence.

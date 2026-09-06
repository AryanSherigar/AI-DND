# Gap Fix Checklist

Working list from docs/fixes_and_evaluation_findings.md §21-23's severity ranking. Each item: research
industry prior art (Mem0, Supermemory, Zep/Graphiti, others already used this session) before fixing, live-verify
against the actual failing instance(s), full test suite, then check the box. Not removed once checked — each
item links to its write-up in fixes_and_evaluation_findings.md.

- [x] **1. Extraction drops qualifying details** — GPA degree, Instagram handle, itemized preferences all lost
      when a detail sits inside a longer descriptive sentence. 3 confirmed instances, 3 categories.
- [x] **2. Temporal filter treats same-day facts as future** — `observed_at` (statement time) used as event time;
      discards genuinely-past events stated later the same day as the question. Up to 74% fact loss in one
      instance.
- [x] **3. Retrieval dilution by generic/tangential content** — user's own topic-adjacent content (wedding
      planning, NAS specs) crowds out the few facts that answer the question. Architecturally harder; one prior
      attempt (user-affinity RRF channel) already reverted after regressing a working case.
- [x] **4. Reader date-arithmetic inconsistency** — states the correct span in prose, computes the wrong number.
      Fixed via structured self-reported-operand verification (§26); 3 real bugs found and fixed in the
      mechanism itself (missing `Literal` import, garbled date-as-float operands, endpoint substitution, unit
      over-correction). Education years 3/5→5/5, mountain bike 0/5→4/5 (compounds with item 5).
- [x] **5. Reader picks the wrong near-duplicate fact** — intention ("considering upgrading") beats completion
      ("upgraded today") despite both correctly dated. Fixed via a concrete worked example in the reader prompt
      (§27) — an abstract instruction alone did not work. A real regression found and fixed along the way
      (magazine-subscription case) turned out to be a pre-existing, unrelated retrieval gap, not caused by this
      fix — documented honestly rather than claimed as resolved.
- [x] **6. Reader gives a generic answer despite on-topic facts present** — investigated (§28), does not
      reproduce as a distinct reader-side bug on either remaining wrong instance: both trace to upstream gaps
      already tracked under items 1 and 3 (a fact absent from the candidate pool entirely, and a fact absent
      from the extracted corpus at all). No reader-prompt change was indicated by the evidence, so none was
      made. Full 30-instance re-score with items 4+5: 73.3% → **76.7%**.
- [x] **7. Overall-flow pass** — refreshed against the 2026-09-06 executable harness, not only the older
      memory-quality findings. The pass is complete; its newly discovered gaps are **not** all fixed. See
      `BEGINNER_BUILD_FLOW.md` Sections 46–54 for the current P0/P1/P2 roadmap: authored-fact retrieval
      projections, tenant-safe streaming/auth, journal privacy, clean Gemini/test migration, durable workers,
      entity-cache hydration, fact lifecycle reconciliation, graph-read scaling, and harness validation.

After each fix: full re-ingest is only required if the fix touches ingestion (items 1, 2 partially); items 3-6
are retrieval/reader-side and can be verified with the cheap retrieval-only harness (§22) against already-
ingested data.

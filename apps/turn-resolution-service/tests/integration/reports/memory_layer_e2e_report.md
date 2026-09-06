# Memory-layer 10-turn integration report

Total wall-clock time: 22.21s

## Latency per call type

| call | n | min | mean | p95 | max |
|---|---|---|---|---|---|
| clone_template_memory_space (wall-clock) | 1 | 1081.9ms | 1081.9ms | 1081.9ms | 1081.9ms |
| get_batch_status | 18 | 4.6ms | 9.8ms | 13.5ms | 13.5ms |
| ingest_batch | 2 | 61.2ms | 62.4ms | 63.7ms | 63.7ms |
| ingest_batch_turnaround (POST to succeeded) | 2 | 7093.6ms | 8095.4ms | 9097.2ms | 9097.2ms |
| ingest_scenario_template (publish, wall-clock) | 1 | 2577.8ms | 2577.8ms | 2577.8ms | 2577.8ms |
| query_memory | 12 | 31.4ms | 68.9ms | 171.6ms | 171.6ms |

## Behavior assertions

| behavior | result | detail |
|---|---|---|
| batch_ingest_timing | PASS | 2 batches fired, 1 facts created across the last 2 |
| fact_round_trip | PASS | turn-2 narrated fact retrievable at turn 10 |
| authored_facts_indexed_at_all | FAIL | 0/4 authored fixture facts present in gated retrieval -- 0/4 means mem1 gap #46 (authored facts never projected into the Postgres retrieval indexes), and makes the two behaviors below unevaluable rather than passing/failing |
| superseded_fact_id_supersession | FAIL | no authored fact indexed at all -- mem1 gap #46, not evaluable |
| visibility_filtering_when_gated | FAIL | no authored fact indexed at all -- mem1 gap #46, not evaluable |

## Fact counts

- facts_authored: 4
- facts_created_by_ingest: 1
- facts_retrieved_round_trip_query: 4
- facts_retrieved_gated_query: 4

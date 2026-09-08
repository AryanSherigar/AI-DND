from __future__ import annotations

import logging
import unittest

from context_memory.core.logging import (
    disable_metrics_collection,
    drain_metrics,
    enable_metrics_collection,
    get_logger,
    setup_logging,
    timed_operation,
)


class LoggingAndLatencyTests(unittest.TestCase):
    def tearDown(self) -> None:
        disable_metrics_collection()  # never leak collection state into another test

    def test_setup_logging_configures_logger(self) -> None:
        setup_logging(level=logging.DEBUG)
        logger = get_logger("test.module")
        self.assertEqual(logger.name, "test.module")

    def test_timed_operation_success(self) -> None:
        logger = get_logger("test.timer")
        with timed_operation(logger, "test_op", {"meta": "val"}) as ctx:
            ctx["custom_result"] = 123
            x = sum([1, 2, 3])
        self.assertEqual(x, 6)
        self.assertEqual(ctx["custom_result"], 123)

    def test_timed_operation_records_failure_and_reraises(self) -> None:
        logger = get_logger("test.timer.fail")
        with self.assertRaises(ValueError):
            with timed_operation(logger, "failing_op"):
                raise ValueError("expected failure")


class MetricsCollectionTests(unittest.TestCase):
    """`enable_metrics_collection`/`drain_metrics` -- opt-in structured sink
    `timed_operation` feeds in parallel with its existing text logs."""

    def tearDown(self) -> None:
        disable_metrics_collection()

    def test_disabled_by_default_collects_nothing(self) -> None:
        logger = get_logger("test.metrics.disabled")
        with timed_operation(logger, "some_op", {"chunk_id": "c1"}):
            pass
        self.assertEqual(
            drain_metrics(), []
        )  # never enabled -- draining a None sink is an empty list, not an error

    def test_enabled_collects_operation_name_elapsed_and_metadata(self) -> None:
        enable_metrics_collection()
        logger = get_logger("test.metrics.enabled")
        with timed_operation(logger, "some_op", {"chunk_id": "c1", "facts": 3}) as ctx:
            ctx["accepted"] = 2
        records = drain_metrics()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["operation"], "some_op")
        self.assertEqual(record["outcome"], "done")
        self.assertEqual(record["chunk_id"], "c1")
        self.assertEqual(record["facts"], 3)
        self.assertEqual(
            record["accepted"], 2
        )  # context mutated inside the `with` block is captured too
        self.assertIsInstance(record["elapsed_ms"], float)
        self.assertGreaterEqual(record["elapsed_ms"], 0.0)
        self.assertIn("wall_time", record)

    def test_failed_operation_is_recorded_with_error_metadata_and_still_reraises(
        self,
    ) -> None:
        enable_metrics_collection()
        logger = get_logger("test.metrics.fail")
        with self.assertRaises(ValueError):
            with timed_operation(logger, "failing_op", {"chunk_id": "c2"}):
                raise ValueError("boom")
        records = drain_metrics()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["outcome"], "failed")
        self.assertEqual(records[0]["error_type"], "ValueError")
        self.assertIn("boom", records[0]["error"])
        self.assertEqual(records[0]["chunk_id"], "c2")

    def test_drain_clears_the_buffer_so_the_next_drain_only_sees_whats_new(
        self,
    ) -> None:
        enable_metrics_collection()
        logger = get_logger("test.metrics.drain")
        with timed_operation(logger, "op_one"):
            pass
        first = drain_metrics()
        self.assertEqual(len(first), 1)
        second = drain_metrics()
        self.assertEqual(second, [])  # already drained, nothing new happened
        with timed_operation(logger, "op_two"):
            pass
        third = drain_metrics()
        self.assertEqual(len(third), 1)
        self.assertEqual(third[0]["operation"], "op_two")

    def test_disable_stops_collection(self) -> None:
        enable_metrics_collection()
        logger = get_logger("test.metrics.disable")
        with timed_operation(logger, "op_before"):
            pass
        disable_metrics_collection()
        with timed_operation(logger, "op_after"):
            pass
        self.assertEqual(
            drain_metrics(), []
        )  # disabled before op_after ran, and disabling drops what was pending


if __name__ == "__main__":
    unittest.main()

import unittest




class QueryRewriteCacheTests(unittest.TestCase):
    """§9: rewrites are nondeterministic on this provider, so identical questions
    must not re-roll the dice."""

    class _CountingClient:
        def __init__(self, outputs):
            self._outputs = list(outputs)
            self.calls = 0

        def structured_completion(self, *a, **kw):
            from context_memory.retrieval.models import QueryRewriterOutput
            self.calls += 1
            return self._outputs[min(self.calls - 1, len(self._outputs) - 1)]

    def _outputs(self):
        from context_memory.retrieval.models import QueryRewriterOutput
        return [
            QueryRewriterOutput(decomposed_queries=["q"], synonyms=["a", "b"]),
            QueryRewriterOutput(decomposed_queries=["q"], synonyms=["c"]),
        ]

    def test_repeat_question_is_served_from_cache(self) -> None:
        from context_memory.retrieval.query_rewriter import QueryRewriter
        client = self._CountingClient(self._outputs())
        rewriter = QueryRewriter(client, cache={})
        first = rewriter.rewrite("same question")
        second = rewriter.rewrite("same question")
        self.assertEqual(client.calls, 1)
        self.assertEqual(first.synonyms, second.synonyms)

    def test_distinct_questions_are_not_conflated(self) -> None:
        from context_memory.retrieval.query_rewriter import QueryRewriter
        client = self._CountingClient(self._outputs())
        rewriter = QueryRewriter(client, cache={})
        rewriter.rewrite("question one")
        rewriter.rewrite("question two")
        self.assertEqual(client.calls, 2)

    def test_no_cache_reproduces_old_behaviour(self) -> None:
        from context_memory.retrieval.query_rewriter import QueryRewriter
        client = self._CountingClient(self._outputs())
        rewriter = QueryRewriter(client, cache=None)
        first = rewriter.rewrite("same question")
        second = rewriter.rewrite("same question")
        self.assertEqual(client.calls, 2)
        self.assertNotEqual(first.synonyms, second.synonyms)


class JsonFileRewriteCacheTests(unittest.TestCase):
    """Persistence: a second process must reuse the first run's rewrites."""

    def _out(self, syns):
        from context_memory.retrieval.models import QueryRewriterOutput
        return QueryRewriterOutput(decomposed_queries=["q"], synonyms=syns)

    def test_survives_a_fresh_instance(self) -> None:
        import tempfile
        from pathlib import Path
        from context_memory.retrieval.query_rewriter import JsonFileRewriteCache

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "rw.json")
            first = JsonFileRewriteCache(path)
            first["question"] = self._out(["a", "b"])

            second = JsonFileRewriteCache(path)  # simulates a new process
            self.assertEqual(second["question"].synonyms, ["a", "b"])
            self.assertEqual(len(second), 1)

    def test_missing_file_starts_empty(self) -> None:
        import tempfile
        from pathlib import Path
        from context_memory.retrieval.query_rewriter import JsonFileRewriteCache

        with tempfile.TemporaryDirectory() as tmp:
            cache = JsonFileRewriteCache(str(Path(tmp) / "absent.json"))
            self.assertEqual(len(cache), 0)

    def test_corrupt_file_degrades_to_empty_not_crash(self) -> None:
        import tempfile
        from pathlib import Path
        from context_memory.retrieval.query_rewriter import JsonFileRewriteCache

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json")
            cache = JsonFileRewriteCache(str(path))
            self.assertEqual(len(cache), 0)
            cache["q"] = self._out(["x"])  # still usable
            self.assertEqual(JsonFileRewriteCache(str(path))["q"].synonyms, ["x"])

    def test_engine_uses_persistent_cache_when_path_set(self) -> None:
        import tempfile
        from pathlib import Path
        from context_memory.core.config import Config
        from context_memory.retrieval import HybridRetrievalEngine
        from context_memory.retrieval.query_rewriter import JsonFileRewriteCache

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "rw.json")
            config = Config(query_rewrite_cache_path=path)
            engine = HybridRetrievalEngine(
                llm_client=object(), embedder=object(), pg_connection=object(),
                hydra_client=object(), config=config,
            )
            self.assertIsInstance(engine._rewrite_cache, JsonFileRewriteCache)

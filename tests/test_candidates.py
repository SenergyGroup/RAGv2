import os
import unittest
from unittest import mock

os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai")


class MultiNeedRetrieveTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("pinecone.Pinecone")
        self.addCleanup(patcher.stop)
        MockPinecone = patcher.start()
        MockPinecone.return_value.Index.return_value = mock.MagicMock()

    def _import(self):
        from app.candidates import multi_need_retrieve
        return multi_need_retrieve

    def test_full_story_only_when_no_needs(self):
        multi_need_retrieve = self._import()
        calls = []

        def fake_retrieve(query, top_k=0, **kwargs):
            calls.append((query, top_k, kwargs))
            return [
                {"id": "svc-1", "score": 0.4, "metadata": {"service_id": "svc-1", "resource_name": "Alpha"}}
            ]

        candidates = multi_need_retrieve("help with food", [], retrieve_fn=fake_retrieve)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "help with food")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["service_id"], "svc-1")
        self.assertIn("metadata", candidates[0])

    def test_per_need_fanout_when_needs_present(self):
        multi_need_retrieve = self._import()
        calls = []

        responses = {
            "family needs food": [
                {"id": "svc-1", "score": 0.3, "metadata": {"service_id": "svc-1", "resource_name": "Alpha"}}
            ],
            "food Context: family needs food": [
                {"id": "svc-2", "score": 0.9, "metadata": {"service_id": "svc-2", "resource_name": "Beta"}}
            ],
            "rent Context: family needs food": [
                {"id": "svc-3", "score": 0.5, "metadata": {"service_id": "svc-3", "resource_name": "Gamma"}}
            ],
            "medical Context: family needs food": [
                {"id": "svc-4", "score": 0.6, "metadata": {"service_id": "svc-4", "resource_name": "Delta"}}
            ],
        }

        def fake_retrieve(query, top_k=0, **kwargs):
            calls.append((query, top_k, kwargs))
            return responses.get(query, [])

        needs = [
            {"slug": "food", "query": "food"},
            {"slug": "rent", "query": "rent"},
            {"slug": "medical", "query": "medical"},
            {"slug": "extra", "query": "extra"},
        ]

        candidates = multi_need_retrieve(
            "family needs food",
            needs,
            retrieve_fn=fake_retrieve,
            per_need_limit=3,
            full_top_k=10,
            per_need_top_k=10,
        )

        self.assertEqual(calls[0][0], "family needs food")
        per_need_calls = calls[1:]
        self.assertEqual(len(per_need_calls), 3)
        self.assertTrue(all("Context:" in q[0] for q in per_need_calls))
        self.assertEqual(len(candidates), 4)

    def test_dedupe_accumulates_matched_needs(self):
        multi_need_retrieve = self._import()
        calls = []

        def fake_retrieve(query, top_k=0, **kwargs):
            calls.append((query, kwargs))
            if query == "story":
                return [
                    {"id": "svc-1", "score": 0.2, "metadata": {"service_id": "svc-1", "resource_name": "Alpha"}}
                ]
            return [
                {
                    "id": "svc-1",
                    "score": 0.8,
                    "metadata": {"service_id": "svc-1", "resource_name": "Alpha", "extra": "x"},
                }
            ]

        needs = [{"slug": "housing", "query": "housing assistance"}]

        candidates = multi_need_retrieve("story", needs, retrieve_fn=fake_retrieve)

        self.assertEqual(len(calls), 2)
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["service_id"], "svc-1")
        self.assertEqual(candidate["matched_needs"], ["housing"])
        self.assertAlmostEqual(candidate["score"], 0.8)
        self.assertEqual(candidate["metadata"].get("extra"), "x")

    def test_retrieve_kwargs_forwarded(self):
        multi_need_retrieve = self._import()

        calls = []

        def fake_retrieve(query, top_k=0, **kwargs):
            calls.append(kwargs)
            return []

        multi_need_retrieve(
            "story",
            [],
            retrieve_fn=fake_retrieve,
            retrieve_kwargs={"metadata_filters": {"city": "Test"}, "namespace": "ns"},
            full_top_k=2,
            per_need_top_k=3,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["metadata_filters"], {"city": "Test"})
        self.assertEqual(calls[0]["namespace"], "ns")


if __name__ == "__main__":
    unittest.main()

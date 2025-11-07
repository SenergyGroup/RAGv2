import json
import os
import unittest
from unittest import mock

os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai")

with mock.patch("pinecone.Pinecone") as MockPinecone:
    MockPinecone.return_value.Index.return_value = mock.MagicMock()
    from app.main import NeedRequest, needs as needs_endpoint

from app.needs import FALLBACK_RESPONSE, extract_needs


class NeedsExtractionTests(unittest.TestCase):
    def test_valid_story_returns_needs(self):
        payload = {"needs": [{"slug": "food-support", "query": "food pantry near downtown"}], "confidence": 0.75}

        def stub_fetcher(messages, schema):
            return json.dumps(payload)

        result = extract_needs("Family needs groceries and meals", response_fetcher=stub_fetcher)
        self.assertGreaterEqual(len(result["needs"]), 1)
        self.assertAlmostEqual(result["confidence"], 0.75)
        self.assertEqual(result["needs"][0]["slug"], "food-support")

    def test_empty_story_returns_empty(self):
        request = NeedRequest(user_story="   ")
        response = needs_endpoint(request)
        expected = dict(FALLBACK_RESPONSE)
        expected["candidates"] = []
        self.assertEqual(response, expected)

    def test_malformed_json_is_handled(self):
        def stub_fetcher(messages, schema):
            return "not-json"

        result = extract_needs("Needs rent help", response_fetcher=stub_fetcher)
        self.assertEqual(result, FALLBACK_RESPONSE)


if __name__ == "__main__":
    unittest.main()

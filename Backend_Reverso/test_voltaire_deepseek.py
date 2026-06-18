import json
import unittest
from unittest.mock import patch

import voltaire_deepseek as vd


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class DeepSeekClientTests(unittest.TestCase):
    def setUp(self):
        self._api_key_patcher = patch("voltaire_deepseek.API_KEY", "sk-test-key")
        self._api_key_patcher.start()

    def tearDown(self):
        self._api_key_patcher.stop()

    def test_analyze_phrase_parses_strict_json(self):
        outer = {
            "choices": [{"message": {"content": json.dumps({
                "has_error": True,
                "corrected": "Je suis content de te voir demain.",
                "error_span": "sui / voire",
                "explanation": "Conjugaison de être et confusion voir/voire.",
                "confidence": 0.93,
            }, ensure_ascii=False)}}]
        }
        captured = {}

        def fake_urlopen(req, timeout=0):
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            captured["auth"] = req.headers.get("Authorization")
            return FakeResponse(outer)

        with patch("urllib.request.urlopen", fake_urlopen):
            result = vd.analyze_phrase("Je sui content de te voire demain.")

        self.assertTrue(result["has_error"])
        self.assertEqual(result["corrected"], "Je suis content de te voir demain.")
        self.assertEqual(result["error_span"], "sui / voire")
        self.assertEqual(captured["auth"], "Bearer sk-test-key")
        self.assertEqual(captured["payload"]["model"], "deepseek-v4-flash")

    def test_analyze_phrase_handles_array_wrapped_json(self):
        outer = {
            "choices": [{"message": {"content": json.dumps([{
                "has_error": False,
                "corrected": "Il est venu hier.",
                "error_span": "",
                "explanation": "",
                "confidence": 0.9,
            }], ensure_ascii=False)}}]
        }
        with patch("urllib.request.urlopen", lambda req, timeout=0: FakeResponse(outer)):
            result = vd.analyze_phrase("Il est venu hier.")
        self.assertFalse(result["has_error"])
        self.assertEqual(result["corrected"], "Il est venu hier.")

    def test_analyze_phrase_forces_original_when_no_error(self):
        outer = {"choices": [{"message": {"content": '{"has_error": false, "corrected": "Phrase changée", "confidence": 0.8}'}}]}
        with patch("urllib.request.urlopen", lambda req, timeout=0: FakeResponse(outer)):
            result = vd.analyze_phrase("Il est venu hier.")
        self.assertFalse(result["has_error"])
        self.assertEqual(result["corrected"], "Il est venu hier.")

    def test_missing_api_key_raises(self):
        with patch("voltaire_deepseek.API_KEY", ""):
            with self.assertRaises(vd.DeepSeekUnavailable):
                vd.analyze_phrase("test")


if __name__ == "__main__":
    unittest.main()

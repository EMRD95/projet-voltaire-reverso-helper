import json
import unittest
from unittest.mock import patch

import voltaire_koboldcpp as vk


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class KoboldCppClientTests(unittest.TestCase):
    def setUp(self):
        self._model_patcher = patch("voltaire_koboldcpp.MODEL", "test-model")
        self._model_patcher.start()

    def tearDown(self):
        self._model_patcher.stop()

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

        with patch("urllib.request.urlopen", fake_urlopen), \
             patch("voltaire_koboldcpp.API_KEY", "***"):
            result = vk.analyze_phrase("Je sui content de te voire demain.")

        self.assertTrue(result["has_error"])
        self.assertEqual(result["corrected"], "Je suis content de te voir demain.")
        self.assertEqual(result["error_span"], "sui / voire")
        self.assertEqual(captured["auth"], "Bearer ***")
        self.assertEqual(captured["payload"]["model"], "test-model")

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
            result = vk.analyze_phrase("Il est venu hier.")
        self.assertFalse(result["has_error"])
        self.assertEqual(result["corrected"], "Il est venu hier.")

    def test_analyze_phrase_forces_original_when_no_error(self):
        outer = {"choices": [{"message": {"content": '{"has_error": false, "corrected": "Phrase changée", "confidence": 0.8}'}}]}
        with patch("urllib.request.urlopen", lambda req, timeout=0: FakeResponse(outer)):
            result = vk.analyze_phrase("Il est venu hier.")
        self.assertFalse(result["has_error"])
        self.assertEqual(result["corrected"], "Il est venu hier.")

    def test_missing_model_raises(self):
        with patch("voltaire_koboldcpp.MODEL", ""):
            with self.assertRaises(vk.KoboldCppUnavailable):
                vk.analyze_phrase("test")


if __name__ == "__main__":
    unittest.main()

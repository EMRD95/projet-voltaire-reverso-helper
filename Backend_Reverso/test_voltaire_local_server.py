import json
import threading
import time
import unittest
import urllib.request
from unittest.mock import patch

import voltaire_local_server as srv


class LocalServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = srv.make_server("127.0.0.1", 8766)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        srv._analysis_cache.clear()
        self._corrector_patcher = patch.object(srv, "CORRECTOR", "koboldcpp")
        self._corrector_patcher.start()
        self._llm_patcher = patch("voltaire_local_server.vk.analyze_phrase", side_effect=self._fake_llm)
        self.mock_llm = self._llm_patcher.start()

    def tearDown(self):
        self._llm_patcher.stop()
        self._corrector_patcher.stop()

    @staticmethod
    def _fake_llm(phrase):
        corrections = {
            "Je sui content de te voire demain.": {
                "has_error": True,
                "corrected": "Je suis content de te voir demain.",
                "error_span": "sui / voire",
                "explanation": "Conjugaison de être et confusion voir/voire.",
                "confidence": 0.93,
            },
            "Nous attendont la réponse de l'agence.": {
                "has_error": True,
                "corrected": "Nous attendons la réponse de l'agence.",
                "error_span": "attendont",
                "explanation": "Avec nous, le verbe prend -ons.",
                "confidence": 0.9,
            },
        }
        return corrections.get(phrase, {
            "has_error": False,
            "corrected": phrase,
            "error_span": "",
            "explanation": "",
            "confidence": 0.8,
        })

    def post_json(self, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8766/check",
            data=data,
            headers={"Content-Type": "application/json", "Origin": "https://www.projet-voltaire.fr"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read().decode("utf-8")
            return r, json.loads(body)

    def test_options_cors_preflight_allows_tampermonkey_fetch(self):
        req = urllib.request.Request(
            "http://127.0.0.1:8766/check",
            headers={
                "Origin": "https://www.projet-voltaire.fr",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
                "Access-Control-Request-Private-Network": "true",
            },
            method="OPTIONS",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            self.assertEqual(r.status, 204)
            self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")
            self.assertEqual(r.headers["Access-Control-Allow-Private-Network"], "true")

    def test_check_endpoint_extracts_phrase_and_returns_analysis(self):
        raw = """
        Projet Voltaire - Test blanc
        Si vous voyez une faute, cliquez dessus ; sinon, cliquez sur le bouton « Il n'y a pas de faute ».
        Je sui content de te voire demain.
        Il n'y a pas de faute
        """
        response, body = self.post_json({"text": raw})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(body["provider"], "koboldcpp")
        self.assertEqual(body["phrase"], "Je sui content de te voire demain.")
        self.assertTrue(body["has_error"])
        self.assertEqual(body["corrected"], "Je suis content de te voir demain.")
        self.assertEqual(body["error_span"], "sui / voire")
        self.assertIn("voir", body["explanation"])

    def test_check_endpoint_prefers_explicit_dom_phrase(self):
        raw = """
        Projet Voltaire - Test blanc
        Si vous voyez une faute, cliquez dessus ; sinon, cliquez sur le bouton « Il n'y a pas de faute ».
        Menu d'accessibilité
        """
        response, body = self.post_json({"text": raw, "phrase": "Nous attendont la réponse de l'agence."})
        self.assertEqual(response.status, 200)
        self.assertEqual(body["phrase"], "Nous attendont la réponse de l'agence.")
        self.assertTrue(body["has_error"])
        self.assertIn("attendons", body["corrected"])

    def test_check_endpoint_caches_same_phrase_to_avoid_llm_spam(self):
        payload = {"text": "", "phrase": "Je sui content de te voire demain."}
        response1, body1 = self.post_json(payload)
        response2, body2 = self.post_json(payload)
        self.assertEqual(response1.status, 200)
        self.assertEqual(response2.status, 200)
        self.assertFalse(body1["cached"])
        self.assertTrue(body2["cached"])
        self.assertEqual(body2["corrected"], "Je suis content de te voir demain.")
        self.assertEqual(self.mock_llm.call_count, 1)

    def test_health_endpoint(self):
        with urllib.request.urlopen("http://127.0.0.1:8766/health", timeout=5) as r:
            self.assertEqual(r.status, 200)
            body = json.loads(r.read().decode("utf-8"))
            self.assertEqual(body["ok"], True)
            self.assertEqual(body["service"], "voltaire-helper")
            self.assertEqual(body["corrector"], "koboldcpp")


if __name__ == "__main__":
    unittest.main()

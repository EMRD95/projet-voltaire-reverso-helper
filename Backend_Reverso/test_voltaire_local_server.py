import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import voltaire_local_server as srv


def _fake_reverso(phrase):
    # Correction connue pour le test, sans appel réseau.
    corrections = {
        "Je sui content de te voire demain.": "Je suis content de te voir demain.",
        "Nous attendont la réponse de l'agence.": "Nous attendons la réponse de l'agence.",
    }
    return corrections.get(phrase, phrase)


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
        self._reverso_patcher = patch("voltaire_local_server.vc.call_reverso", side_effect=_fake_reverso)
        self._reverso_patcher.start()

    def tearDown(self):
        self._reverso_patcher.stop()

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
        self.assertEqual(body["phrase"], "Je sui content de te voire demain.")
        self.assertTrue(body["has_error"])
        self.assertEqual(body["corrected"], "Je suis content de te voir demain.")

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

    def test_health_endpoint(self):
        with urllib.request.urlopen("http://127.0.0.1:8766/health", timeout=5) as r:
            self.assertEqual(r.status, 200)
            self.assertEqual(json.loads(r.read().decode("utf-8"))["ok"], True)


if __name__ == "__main__":
    unittest.main()

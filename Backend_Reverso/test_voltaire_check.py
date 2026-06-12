import json
import unittest
from unittest.mock import patch

import voltaire_check as vc


class VoltaireCheckTests(unittest.TestCase):
    def test_extract_phrase_from_powertoys_ocr_noise(self):
        raw = """
        Projet Voltaire - Test blanc
        Si vous voyez une faute, cliquez dessus ; sinon, cliquez sur le bouton « Il n'y a pas de faute ».
        Les employées de cette entreprise sont très compétents.
        Il n'y a pas de faute
        Valider la réponse
        """
        self.assertEqual(
            vc.extract_phrase(raw),
            "Les employées de cette entreprise sont très compétents.",
        )

    def test_extract_phrase_keeps_short_question_sentence(self):
        raw = """
        Si vous voyez une faute, cliquez dessus ; sinon, cliquez sur le bouton « Il n'y a pas de faute ».
        Il est venu hier.
        Il n'y a pas de faute
        """
        self.assertEqual(vc.extract_phrase(raw), "Il est venu hier.")

    def test_extract_phrase_from_single_line_ocr(self):
        raw = "Projet Voltaire - Test blanc Si vous voyez une faute, cliquez dessus ; sinon, cliquez sur le bouton « Il n'y a pas de faute ». Les employées de cette entreprise sont très compétents. Il n'y a pas de faute Valider la réponse"
        self.assertEqual(
            vc.extract_phrase(raw),
            "Les employées de cette entreprise sont très compétents.",
        )

    def test_extract_phrase_strips_leading_ocr_garbage(self):
        raw = "Projet Voltaire - Test blanc Si vous voyez une faute, cliquez dessus ; sinon, cliquez sur le bouton � Il ny a pas de faute �. Les employées de cette entreprise sont très compétents. Il ny a pas de faute Valider la réponse"
        self.assertEqual(
            vc.extract_phrase(raw),
            "Les employées de cette entreprise sont très compétents.",
        )

    def test_extract_phrase_from_single_word_dom_fragments(self):
        raw = """
        Test blanc
        Cliquez sur la faute
        Si vous voyez une faute, cliquez dessus ; sinon, cliquez sur le bouton « Il n'y a pas de faute ».
        Nous
        attendont
        la
        réponse
        de
        l'agence.
        Il n'y a pas de faute
        Progression
        Temps
        Menu d'accessibilité
        """
        self.assertEqual(vc.extract_phrase(raw), "Nous attendont la réponse de l'agence.")

    def test_extract_phrase_stops_after_no_mistake_button(self):
        raw = """
        Si vous voyez une faute, cliquez dessus ; sinon, cliquez sur le bouton « Il n'y a pas de faute ».
        Il n'y a pas de faute
        Progression
        Temps
        Menu d'accessibilité
        """
        self.assertEqual(vc.extract_phrase(raw), "")

    def test_has_error_false_when_reverso_returns_same_sentence(self):
        result = vc.analyze_result("Il est venu hier.", "Il est venu hier.")
        self.assertFalse(result.has_error)
        self.assertEqual(result.corrected, "Il est venu hier.")

    def test_has_error_true_when_reverso_changes_sentence(self):
        result = vc.analyze_result("Je sui content de te voire demain.", "Je suis content de te voir demain.")
        self.assertTrue(result.has_error)
        self.assertEqual(result.corrected, "Je suis content de te voir demain.")

    def test_reverso_payload_is_valid_json_and_returns_text(self):
        calls = {}

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({"text": "Je suis content."}).encode("utf-8")

        def fake_urlopen(req, timeout=0):
            calls["url"] = req.full_url
            calls["data"] = req.data.decode("utf-8")
            calls["content_type"] = req.headers.get("Content-type")
            return FakeResponse()

        with patch("urllib.request.urlopen", fake_urlopen):
            corrected = vc.call_reverso("Je sui content.")

        self.assertEqual(corrected, "Je suis content.")
        self.assertEqual(calls["url"], vc.REVERSO_URL)
        self.assertEqual(calls["content_type"], "application/json")
        parsed = json.loads(calls["data"])
        self.assertEqual(parsed["text"], "Je sui content.")
        self.assertEqual(parsed["language"], "fra")

    def test_reverso_retries_transient_http_403(self):
        attempts = {"count": 0}

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({"text": "Je suis content."}).encode("utf-8")

        def fake_urlopen(req, timeout=0):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise vc.urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
            return FakeResponse()

        with patch("urllib.request.urlopen", fake_urlopen), patch("time.sleep", lambda _: None):
            corrected = vc.call_reverso("Je sui content.")

        self.assertEqual(corrected, "Je suis content.")
        self.assertEqual(attempts["count"], 2)


if __name__ == "__main__":
    unittest.main()

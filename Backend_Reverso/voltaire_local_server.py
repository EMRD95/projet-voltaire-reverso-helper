#!/usr/bin/env python3
"""Serveur local pour le userscript Projet Voltaire.

Deux backends au choix (configurable via VOLTAIRE_CORRECTOR) :

  reverso    → API Reverso (web, gratuit, parfois rate-limité)
  koboldcpp  → API koboldcpp locale (OpenAI-compatible, modèle au choix)

Flux : page → serveur local :8765 → backend → panneau flottant
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import voltaire_check as vc
import voltaire_koboldcpp as vk

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
CACHE_TTL_SECONDS = 900.0

CORRECTOR = os.environ.get("VOLTAIRE_CORRECTOR", "koboldcpp").strip().lower()
if CORRECTOR not in ("reverso", "koboldcpp"):
    print(f"VOLTAIRE_CORRECTOR={CORRECTOR!r} invalide. Valeurs: reverso, koboldcpp. Utilisation de koboldcpp.")
    CORRECTOR = "koboldcpp"

_cache_lock = threading.Lock()
_analysis_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _call_reverso(phrase: str) -> dict[str, Any]:
    """Appelle l'API Reverso et retourne un payload normalisé."""
    try:
        corrected = vc.call_reverso(phrase)
        analysis = vc.analyze_result(phrase, corrected)
        return {
            "has_error": analysis.has_error,
            "corrected": analysis.corrected,
            "error_span": "",
            "explanation": "",
            "confidence": 0.85 if analysis.has_error else 1.0,
        }
    except Exception as e:
        raise RuntimeError(f"Erreur Reverso: {e}") from e


def _cached_analysis(phrase: str) -> dict[str, Any]:
    now = time.monotonic()
    with _cache_lock:
        cached = _analysis_cache.get(phrase)
        if cached and now - cached[0] <= CACHE_TTL_SECONDS:
            payload = dict(cached[1])
            payload["cached"] = True
            return payload

    if CORRECTOR == "reverso":
        llm = _call_reverso(phrase)
        provider = "reverso"
    else:
        llm = vk.analyze_phrase(phrase)
        provider = "koboldcpp"

    payload = {
        "ok": True,
        "phrase": phrase,
        "corrected": llm["corrected"],
        "has_error": bool(llm["has_error"]),
        "result": "FAUTE PROBABLE" if llm["has_error"] else "PAS DE FAUTE DÉTECTÉE",
        "cached": False,
        "provider": provider,
        "error_span": llm.get("error_span", ""),
        "explanation": llm.get("explanation", ""),
        "confidence": llm.get("confidence", 0.0),
    }
    with _cache_lock:
        _analysis_cache[phrase] = (time.monotonic(), dict(payload))
    return payload


def response_payload(raw_text: str, explicit_phrase: str = "") -> dict[str, Any]:
    phrase = vc.normalize_phrase(explicit_phrase) if explicit_phrase else ""
    if not phrase:
        phrase = vc.extract_phrase(raw_text)
    if not phrase:
        return {
            "ok": False,
            "error": "phrase_not_found",
            "message": "Phrase Projet Voltaire introuvable dans le texte reçu.",
            "phrase": "",
        }
    return _cached_analysis(phrase)


class Handler(BaseHTTPRequestHandler):
    server_version = "VoltaireHelper/4.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Requested-With")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Cache-Control", "no-store")

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError) as e:
            self.log_message("client a fermé la connexion avant la réponse: %s", e)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/health":
            info = {
                "ok": True,
                "service": "voltaire-helper",
                "corrector": CORRECTOR,
            }
            if CORRECTOR == "koboldcpp":
                info["koboldcpp_base_url"] = vk.BASE_URL
                info["model"] = vk.MODEL
            self.send_json(200, info)
        else:
            self.send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/check":
            self.send_json(404, {"ok": False, "error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            body = json.loads(raw) if raw else {}
            text = body.get("text") or ""
            phrase = body.get("phrase") or ""
            if not isinstance(text, str):
                self.send_json(400, {"ok": False, "error": "text_must_be_string"})
                return
            if not isinstance(phrase, str):
                self.send_json(400, {"ok": False, "error": "phrase_must_be_string"})
                return
            payload = response_payload(text, phrase)
            self.send_json(200 if payload.get("ok") else 422, payload)
        except Exception as e:
            message = str(e)
            print("Erreur pendant /check:")
            traceback.print_exc()
            status = 503 if any(k in message.lower() for k in ("koboldcpp", "reverso")) else 500
            self.send_json(status, {"ok": False, "error": "server_error", "message": message})


def make_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Serveur local Projet Voltaire Helper")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = p.parse_args(argv)
    httpd = make_server(args.host, args.port)
    print(f"Voltaire Helper: http://{args.host}:{args.port}")
    print(f"  Corrector: {CORRECTOR}")
    if CORRECTOR == "koboldcpp":
        print(f"  koboldcpp : {vk.BASE_URL}")
        print(f"  Model     : {vk.MODEL or '(non défini — configure VOLTAIRE_KOBOLDCPP_MODEL)'}")
    print("  Endpoint  : POST /check {text: ..., phrase: ...}")
    print("Laisse cette fenêtre ouverte. Ctrl+C pour arrêter.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
        return 0
    finally:
        httpd.server_close()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Serveur local pour le script navigateur Projet Voltaire.

Expose http://127.0.0.1:8765/check avec CORS, reçoit le texte visible de la
page, extrait la phrase, appelle Reverso via voltaire_check.py et renvoie JSON.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import voltaire_check as vc

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def response_payload(raw_text: str, explicit_phrase: str = "") -> dict[str, Any]:
    # Le userscript sait souvent extraire la phrase directement du DOM React.
    # On la privilégie quand elle est fournie, puis on garde l'extracteur texte
    # en filet de sécurité pour le mode OCR / ancien script.
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
    corrected = vc.call_reverso(phrase)
    analysis = vc.analyze_result(phrase, corrected)
    return {
        "ok": True,
        "phrase": analysis.original,
        "corrected": analysis.corrected,
        "has_error": analysis.has_error,
        "result": "FAUTE PROBABLE" if analysis.has_error else "PAS DE FAUTE DÉTECTÉE",
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "VoltaireLocalServer/1.0"

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
        self.send_response(status)
        self.cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/health":
            self.send_json(200, {"ok": True, "service": "voltaire-local-server"})
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
            self.send_json(500, {"ok": False, "error": "server_error", "message": str(e)})


def make_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Serveur local Reverso pour userscript Projet Voltaire")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = p.parse_args(argv)
    httpd = make_server(args.host, args.port)
    print(f"Serveur local Projet Voltaire: http://{args.host}:{args.port}")
    print("Endpoint: POST /check {text: ...}")
    print("Laisse cette fenêtre ouverte pendant l'utilisation du userscript. Ctrl+C pour arrêter.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
        return 0
    finally:
        httpd.server_close()


if __name__ == "__main__":
    raise SystemExit(main())

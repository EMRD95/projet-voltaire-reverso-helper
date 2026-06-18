#!/usr/bin/env python3
"""Client DeepSeek pour Voltaire Helper.

DeepSeek expose une API OpenAI-compatible à https://api.deepseek.com.
Nécessite une clé API (https://platform.deepseek.com/api_keys).

Configuration via variables d'environnement :
  VOLTAIRE_DEEPSEEK_API_KEY   Clé API DeepSeek (obligatoire)
  VOLTAIRE_DEEPSEEK_BASE_URL  URL de base (défaut: https://api.deepseek.com)
  VOLTAIRE_DEEPSEEK_MODEL     Modèle (défaut: deepseek-chat)
  VOLTAIRE_DEEPSEEK_TIMEOUT   Timeout HTTP en secondes (défaut: 90)
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

BASE_URL = os.environ.get("VOLTAIRE_DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
API_KEY = os.environ.get("VOLTAIRE_DEEPSEEK_API_KEY", "").strip()
MODEL = os.environ.get("VOLTAIRE_DEEPSEEK_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash"
TIMEOUT_SECONDS = int(os.environ.get("VOLTAIRE_DEEPSEEK_TIMEOUT", "90"))

SYSTEM_PROMPT = """Tu es un correcteur orthographique et grammatical expert en français.
Objectif: dire si la phrase contient une faute d'orthographe, grammaire, conjugaison ou accord.
Ne juge pas le style. Ignore les variantes typographiques (apostrophe droite/courbe, espaces fines, guillemets).
Ne réécris pas inutilement une phrase correcte.
Si une faute existe, corrige uniquement le minimum nécessaire.
Réponds STRICTEMENT en JSON valide, sans Markdown, sans texte autour.
Schéma exact:
{
  "has_error": true|false,
  "corrected": "phrase corrigée ou phrase originale si aucune faute",
  "error_span": "mot ou groupe fautif, sinon chaîne vide",
  "explanation": "explication très courte en français, sinon chaîne vide",
  "confidence": 0.0
}
Contraintes:
- La clé corrected doit contenir une phrase complète.
- Si has_error=false, corrected doit être identique à la phrase reçue.
- Ne propose jamais plusieurs options.
"""


class DeepSeekUnavailable(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Réponse DeepSeek vide")
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
            return parsed[0]
        if isinstance(parsed, dict):
            return parsed
        raise json.JSONDecodeError("not a dict or single-element list", text, 0)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise RuntimeError(f"Réponse DeepSeek non JSON: {text[:300]}")
        return json.loads(match.group(0))


def _normalize_result(phrase: str, obj: dict[str, Any]) -> dict[str, Any]:
    corrected = str(obj.get("corrected") or phrase).strip()
    has_error = bool(obj.get("has_error"))
    if not has_error:
        corrected = phrase
    elif corrected == phrase:
        has_error = False

    confidence_raw = obj.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return {
        "has_error": has_error,
        "corrected": corrected,
        "error_span": str(obj.get("error_span") or "").strip(),
        "explanation": str(obj.get("explanation") or "").strip(),
        "confidence": confidence,
    }


def analyze_phrase(phrase: str) -> dict[str, Any]:
    """Appelle DeepSeek /v1/chat/completions et retourne un dict normalisé."""
    if not phrase or not phrase.strip():
        raise ValueError("phrase vide")

    if not API_KEY:
        raise DeepSeekUnavailable(
            "VOLTAIRE_DEEPSEEK_API_KEY n'est pas défini. "
            "Crée une clé sur https://platform.deepseek.com/api_keys"
        )

    endpoint = BASE_URL + "/chat/completions"
    payload = {
        "model": MODEL,
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 220,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Phrase à analyser:\n" + phrase},
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},   # pas besoin de reasoning pour de la correction
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer " + API_KEY,
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise DeepSeekUnavailable(f"Erreur DeepSeek HTTP {e.code}: {detail[:500]}") from e
    except urllib.error.URLError as e:
        raise DeepSeekUnavailable(
            f"DeepSeek injoignable sur {BASE_URL}. Vérifie ta connexion. Détail: {e}"
        ) from e

    outer = json.loads(body)
    try:
        content = outer["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Réponse DeepSeek inattendue: {body[:500]}") from e
    return _normalize_result(phrase, _extract_json(content))

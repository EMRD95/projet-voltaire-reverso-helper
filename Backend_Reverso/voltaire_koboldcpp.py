#!/usr/bin/env python3
"""Client koboldcpp pour Voltaire Helper.

koboldcpp expose une API OpenAI-compatible (flag --api ou « Start Kobold API »
dans le launcher Windows). Le nom du modèle est auto-détecté via /api/v1/model.

Configuration via variables d'environnement :
  VOLTAIRE_KOBOLDCPP_BASE_URL          URL de base koboldcpp (défaut: http://127.0.0.1:5001)
  VOLTAIRE_KOBOLDCPP_TIMEOUT           Timeout HTTP en secondes (défaut: 90)
  VOLTAIRE_KOBOLDCPP_USE_INSTRUCTIONS  Charge instructions.txt (défaut: 0)

Par défaut, instructions.txt n'est pas utilisé avec koboldcpp pour éviter un prompt trop lourd.
Mettre VOLTAIRE_KOBOLDCPP_USE_INSTRUCTIONS=1 pour l'ajouter au prompt système.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BASE_URL = os.environ.get("VOLTAIRE_KOBOLDCPP_BASE_URL", "http://127.0.0.1:5001").rstrip("/")
TIMEOUT_SECONDS = int(os.environ.get("VOLTAIRE_KOBOLDCPP_TIMEOUT", "90"))
USE_INSTRUCTIONS = os.environ.get("VOLTAIRE_KOBOLDCPP_USE_INSTRUCTIONS", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "oui",
    "on",
}

_model_cache: str | None = None

_BASE_SYSTEM_PROMPT = """Tu es un correcteur orthographique et grammatical expert en français.
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

# Charge instructions.txt (éditable par l'utilisateur) seulement si la config l'active.
_instructions_path = Path(__file__).resolve().parent / "instructions.txt"
if USE_INSTRUCTIONS:
    try:
        _instructions = _instructions_path.read_text(encoding="utf-8").strip()
        if _instructions:
            SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + "\n\nRègles supplémentaires de l'utilisateur :\n" + _instructions
        else:
            SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT
    except OSError:
        SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT
else:
    SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT


class KoboldCppUnavailable(RuntimeError):
    pass


def _detect_model() -> str:
    """Détecte le modèle chargé dans koboldcpp via /api/v1/model."""
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    try:
        req = urllib.request.Request(BASE_URL + "/api/v1/model")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
        _model_cache = body.get("result", "")
        if not _model_cache:
            raise KoboldCppUnavailable("koboldcpp n'a pas retourné de nom de modèle.")
        return _model_cache
    except urllib.error.URLError as e:
        raise KoboldCppUnavailable(
            f"koboldcpp injoignable sur {BASE_URL}. Lance koboldcpp avec --api. Détail: {e}"
        ) from e


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Réponse koboldcpp vide")
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
            raise RuntimeError(f"Réponse koboldcpp non JSON: {text[:300]}")
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
    """Appelle koboldcpp /v1/chat/completions et retourne un dict normalisé."""
    if not phrase or not phrase.strip():
        raise ValueError("phrase vide")

    model = _detect_model()
    endpoint = BASE_URL + "/v1/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 220,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Phrase à analyser:\n" + phrase},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
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
        raise KoboldCppUnavailable(f"Erreur koboldcpp HTTP {e.code}: {detail[:500]}") from e
    except urllib.error.URLError as e:
        raise KoboldCppUnavailable(
            f"koboldcpp injoignable sur {BASE_URL}. "
            "Lance koboldcpp (flag --api). "
            f"Détail: {e}"
        ) from e

    outer = json.loads(body)
    try:
        content = outer["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Réponse koboldcpp inattendue: {body[:500]}") from e
    return _normalize_result(phrase, _extract_json(content))

#!/usr/bin/env python3
"""Assistant terminal simple pour Projet Voltaire.

Usage rapide :
  python voltaire_check.py --text "Je sui content."
  python voltaire_check.py --clipboard
  python voltaire_check.py --watch

Le mode --watch est prévu avec PowerToys Text Extractor :
1. Lance RUN_VOLTAIRE_SIMPLE.cmd
2. Sur Projet Voltaire, fais Windows+Shift+T et encadre la phrase.
3. Le texte OCR arrive dans le presse-papiers, le script nettoie la phrase,
   appelle Reverso, puis affiche FAUTE ou PAS DE FAUTE.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

REVERSO_URL = "https://orthographe.reverso.net/api/v1/Spelling"

NOISE_CONTAINS = [
    "projet voltaire",
    "test blanc",
    "si vous voyez une faute",
    "cliquez dessus",
    "sinon, cliquez",
    "il n'y a pas de faute",
    "il n’y a pas de faute",
    "valider la réponse",
    "valider la reponse",
    "menu d'accessibilité",
    "menu d'accessibilite",
    "accessibilité",
    "accessibilite",
    "écouter",
    "ecouter",
    "suivant",
    "précédent",
    "precedent",
    "rejouer",
    "continuer",
    "quitter",
]

STOP_CONTAINS = [
    "il n'y a pas de faute",
    "il n’y a pas de faute",
    "valider la réponse",
    "valider la reponse",
    "suivant",
    "quitter",
]


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def norm_for_filter(s: str) -> str:
    s = s.replace("\u00a0", " ").replace("\u202f", " ")
    s = s.replace("’", "'").replace("‘", "'").replace("«", " ").replace("»", " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return strip_accents(s)


def clean_line(line: str) -> str:
    line = line.replace("\u00a0", " ").replace("\u202f", " ")
    line = line.replace("“", '"').replace("”", '"').replace("’", "'")
    line = re.sub(r"\s+", " ", line).strip()
    # OCR ajoute parfois des puces/boutons au début.
    line = re.sub(r"^[•\-–—*·\s]+", "", line).strip()
    return line


def is_noise_line(line: str) -> bool:
    n = norm_for_filter(line)
    if not n:
        return True
    if any(x in n for x in NOISE_CONTAINS):
        return True
    if re.fullmatch(r"[0-9\s/.:\-]+", n):
        return True
    if len(n) < 3:
        return True
    return False


def looks_like_sentence(line: str) -> bool:
    if not re.search(r"[A-Za-zÀ-ÿ]", line):
        return False
    words = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’-]*", line)
    return len(words) >= 2


def extract_phrase(raw: str) -> str:
    """Extrait la phrase utile depuis un OCR PowerToys ou un texte brut.

    Projet Voltaire affiche souvent : instruction -> phrase -> bouton.
    On privilégie donc le bloc après l'instruction et avant le bouton.
    Si l'instruction n'est pas présente, on prend la meilleure ligne candidate.
    """
    if not raw:
        return ""

    lines = [clean_line(x) for x in re.split(r"[\r\n]+", raw)]
    lines = [x for x in lines if x]

    # PowerToys / le presse-papiers Windows peuvent parfois aplatir l'OCR en
    # une seule ligne : instruction + phrase + boutons. On découpe ce cas avant
    # le filtrage, sinon toute la ligne serait rejetée comme bruit.
    if len(lines) == 1:
        compact = lines[0]
        n = norm_for_filter(compact)
        if "si vous voyez une faute" in n or "cliquez dessus" in n:
            candidate = compact
            # Retire tout ce qui précède la fin de l'instruction.
            m = re.search(
                r"(?:bouton\s*)?[«\"]?\s*Il\s+n['’]?y\s+a\s+pas\s+de\s+faute\s*[»\"]?\s*[.;:]?\s*",
                candidate,
                flags=re.IGNORECASE,
            )
            if m:
                candidate = candidate[m.end():]
            else:
                m = re.search(r"cliquez\s+dessus.*?(?:[.;:]\s*)", candidate, flags=re.IGNORECASE)
                if m:
                    candidate = candidate[m.end():]
            # Coupe avant les boutons répétés après la phrase.
            stop = re.search(
                r"\s+(?:Il\s+n['’]?y\s+a\s+pas\s+de\s+faute|Valider\s+la\s+r[ée]ponse|Suivant|Quitter)\b",
                candidate,
                flags=re.IGNORECASE,
            )
            if stop:
                candidate = candidate[:stop.start()]
            candidate = normalize_phrase(candidate)
            if candidate and looks_like_sentence(candidate):
                return candidate

        # Si l'utilisateur tape juste une phrase dans le terminal.
        if not is_noise_line(compact):
            return compact

    after_instruction = False
    block: list[str] = []
    candidates: list[str] = []
    saw_instruction = False

    for line in lines:
        n = norm_for_filter(line)
        if "si vous voyez une faute" in n or "cliquez dessus" in n:
            after_instruction = True
            saw_instruction = True
            continue
        if after_instruction and any(stop in n for stop in STOP_CONTAINS):
            # Une fois le bouton "Il n'y a pas de faute" atteint, les textes
            # suivants appartiennent au chrome de page (progression, menu, etc.).
            break
        if after_instruction:
            # Sur l'app React Native Web, la phrase est souvent découpée en
            # fragments/ mots cliquables, un par ligne via innerText. Il faut
            # garder aussi les mots courts ("la", "de") et seuls ("Nous",
            # "attendont"), sinon on perd des bouts de la phrase.
            if n and not any(x in n for x in NOISE_CONTAINS) and re.search(r"[A-Za-zÀ-ÿ0-9]", line):
                block.append(line)
            continue
        if is_noise_line(line):
            continue
        if looks_like_sentence(line):
            candidates.append(line)

    if block:
        return normalize_phrase(join_phrase_fragments(block))
    if saw_instruction:
        return ""
    if candidates:
        # Généralement la phrase est la ligne la plus longue non bruitée.
        return normalize_phrase(max(candidates, key=len))

    return ""


def join_phrase_fragments(fragments: list[str]) -> str:
    """Recompose une phrase découpée par l'UI en mots/fragments cliquables."""
    out = ""
    for raw in fragments:
        part = clean_line(raw)
        if not part:
            continue
        if not out:
            out = part
        elif re.fullmatch(r"[,.;:!?…)\]}»]+", part):
            out += part
        elif out.endswith(("'", "’", "-", "«", "(", "[", "{")):
            out += part
        elif part.startswith(("'", "’", "-")):
            out += part
        else:
            out += " " + part
    return out


def normalize_phrase(s: str) -> str:
    s = clean_line(s)
    s = re.sub(r"^[^A-Za-zÀ-ÿ0-9]+", "", s)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    s = re.sub(r"([«])\s+", r"\1", s)
    s = re.sub(r"\s+([»])", r"\1", s)
    return s.strip()


def comparison_key(s: str) -> str:
    s = normalize_phrase(s)
    s = s.replace("’", "'").replace("œ", "oe").replace("Œ", "OE")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


@dataclasses.dataclass
class Analysis:
    original: str
    corrected: str
    has_error: bool


def analyze_result(original: str, corrected: str) -> Analysis:
    corrected = normalize_phrase(corrected or "")
    original = normalize_phrase(original or "")
    return Analysis(
        original=original,
        corrected=corrected,
        has_error=comparison_key(original) != comparison_key(corrected),
    )


def call_reverso(text: str, timeout: int = 15) -> str:
    payload = {
        "englishDialect": "indifferent",
        "autoReplace": True,
        "getCorrectionDetails": True,
        "interfaceLanguage": "fr",
        "locale": "",
        "language": "fra",
        "text": text,
        "originalText": "",
        "spellingFeedbackOptions": {
            "insertFeedback": True,
            "userLoggedOn": False,
        },
        "origin": "interactive",
        "isHtml": False,
        "IsUserPremium": False,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    user_agents = [
        "ClipboardSpellChecker/1.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36",
        "Mozilla/5.0 VoltaireSimple/1.0",
    ]
    last_http_error: urllib.error.HTTPError | None = None
    body = ""
    for attempt, user_agent in enumerate(user_agents, start=1):
        req = urllib.request.Request(
            REVERSO_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": user_agent,
                "Accept": "application/json, text/plain, */*",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
            break
        except urllib.error.HTTPError as e:
            last_http_error = e
            # Reverso met parfois Cloudflare devant l'endpoint. Dans ce cas,
            # un retry court avec un autre User-Agent suffit souvent.
            if e.code in {403, 429, 500, 502, 503, 504} and attempt < len(user_agents):
                time.sleep(0.6 * attempt)
                continue
            detail = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise RuntimeError(f"Erreur HTTP Reverso {e.code}: {detail[:300]}") from e
        except urllib.error.URLError as e:
            if attempt < len(user_agents):
                time.sleep(0.6 * attempt)
                continue
            raise RuntimeError(f"Erreur réseau Reverso: {e}") from e
    else:
        if last_http_error is not None:
            detail = last_http_error.read().decode("utf-8", errors="replace") if last_http_error.fp else ""
            raise RuntimeError(f"Erreur HTTP Reverso {last_http_error.code}: {detail[:300]}") from last_http_error

    parsed = json.loads(body)
    if "text" not in parsed:
        raise RuntimeError(f"Réponse Reverso inattendue: {body[:500]}")
    return parsed["text"]


def get_clipboard_text() -> str:
    if os.name == "nt":
        # -Raw garde les retours ligne du OCR PowerToys.
        cp = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    else:
        cp = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or "Impossible de lire le presse-papiers")
    return cp.stdout


def show_analysis(analysis: Analysis) -> None:
    print("\n" + "=" * 70)
    print(f"PHRASE : {analysis.original}")
    if analysis.has_error:
        print("RÉSULTAT: FAUTE PROBABLE")
        print(f"CORRIGÉ: {analysis.corrected}")
        print("DIFF   :")
        for line in difflib.ndiff([analysis.original], [analysis.corrected]):
            print("  " + line)
    else:
        print("RÉSULTAT: PAS DE FAUTE DÉTECTÉE")
        print(f"REVERSO: {analysis.corrected}")
    print("=" * 70)


def analyze_text(raw: str, raw_mode: bool = False) -> Analysis:
    phrase = normalize_phrase(raw) if raw_mode else extract_phrase(raw)
    if not phrase:
        raise RuntimeError("Je n'ai pas trouvé la phrase dans le texte/OCR fourni.")
    corrected = call_reverso(phrase)
    return analyze_result(phrase, corrected)


def watch_clipboard(interval: float = 0.7) -> None:
    print("Mode surveillance presse-papiers.")
    print("Sur Projet Voltaire: Windows + Shift + T, encadre uniquement la phrase si possible.")
    print("Ctrl+C pour arrêter.\n")
    last = None
    while True:
        try:
            raw = get_clipboard_text()
            key = raw.strip()
            if key and key != last:
                last = key
                try:
                    analysis = analyze_text(raw)
                    show_analysis(analysis)
                except Exception as e:  # le watcher ne doit pas mourir sur un mauvais OCR
                    print(f"[ignoré] {e}")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nArrêt.")
            return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Détecte faute / pas faute via Reverso pour Projet Voltaire.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="Phrase ou OCR à analyser")
    src.add_argument("--file", help="Fichier texte/HTML/OCR à analyser")
    src.add_argument("--clipboard", action="store_true", help="Analyser le presse-papiers une fois")
    src.add_argument("--watch", action="store_true", help="Surveiller le presse-papiers en boucle")
    parser.add_argument("--raw", action="store_true", help="Ne pas filtrer l'OCR, envoyer le texte tel quel")
    args = parser.parse_args(argv)

    try:
        if args.watch:
            watch_clipboard()
            return 0
        if args.clipboard:
            raw = get_clipboard_text()
        elif args.file:
            raw = Path(args.file).read_text(encoding="utf-8", errors="replace")
        else:
            raw = args.text

        analysis = analyze_text(raw, raw_mode=args.raw)
        show_analysis(analysis)
        return 1 if analysis.has_error else 0
    except Exception as e:
        print(f"ERREUR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

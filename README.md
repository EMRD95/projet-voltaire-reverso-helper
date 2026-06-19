# 🏰 Projet Voltaire Helper

<p align="center">
  <img src="Tampermonkey/assets/voltaire_happy.png" width="64" alt="Voltaire content" />
  <img src="Tampermonkey/assets/voltaire_mad.png" width="64" alt="Voltaire fâché" />
</p>

<p align="center">
  <img src="Screenshots/faute-probable.png" width="45%" alt="Panneau FAUTE PROBABLE" />
  <img src="Screenshots/il-n-y-a-pas-de-faute.png" width="45%" alt="Panneau IL N'Y A PAS DE FAUTE" />
</p>

**Un assistant d'entraînement pour Projet Voltaire.** Le script ne clique pas à ta place, il affiche l'analyse pour t'aider à apprendre l'orthographe et la grammaire avant de soumettre ta réponse.

Trois backends au choix :

| Backend | Type | Avantage | Inconvénient |
|---------|------|----------|-------------|
| **Reverso** | API web | Zéro setup, gratuit, simple, ~90 % fiable | Rate-limité (429), public |
| **DeepSeek** | API cloud | Pas cher, plus précis avec `instructions.txt` | Clé API + crédit requis (~2 $) |
| **koboldcpp** | LLM local | Illimité, privé, rapide | Nécessite un bon PC + modèle GGUF |

---

## 🧠 Fonctionnement

```
Page Projet Voltaire → Tampermonkey (extrait la phrase du DOM)
                             ↓
                  Backend local :8765 → Reverso / DeepSeek / koboldcpp
                             ↓
                  Panneau flottant : résultat + correction
```

Le backend écoute sur `localhost:8765` et expose un endpoint `POST /check`. Le userscript Tampermonkey extrait la phrase depuis le DOM React Native Web et l'envoie au backend.

---

## 🚀 Utilisation

### Option 1 — Reverso (API web, recommandé)

```bat
Backend_Reverso\start_backend_reverso.cmd
```

C'est le backend le plus simple : **zéro setup**, zéro clé API. Rapide et assez précis (~90 % des corrections sont bonnes). Si tu veux vraiment pas te prendre la tête, prends celui-là.

Gratuit mais parfois rate-limité (erreur 429) — attends ~1 minute entre deux vérifications.

### Option 2 — DeepSeek v4 Pro Flash (API cloud)

Plus précis que Reverso, surtout avec un `instructions.txt` bien calibré. Le modèle `deepseek-v4-flash` coûte très peu : **2 $ de crédit suffisent pour des dizaines d'heures** d'entraînement.

1. **Crée une clé API** sur https://platform.deepseek.com/api_keys
2. **Mets quelques centimes** sur ton compte DeepSeek (2 $ suffisent large)
3. **Configure** : copie `deepseek_config.example.cmd` en `deepseek_config.cmd` et mets ta clé :

```bat
set VOLTAIRE_DEEPSEEK_API_KEY=***
```

4. **Lance le backend** :

```bat
Backend_Reverso\start_backend_deepseek.cmd
```

### Option 3 — koboldcpp (LLM local)

Si tu as **un bon PC** avec assez de RAM/VRAM, tu peux faire tourner un LLM local pour du zéro latence et 100 % privé.

1. **Télécharge [koboldcpp](https://github.com/LostRuins/koboldcpp/releases)**
2. **Télécharge un modèle GGUF** — [`gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf`](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf) recommandé (tourne sur un PC portable, ~10 Go RAM)
3. **Lance koboldcpp** avec le modèle de ton choix et l'API activée (flag `--api` en CLI, ou coche « Start Kobold API » dans le launcher)
4. **Lance le backend** (le modèle est auto-détecté, rien à configurer) :

```bat
Backend_Reverso\start_backend_koboldcpp.cmd
```

Si koboldcpp tourne sur un autre port, copie `koboldcpp_config.example.cmd` en `koboldcpp_config.cmd` et change le port.

### Installer le userscript

1. Ouvre Tampermonkey → **Create a new script**
2. Copie/colle `Tampermonkey/tampermonkey_voltaire_helper.user.js`
3. Sauvegarde
4. Ouvre Projet Voltaire → le panneau apparaît
5. **Démarrer** → analyse la phrase affichée

---

## 📁 Structure

```text
├── Backend_Reverso/
│   ├── voltaire_local_server.py        # Serveur HTTP CORS (triple backend)
│   ├── voltaire_check.py               # Extracteur de phrase + client Reverso
│   ├── voltaire_koboldcpp.py           # Client koboldcpp
│   ├── voltaire_deepseek.py            # Client DeepSeek
│   ├── start_backend_koboldcpp.cmd     # Lancement koboldcpp
│   ├── start_backend_deepseek.cmd      # Lancement DeepSeek
│   ├── start_backend_reverso.cmd       # Lancement Reverso
│   ├── koboldcpp_config.example.cmd    # Exemple config koboldcpp
│   ├── deepseek_config.example.cmd     # Exemple config DeepSeek
│   ├── instructions.txt                # Règles de correction personnalisées
│   ├── test_voltaire_check.py
│   ├── test_voltaire_koboldcpp.py
│   ├── test_voltaire_deepseek.py
│   └── test_voltaire_local_server.py
├── Tampermonkey/
│   ├── tampermonkey_voltaire_helper.user.js
│   └── assets/
│       ├── voltaire_happy.png
│       └── voltaire_mad.png
├── Screenshots/
└── .github/workflows/backend-tests.yml
```

---

## 📝 Règles personnalisées (`instructions.txt`)

Tu peux créer un fichier `Backend_Reverso/instructions.txt` pour donner des règles de correction spécifiques aux LLMs (koboldcpp et DeepSeek). Par exemple, si tu as du mal avec les participes passés ou les accords du participe, écris tes règles dedans et le LLM les appliquera en priorité.

Le fichier est chargé automatiquement au démarrage et ajouté au prompt système. S'il est vide ou absent, le prompt par défaut s'applique.

---

## ⚙️ Configuration

Tout se passe par variables d'environnement :

| Variable | Défaut | Description |
|----------|--------|-------------|
| `VOLTAIRE_CORRECTOR` | `reverso` | `reverso`, `deepseek` ou `koboldcpp` |
| `VOLTAIRE_KOBOLDCPP_BASE_URL` | `http://127.0.0.1:5001` | URL de l'API koboldcpp |
| `VOLTAIRE_KOBOLDCPP_TIMEOUT` | `90` | Timeout HTTP koboldcpp |
| `VOLTAIRE_DEEPSEEK_API_KEY` | *(vide)* | Clé API DeepSeek |
| `VOLTAIRE_DEEPSEEK_MODEL` | `deepseek-v4-flash` | Modèle DeepSeek |
| `VOLTAIRE_DEEPSEEK_TIMEOUT` | `90` | Timeout HTTP DeepSeek |

---

## ✅ Tests

```bash
cd Backend_Reverso
python -m unittest discover -v
```

CI GitHub Actions : ![CI](https://github.com/EMRD95/projet-voltaire-reverso-helper/actions/workflows/backend-tests.yml/badge.svg)

---

## ⚖️ Mention légale

Ce projet est un outil tiers indépendant, fourni à des fins exclusivement personnelles, pédagogiques et expérimentales. Il vise à permettre à son utilisateur de personnaliser son environnement numérique et de s'approprier ses outils d'apprentissage pour une expérience plus immersive de l'orthographe et de la grammaire.

Ce projet n'est ni affilié à Projet Voltaire, ni soutenu, validé, autorisé ou approuvé par Projet Voltaire ou par ses sociétés, ayants droit, représentants, partenaires ou affiliés. Projet Voltaire est une marque, un service et une société distincts appartenant à leurs titulaires respectifs. Toute référence à Projet Voltaire est uniquement descriptive et sert à identifier le contexte d'utilisation de cet outil tiers.

L'utilisation de ce projet relève de la seule responsabilité de l'utilisateur, dans le respect des conditions d'utilisation des services tiers concernés.

---

## 📄 Licence

MIT

# 🏰 Projet Voltaire Reverso Helper

<p align="center">
  <img src="Screenshots/faute-probable.png" width="45%" alt="Panneau FAUTE PROBABLE" />
  <img src="Screenshots/il-n-y-a-pas-de-faute.png" width="45%" alt="Panneau IL N'Y A PAS DE FAUTE" />
</p>

<p align="center">
  <img src="Tampermonkey/assets/voltaire_happy.png" width="64" alt="Voltaire content" />
  <img src="Tampermonkey/assets/voltaire_mad.png" width="64" alt="Voltaire fâché" />
</p>

**Un assistant d'entraînement pour Projet Voltaire.** Le script ne clique pas à ta place, il affiche l'analyse de [Reverso](https://www.reverso.net/orthographe/) pour t'aider à apprendre l'orthographe et la grammaire avant de soumettre ta réponse.

---

## 🧠 Fonctionnement

```
Page Projet Voltaire → Tampermonkey (extrait la phrase du DOM React)
                                   ↓
                        Backend local :8765 → API Reverso gratuite
                                   ↓
                        Panneau flottant : résultat + correction
```

1. **Userscript Tampermonkey** : extrait la phrase depuis le DOM React Native Web
2. **Backend Python local** (`localhost:8765`) : appelle l'API Reverso gratuite
3. **Panneau flottant déplaçable/pliable** :
   - **FAUTE PROBABLE** + Voltaire fâché — mot suspect en gras/souligné
   - **IL N'Y A PAS DE FAUTE** + Voltaire content

---

## 📁 Structure

```text
├── Backend_Reverso/
│   ├── voltaire_local_server.py    # Serveur HTTP CORS
│   ├── voltaire_check.py           # Extracteur + appel Reverso
│   ├── start_backend.cmd           # Lancement Windows
│   ├── test_voltaire_check.py      # Tests extracteur
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

## 🚀 Utilisation

### 1. Lancer le backend

```bat
Backend_Reverso\start_backend.cmd
```

Le serveur écoute sur `http://127.0.0.1:8765`.

### 2. Installer Tampermonkey

1. Ouvrir Tampermonkey → **Create a new script**
2. Copier/coller `Tampermonkey/tampermonkey_voltaire_helper.user.js`
3. Sauvegarder

### 3. Utiliser

1. Ouvrir Projet Voltaire dans Chrome
2. Le panneau apparaît (arrêté par défaut)
3. **Démarrer** → analyse la phrase affichée
4. **Plier/Déplier** → cache la réponse avant de soumettre

---

## ✅ Tests

```bash
cd Backend_Reverso
python -m unittest test_voltaire_check.py test_voltaire_local_server.py -v
# 14 tests OK
```

CI GitHub Actions : ![CI](https://github.com/EMRD95/projet-voltaire-reverso-helper/actions/workflows/backend-tests.yml/badge.svg)

---

## 🛠️ Fonctionnalités

- Extraction DOM React Native Web (`.sentence`, `css-146c3p1`, `r-18u37iz`)
- API Reverso gratuite (correction orthographique FR)
- Panneau flottant déplaçable (position mémorisée)
- Démarrage/arrêt manuel
- Mode plié/déplié
- Mot suspect en gras/souligné
- Images Voltaire content/fâché (base64 inline)
- Sans code couleur vert/rouge
- Retry automatique Reverso (403/429/5xx)
- Fallback texte mode OCR
- GitHub Actions CI (14 tests)

---

## 📄 Licence

MIT

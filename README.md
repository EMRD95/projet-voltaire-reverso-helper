# 🏰 Projet Voltaire Reverso Helper

<p align="center">
  <img src="Tampermonkey/assets/voltaire_happy.png" width="80" alt="Voltaire content" />
  <img src="Tampermonkey/assets/voltaire_mad.png" width="80" alt="Voltaire fâché" />
</p>

**Un assistant d'entraînement pour la plateforme Projet Voltaire, pas un outil de triche.**

L'objectif est d'**augmenter** la plateforme avec les connaissances de l'outil [Reverso](https://www.reverso.net/orthographe/) pour mieux apprendre l'orthographe et la grammaire française. Le script **ne clique pas à ta place** — il t'affiche simplement l'analyse de Reverso pour que tu puisses vérifier ton raisonnement avant de soumettre ta réponse.

---

## 🧠 Comment ça marche

```text
┌─────────────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Projet Voltaire (web)  │────▶│  Backend Reverso  │────▶│  Reverso API │
│  Tampermonkey userscript │     │  localhost:8765   │     │  (gratuite)  │
└─────────────────────────┘     └──────────────────┘     └─────────────┘
         │                              │
         │  extrait la phrase           │  corrige + détecte
         │  depuis le DOM React         │  si faute
         ▼                              ▼
   ┌──────────────────────────────────────────┐
   │  Panneau flottant (déplaçable/pliable)   │
   │  FAUTE PROBABLE  ou  IL N'Y A PAS DE FAUTE │
   │  + zone suspecte en gras/souligné         │
   └──────────────────────────────────────────┘
```

1. Un **userscript Tampermonkey** tourne dans la page Projet Voltaire.
2. Il extrait la phrase directement depuis le DOM React Native Web.
3. Il envoie la phrase au **backend local Python** (`localhost:8765`).
4. Le backend appelle l'**API Reverso gratuite** de correction orthographique.
5. Le résultat s'affiche dans un panneau flottant :
   - **FAUTE PROBABLE** avec Voltaire fâché 😠
   - **IL N'Y A PAS DE FAUTE** avec Voltaire content 😊
   - Le(s) mot(s) modifié(s) par Reverso sont en **gras/souligné**

---

## 📁 Structure du projet

```text
projet_voltaire_tampermonkey_reverso/
├── README.md
├── Backend_Reverso/          # Serveur local Python
│   ├── voltaire_local_server.py
│   ├── voltaire_check.py
│   ├── start_backend.cmd
│   ├── test_voltaire_check.py
│   └── test_voltaire_local_server.py
└── Tampermonkey/             # Script navigateur
    ├── tampermonkey_voltaire_helper.user.js
    └── assets/
        ├── voltaire_happy.png
        └── voltaire_mad.png
```

---

## 🚀 Utilisation rapide

### 1. Lancer le backend

```bat
C:\...\Backend_Reverso\start_backend.cmd
```

Le serveur écoute sur `http://127.0.0.1:8765`.

### 2. Installer le script Tampermonkey

1. Ouvrir Tampermonkey > **Create a new script**
2. Copier/coller le contenu de `Tampermonkey/tampermonkey_voltaire_helper.user.js`
3. Sauvegarder

### 3. Utiliser

1. Ouvrir Projet Voltaire dans Chrome
2. Le panneau apparaît (arrêté par défaut)
3. Cliquer sur **Démarrer** pour analyser la phrase affichée
4. Cliquer sur **Plier/Déplier** pour cacher la réponse avant de soumettre

---

## ✅ Tests

```bash
cd Backend_Reverso
python -m unittest test_voltaire_check.py test_voltaire_local_server.py -v
# 14 tests OK
```

---

## ⚠️ Ce n'est PAS un outil de triche

- Le script **ne clique pas** à ta place.
- Il **ne valide pas** automatiquement les réponses.
- Il te montre l'analyse de Reverso pour que tu puisses **apprendre** de tes erreurs.
- L'idée est d'utiliser la puissance de Reverso comme un **professeur particulier** toujours disponible.

---

## 🛠️ Fonctionnalités (v1.4.2)

- ✅ Extraction de la phrase depuis le DOM React Native Web
- ✅ API Reverso gratuite (correction orthographique FR)
- ✅ Panneau flottant déplaçable (position mémorisée)
- ✅ Démarrage/arrêt manuel (bouton Démarrer/Arrêter)
- ✅ Mode plié/déplié pour vérifier avant de soumettre
- ✅ Mise en gras/souligné du mot suspect (via Reverso)
- ✅ Images Voltaire content/fâché selon le résultat
- ✅ Sans code couleur vert/rouge
- ✅ Backend Python avec CORS pour Tampermonkey
- ✅ Retry automatique en cas d'erreur réseau Reverso
- ✅ Fallback texte si le DOM React n'est pas accessible

---

## 📄 Licence

MIT — Utilisez, modifiez, partagez librement. Apprenez bien !

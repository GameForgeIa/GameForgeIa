# ForgeGameIA v2 — 100% depuis un téléphone

## Stack 100% gratuite et open source

- **Godot** (moteur de jeu, MIT) · **Capacitor** (wrapper Android, MIT)
  · **FastAPI** (backend, MIT) · **GitHub Actions** (compilation dans le
  cloud, gratuit) · **GitHub Pages** (hébergement web, gratuit) ·
  **Render** (hébergement backend, offre gratuite). Seule dépendance
  payante à l'usage : les appels à l'API Anthropic (Claude) pour faire
  tourner les agents — tarifée à l'usage, pas d'abonnement fixe.

## Ce que contient ce dossier

- `backend/` — serveur avec 6 agents IA (Producteur, Game Designer, Level
  Designer, Narratif, Artiste, Sound Designer, Programmeur)
- `forge_web/` — l'app de chat, en web (aucune compilation, s'ouvre dans
  ton navigateur, installable sur l'écran d'accueil)
- `game_godot/` — le jeu 3D isométrique (Godot), avec un système qui le
  compile automatiquement en `.apk` dans le cloud via GitHub Actions

## Étapes, dans l'ordre

### 1. Créer un compte GitHub (gratuit)
Depuis ton téléphone : github.com ou l'app GitHub. Crée un nouveau
**repository** (dépôt), par exemple nommé `forgegameia`.

### 2. Uploader ce dossier sur GitHub
Depuis l'app GitHub ou le site mobile, tu peux créer les fichiers un par
un ("Add file" → "Upload files" accepte aussi plusieurs fichiers/dossiers
glissés depuis ton stockage téléphone). Uploade tout le contenu de ce
dossier (`backend/`, `forge_web/`, `game_godot/` avec son sous-dossier
`.github/workflows/`).

### 3. Déployer le backend sur Render (gratuit)
- Va sur render.com, connecte-toi avec GitHub
- "New +" → "Web Service" → sélectionne ton dépôt, dossier `backend`
- Commande de démarrage : `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Ajoute la variable d'environnement `ANTHROPIC_API_KEY` (ta clef API
  Anthropic, à récupérer sur console.anthropic.com)
- Render te donne une URL du style `https://forgegameia.onrender.com`

### 4. Connecter l'app web à ton backend
Dans `forge_web/index.html`, remplace la ligne :
```js
const BACKEND_URL = "https://TON-BACKEND.onrender.com";
```
par ta vraie URL Render. Fais pareil dans `game_godot/Main.gd` (variable
`BACKEND_URL`, en ajoutant `/latest-level` à la fin).
Tu peux éditer ces fichiers texte directement depuis l'éditeur web de
GitHub (icône crayon sur chaque fichier), sans rien installer.

### 5. Ouvrir l'app de chat
Héberge `forge_web/` gratuitement avec **GitHub Pages** (Paramètres du
dépôt → Pages → sélectionner la branche). Tu obtiens une URL du style
`https://tonpseudo.github.io/forgegameia/forge_web/`. Ouvre-la dans ton
navigateur mobile, puis "Ajouter à l'écran d'accueil" pour qu'elle se
comporte comme une app.

### 6. Récupérer le jeu compilé
Dans GitHub, onglet **Actions** de ton dépôt : le workflow "Build Android
APK" se lance automatiquement. Une fois terminé (quelques minutes),
clique dessus → section "Artifacts" → télécharge `lejeu-apk`. C'est un
`.zip` contenant le `.apk`. Décompresse-le et installe l'APK (Android te
demandera d'autoriser "l'installation depuis des sources inconnues" —
normal, c'est parce que l'app ne vient pas du Play Store).

## Copyright et propriété (information générale, pas un conseil juridique)

Je ne suis pas juriste — voici les faits utiles, à confirmer auprès d'un
avocat en propriété intellectuelle si tu veux protéger ça sérieusement
(par exemple avant de commercialiser).

- **Le droit d'auteur (copyright) naît automatiquement** dès la création
  d'une œuvre originale, en France comme dans la plupart des pays
  (Convention de Berne). Aucune "annonce" ni dépôt n'est nécessaire pour
  qu'il existe — contrairement à ce qu'on pense souvent. Ce qui compte
  légalement, c'est la date de création et la preuve que tu en es
  l'auteur (d'où l'intérêt d'un historique Git horodaté, par exemple).
- **Le code que je t'ai écrit ici t'appartient** : les sorties générées
  par Claude pour toi te reviennent selon les conditions d'utilisation
  actuelles d'Anthropic — vérifie la version en vigueur sur
  anthropic.com/legal si tu veux la formulation exacte.
- **"ForgeGameIA" en tant que marque (nom, logo)** est une notion
  différente du droit d'auteur : la protéger efficacement contre un usage
  par quelqu'un d'autre nécessite un dépôt de marque (en France : INPI,
  environ 190€ pour une classe). Le droit d'auteur ne protège pas les
  noms.
- **Ce que tu peux faire dès maintenant, gratuitement** :
  - Ajouter une notice de copyright dans le dépôt (fichier `LICENSE`,
    voir ci-dessous), ce qui documente ta revendication même si elle
    existe déjà légalement.
  - Garder le dépôt GitHub **privé** si tu ne veux pas que le code soit
    réutilisable par d'autres (un dépôt public sans licence reste
    "tous droits réservés" par défaut, mais privé évite toute ambiguïté).

J'ajoute un fichier `LICENSE` avec une notice "tous droits réservés" à ton
nom — modifie `[Ton Nom]` par ton vrai nom ou celui de ta structure.

## Nouveautés V2 — ton setup actuel

Avec GitHub+Render déjà liés, Web to App, ApiClient et Godot V4 installés,
voici le parcours mis à jour.

### A. Créer ta base Supabase (persistance des agents, gratuit à vie)
1. Va sur supabase.com, connecte-toi avec ton Gmail.
2. "New project" → note l'URL du projet et la clef "anon public" (Settings
   → API).
3. Dans l'éditeur SQL du projet (menu de gauche), colle et exécute :
   ```sql
   create table kv_store (
     key text primary key,
     value jsonb
   );
   ```

### B. Récupérer une clef Gemini gratuite
Va sur aistudio.google.com avec ton Gmail → "Get API key" → copie la clef.

### C. Déployer le backend GRATUITEMENT sur Render, tout automatique

⚠️ Si tu as déjà créé un service "Background Worker" sur Render : **supprime-le**
(Settings tout en bas → "Delete Service"). Ce type de service n'a pas de
version gratuite — c'est pour ça que Render te proposait de payer. Le
plan gratuit de Render n'existe que pour le type **"Web Service"**, ce
qu'on va utiliser ici.

Ce dépôt contient un fichier `render.yaml` à sa racine qui configure tout
automatiquement (type de service, commandes, plan gratuit) — tu n'as
presque rien à régler à la main :

1. Sur render.com, va dans l'onglet **"Blueprints"** (menu de gauche).
2. **"New Blueprint Instance"**.
3. Sélectionne ton dépôt GitHub (ForgeGameAi).
4. Render détecte automatiquement `render.yaml` et affiche le service à
   créer : type Web Service, plan **Free**. Clique **"Deploy Blueprint"**.
5. Il va te demander de renseigner 3 valeurs secrètes (normal, elles ne
   sont jamais mises dans le code par sécurité) :
   - `GEMINI_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
6. Une fois déployé, Render t'affiche l'URL de ton backend (du style
   `https://forgegameia-backend.onrender.com`) — c'est celle à mettre
   dans `forge_web/index.html` et `game_godot/Main.gd`.

À partir de maintenant, à chaque fois que tu modifies des fichiers sur
GitHub, Render redéploie automatiquement — plus besoin de retoucher au
dashboard.

### D. Tester avec ApiClient avant de brancher les apps
Requête `POST` vers `https://ton-backend.onrender.com/chat` avec le body :
```json
{"message": "crée un niveau avec une colline centrale", "attachments": []}
```
Si tu reçois une réponse JSON avec `"reply"`, le backend fonctionne.

### E. Empaqueter ForgeGameIA avec Web to App
Plus besoin de GitHub Actions/Capacitor pour cette app : héberge
`forge_web/index.html` sur GitHub Pages (comme avant), puis donne cette
URL à ton app "Web to App" pour générer directement l'APK sur ton
téléphone.

### F. Le jeu Godot
Ouvre le dossier `game_godot/` directement dans l'app Godot V4 sur ton
téléphone pour visualiser/ajuster la scène. Pour la compilation en APK,
le workflow GitHub Actions déjà en place (`.github/workflows/build-apk.yml`)
reste la solution la plus fiable si l'export depuis l'éditeur mobile pose
problème.

### G. Apprentissage web du Manager
Un appel à `POST /studio-learn` (testable directement via ApiClient) fait
faire une vraie recherche Google au Manager sur le métier de studio de jeu
vidéo, et garde ses notes en mémoire durable (Supabase). À faire une fois,
pas besoin de répéter à chaque session.

## Nouveautés V1.1

- **Hiérarchie stricte** : Manager → grands agents du studio (Game
  Designer, Level Designer, Narratif, Artiste, Sound Designer,
  Programmeur) → leurs sous-agents. Un sous-agent est toujours rattaché à
  un grand agent, jamais directement au Manager, jamais à un autre
  sous-agent.
- **Lancer la simulation** : après qu'un niveau est généré, un bouton
  "🎮 Lancer la simulation" apparaît dans le chat. Il ouvre directement
  l'app du jeu Godot *si elle est déjà installée* sur ton téléphone — elle
  recharge automatiquement le dernier niveau généré. Si l'app n'est pas
  installée, un message te renvoie vers le README pour récupérer le
  dernier `.apk` compilé (voir plus haut, étape "Récupérer le jeu
  compilé").
- **ForgeGameIA devient une vraie app Android** (en plus de la web app) :
  compilée gratuitement dans le cloud via GitHub Actions, avec
  **Capacitor** (outil open source, licence MIT) qui empaquette la même
  interface web dans une coquille Android native. Aucune installation
  locale requise.
  - Dans l'onglet **Actions** de ton dépôt GitHub, le workflow "Build
    ForgeGameIA APK" se lance automatiquement à chaque mise à jour de
    `forge_web/`. Télécharge l'artifact `forgegameia-apk` une fois prêt,
    et installe-le comme pour le jeu.
  - Tu peux donc soit utiliser ForgeGameIA comme web app (PWA, étape 5
    ci-dessus), soit comme app Android installée — les deux fonctionnent
    de façon identique, à toi de choisir.

## Nouveautés V1

- **Le Manager gère vraiment l'équipe** : pour chaque message, il décide
  soit de router vers un agent existant, soit de **créer un nouveau
  sous-agent** spécialisé (rattaché à un agent parent) si le besoin est
  précis ou répétitif. Ces sous-agents restent disponibles ensuite — tu
  les vois apparaître dans la barre d'équipe en haut de l'app de chat
  (indentés avec ↳).
- **Pièces jointes** : le bouton 📎 permet de joindre des fichiers
  (images, PDF, texte...). Ils sont transmis à l'agent choisi comme
  référence — utile pour donner un artwork de style à l'Artiste, un
  document de lore au Narrative Designer, etc.
- Note : la liste d'agents et les sous-agents créés vivent en mémoire du
  serveur pour l'instant (repartent à zéro si le service Render redémarre
  après une longue veille) — une vraie persistance (base de données) sera
  la prochaine étape si tu veux que ça tienne dans la durée.

## Comment ça se joue

1. Tu ouvres ForgeGameIA (web app) et tu écris un prompt, ex :
   *"crée une carte de bataille avec une colline au centre et 3 unités
   de chaque camp"*.
2. Le Producteur route ça vers le Game Designer, qui génère une grille
   isométrique en JSON (tuiles + hauteurs + unités).
3. Tu ouvres l'app du jeu (l'APK installé), elle charge cette carte et
   l'affiche en 3D isométrique.

Tu peux aussi demander autre chose dans le chat : *"écris un dialogue
d'ouverture pour ce niveau"* ou *"quelle ambiance sonore pour une scène
de bataille dans une forêt en flammes ?"* — ça ira vers les bons agents
(narratif, sound designer, etc.), affichés comme notes dans le chat.

## Pour la suite, sans ordinateur

**Claude Code est utilisable depuis le téléphone** (via l'app Claude) et
peut travailler directement sur ton dépôt GitHub à distance — c'est
l'option à privilégier pour ajuster le code, corriger un bug dans le
workflow de build, ou ajouter de nouvelles fonctionnalités sans que tu
aies à écrire toi-même la moindre ligne.

## État du projet V1 — ce qui est corrigé, ce qui reste limité

**Corrigé dans cette version :**
- ✅ Combat au tour par tour réellement jouable : sélectionne une unité
  (tape dessus), les cases atteignables s'affichent en vert, déplace-toi,
  attaque une unité ennemie adjacente, l'IA ennemie joue son tour, et la
  partie détecte victoire/défaite.
- ✅ Historique de niveaux : les 20 dernières cartes générées sont
  gardées, tu peux en réactiver une depuis le bouton "📜 Historique".
- ✅ Vraies stats de combat (PV, attaque, portée de déplacement) au lieu
  de simples pions statiques.
- ✅ Persistance complète (Supabase) : agents, sous-agents et historique
  survivent aux redémarrages.

**Ce qui reste honnêtement limité, et pourquoi je ne peux pas le "corriger"
gratuitement :**
- ❌ **Pas de vrais graphismes ni de vraie musique.** Les unités et le
  terrain restent des formes géométriques colorées. Créer de vrais
  modèles 3D, textures et musiques demande soit un(e) artiste humain(e),
  soit des API de génération d'images/audio qui sont payantes (les
  versions gratuites de ces API sont soit inexistantes soit trop limitées
  pour un usage réel). Les agents "Artiste" et "Sound Designer"
  continuent donc à produire des *descriptions textuelles* que tu peux
  ensuite confier à un(e) artiste, ou utiliser toi-même dans un outil de
  génération d'image si tu es prêt à payer pour ça un jour.
- ❌ **Le serveur gratuit Render se met en veille après inactivité** — le
  premier message après une pause peut prendre 30-50 secondes. C'est une
  contrainte du plan gratuit ; la seule vraie solution est un plan payant
  (quelques dollars/mois) qui garde le serveur toujours actif.
- ❌ Pas encore d'objets, de sorts, ni de progression de personnage
  (XP/niveaux) — le combat reste volontairement simple pour l'instant.

Une app "professionnelle" au sens propre (assets originaux, serveur
toujours disponible, plusieurs testeurs) implique tôt ou tard un minimum
de coûts. Ce projet reste 100% gratuit et fonctionnel pour prototyper et
jouer seul — dis-moi si/quand tu veux qu'on regarde les options payantes
pour franchir ce palier.

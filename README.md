# 🖤 Mika — Bot Discord IA

Bot Discord en français, personnalité « e-girl dominatrice, entre potes ». Il discute par mention, réponse ou prénom, propose des jeux, de la modération, de l'économie, des tickets, des Kahoot et plus encore. Tout tient dans un seul fichier : `bot.py`.

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration (`.env`)](#configuration-env)
- [Permissions et intents Discord](#permissions-et-intents-discord)
- [Commandes](#commandes)
- [Logs](#logs)
- [Données et sauvegarde](#données-et-sauvegarde)
- [Dépannage](#dépannage)
- [Crédits](#Crédits)

## Fonctionnalités

- **Chat IA** : répond aux mentions, aux réponses à ses messages et quand on écrit son prénom ; rebonds spontanés et réactions emoji aléatoires ; mémoire par salon (SQLite).
- **Social** : mariage (jusqu'à 3 par mariage), compatibilité, roast, blagues, 8ball.
- **Jeux** : pierre-feuille-ciseaux (et duel), quiz, blackjack et poker multi-joueurs, quiz créés par les membres, **Kahoot** (quiz live multi-joueurs, créés à la main ou par l'IA), classements et stats.
- **Économie** : solde, bonus quotidien, dons, classement des plus riches, mises sur les jeux.
- **Modération** : panel de punitions, auto-modération, mots interdits, mute vocal, purge, silence.
- **Logs filtrables par type** : sanctions, commandes, rôles, auto-modération, tickets, actions admin, arrivées, messages, vocal.
- **Tickets** d'assistance avec panneau à bouton et transcripts.
- **Accueil** personnalisé (messages écrits à la main ou générés par l'IA).
- **Outils** : sondages à boutons, annonces, panneau de rôles-réactions, commandes personnalisées (`/cc`, `!nom`), météo, recherche web.
- **IA pour les admins** : `/creeserveur` (génère rôles, salons et permissions), `/dev projet` (génère un site ou une app en zip), `/optimiser` (analyse des performances).
- **Panneau d'administration complet** : `/adminpanel`.

## Prérequis

- Python **3.10 ou plus**
- Un bot Discord (token) créé sur le [Developer Portal](https://discord.com/developers/applications)
- Une clé API pour un service compatible OpenAI (par défaut : [Groq](https://console.groq.com), gratuit)

Dépendances Python utilisées par `bot.py` :

```
discord.py
aiosqlite
httpx
openai
ddgs
python-dotenv
```

## Installation

```bash
# 1. Récupérer le projet
git clone <ton-repo> && cd <ton-repo>

# 2. (Recommandé) environnement virtuel
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate

# 3. Installer les dépendances
pip install discord.py aiosqlite httpx openai ddgs python-dotenv

# 4. Créer le fichier de configuration
cp .env.example .env             # puis édite-le (voir ci-dessous)

# 5. Lancer
python bot.py
```

Au premier démarrage, les commandes slash se synchronisent automatiquement. Elles ne sont resynchronisées ensuite que si la liste des commandes change.

## Configuration (`.env`)

### Obligatoires

| Variable | Description |
| --- | --- |
| `DISCORD_TOKEN` | Token du bot Discord |
| `AI_API_KEY` | Clé API du service d'IA |

### Optionnelles

| Variable | Défaut | Description |
| --- | --- | --- |
| `AI_BASE_URL` | `https://api.groq.com/openai/v1` | Adresse de l'API (tout service « OpenAI-compatible ») |
| `AI_MODEL` | `openai/gpt-oss-120b` | Modèle utilisé |
| `BOT_NAME` | `Mika` | Prénom du bot (déclenche aussi ses réponses) |
| `DB_PATH` | `bot.db` | Chemin de la base SQLite |
| `HISTORY_SIZE` | `12` | Nombre de messages de contexte envoyés à l'IA |
| `REACT_CHANCE` | `0.05` | Probabilité d'une réaction emoji spontanée |
| `SPONTANEOUS_CHANCE` | `0.03` | Probabilité de rebondir sans être appelé |
| `PHRASE_CHANCE` | `0.60` | Probabilité d'une phrase « mommy » sur câlin/bisou |
| `NAME_TRIGGER` | `1` | `1` : répond aussi quand on écrit son prénom ; `0` : désactivé |
| `DEV_MAX_TOKENS` | `8000` | Taille max de sortie de `/dev projet` (à baisser si ton modèle limite) |
| `SYNC_ON_START` | *(vide)* | `1` : force la resynchronisation des commandes à chaque démarrage |

Exemple minimal :

```env
DISCORD_TOKEN=ton_token_discord
AI_API_KEY=ta_cle_api
```

## Permissions et intents Discord

Dans le **Developer Portal → Bot → Privileged Gateway Intents**, active :

- **Message Content Intent**
- **Server Members Intent**
- **Presence Intent**

Pour l'invitation du bot, utilise les scopes `bot` et `applications.commands`. Donne-lui les permissions dont tu as besoin selon les fonctions utilisées : gérer les rôles, gérer les salons, gérer les messages, expulser / bannir, exclure des membres (mute), gérer les emojis, voir les salons, envoyer des messages, intégrer des liens, ajouter des réactions, utiliser les emojis externes. Le plus simple est de lui donner **Administrateur** sur un serveur de confiance.

> Le rôle du bot doit être placé **au-dessus** des rôles qu'il doit gérer ou sanctionner.

## Commandes

Les commandes marquées *(admin)* ou *(staff)* sont réservées. `/aide` affiche tout ce que le bot sait faire, `/aideadmin` la partie réservée aux admins.

### 💬 IA et discussion

| Commande | Description |
| --- | --- |
| `/ask` | Pose une question |
| `/recherche` | Recherche sur le web et donne des liens |
| `/roast` | Chambre quelqu'un |
| `/blague` | Blague coquine (sous-entendus, jamais explicite) |
| `/8ball` | Réponse à une question fermée |
| `/choisir` | Tranche entre plusieurs options |
| `/meteo` | Météo d'une ville |
| `/reset` | Efface la mémoire du salon |

### 💍 Social

| Commande | Description |
| --- | --- |
| `/marie`, `/mariage`, `/divorce` | Mariage (jusqu'à 3 personnes) |
| `/ship` | Compatibilité entre deux personnes |
| `/statu` | Profil d'un membre : statut, stats de jeu, argent |

### 🎮 Jeux

| Commande | Description |
| --- | --- |
| `/jeux` | Panel regroupant tous les jeux |
| `/pfc`, `/pfcduel` | Pierre-feuille-ciseaux (contre le bot ou en duel, mise possible) |
| `/quiz` | Quiz rapide : le premier qui trouve gagne |
| `/blackjack`, `/regleblackjack` | Blackjack, seul ou à plusieurs, et ses règles |
| `/poker`, `/reglepoker`, `/main` | Texas Hold'em, ses règles, classement des mains |
| `/classement`, `/stat` | Classement du serveur et stats individuelles (victoires, défaites, K/D) |
| `/quizperso creer\|jouer\|liste\|supprimer` | Quiz créés par les membres |
| `/kahoot creer\|generer\|lancer\|liste\|supprimer` | Kahoot (quiz live multi-joueurs), à la main ou par l'IA |

### 🪙 Économie

| Commande | Description |
| --- | --- |
| `/solde` | Ton porte-monnaie |
| `/daily` | Bonus quotidien |
| `/donner` | Donne des pièces |
| `/richesse` | Les plus riches du serveur |
| `/ecopanel` *(admin)* | Panneau de l'économie et des mises |
| `/eco config\|donner\|retirer\|reset` *(admin)* | Réglages et gestion des soldes |

### 🔨 Modération

| Commande | Description |
| --- | --- |
| `/punition panel` | Panel de punitions du staff |
| `/punition deban` | Débannit quelqu'un (avec log) |
| `/automod config\|mot\|pardon\|statut` *(admin)* | Auto-modération et mots interdits |
| `/purge` *(staff)* | Supprime un nombre de messages |
| `/silence` *(staff)* | Le bot se tait un moment (`off` pour annuler) |
| `/logs` *(admin)* | Définit le salon des logs |

### 🎫 Tickets

| Commande | Description |
| --- | --- |
| `/ticket config` *(staff)* | Règle le système |
| `/ticket panel` *(staff)* | Poste le panneau « Ouvrir un ticket » |
| `/ticket fermer` | Ferme le ticket (transcript sauvegardé) |
| `/ticket ajouter` / `retirer` *(staff)* | Ajoute ou retire un membre du ticket |

### 👋 Accueil, annonces, sondages

| Commande | Description |
| --- | --- |
| `/bienvenue config\|generer\|tester` | Messages d'accueil personnalisés, générés par l'IA, aperçu privé |
| `/sondage` | Sondage interactif à boutons |
| `/annonce` *(staff)* | Publie une annonce dans un salon |
| `/rolereaction` *(admin)* | Panneau pour choisir ses rôles |

### 🛠️ Commandes personnalisées

| Commande | Description |
| --- | --- |
| `/commande ajouter\|modifier\|supprimer\|liste` *(admin)* | Gère les commandes du serveur |
| `/cc` | Lance une commande personnalisée |
| `!nom` | Raccourci pour lancer une commande personnalisée |

### 🏗️ Serveur et outils admin

| Commande | Description |
| --- | --- |
| `/adminpanel` *(admin)* | Panneau de configuration complet : fonctionnalités, modération, logs par type, économie, accueil, outils. Options : `page` (section à ouvrir), `reactions`, `spontane`, `salutations`, `nom` (activer / couper directement) |
| `/style` *(admin)* | Change la personnalité du bot sur ce serveur |
| `/envoyer` *(admin)* | Message anonyme ou sous un pseudo perso |
| `/creeserveur` *(admin)* | L'IA génère un serveur complet : rôles, salons, permissions |
| `/creersalon`, `/supprimersalon` *(staff)* | Crée ou supprime un salon / une catégorie |
| `/role creer\|supprimer` *(staff)* | Crée ou supprime un rôle |
| `/emoji agrandir\|ajouter` | Affiche un emoji en grand / l'ajoute au serveur *(admin)* |
| `/dev projet\|question` | L'IA génère un site ou une app (zip) / répond à une question de dev |
| `/optimiser` *(admin)* | Analyse les performances et propose des améliorations |
| `/info` | Stats du serveur |
| `/ping` | Latence du bot |
| `/test` *(admin)* | Vérifie que tout fonctionne |
| `/sync` *(owner)* | Resynchronise les commandes |

## Logs

Définis le salon avec `/logs`, puis choisis les types à enregistrer dans `/adminpanel`.

| Type | Contenu | Par défaut |
| --- | --- | --- |
| 🔨 Sanctions | mute, kick, ban, avertissement, vocal | activé |
| 📋 Commandes | slash, panels, `!nom` | activé |
| 🎭 Rôles | donnés, retirés, créés, supprimés, panneaux | activé |
| 🛡️ Auto-modération | infractions et sanctions auto | activé |
| 🎫 Tickets | ouverture, fermeture, transcripts | activé |
| 🛠️ Actions admin | envoyer, salons, serveur IA | activé |
| 👋 Arrivées et départs | membres qui rejoignent / partent | désactivé |
| 💬 Messages | supprimés / modifiés | désactivé |
| 🎙️ Vocal | connexion, départ, déplacement | désactivé |

Les logs de tickets peuvent aussi avoir un salon dédié (`/ticket config`) ; à défaut, ils vont dans le salon de logs général.

## Données et sauvegarde

Tout est stocké dans un fichier SQLite (`bot.db` par défaut, modifiable via `DB_PATH`) : mémoire des salons, économie, stats de jeu, quiz, Kahoot, paramètres par serveur, etc. Les tables sont créées automatiquement.

Pour sauvegarder : arrête le bot et copie `bot.db` (ainsi que les éventuels fichiers `bot.db-wal` et `bot.db-shm`).

Les boutons de rôles, sondages et tickets restent actifs après un redémarrage.

## Dépannage

- **Le bot ne répond pas aux messages** : vérifie que le *Message Content Intent* est activé dans le Developer Portal.
- **Il ne démarre pas** : `DISCORD_TOKEN` et `AI_API_KEY` doivent être définis dans `.env`.
- **Les commandes n'apparaissent pas** : redémarre le bot, lance `/sync` (owner) ou mets `SYNC_ON_START=1` une fois. La propagation côté Discord peut prendre quelques minutes.
- **Il ne peut pas sanctionner ou gérer un rôle** : place le rôle du bot au-dessus des rôles concernés et vérifie ses permissions.
- **`/dev projet` renvoie des fichiers coupés** : baisse `DEV_MAX_TOKENS` si ton modèle limite la taille de sortie.
- **Erreurs d'IA** : vérifie `AI_BASE_URL`, `AI_MODEL` et ta clé ; les limites de débit des offres gratuites peuvent être atteintes.
- 
  ## 🙏 Crédits

- [discord.py](https://github.com/Rapptz/discord.py)
- [Open-Meteo](https://open-meteo.com/) — météo gratuite sans clé
- [ddgs](https://pypi.org/project/ddgs/) — recherche DuckDuckGo
- [Groq](https://groq.com/) — IA par défaut
- [Claude](https://claude.ai/new) - IA pour le code 
 
Fait avec 🖤 — *sois sage, petit chat.*


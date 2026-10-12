# 🖤 Mika — Bot Discord IA « e-girl dominatrice »

Mika est un bot Discord en français pour serveurs entre potes. Elle discute grâce à une IA (n'importe quel service compatible OpenAI), vanne, flirte (jamais de contenu explicite), joue avec vous, gère la modération et retient le fil de la discussion dans une base SQLite.

> **Python 3.10+ requis** • discord.py **2.4+** • aucune base externe à installer.

---

## ✨ Fonctionnalités

| Catégorie | Contenu |
|---|---|
| 💬 **Chat IA** | Répond quand on la mentionne, quand on répond à un de ses messages, ou quand on écrit son prénom (« Mika, t'en penses quoi ? »). Réponses courtes (1 à 3 phrases), mémoire par salon. |
| 🎭 **Styles** | 4 personnalités au choix par serveur : Dominatrice (défaut), Mommy, Douce, Sarcastique. |
| 🔎 **Recherche web** | `/recherche` (liens) et `/ask web:True` (l'IA s'appuie sur DuckDuckGo). Déclenchement automatique sur des mots comme « actu », « prix », « score »… |
| 🌤️ **Météo** | Vraies données Open-Meteo (sans clé). `/meteo Lyon` ou simplement « météo Lyon » dans le chat. |
| 😈 **Taquineries** | `/roast`, `/blague`, `/8ball`, `/choisir`, `/ship`. |
| 💋 **Actions sociales** | `/kiss` `/hug` `/pat` `/slap` `/bonk` `/gift`. Variantes plus osées uniquement dans les salons NSFW. |
| 💍 **Mariage** | `/marie`, `/mariage`, `/divorce` — jusqu'à 3 personnes par mariage, tout le monde doit accepter. |
| 🎮 **Mini-jeux** | `/pfc`, `/quiz` (généré par l'IA), `/blackjack` (solo ou jusqu'à 5), `/poker` Texas Hold'em (jusqu'à 6 joueurs, Mika joue aussi). |
| 🏆 **Stats** | `/classement` et `/stat` : victoires, défaites, K/D, points, top %. |
| 🛠️ **Commandes perso** | Créées par les admins, utilisables en `/cc nom` ou `!nom`. Variables `{user}` et `{server}`. |
| 🔨 **Modération** | Panel de punitions : mute, unmute, avertir, expulser, bannir, nettoyer, mute vocal, casque, donner/retirer un rôle, deban. |
| 📜 **Logs** | Toutes les sanctions **et** toutes les commandes du bot sont tracées dans un salon de logs. |
| 🎭 **Rôles à boutons** | `/rolereaction` — panneaux persistants, même après redémarrage. |
| 🛡️ **Mode protectrice** | Si quelqu'un semble aller mal, Mika devient douce. En cas de détresse grave, elle ajoute le 3114 (France) et le 112. |

---

## 🚀 Installation

### 1. Récupérer le code

```bash
git clone <ton-repo>
cd <ton-repo>
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
```

### 2. Installer les dépendances

Crée un fichier `requirements.txt` :

```text
discord.py>=2.4
aiosqlite
httpx
openai>=1.0
ddgs
python-dotenv
```

puis :

```bash
pip install -r requirements.txt
```

### 3. Configurer le `.env`

Crée un fichier `.env` à la racine (voir [Configuration](#️-configuration)) :

```env
DISCORD_TOKEN=ton_token_discord
AI_API_KEY=ta_cle_api_ia
```

### 4. Lancer

```bash
python bot.py
```

*(remplace `bot.py` par le nom réel de ton fichier)*

Au premier démarrage, les commandes slash sont synchronisées automatiquement. Elles peuvent mettre quelques minutes à apparaître sur Discord.

---

## 🔧 Créer l'application Discord

1. Va sur le [Developer Portal](https://discord.com/developers/applications) → **New Application**.
2. Onglet **Bot** → **Reset Token** → copie le token dans `DISCORD_TOKEN`.
3. Toujours dans **Bot**, active les trois **Privileged Gateway Intents** :
   - ✅ **Presence Intent** (pour `/statu`)
   - ✅ **Server Members Intent** (pour le vocal, les rôles, la modération)
   - ✅ **Message Content Intent** (indispensable pour le chat)
4. Onglet **OAuth2 → URL Generator** : coche les scopes `bot` et `applications.commands`, puis les permissions ci-dessous, et ouvre l'URL générée pour inviter le bot.

### Permissions recommandées

| Usage | Permission |
|---|---|
| Base | Voir les salons, Envoyer des messages, Intégrer des liens, Ajouter des réactions, Lire l'historique, Utiliser les emojis externes |
| Modération | Exclure temporairement des membres, Expulser, Bannir, Gérer les messages |
| Vocal | Rendre muets les membres, Mettre en sourdine les membres |
| Rôles | Gérer les rôles |
| `/envoyer` | Gérer les webhooks |
| `/emoji ajouter` | Gérer les expressions |

> ⚠️ **Hiérarchie des rôles** : le rôle de Mika doit être **au-dessus** des rôles qu'elle doit attribuer ou des membres qu'elle doit sanctionner.

---

## ⚙️ Configuration

Toutes les variables se règlent dans le `.env`.

| Variable | Défaut | Description |
|---|---|---|
| `DISCORD_TOKEN` | — | **Obligatoire.** Token du bot. |
| `AI_API_KEY` | — | **Obligatoire.** Clé API du fournisseur d'IA. |
| `AI_BASE_URL` | `https://api.groq.com/openai/v1` | Endpoint compatible OpenAI. |
| `AI_MODEL` | `openai/gpt-oss-120b` | Modèle utilisé. |
| `BOT_NAME` | `Mika` | Prénom du bot (sert aussi de déclencheur). |
| `DB_PATH` | `bot.db` | Chemin de la base SQLite. |
| `HISTORY_SIZE` | `12` | Nombre de messages de contexte envoyés à l'IA. |
| `REACT_CHANCE` | `0.05` | Probabilité d'une réaction emoji choisie par l'IA. |
| `SPONTANEOUS_CHANCE` | `0.03` | Probabilité de rebondir sans être appelée (si activé). |
| `PHRASE_CHANCE` | `0.60` | Probabilité d'une phrase « mommy » sur câlin / bisou en chat. |
| `NAME_TRIGGER` | `1` | `1` = répond aussi quand on écrit son prénom, `0` = non. |
| `SYNC_ON_START` | — | Mets `1` pour forcer la resynchronisation des commandes au démarrage. |

### Changer de fournisseur d'IA

Tout service « OpenAI-compatible » fonctionne. Exemples :

```env
# Groq (défaut, gratuit)
AI_BASE_URL=https://api.groq.com/openai/v1
AI_MODEL=openai/gpt-oss-120b

# OpenAI
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# Ollama en local
AI_BASE_URL=http://localhost:11434/v1
AI_API_KEY=ollama
AI_MODEL=llama3.1
```

> Le mode JSON (utilisé par `/quiz`) doit être supporté par le modèle choisi. Utilise `/test` pour vérifier.

---

## 📚 Commandes

### 👥 Pour tout le monde

**Discussion & IA**
- `/ask question [detail] [web]` — pose une question (réponse courte, détaillée, ou avec recherche web)
- `/recherche requete` — résultats web avec liens
- `/roast @membre [contexte]` — Mika chambre quelqu'un
- `/blague [theme]` — blague coquine (sous-entendus, jamais explicite)
- `/reset` — efface la mémoire du salon

**Décisions & fun**
- `/8ball question` — oui / non / peut-être
- `/choisir options` — ex : `pizza, tacos ou burger`
- `/ship @a @b` — compatibilité (stable pour un même duo)

**Actions**
- `/kiss` `/hug` `/pat` `/slap` `/bonk` `/gift` + `@membre`
- Essaie-les sur Mika elle-même 😏

**Mariage**
- `/marie @membre [@membre2]` — demande (3 personnes max, tout le monde accepte)
- `/mariage [@membre]` — voir un mariage
- `/divorce confirmer:True` — quitter son mariage

**Jeux & stats**
- `/pfc` — pierre-feuille-ciseaux
- `/quiz [theme]` — premier qui trouve gagne (30 s)
- `/blackjack` — solo ou table jusqu'à 5 joueurs
- `/poker` — Texas Hold'em jusqu'à 6 joueurs, sans mises
- `/classement [jeu]` — top 10 du serveur
- `/stat [joueur]` — stats détaillées par jeu

*Barème : victoire 10 pts • égalité 3 pts • participation 1 pt.*

**Divers**
- `/meteo ville` — météo actuelle + 3 jours
- `/ping` — latence websocket et API
- `/statu @membre` — statut, activité, appareils, vocal
- `/emoji agrandir` — affiche un emoji personnalisé en grand
- `/cc nom` ou `!nom` — commande personnalisée du serveur
- `/aide` — le mode d'emploi

**Dans le chat (sans commande)**
- « coucou », « ça va ? », « tu fais quoi ? », « bonne nuit » → réponses instantanées, sans IA
- « météo Lyon » → météo directe
- « câlin », « bisou »… → phrases « mommy » aléatoires

### 🛡️ Staff & admins

| Commande | Permission | Rôle |
|---|---|---|
| `/adminpanel` | Administrateur | Panel regroupant presque tout, en boutons |
| `/aideadmin` | Administrateur | Liste des commandes admin |
| `/punition panel @membre` | Staff (au moins une perm. de modération) | Panel complet de sanctions |
| `/punition deban` | Bannir des membres | Débannir (autocomplétion des bannis) |
| `/config` | Gérer le serveur | Réactions, rebonds spontanés, salutations, réponse au prénom |
| `/style` | Gérer le serveur | Change la personnalité |
| `/logs [salon] [desactiver]` | Gérer le serveur | Salon de logs |
| `/silence durée` | Gérer le serveur | Mika se tait (`10`, `30m`, `2h`, `1j`, ou `off`) |
| `/test` | Gérer le serveur | Auto-diagnostic complet |
| `/commande ajouter\|modifier\|supprimer\|liste` | Administrateur | Commandes perso |
| `/rolereaction` | Gérer les rôles | Panneau de rôles à boutons |
| `/envoyer` | Administrateur | Message anonyme ou sous pseudo perso (tracé dans les logs) |
| `/emoji ajouter` | Gérer les expressions | Ajoute un emoji au serveur |
| `/sync` | Owner du bot | Resynchroniser les commandes |

### 🔨 Panel de punitions

Ouvert par `/punition panel @membre`, il propose :

- 🤐 **Mute rapide** (5 min → 1 semaine) ou **mute perso** — timeout Discord, 28 jours max
- ⚠️ **Avertir** • 🔊 **Unmute**
- 👢 **Expulser** • 🔨 **Bannir** • 🧹 **Nettoyer** (1 à 100 messages du membre)
- 🎙️ **Mute voc** • 🎧 **Casque** • 🔊 **Libérer voc** — avec durée optionnelle, levée automatique
- 🎀 **Donner un rôle** • ✂️ **Retirer un rôle**

Chaque sanction est annoncée dans le salon (ton « Mommy ») **et** enregistrée dans le salon de logs. Le bot refuse de sanctionner le propriétaire, lui-même, ou quelqu'un de plus haut que le modérateur dans la hiérarchie.

### 📜 Ce qui est logué

- Toutes les sanctions (mute, unmute, warn, kick, ban, deban, purge, vocal, rôles)
- Fin automatique des sanctions vocales
- Toutes les commandes slash (avec leurs options), les actions du panel admin et les `!commandes` perso
- Les tentatives refusées (permissions manquantes) et les erreurs
- Les rôles pris / retirés via un panneau `/rolereaction`
- Chaque usage de `/envoyer` (l'anonymat vaut pour les membres, pas pour le staff)

Pour l'activer : `/logs salon:#ton-salon`.

---

## 🎭 Personnalisation

### Le caractère

Tout se règle dans le fichier, section **PERSONNALITÉ** :

- `PERSONA` — le prompt de base (ton, limites, longueur)
- `TONE_SOFT` / `TONE_SPICY` — ajustement selon que le salon est normal ou NSFW
- `STYLES` — les 4 styles sélectionnables avec `/style`
- `MOMMY_SOFT` / `MOMMY_SPICY`, `GREET_*`, `ACTIONS` — les phrases prêtes à l'emploi
- `FOOTERS` et `COLOR_*` — la charte graphique des embeds

### Garde-fous intégrés

Ils sont codés dans le prompt et ne dépendent pas du style choisi :

- Aucun contenu sexuel explicite
- Si quelqu'un se dit mineur ou parle de collège / lycée, plus aucun sous-entendu
- Aucun propos haineux
- Mode protectrice automatique quand quelqu'un semble aller mal
- L'IA n'invente jamais d'URL

### Salons NSFW

Dans un salon marqué NSFW, Mika est un peu plus osée (phrases « spicy », ton `TONE_SPICY`). Elle reste non explicite.

---

## 🧠 Fonctionnement interne

- **Mémoire** : les 40 derniers messages de chaque salon sont conservés ; `HISTORY_SIZE` d'entre eux sont envoyés à l'IA.
- **Base SQLite** (`bot.db`) : historique, réglages, commandes perso, mariages, stats de jeu, minuteurs vocaux.
- **Synchronisation des commandes** : le bot calcule une empreinte de ses commandes et ne resynchronise que si elle change (économise les limites d'API Discord).
- **Anti-spam** : cooldown de 8 s par utilisateur sur les commandes IA, 3 s sur le chat, 5 s sur la météo.
- **Pings** : le bot ne ping jamais `@everyone` ni les rôles ; les pings utilisateurs sont autorisés uniquement quand c'est voulu.
- **Persistance** : les boutons de `/rolereaction` restent actifs après un redémarrage.

---

## 🧪 Vérifier que tout marche

Lance **`/test`** (permission « Gérer le serveur »). Il contrôle : base de données, IA texte et JSON, recherche web, salutations, actions, modération, blackjack, poker, stats, commandes perso, météo, commandes enregistrées, salon de logs, permissions et intents. Chaque ligne est ✅, ⚠️ ou ❌.

---

## 🩺 Dépannage

| Problème | Solution |
|---|---|
| Le bot ne répond pas aux messages | Active **Message Content Intent** dans le Developer Portal. |
| Les commandes slash n'apparaissent pas | Attends quelques minutes, ou lance `/sync` (owner), ou `SYNC_ON_START=1`. |
| « Mon rôle n'est pas assez haut » | Monte le rôle de Mika au-dessus des rôles / membres ciblés. |
| `/statu` donne un statut faux | Active **Presence Intent** et **Server Members Intent**. |
| Mute vocal impossible | Le membre doit être en vocal ; Mika a besoin de « Rendre muets » / « Mettre en sourdine ». |
| `/envoyer` avec pseudo perso refusé | Donne-lui « Gérer les webhooks » dans le salon. |
| « J'ai trop parlé » | Limite de requêtes de ton fournisseur d'IA atteinte : attends ou change de modèle. |
| `/quiz` échoue | Ton modèle ne gère pas bien le JSON ; essaie un autre modèle. |
| Pas de logs | Définis un salon avec `/logs` et donne à Mika « Envoyer des messages » + « Intégrer des liens ». |
| `/recherche` échoue | DuckDuckGo limite parfois les requêtes ; réessaie plus tard. |
| Impossible de joindre le service météo | Open-Meteo est temporairement indisponible ou ton hébergeur bloque la sortie réseau. |

---

## 📁 Structure

```text
.
├── bot.py            # tout le bot (un seul fichier)
├── bot.db            # base SQLite (créée automatiquement)
├── .env              # configuration (ne jamais committer)
├── .env.example      # modèle de configuration
└── requirements.txt
```

Ajoute ceci à ton `.gitignore` :

```text
.env
bot.db
.venv/
__pycache__/
```

> 🔐 **Ne partage jamais** ton `DISCORD_TOKEN` ni ta clé `AI_API_KEY`. Si l'un d'eux fuite, régénère-le immédiatement.

---

## 🙏 Crédits

- [discord.py](https://github.com/Rapptz/discord.py)
- [Open-Meteo](https://open-meteo.com/) — météo gratuite sans clé
- [ddgs](https://pypi.org/project/ddgs/) — recherche DuckDuckGo
- [Groq](https://groq.com/) — IA par défaut
- [Claude](https://claude.ai/new) - IA pour le code 
 
Fait avec 🖤 — *sois sage, petit chat.*

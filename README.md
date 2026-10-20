# 🖤 Mika — Bot Discord IA

Bot Discord en français, personnalité « e-girl dominatrice, entre potes ». Il discute par mention, réponse ou prénom, propose des jeux, de la modération, une économie complète avec boutique, des niveaux avec prestige, des cartes en image, des tickets, des Kahoot, des giveaways et plus encore. Tout tient dans un seul fichier : `bot.py`.

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration (`.env`)](#configuration-env)
- [Système de niveaux](#système-de-niveaux)
- [Économie et boutique](#économie-et-boutique)
- [Cartes, événements et classement de la semaine](#cartes-événements-et-classement-de-la-semaine)
- [Permissions et intents Discord](#permissions-et-intents-discord)
- [Commandes](#commandes)
- [Logs](#logs)
- [Données et sauvegarde](#données-et-sauvegarde)
- [Dépannage](#dépannage)
- [Crédits](#crédits)

## Fonctionnalités

- **Chat IA** : répond aux mentions, aux réponses à ses messages et quand on écrit son prénom ; rebonds spontanés et réactions emoji aléatoires ; mémoire par salon (SQLite) ; mode « protectrice » automatique si quelqu'un semble aller mal.
- **Social** : mariage (jusqu'à 3 par mariage), compatibilité, roast, blagues, 8ball, actions (`/action` : bisou, câlin, headpat, gifle, bonk, cadeau).
- **Jeux** : pierre-feuille-ciseaux (et duel), quiz, blackjack et poker multi-joueurs, quiz créés par les membres, **Kahoot** (quiz live multi-joueurs, créés à la main ou par l'IA), classements et stats.
- **Économie** : solde, bonus quotidien avec série et jackpot hebdo, `/argent travail`, `/argent crime`, dons (avec taxe), classement des plus riches, mises sur les jeux.
- **Boutique** : rôles, boosts d'XP, coffres mystère, boucliers anti-braquage et **cosmétiques** (titres, couleurs et fonds de carte), plus une **boutique tournante** d'articles à durée limitée. Les admins peuvent aussi offrir ou reprendre un cosmétique à un membre.
- **Quêtes, succès, banque, braquages** : 3 quêtes par jour et 3 par semaine, badges avec récompenses, compte en banque à intérêts, vols entre joueurs.
- **Niveaux** : de l'XP en discutant, **en vocal et en jouant**, des pièces gagnées en vocal, annonces de passage de niveau, rôles offerts à certains niveaux, **prestige**, classements (XP ou temps en vocal), anti-farm et plafonds quotidiens.
- **Cartes en image** : carte de niveau et carte de profil, personnalisées avec les cosmétiques équipés.
- **Événements automatiques** : pluie de pièces, coffre, calcul éclair, happy hour d'XP ; **classement de la semaine** posté chaque lundi avec récompenses.
- **Modération** : panel de punitions, auto-modération (dont insultes envers le bot), mots interdits, mute vocal, purge, silence, salons interdits au bot.
- **Règles obligatoires** : les nouveaux membres doivent accepter les règles (bouton), sinon expulsion.
- **Giveaways** à bouton, tirage automatique, relance possible.
- **Logs filtrables par type** : sanctions, commandes, rôles, auto-modération, tickets, actions admin, arrivées, messages, vocal.
- **Tickets** d'assistance avec panneau à bouton et transcripts.
- **Accueil** personnalisé (messages écrits à la main ou générés par l'IA) et **rôle automatique** à l'arrivée.
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
psutil
pillow
```

> `psutil` est optionnel (affiche la RAM dans `/optimiser`).
>
> `pillow` est optionnel : sans lui, seules les cartes en image (`/carte`) sont indisponibles.
>
> Les niveaux, l'économie et la boutique n'ajoutent **aucune dépendance**.

## Installation

```bash
# 1. Récupérer le projet
git clone <ton-repo> && cd <ton-repo>

# 2. (Recommandé) environnement virtuel
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Créer le fichier de configuration
cp .env.example .env             # puis édite-le (voir ci-dessous)

# 5. Lancer
python bot.py
```

Dans `requirements.txt`, mets **une dépendance par ligne**, sans `pip install` devant, sinon pip rejette tout le fichier.

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
| `EMBED_AIRY` | `1` | `1` : messages (embeds) aérés ; `0` : présentation compacte |
| `BOT_LINK` | lien GitHub du projet | Lien affiché par `/bot lien` |
| `DEV_MAX_TOKENS` | `8000` | Taille max de sortie de `/dev projet` (à baisser si ton modèle limite) |
| `SYNC_ON_START` | *(vide)* | `1` : force la resynchronisation des commandes à chaque démarrage |

Exemple minimal :

```env
DISCORD_TOKEN=ton_token_discord
AI_API_KEY=ta_cle_api
```

Le nom de la commande de giveaway se change avec la constante `GW_CMD` en haut de `bot.py` (par défaut `givawayyy`).

> Les réglages des niveaux, de l'économie et des événements ne passent **pas** par le `.env` : ils se règlent par serveur, avec `/xp config`, `/eco config`, `/ecoplus config`, `/auto` ou `/adminpanel` (voir ci-dessous).

## Système de niveaux

Les niveaux sont **désactivés par défaut** (comme l'économie). Un admin les active avec `/xp config actif:True`, ou avec le bouton **Niveaux** dans `/adminpanel` › *Économie & accueil*.

### Comment on gagne de l'XP

| Source | Gain par défaut | Détails |
| --- | --- | --- |
| 💬 Chat | environ **20 XP** par message | 1 message par minute et par membre maximum (anti-spam, anti copier-coller), gain aléatoire ±25 % |
| 🎙️ Vocal | **10 XP** par minute | Paie toutes les minutes tant que tu remplis les conditions ci-dessous |
| 🎮 Jeux | **40 / 20 / 10 XP** | Victoire / égalité / défaite, avec bonus de mise et de série de victoires 🔥 |
| 📅 `/daily` et `/argent travail` | **50 XP** et **30 XP** | |
| 🪙 Vocal (argent) | **5 pièces** par minute | Seulement si l'**économie** est activée (`/ecopanel`) |
| 🏆 Passage de niveau | **25 pièces × le niveau** | Une seule fois par niveau (20 % si déjà touché, après un prestige) ; réglable avec `argent_niveau` |

### Plafonds quotidiens (anti-farm)

Par membre et par jour : **2 000 XP** de chat, **3 000 XP** de vocal et **1 500 XP** de jeux (`0` = illimité). Une fois le plafond atteint, plus d'XP de ce type jusqu'au lendemain.

### Anti-farm en vocal

Pour qu'une minute en vocal compte, il faut :

- ne pas avoir le **casque coupé** (en sourdine, par toi ou par un modérateur) ;
- ne pas être dans le **salon AFK** du serveur ;
- être **au moins 2** membres (non bots, casque actif) dans le salon (réglable avec `membres_min`, `1` = même seul).

Les bots ne gagnent rien. Les messages sanctionnés par l'auto-modération et ceux envoyés dans un salon interdit (`/interdit`) ne rapportent pas d'XP.

### Courbe de niveaux

Il faut `5·n² + 50·n + 100` XP pour passer du niveau `n` au niveau `n+1` (même courbe que MEE6).

| Niveau | XP total nécessaire |
| --- | --- |
| 1 | 100 |
| 5 | 1 150 |
| 10 | 4 675 |
| 20 | 23 850 |

### Prestige

Au niveau requis (**50** par défaut), `/profil prestige` remet le niveau à zéro contre une ⭐ **permanente** et un **bonus d'XP définitif** (**+5 %** par étoile, **10 étoiles** maximum par défaut). Les trois valeurs se règlent avec `/xp config` (`prestige_niveau`, `prestige_bonus`, `prestige_max`).

### Réglages (`/xp config`)

| Option | Défaut | Description |
| --- | --- | --- |
| `actif` | désactivé | Active ou coupe les niveaux |
| `xp_message` | `20` | XP moyen par message |
| `xp_vocal` | `10` | XP par minute en vocal |
| `argent_vocal` | `5` | Pièces par minute en vocal (économie requise) |
| `membres_min` | `2` | Nombre minimum de membres dans le salon vocal |
| `argent_niveau` | `25` | Pièces offertes à chaque niveau gagné (× le niveau) |
| `plafond_chat`, `plafond_vocal`, `plafond_jeux` | `2000`, `3000`, `1500` | XP maximum par jour et par membre (`0` = illimité) |
| `vocal` | activé | Active ou coupe les gains en vocal |
| `salon` | *(aucun)* | Salon où annoncer les passages de niveau |
| `salon_auto` | | `True` : annoncer dans le salon où le membre parle (ou dans le salon vocal) |

Sans salon défini, l'annonce est envoyée dans le salon où le membre vient de discuter, ou dans le chat du salon vocal pour un niveau gagné en vocal. Rien n'est annoncé pendant un `/silence`.

`/xp evenement` lance une période de **double XP**.

### Rôles-récompenses

Avec `/recompense ajouter`, tu choisis un niveau et un rôle : le rôle est donné automatiquement quand le membre atteint ce niveau (plusieurs rôles par niveau possibles). Pour les membres qui ont **déjà** dépassé le niveau, lance `/recompense appliquer`.

> Le rôle du bot doit être placé **au-dessus** des rôles-récompenses, avec la permission « Gérer les rôles ». Retirer de l'XP ou supprimer une récompense **ne retire pas** les rôles déjà donnés.

## Économie et boutique

L'économie est **désactivée par défaut**. Un admin l'active avec `/ecopanel` (ou `/eco config`).

### Valeurs par défaut

| Réglage | Défaut | Description |
| --- | --- | --- |
| Solde de départ | `1000` | Pièces d'un nouveau membre |
| Bonus `/daily` | `200` | Grimpe avec la **série** (elle continue si tu réclames dans les 48 h), jackpot chaque semaine |
| Mises | `10` à `5000` | Limites des mises sur `/blackjack`, `/poker`, `/pfc duel` |
| Taxe sur `/argent donner` | `5 %` | Détruits (réglable avec `/eco config taxe_don`, `0` = aucune) |
| `/argent crime` | 55 % de réussite | Gain en cas de succès, amende sinon |

### Quêtes, succès, banque et braquages

Chaque module s'active et se règle avec `/ecoplus config`.

| Module | Fonctionnement |
| --- | --- |
| 📜 **Quêtes** | 3 quêtes **du jour** et 3 **de la semaine** avec `/profil quetes`. Terminer les 3 donne un bonus : **150 🪙 + 50 XP** (jour), **600 🪙 + 150 XP** (semaine) |
| 🏅 **Succès** | `/profil succes` : badges débloqués avec des pièces à chaque fois. Ils s'affichent sur la carte de profil |
| 🏦 **Banque** | `/argent banque voir\|deposer\|retirer` : **1 % d'intérêts par jour** (30 jours rattrapés au maximum), plafond du compte **50 000 🪙**, à l'abri des braqueurs |
| 🥷 **Braquages** | `/argent braquer @membre` : **45 %** de réussite, **90 min** entre deux braquages, butin max **5 000 🪙**, la victime est protégée **30 min** après un vol, il faut **200 🪙** en poche pour être braquable. Raté = amende |

### La boutique

`/boutique voir` ouvre une vitrine par catégorie, avec un **aperçu** de l'objet sur ta propre carte avant d'acheter.

| Catégorie | Contenu |
| --- | --- |
| 🎭 Rôles | Un rôle du serveur, donné à l'achat |
| ⚡ Boosts d'XP | Multiplicateur d'XP pendant une durée |
| 🏷️ Titres | Texte affiché sur tes cartes |
| 🎨 Couleurs de carte | Couleur d'accent : avatar, barre de progression, niveau |
| 🖼️ Fonds de carte | Couleur de fond des cartes |
| 🎁 Coffres mystère | Pièces ou objet rare au hasard (voir ci-dessous) |
| 🛡️ Boucliers | Protection contre les braquages pendant une durée |
| ⏳ Édition limitée | Articles de la boutique tournante |

Les cosmétiques achetés s'équipent avec **`/boutique cosmetiques`** (un seul titre, une seule couleur et un seul fond équipés à la fois). Le premier objet d'une catégorie est équipé automatiquement.

**Coffre mystère :** 🪙 pièces (40 à 100 % du prix) **55 %** • ✨ objet rare **28 %** • 💰 gros paquet de pièces (150 à 250 %) **14 %** • 🌟 objet légendaire **3 %**. En moyenne, les pièces rendent moins que le prix : c'est un pari.

**Boutique tournante :** quelques articles tirés au sort dans une réserve, disponibles un temps limité (3 articles pendant 48 h, toutes les 168 h par défaut). Active-la avec `/boutiqueadmin rotation config`.

### Remplir la boutique (admin)

| Commande | Description |
| --- | --- |
| `/boutiqueadmin gerer` | Panneau complet : ajouter, modifier prix / nom, retirer (boutique et réserve tournante) |
| `/boutiqueadmin ajouter role\|titre\|couleur\|fond\|coffre\|bouclier\|boost` | Ajout rapide en une commande |
| `/boutiqueadmin retirer_article` | Retire un article de la boutique |
| `/boutiqueadmin rotation config\|role\|boost\|liste\|retirer\|lancer` | Gère la boutique tournante |

> La boutique permanente est limitée à **25 articles** (limite d'un menu déroulant Discord).

### Offrir ou reprendre un cosmétique (admin)

```text
/boutiqueadmin donner  membre:@Alice  type:Couleur de carte  nom:Rose bonbon   hexa:#FF69B4
/boutiqueadmin donner  membre:@Alice  type:Fond de carte     nom:Nuit étoilée   hexa:#1B2A49
/boutiqueadmin donner  membre:@Alice  type:Titre             nom:Reine du vocal
/boutiqueadmin retirer membre:@Alice  objet:<à choisir dans la liste>
```

- `type` : **Titre**, **Couleur de carte** ou **Fond de carte**.
- `hexa` est **obligatoire** pour une couleur ou un fond (`#FF69B4` ou `#F6B`).
- `retirer` propose en autocomplétion **ce que le membre possède vraiment** : pas besoin de taper le nom exact.
- L'objet donné est équipé tout de suite seulement si rien n'est déjà équipé dans sa catégorie.

### Idées de codes couleur

| Couleur de carte | Hexa | Fond de carte | Hexa |
| --- | --- | --- | --- |
| Rose bonbon | `#FF69B4` | Nuit étoilée | `#1B2A49` |
| Or | `#FFD700` | Prune | `#4A1942` |
| Menthe | `#3EB489` | Forêt | `#1F3D2B` |
| Ciel | `#87CEEB` | Bordeaux | `#4A0E1B` |
| Violet | `#B07CFF` | Abysses | `#0B3954` |

> Les fonds sombres ou moyens rendent le mieux. Un fond très clair fonctionne, mais la carte est assombrie pour que le texte reste lisible.

## Cartes, événements et classement de la semaine

### Cartes en image

`/carte niveau [@membre]` et `/carte profil [@membre]` génèrent une image (nécessite **Pillow**). Elles affichent le titre, la couleur et le fond équipés. La carte de profil ajoute pièces, banque, série de `/daily`, victoires et badges de succès.

### Événements automatiques

Des événements surgissent au hasard dans le salon choisi : **pluie de pièces**, **coffre**, **calcul éclair** et **happy hour d'XP** ⚡. Le plus rapide gagne.

| Commande | Description |
| --- | --- |
| `/auto evenements` | Active, choisit le salon, la fréquence moyenne (en minutes) et le gain de base |
| `/auto lancer` | Déclenche un événement tout de suite |

### Classement de la semaine

`/profil semaine` affiche le classement de la semaine (XP, messages, vocal, victoires). Chaque **lundi**, le bot poste le podium dans le salon prévu et récompense les meilleurs.

| Commande | Description |
| --- | --- |
| `/auto classement` | Active, choisit le salon et les récompenses |
| `/auto poster` | Poste le classement de la semaine en cours maintenant (sans récompense) |

## Permissions et intents Discord

Dans le **Developer Portal → Bot → Privileged Gateway Intents**, active :

- **Message Content Intent**
- **Server Members Intent**
- **Presence Intent**

Pour l'invitation du bot, utilise les scopes `bot` et `applications.commands`. Donne-lui les permissions dont tu as besoin selon les fonctions utilisées : gérer les rôles (dont les rôles-récompenses de niveau et les rôles vendus en boutique), gérer les salons, gérer les messages, gérer les webhooks (`/envoyer` sous pseudo), expulser / bannir, exclure des membres (mute), rendre muets / sourdine (vocal), gérer les emojis, voir les salons, envoyer des messages, intégrer des liens, joindre des fichiers (cartes en image), ajouter des réactions, utiliser les emojis externes. Le plus simple est de lui donner **Administrateur** sur un serveur de confiance.

> Le rôle du bot doit être placé **au-dessus** des rôles qu'il doit gérer ou sanctionner.

## Commandes

Pour garder la liste courte (Discord limite à 100 commandes), les commandes sont **regroupées** : tape `/` puis le nom du groupe, et Discord propose les sous-commandes.

| Groupe | Contient |
| --- | --- |
| `/action` | bisou, câlin, headpat, gifle, bonk, cadeau (menu « type ») |
| `/fun` | `roast`, `blague`, `8ball`, `choisir`, `ship` |
| `/mariage` | `proposer`, `voir`, `divorcer` |
| `/pfc` | `bot` (contre moi), `duel` (contre un membre, mise possible) |
| `/quiz` | `rapide`, `perso …` (quiz des membres), `kahoot …` |
| `/stat` | `classement`, `joueur` |
| `/reglesjeux` | `blackjack`, `poker`, `mains` |
| `/profil` | `voir`, `top`, `prestige`, `semaine`, `quetes`, `succes` |
| `/argent` | `travail`, `crime`, `braquer`, `donner`, `richesse`, `banque …` |
| `/boutique` | `voir`, `cosmetiques` |
| `/bot` | `ping`, `lien`, `serveur` |

Restent en commandes directes, car ce sont les plus utilisées : `/ask`, `/solde`, `/daily`, `/niveau`, `/blackjack`, `/poker`, `/jeux`, `/carte`, `/aide`.

Les commandes marquées *(admin)* ou *(staff)* sont réservées. `/aide` affiche tout ce que le bot sait faire, `/aideadmin` la partie réservée aux admins.

### 💬 IA et discussion

| Commande | Description |
| --- | --- |
| `/ask` | Pose une question (options : `detail`, `web`) |
| `/recherche` | Recherche sur le web et donne des liens |
| `/fun roast` | Chambre quelqu'un |
| `/fun blague` | Blague coquine (sous-entendus, jamais explicite) |
| `/fun 8ball` | Réponse à une question fermée |
| `/fun choisir` | Tranche entre plusieurs options |
| `/meteo` | Météo d'une ville (aussi : « météo Lyon » dans le chat) |
| `/reset` | Efface la mémoire du salon |

### 💋 Social

| Commande | Description |
| --- | --- |
| `/action type @membre` | Bisou, câlin, headpat, gifle, bonk ou cadeau : petite scène avec ping (essaie sur Mika 😏) |
| `/mariage proposer`, `/mariage voir`, `/mariage divorcer` | Mariage (jusqu'à 3 personnes) |
| `/fun ship` | Compatibilité entre deux personnes |
| `/profil voir` | Profil d'un membre : statut, stats de jeu, argent et niveau |

### 🎮 Jeux

| Commande | Description |
| --- | --- |
| `/jeux` | Panel regroupant tous les jeux |
| `/pfc bot`, `/pfc duel` | Pierre-feuille-ciseaux (contre le bot ou en duel, mise possible) |
| `/quiz rapide` | Quiz rapide : le premier qui trouve gagne |
| `/blackjack`, `/reglesjeux blackjack` | Blackjack, seul ou à plusieurs, et ses règles |
| `/poker`, `/reglesjeux poker`, `/reglesjeux mains` | Texas Hold'em, ses règles, classement des mains |
| `/stat classement`, `/stat joueur` | Classement du serveur et stats individuelles (victoires, défaites, K/D) |
| `/quiz perso creer\|jouer\|liste\|supprimer` | Quiz créés par les membres |
| `/quiz kahoot creer\|generer\|lancer\|liste\|supprimer` | Kahoot (quiz live multi-joueurs), à la main ou par l'IA |

### 🪙 Économie

| Commande | Description |
| --- | --- |
| `/solde` | Ton porte-monnaie |
| `/daily` | Bonus quotidien (série + jackpot hebdo) |
| `/argent travail` | Gagne des pièces en travaillant (délai entre deux) |
| `/argent crime` | Plus risqué : gros gain ou amende 😈 |
| `/argent donner` | Donne des pièces (petite taxe) |
| `/argent richesse` | Les plus riches du serveur |
| `/boutique voir` | Dépense tes pièces : rôles, boosts, cosmétiques, coffres, boucliers |
| `/boutique cosmetiques` | Équipe tes titres, couleurs et fonds de carte |
| `/profil quetes` | Quêtes du jour et de la semaine |
| `/profil succes [@membre]` | Succès et badges |
| `/argent banque voir\|deposer\|retirer` | Compte en banque à intérêts |
| `/argent braquer @membre` | Vole des pièces à un autre joueur 🥷 |

### 🪙 Économie (admin)

| Commande | Description |
| --- | --- |
| `/ecopanel` *(admin)* | Panneau de l'économie et des mises |
| `/eco config\|donner\|retirer\|reset` *(admin)* | Réglages (dont `taxe_don`) et gestion des soldes |
| `/ecoplus config` *(admin)* | Quêtes, succès, banque (taux, plafond) et braquages (chance, délai, bouclier, butin max) |
| `/boutiqueadmin …` *(admin)* | Gère la boutique (voir [Économie et boutique](#économie-et-boutique)) |
| `/auto evenements\|classement\|lancer\|poster` *(admin)* | Événements automatiques et classement du lundi |

### 📈 Niveaux et cartes

| Commande | Description |
| --- | --- |
| `/niveau [@membre]` | Niveau, barre de progression, rang, temps en vocal et prochain rôle à débloquer |
| `/profil top [tri]` | Classement des membres, par XP (défaut) ou par temps passé en vocal |
| `/profil prestige` | Remet ton niveau à zéro contre une ⭐ permanente et un bonus d'XP |
| `/carte niveau\|profil [@membre]` | Ta carte en image |
| `/profil semaine` | Le classement de la semaine |
| `/xp config` *(admin)* | Active les niveaux, règle les gains d'XP et d'argent, l'anti-farm, le prestige et le salon d'annonces |
| `/xp donner\|retirer\|reset\|evenement` *(admin)* | Ajuste l'XP d'un membre / lance un double XP |
| `/recompense ajouter\|retirer\|liste\|appliquer` *(admin)* | Rôles offerts en atteignant un niveau |

### 🔨 Modération

| Commande | Description |
| --- | --- |
| `/punition panel` | Panel de punitions du staff (mute, avertir, expulser, bannir, nettoyer, mute vocal, casque, rôles) |
| `/punition deban` | Débannit quelqu'un (avec log) |
| `/automod config\|mot\|pardon\|statut` *(admin)* | Auto-modération et mots interdits |
| `/interdit ajouter\|retirer\|liste\|vider` *(staff)* | Salons ou catégories où le bot ne parle plus |
| `/purge` *(staff)* | Supprime un nombre de messages |
| `/silence` *(staff)* | Le bot se tait un moment (`off` pour annuler) |
| `/logs` *(admin)* | Définit le salon des logs |

### 📜 Règles obligatoires

| Commande | Description |
| --- | --- |
| `/regle serveur` *(admin)* | Texte des règles, salon, rôle donné à l'acceptation, délai, activation. Refus ou délai dépassé = expulsion |
| `/regle afficher` | Relis les règles du serveur |

> Le salon des règles doit être visible par les nouveaux membres, et le bot doit avoir la permission « Expulser des membres ». Les admins et le propriétaire ne sont jamais expulsés.

### 🎉 Giveaways

| Commande | Description |
| --- | --- |
| `/givawayyy lancer` *(staff)* | Lance un giveaway (lot, durée, gagnants, rôle requis) |
| `/givawayyy terminer\|relancer\|annuler\|liste` *(staff)* | Gère les giveaways (choix dans la liste) |

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
| `/bienvenue config\|generer\|tester` *(staff)* | Messages d'accueil personnalisés, générés par l'IA, aperçu privé |
| `/autorole definir\|retirer\|etat` *(staff)* | Rôle donné automatiquement aux nouveaux (membres ou bots) |
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
| `/adminpanel` *(admin)* | Panneau de configuration complet : fonctionnalités, modération, logs par type, économie et niveaux, accueil, outils. Options : `page` (section à ouvrir), `reactions`, `spontane`, `salutations`, `nom` (activer / couper directement) |
| `/style` *(admin)* | Change la personnalité du bot sur ce serveur (dominatrice, mommy, douce, sarcastique) |
| `/envoyer` *(admin)* | Message anonyme, sous un pseudo perso ou avec l'identité du bot |
| `/creeserveur` *(admin)* | L'IA génère un serveur complet : rôles, salons, permissions |
| `/creersalon`, `/supprimersalon` *(staff)* | Crée ou supprime un salon / une catégorie |
| `/role creer\|supprimer` *(staff)* | Crée ou supprime un rôle |
| `/emoji agrandir\|ajouter` | Affiche un emoji en grand / l'ajoute au serveur *(admin)* |
| `/dev projet\|question` | L'IA génère un site ou une app (zip) / répond à une question de dev |
| `/optimiser` *(admin)* | Analyse les performances et propose des améliorations |
| `/bot serveur` | Stats du serveur |
| `/bot lien` | Lien du projet (GitHub) |
| `/bot ping` | Latence du bot |
| `/test` *(admin)* | Vérifie que tout fonctionne |
| `/sync` *(owner)* | Resynchronise les commandes |

## Logs

Définis le salon avec `/logs`, puis choisis les types à enregistrer dans `/adminpanel`.

| Type | Contenu | Par défaut |
| --- | --- | --- |
| 🔨 Sanctions | mute, kick, ban, avertissement, vocal, règles refusées | activé |
| 📋 Commandes | slash, panels, `!nom` (dont `/xp`, `/recompense` et `/boutiqueadmin`) | activé |
| 🎭 Rôles | donnés, retirés, créés, supprimés, panneaux, rôle auto | activé |
| 🛡️ Auto-modération | infractions et sanctions auto | activé |
| 🎫 Tickets | ouverture, fermeture, transcripts | activé |
| 🛠️ Actions admin | envoyer, salons, serveur IA, giveaways | activé |
| 👋 Arrivées et départs | membres qui rejoignent / partent, règles acceptées | désactivé |
| 💬 Messages | supprimés / modifiés | désactivé |
| 🎙️ Vocal | connexion, départ, déplacement | désactivé |

Les logs de tickets peuvent aussi avoir un salon dédié (`/ticket config`) ; à défaut, ils vont dans le salon de logs général.

## Données et sauvegarde

Tout est stocké dans un fichier SQLite (`bot.db` par défaut, modifiable via `DB_PATH`) : mémoire des salons, économie et boutique, **cosmétiques des membres**, **niveaux et rôles-récompenses**, quêtes, succès, banque, stats de jeu, quiz, Kahoot, giveaways, règles en attente, paramètres par serveur, etc. Les tables sont créées automatiquement, y compris sur une base existante : activer un module ne supprime rien.

Pour sauvegarder : arrête le bot et copie `bot.db` (ainsi que les éventuels fichiers `bot.db-wal` et `bot.db-shm`).

Les boutons de rôles, sondages, tickets, giveaways et règles restent actifs après un redémarrage.

## Dépannage

- **Le bot ne répond pas aux messages** : vérifie que le *Message Content Intent* est activé dans le Developer Portal.
- **Il ne démarre pas** : `DISCORD_TOKEN` et `AI_API_KEY` doivent être définis dans `.env`.
- **`TypeError: bad operand type for unary -: 'str'` au démarrage** : un `-` ou un `+` s'est glissé au tout début du fichier lors d'un copier-coller (souvent depuis une vue de diff). Supprime-le, ou envoie le fichier plutôt que de coller son contenu.
- **Les commandes n'apparaissent pas** : redémarre le bot, lance `/sync` (owner) ou mets `SYNC_ON_START=1` une fois. La propagation côté Discord peut prendre quelques minutes.
- **Il ne peut pas sanctionner ou gérer un rôle** : place le rôle du bot au-dessus des rôles concernés et vérifie ses permissions.
- **`/dev projet` renvoie des fichiers coupés** : baisse `DEV_MAX_TOKENS` si ton modèle limite la taille de sortie.
- **Erreurs d'IA** : vérifie `AI_BASE_URL`, `AI_MODEL` et ta clé ; les limites de débit des offres gratuites peuvent être atteintes.
- **Les règles n'expulsent personne** : le texte et le salon doivent être définis (`/regle serveur`), et le bot doit avoir « Expulser des membres » avec un rôle au-dessus du nouveau.
- **`/niveau` répond que les niveaux ne sont pas activés** : lance `/xp config actif:True` (ou active **Niveaux** dans `/adminpanel` › *Économie & accueil*).
- **Personne ne gagne d'XP en vocal** : vérifie que `vocal` est activé dans `/xp config`, que les membres n'ont pas le casque coupé, ne sont pas dans le salon AFK, et qu'ils sont assez nombreux dans le salon (`membres_min`, 2 par défaut).
- **L'XP monte mais pas l'argent en vocal** : l'économie doit être activée (`/ecopanel`), et `argent_vocal` doit être supérieur à 0.
- **Plus d'XP alors que le membre est actif** : il a probablement atteint un plafond quotidien (chat, vocal ou jeux) ; vois `/xp config`.
- **Pas d'annonce de passage de niveau** : le bot doit pouvoir envoyer des messages et intégrer des liens dans le salon d'annonces (ou le salon du membre), et il ne doit pas être en `/silence` ni dans un salon interdit.
- **Un rôle-récompense n'est pas donné** : le rôle du bot doit être **au-dessus** de ce rôle avec « Gérer les rôles » (rôles de bot ou `@everyone` impossibles). Pour les membres qui avaient déjà le niveau avant l'ajout, lance `/recompense appliquer`.
- **`/carte` répond qu'il faut Pillow** : `pip install pillow`, puis relance le bot.
- **Le titre ou le fond n'apparaît pas sur la carte** : l'objet doit être **équipé** (✅ dans `/boutique cosmetiques`). Un second objet de la même catégorie n'est pas équipé automatiquement. Un titre composé uniquement d'emojis ne peut pas être dessiné.
- **La boutique est pleine** : elle est limitée à 25 articles ; retire-en avec `/boutiqueadmin gerer`.
- **`/boutiqueadmin donner` refuse un fond ou une couleur** : le code `hexa` est obligatoire et doit être valide (`#FF69B4`).
- **Un rôle de la boutique n'est pas donné** : le rôle du bot doit être au-dessus du rôle vendu, avec « Gérer les rôles ».
- **`/aideadmin` ou un embed refuse de s'afficher** : Discord limite un champ à 1 024 caractères et un embed à 6 000 ; si tu modifies les textes d'aide, reste sous ces limites.

## Crédits

- [discord.py](https://github.com/Rapptz/discord.py)
- [Open-Meteo](https://open-meteo.com/) — météo gratuite sans clé
- [ddgs](https://pypi.org/project/ddgs/) — recherche DuckDuckGo
- [Pillow](https://python-pillow.org/) — cartes en image
- [Groq](https://groq.com/) — IA par défaut
- [Claude](https://claude.ai/new) — IA pour le code

Fait par [MrMisteur](https://github.com/MrMisteur) - *sois sage, petit chat 🖤*

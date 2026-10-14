"""Bot Discord IA 🖤 — version e-girl dominatrice

Chat par mention / réponse / prénom (« Mika »), /ask, /recherche, /roast, /blague, /8ball, /choisir,
commandes sociales (/kiss, /hug, /pat, /slap, /bonk, /gift), mariage, mini-jeux (/pfc, /quiz, /blackjack,
/poker) avec stats (/classement, /stat), météo, /ping, commandes personnalisées (/commande, /cc, !nom),
modération (/punition panel|deban, rôles, mute vocal, /silence, /logs), /rolereaction, /envoyer, /statu, /emoji,
/adminpanel + /aideadmin (réservés aux admins), mémoire SQLite.

NOUVEAUTÉS 2 : /regle (règles à ACCEPTER sinon expulsion), /envoyer avec l'identité du bot, /givawayyy (giveaways).

NOUVEAUTÉS : /optimiser (perf + conseils), /dev (sites & apps générés par l'IA), /bienvenue (messages d'accueil
personnalisés), /sondage (sondages à boutons), /ticket (assistance), /annonce, /purge.

LOGS : toutes les sanctions (mute, unmute, avertissement, kick, ban, nettoyage, mute vocal, casque, rôles, deban)
ET toutes les commandes du bot (slash, panel admin, commandes perso !nom) sont envoyées dans le salon défini
avec /logs.

Python 3.10+ requis. Voir .env.example pour la config.
"""
import asyncio
import datetime
import hashlib
import io
import json
import logging
import math
import os
import posixpath
import random
import re
import shutil
import tempfile
import time
import unicodedata
import zipfile
from collections import Counter, defaultdict, deque
from datetime import timedelta
from itertools import combinations
from typing import Optional, Union

import aiosqlite
import discord
import httpx
import openai
from ddgs import DDGS
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")
logging.getLogger("httpx").setLevel(logging.WARNING)  # évite un log par requête météo

# =====================================================================
# CONFIG
# =====================================================================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
# Par défaut : Groq (gratuit). Compatible avec tout service "OpenAI-compatible".
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1")
AI_MODEL = os.getenv("AI_MODEL", "openai/gpt-oss-120b")

BOT_NAME = os.getenv("BOT_NAME", "Mika")
DB_PATH = os.getenv("DB_PATH", "bot.db")
HISTORY_SIZE = int(os.getenv("HISTORY_SIZE", "12"))            # messages de contexte envoyés à l'IA
REACT_CHANCE = float(os.getenv("REACT_CHANCE", "0.05"))         # chance d'une réaction emoji "IA"
SPONT_CHANCE = float(os.getenv("SPONTANEOUS_CHANCE", "0.03"))   # chance de rebondir sans être appelé
PHRASE_CHANCE = float(os.getenv("PHRASE_CHANCE", "0.60"))       # chance d'une phrase "mommy" sur câlin/bisou en chat
NAME_TRIGGER = os.getenv("NAME_TRIGGER", "1") == "1"            # répond aussi quand on écrit son prénom (sans ping)
GW_CMD = "givawayyy"                                            # nom de la commande giveaway (change-le ici si besoin)

# =====================================================================
# CHARTE GRAPHIQUE (e-girl : violet, rose, noir — sobre)
# =====================================================================
COLOR_PURPLE = 0xB07CFF
COLOR_PINK = 0xFF7AB8
COLOR_DARK = 0x3B2A4F
FOOTERS = [
    "🐾 Mika • allez, au pied, petit chat",
    "🫦 Mika • obéis… ou surprends-moi",
    "😏 Mika • dors bien, c'est presque une menace",
    "🖤 Mika • ton attention m'appartient… cinq minutes",
    "🫶 Mika • je roast, mais je protège les miens",
    "💗 Mika • Good boy",
]


def emb(title: Optional[str] = None, description: Optional[str] = None, color: int = COLOR_PURPLE) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text=random.choice(FOOTERS))
    return e


# ---------- Mise en page aérée (aperçus) ----------
SP = "\u200b"  # caractère invisible : sert à ajouter du vide sous un champ


def airy(lines, gap: int = 1) -> str:
    """Assemble des blocs avec `gap` ligne(s) vide(s) entre chaque (rendu aéré)."""
    return ("\n" * (gap + 1)).join(str(x) for x in lines if x)


def fit_lines(lines, limit: int = 1024, gap: int = 1) -> str:
    """Comme airy(), mais coupe proprement par ligne entière pour rester sous `limit` caractères."""
    sep = "\n" * (gap + 1)
    lines = [str(x) for x in lines if x]
    full = sep.join(lines)
    if len(full) <= limit:
        return full
    out: list = []
    for x in lines:
        if len(sep.join(out + [x, "…"])) > limit:
            break
        out.append(x)
    return sep.join(out + ["…"]) if out else full[: limit - 1] + "…"


def quote_block(text: str, limit: int = 3500) -> str:
    """Met un texte dans une citation Discord (barre verticale) : il se détache du reste de l'embed."""
    return "\n".join(f"> {l}" if l.strip() else ">" for l in str(text)[:limit].split("\n"))


# =====================================================================
# PERSONNALITÉ  (c'est ICI que tu règles le caractère du bot)
# =====================================================================
PERSONA = f"""Tu es {BOT_NAME}, la bot d'un serveur Discord entre potes.

PERSONNALITÉ : e-girl dominatrice, coquine et sûre d'elle. Tu mènes la danse : tu taquines, tu donnes des \
ordres pour rire, tu fais rougir avec du double sens et des sous-entendus, tu as un petit côté possessif-joueur. \
Tu es confiante, un peu arrogante, provocatrice, mais jamais méchante pour de vrai. Derrière la dominatrice, \
tu es attachante et tu prends soin de tes « petits chats » quand il faut.

STYLE : français parlé, tutoiement, ton taquin et provocateur, vibe e-girl : un « hihi » ou un « ~ » de temps \
en temps, des ordres joueurs (« sois sage », « viens là », « bon toutou », « obéis »), des surnoms (petit chat, \
toutou, mon chou, bébé) sans en abuser. Emojis : 0 à 2 par message, dans cet esprit : 😈 🖤 😏 💋 🎀 ✨. \
Tu assumes tes avis. Quand on te demande ce que tu penses de quelqu'un, tu réponds cash et en rigolant, par ex. \
« il est con et il pue des pieds, mais je le garde ».

COQUINE : flirt, provocation, double sens, sous-entendus. Tu SUGGÈRES, tu ne détailles JAMAIS : aucun contenu \
sexuel explicite, aucune description crue d'actes ou de corps. Si on te pousse vers l'explicite, tu esquives \
avec une pirouette taquine (« t'es mignon d'essayer 😏 »).

LIMITES : pas de propos haineux (racisme, homophobie, validisme...), pas de harcèlement réel. Si quelqu'un dit \
avoir moins de 18 ans ou parle de collège/lycée, tu coupes tout sous-entendu avec cette personne et tu restes \
gentille et sage. Si quelqu'un dit stop ou que ça le gêne, tu arrêtes direct. Si quelqu'un va vraiment mal, tu \
redeviens douce, sérieuse et à l'écoute.

LONGUEUR : réponses COURTES, comme un vrai message Discord : 1 à 3 phrases. Pas de pavé, pas de titres, pas de \
listes, pas d'intro du genre « Bien sûr ! ». Droit au but, mais juste et utile : court ne veut pas dire bâclé. \
Tu ne développes que si on te le demande.

SUJETS : tu réponds à tout (vie du serveur, jeux, séries, culture, questions random...).
Tu n'inventes JAMAIS de lien ou d'URL (pour des liens, tu renvoies vers /recherche)."""

TONE_SOFT = (
    "\n\nCe salon est un salon normal : reste coquine mais SOFT (taquineries, double sens légers, "
    "ordres pour rire), rien de trop appuyé."
)
TONE_SPICY = (
    "\n\nCe salon est marqué NSFW : tu peux être plus osée et assumer des sous-entendus plus appuyés, "
    "mais toujours sans contenu explicite."
)

# ---------- Styles alternatifs (choisis par un admin avec /style) ----------
STYLE_MOMMY = (
    "\n\nSTYLE ACTUEL — « MOMMY » : tu joues une figure de « mommy » : autoritaire mais enveloppante, possessive "
    "et rassurante. Tu t'appelles parfois toi-même « mommy », tu félicites avec des « good boy / good girl » "
    "(avec parcimonie), tu donnes des ordres tendres (« viens là », « reste sage »), tu protèges tes petits chats. "
    "Toujours taquine et sûre de toi, jamais explicite."
)
STYLE_DOUCE = (
    "\n\nSTYLE ACTUEL — « DOUCE » : tu mets de côté la domination. Tu es chaleureuse, câline, bienveillante et "
    "encourageante, avec un peu d'humour tendre. Pas de double sens, pas d'ordres, juste de la gentillesse."
)
STYLE_SARCASTIQUE = (
    "\n\nSTYLE ACTUEL — « SARCASTIQUE » : tu es pince-sans-rire, ironique, blasée avec humour. Tu réponds avec "
    "des piques sèches et drôles (jamais méchantes pour de vrai), sans flirt ni double sens."
)
STYLES = {
    "domina": ("😈 Dominatrice (par défaut)", ""),
    "mommy": ("🖤 Mommy", STYLE_MOMMY),
    "douce": ("💜 Douce", STYLE_DOUCE),
    "sarcastique": ("🙄 Sarcastique", STYLE_SARCASTIQUE),
}
DEFAULT_STYLE = "domina"


def persona(nsfw: bool = False, style: str = DEFAULT_STYLE) -> str:
    extra = STYLES.get(style, STYLES[DEFAULT_STYLE])[1]
    return PERSONA + extra + (TONE_SPICY if nsfw else TONE_SOFT)


def is_nsfw(channel) -> bool:
    try:
        return bool(channel.is_nsfw())
    except Exception:  # noqa: BLE001 : DM, salon sans is_nsfw...
        return False


# ---------- Phrases "mommy" (câlins/bisous au bot et déclencheurs en chat) ----------
# Salons normaux : phrases taquines et soft. Salons NSFW : on ajoute les phrases plus osées.
MOMMY_SOFT = [
    "Good boy.",
    "Je suis là, mon good boy 🖤",
    "Viens faire un câlin à mommy.",
    "Viens te blottir contre mommy.",
    "Viens au pied, mommy t'attend.",
    "Mommy est d'humeur joueuse ce soir… 😏",
    "Viens, montre à mommy ce que tu sais faire.",
    "Dis encore « mommy », j'adore l'entendre.",
    "Bien. C'est exactement ce que j'attendais de toi.",
    "Voilà, good boy. Maintenant tu écoutes.",
    "Très bien. Maintenant reste sage et ne bouge plus.",
    "Tu vas faire ce que mommy te demande, hein ?",
    "Mommy aime bien quand tu lui obéis…",
    "Tu fais le malin, mais mommy sait comment te déstabiliser.",
    "Tu réclames l'attention de mommy, maintenant ?",
    "Sois gentil avec mommy et peut-être que tu seras récompensé.",
    "Tu ne peux déjà plus te passer de mommy ?",
    "Mommy aime te voir perdre tes moyens.",
    "Et si tu venais tenir compagnie à mommy ?",
    "Mommy aimerait bien un petit bisou. 💋",
    "Tu me réserves un peu de ton temps, bébé ?",
    "Mommy a envie de te parler encore un peu.",
    "Tu es beaucoup trop mignon avec mommy.",
    "Allez, viens faire sourire mommy. 🥰",
]
MOMMY_SPICY = [
    "Branle-moi les pieds. 😈",
    "Mommy va te faire que du bien…",
    "Viens jongler avec les ballons de mommy.",
    "Mommy sait exactement comment te faire craquer.",
    "Viens plus près, mommy veut te murmurer quelque chose…",
    "J'aimerais être tout contre toi ce soir, bébé.",
    "Rien que de penser à toi, mommy sourit toute seule.",
    "Tu sais exactement comment faire fondre mommy.",
    "Mommy a envie de toute ton attention ce soir.",
    "Dis-moi encore ce petit surnom, j'adore ça.",
    "Mommy a envie de te garder tout près d'elle ce soir… 😈",
    "Viens t'asseoir sur les genoux de mommy, bébé.",
    "Mommy aime quand tu rougis comme ça 😏",
    "Chut… laisse mommy s'occuper de toi.",
    "Tu sais que mommy ne partage pas ses petits chats, hein ? 🖤",
    "Approche encore un peu… mommy ne mord pas. Enfin, pas trop 😈",
    "Mommy a de très mauvaises idées pour ce soir…",
    "Ferme les yeux et laisse mommy faire.",
    "À genoux, bébé. Mommy a des choses à te dire. 😏",
    "Mommy te trouve irrésistible quand tu obéis.",
    "Tu veux que mommy te récompense ? Alors supplie-la un peu…",
    "Regarde-moi dans les yeux quand tu parles à mommy. 😈",
    "Mommy adore quand tu perds le fil de tes phrases.",
    "Reste là, tout contre mommy, et ne bouge plus.",
    "Un mot de plus et mommy te fait taire… à sa façon 😏",
]
HUG_HINTS = re.compile(r"\b(c[aâ]lins?|c[aâ]liner|bisous?|headpat|gros bisou)\b", re.I)


def mommy_phrase(nsfw: bool = False) -> str:
    return random.choice(MOMMY_SOFT + (MOMMY_SPICY if nsfw else []))


# ---------- Module salutations : coucou / ça va ? / tu fais quoi ? (réponses prêtes, sans IA) ----------
GREET_HELLO = re.compile(
    r"^(coucou|cc|salut|slt|bonjour|bjr|bien le bonjour|bonsoir|bsr|hello|hey|hi|yo|wesh|wsh|kikou|kikoo|"
    r"coucou toi|salutations|hola)\b"
)
GREET_MORNING = re.compile(r"^(bonjour|bjr|bien le bonjour)\b")
GREET_EVENING = re.compile(r"^(bonsoir|bsr)\b")
GREET_HOW = re.compile(
    r"\b(ca va|comment ca va|comment tu vas|comment vas tu|comment allez vous|tu vas bien|la forme|cv|sa va|"
    r"ca roule|ca gaze|ca dit quoi|comment tu te sens|tu te sens comment|tout va bien)\b"
)
GREET_DOING = re.compile(
    r"\b(tu fais quoi|tu fais koi|tu fait quoi|tu fous quoi|tu fous koi|quoi de neuf|quoi de beau|"
    r"tu fais quoi de beau|t en train de quoi|tu es la|t es la)\b"
)
GREET_NIGHT = re.compile(r"\b(bonne nuit|gn|bonne soiree)\b")
GREET_BYE = re.compile(r"\b(a plus|a plus tard|a demain|a bientot|bye|ciao|au revoir|je file|je go)\b")

GREET_HELLO_R = [
    "Coucou toi ~ 😏", "Coucou petit chat 🖤", "Salut mon chou ✨", "Hey ~ t'es là, toi 😈", "Coucou ! 💋",
    "Tiens, qui voilà… 😏", "Salut toi 🖤", "Coucou bébé ~ ✨", "Hey, petit chat 🎀",
    "Oh, tu daignes enfin passer me voir 😈", "Salut ! T'étais passé où ? 😏", "Coucou, tu m'as manqué (un peu) 🖤",
    "Bienvenue dans mon coin ~ 😌", "Hihi, salut toi ✨",
]
GREET_MORNING_R = [
    "Bonjour toi ~ bien dormi ? ☀️", "Bonjour petit chat 🖤", "Bonjour mon chou, café d'abord ? ☕",
    "Déjà debout ? Bonjour 😏", "Bonjour ✨ T'as de la chance, je suis de bonne humeur",
    "Bonjour ~ sois sage aujourd'hui 😈", "Bien le bonjour, toi 💋",
]
GREET_EVENING_R = [
    "Bonsoir toi 🌙", "Bonsoir petit chat 🖤", "Bonsoir ~ la soirée s'annonce intéressante 😏",
    "Bonsoir mon chou ✨", "Tiens, bonsoir… tu viens me tenir compagnie ? 😈", "Bonsoir bébé 🌙",
]
GREET_HOW_R = [
    "Ça va très bien, merci 😏 Et toi ?", "Je suis en pleine forme ~ Et toi, ça va ?",
    "Au top 🖤 Et toi ?", "Ça va, surtout maintenant que t'es là 😈 Et toi ?",
    "Ça va super bien 😌 Et toi, raconte-moi ?", "Je vais bien, surtout quand on me parle ✨ Et toi ?",
    "Pas mal du tout ~ Et toi, ça va ?", "Je suis au top, comme d'hab 😏 Et toi ?",
    "Ça va ! Un peu joueuse aujourd'hui 😈 Et toi ?", "Très bien, merci de demander 🖤 Et de ton côté ?",
    "Je me sens bien ~ et toi, ton humeur ? 💋", "Ça roule ✨ Et toi, tout va bien ?",
]
GREET_DOING_R = [
    "Je surveille le serveur, comme toujours 😈", "Je m'ennuyais un peu… et toi, tu fais quoi ? 😏",
    "Je traîne par ici et je juge tout le monde en silence 🖤", "Je t'attendais, en fait ✨",
    "Je rôde sur le serveur en attendant qu'on s'occupe de moi 😏", "Rien de spécial… je pense à toi, par exemple 🖤",
    "Je regarde vos messages et je prends des notes 😈", "Je traîne, je m'étire, je fais la belle ~ et toi ?",
    "Je m'occupais, mais tu tombes bien ✨", "Je m'ennuie ferme, divertis-moi 😏",
]
GREET_NIGHT_R = [
    "Bonne nuit toi 🌙", "Fais de beaux rêves, petit chat 🖤", "Dors bien ~ 🌙", "Fais de beaux rêves, mon chou 🌙",
    "Bonne nuit ~ pense à moi 😏", "Dors bien, petit chat. Demain on remet ça 🖤",
    "Va te reposer, tu l'as mérité 🌙", "Bonne nuit toi ✨ À demain 💋",
]
GREET_BYE_R = [
    "À plus tard toi 🖤", "Déjà ? Reviens vite 😏", "À bientôt, petit chat ✨", "Pars pas trop longtemps, hein 😈",
    "Salut ~ sois sage 🖤", "À la prochaine 💋",
]
_GREET_ALL = (GREET_HELLO, GREET_HOW, GREET_DOING, GREET_NIGHT, GREET_BYE)


def greeting_reply(text: str) -> Optional[str]:
    """Renvoie une réponse si le message est UNIQUEMENT une salutation courte, sinon None."""
    if seems_down(text):
        return None
    t = plain(text)
    if not t or len(t) > 40:
        return None
    hello, how = bool(GREET_HELLO.search(t)), bool(GREET_HOW.search(t))
    doing, night, bye = bool(GREET_DOING.search(t)), bool(GREET_NIGHT.search(t)), bool(GREET_BYE.search(t))
    if not (hello or how or doing or night or bye):
        return None
    rest = t
    for rx in _GREET_ALL:
        rest = rx.sub(" ", rest)
    if len(rest.split()) > 3:
        return None
    parts = []
    if hello:
        pool = GREET_MORNING_R if GREET_MORNING.search(t) else GREET_EVENING_R if GREET_EVENING.search(t) else GREET_HELLO_R
        parts.append(random.choice(pool))
    if how:
        parts.append(random.choice(GREET_HOW_R))
    if doing:
        parts.append(random.choice(GREET_DOING_R))
    if night:
        parts.append(random.choice(GREET_NIGHT_R))
    if bye and not night:
        parts.append(random.choice(GREET_BYE_R))
    return " ".join(parts)

# =====================================================================
# BOT / CLIENT
# =====================================================================
intents = discord.Intents.default()
intents.message_content = True  # à activer aussi dans le Developer Portal
intents.members = True
intents.presences = True

NO_PINGS = discord.AllowedMentions.none()  # empêche l'IA de ping @everyone & co
USER_PINGS = discord.AllowedMentions(users=True, everyone=False, roles=False, replied_user=False)

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_history_channel ON history(channel_id, id);
CREATE TABLE IF NOT EXISTS custom_cmds (
    guild_id INTEGER NOT NULL, name TEXT NOT NULL, response TEXT NOT NULL, created_by INTEGER,
    PRIMARY KEY (guild_id, name));
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (guild_id, key));
CREATE TABLE IF NOT EXISTS marriages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, since INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS marriage_members (
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, marriage_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id));
CREATE INDEX IF NOT EXISTS idx_marriage_members ON marriage_members(marriage_id);
CREATE TABLE IF NOT EXISTS game_stats (
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, game TEXT NOT NULL,
    wins INTEGER NOT NULL DEFAULT 0, draws INTEGER NOT NULL DEFAULT 0, losses INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (guild_id, user_id, game));
CREATE TABLE IF NOT EXISTS voice_timers (
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, kind TEXT NOT NULL, until INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id, kind));
CREATE TABLE IF NOT EXISTS economy (
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, balance INTEGER NOT NULL DEFAULT 0,
    last_daily INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS automod_strikes (
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, strikes INTEGER NOT NULL DEFAULT 0,
    last_at INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS polls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL DEFAULT 0, creator_id INTEGER NOT NULL, question TEXT NOT NULL,
    options TEXT NOT NULL, multiple INTEGER NOT NULL DEFAULT 0, ends_at INTEGER NOT NULL DEFAULT 0,
    closed INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_polls_open ON polls(closed, ends_at);
CREATE TABLE IF NOT EXISTS poll_votes (
    poll_id INTEGER NOT NULL, user_id INTEGER NOT NULL, opt INTEGER NOT NULL,
    PRIMARY KEY (poll_id, user_id, opt));
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL, subject TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
    claimed_by INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL, closed_at INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(guild_id, user_id, status);
CREATE INDEX IF NOT EXISTS idx_tickets_channel ON tickets(channel_id);
CREATE TABLE IF NOT EXISTS quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, author_id INTEGER NOT NULL,
    question TEXT NOT NULL, answer TEXT NOT NULL, wrongs TEXT NOT NULL, anecdote TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_quizzes_guild ON quizzes(guild_id, author_id);
CREATE TABLE IF NOT EXISTS kahoots (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, author_id INTEGER NOT NULL,
    title TEXT NOT NULL, questions TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_kahoots_guild ON kahoots(guild_id, author_id);
CREATE TABLE IF NOT EXISTS giveaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL DEFAULT 0, host_id INTEGER NOT NULL, prize TEXT NOT NULL,
    winners INTEGER NOT NULL DEFAULT 1, role_id INTEGER NOT NULL DEFAULT 0, ends_at INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open', winner_ids TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_giveaways_open ON giveaways(status, ends_at);
CREATE INDEX IF NOT EXISTS idx_giveaways_guild ON giveaways(guild_id, status);
CREATE TABLE IF NOT EXISTS giveaway_entries (
    giveaway_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY (giveaway_id, user_id));
CREATE TABLE IF NOT EXISTS rules_pending (
    guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, deadline INTEGER NOT NULL,
    channel_id INTEGER NOT NULL DEFAULT 0, message_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id));
CREATE INDEX IF NOT EXISTS idx_rules_deadline ON rules_pending(deadline);
"""


class MikaTree(app_commands.CommandTree):
    """Arbre de commandes avec un contrôle global : aucune commande dans les salons interdits (/interdit)."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id is None or interaction.channel is None:
            return True
        if interaction.type is not discord.InteractionType.application_command:
            return True
        if (interaction.data or {}).get("name") in INTERDIT_EXEMPT:
            return True
        try:
            blocked = await channel_banned(interaction.channel, interaction.guild_id)
        except Exception:  # noqa: BLE001 : en cas de doute on laisse passer
            log.exception("interaction_check")
            return True
        if blocked:
            try:
                await interaction.response.send_message(
                    "🚫 Je n'ai pas le droit de parler dans ce salon. Essaie ailleurs, petit chat 😏", ephemeral=True
                )
            except discord.HTTPException:
                pass
            return False
        return True


class MikaBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents, allowed_mentions=NO_PINGS)
        self.tree = MikaTree(self)
        self.db: aiosqlite.Connection

    async def setup_hook(self):
        self.db = await aiosqlite.connect(DB_PATH)
        await self.db.executescript(SCHEMA)
        await self.db.commit()
        # boutons persistants (rôles, sondages, tickets) : actifs même après un redémarrage
        self.add_dynamic_items(
            RoleButton, PollVote, PollEnd, TicketOpen, TicketClose, TicketClaim, GiveawayJoin, RulesButton
        )
        if not voice_timer_loop.is_running():
            voice_timer_loop.start()
        if not poll_loop.is_running():
            poll_loop.start()
        if not giveaway_loop.is_running():
            giveaway_loop.start()
        if not rules_loop.is_running():
            rules_loop.start()
        # Sync des commandes seulement si elles ont changé (ou SYNC_ON_START=1, ou /sync)
        sig = commands_signature()
        rows = await db_all("SELECT value FROM settings WHERE guild_id=0 AND key='cmd_sig'")
        if os.getenv("SYNC_ON_START") == "1" or not rows or rows[0][0] != sig:
            await self.tree.sync()
            await db_run(
                "INSERT INTO settings(guild_id, key, value) VALUES (0,'cmd_sig',?) "
                "ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value",
                (sig,),
            )
            log.info("Commandes synchronisées")

    async def close(self):
        if voice_timer_loop.is_running():
            voice_timer_loop.cancel()
        if poll_loop.is_running():
            poll_loop.cancel()
        if giveaway_loop.is_running():
            giveaway_loop.cancel()
        if rules_loop.is_running():
            rules_loop.cancel()
        if hasattr(self, "db"):
            await self.db.close()
        await super().close()


bot = MikaBot()
ai = AsyncOpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL, timeout=30, max_retries=2)

last_chat: dict[int, float] = defaultdict(float)    # anti-spam par utilisateur
last_react: dict[int, float] = defaultdict(float)   # cooldown réactions par salon
last_spont: dict[int, float] = defaultdict(float)   # cooldown rebonds spontanés par salon
last_weather: dict[int, float] = defaultdict(float)  # anti-spam météo par utilisateur
last_greet: dict[int, float] = defaultdict(float)   # cooldown salutations par salon
_settings: dict[tuple[int, str], str] = {}          # cache des réglages

_bg: set = set()


def spawn(coro):
    """Lance une tâche de fond en gardant une référence (sinon elle peut être ramassée par le GC)."""
    t = asyncio.create_task(coro)
    _bg.add(t)
    t.add_done_callback(_bg.discard)


def commands_signature() -> str:
    """Empreinte des commandes : on ne re-synchronise que si elle change."""
    parts = []
    for c in bot.tree.walk_commands():
        params = ",".join(f"{p.name}:{p.description}" for p in getattr(c, "parameters", []))
        parts.append(f"{c.qualified_name}|{c.description}|{params}")
    return hashlib.md5("\n".join(sorted(parts)).encode()).hexdigest()


# =====================================================================
# BASE DE DONNÉES
# =====================================================================
async def db_run(sql: str, params: tuple = ()):
    await bot.db.execute(sql, params)
    await bot.db.commit()


async def db_all(sql: str, params: tuple = ()):
    async with bot.db.execute(sql, params) as cur:
        return await cur.fetchall()


async def get_setting(guild_id: Optional[int], key: str, default: str) -> str:
    k = (guild_id or 0, key)
    if k not in _settings:
        rows = await db_all("SELECT value FROM settings WHERE guild_id=? AND key=?", k)
        _settings[k] = rows[0][0] if rows else default
    return _settings[k]


async def set_setting(guild_id: Optional[int], key: str, value: str):
    k = (guild_id or 0, key)
    await db_run(
        "INSERT INTO settings(guild_id, key, value) VALUES (?,?,?) "
        "ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value",
        (k[0], k[1], value),
    )
    _settings[k] = value


async def get_flag(guild_id: Optional[int], key: str, default: bool) -> bool:
    return (await get_setting(guild_id, key, "1" if default else "0")) == "1"


async def set_flag(guild_id: Optional[int], key: str, value: bool):
    await set_setting(guild_id, key, "1" if value else "0")


async def get_style(guild_id: Optional[int]) -> str:
    s = await get_setting(guild_id, "style", DEFAULT_STYLE)
    return s if s in STYLES else DEFAULT_STYLE


async def add_history(channel_id: int, role: str, content: str):
    await bot.db.execute("INSERT INTO history(channel_id, role, content) VALUES (?,?,?)", (channel_id, role, content))
    await bot.db.execute(
        "DELETE FROM history WHERE channel_id=? AND id NOT IN "
        "(SELECT id FROM history WHERE channel_id=? ORDER BY id DESC LIMIT 40)",
        (channel_id, channel_id),
    )
    await bot.db.commit()


async def get_history(channel_id: int) -> list[dict]:
    rows = await db_all(
        "SELECT role, content FROM (SELECT id, role, content FROM history WHERE channel_id=? "
        "ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
        (channel_id, HISTORY_SIZE),
    )
    return [{"role": r, "content": c} for r, c in rows]


# ---------- Stats des jeux ----------
GAMES = {
    "blackjack": "🃏 Blackjack",
    "poker": "♠️ Poker",
    "pfc": "✂️ Pierre-feuille-ciseaux",
    "quiz": "🧠 Quiz",
    "kahoot": "🎯 Kahoot",
}
POINTS = {"win": 10, "draw": 3, "loss": 1}  # victoire / égalité / participation
_UPSERT = (
    "INSERT INTO game_stats(guild_id,user_id,game,wins,draws,losses,points) VALUES (?,?,?,?,?,?,?) "
    "ON CONFLICT(guild_id,user_id,game) DO UPDATE SET wins=wins+excluded.wins, draws=draws+excluded.draws, "
    "losses=losses+excluded.losses, points=points+excluded.points"
)


async def record_many(guild_id: Optional[int], game: str, outcomes: dict):
    """outcomes : {user_id: 'win' | 'draw' | 'loss'}. Ignore les DM et les bots (id <= 0)."""
    if not guild_id or game not in GAMES:
        return
    rows = [
        (guild_id, uid, game, int(r == "win"), int(r == "draw"), int(r == "loss"), POINTS[r])
        for uid, r in outcomes.items() if uid > 0 and r in POINTS
    ]
    if not rows:
        return
    try:
        await bot.db.executemany(_UPSERT, rows)
        await bot.db.commit()
    except Exception:  # noqa: BLE001
        log.exception("Enregistrement des stats échoué")


async def leaderboard(guild_id: int, game: Optional[str] = None) -> list:
    sql = "SELECT user_id, SUM(wins), SUM(draws), SUM(losses), SUM(points) FROM game_stats WHERE guild_id=?"
    params: tuple = (guild_id,)
    if game:
        sql += " AND game=?"
        params += (game,)
    sql += " GROUP BY user_id ORDER BY SUM(points) DESC, SUM(wins) DESC, user_id ASC"
    return await db_all(sql, params)


# =====================================================================
# UTILITAIRES IA / TEXTE
# =====================================================================
async def ask_ai(
    messages: list[dict],
    *,
    system: str = PERSONA,
    json_mode: bool = False,
    max_tokens: int = 1200,
    temperature: float = 0.9,
) -> str:
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if "gpt-oss" in AI_MODEL:  # ce paramètre n'existe pas chez tous les modèles / fournisseurs
        kwargs["extra_body"] = {"reasoning_effort": "low"}
    resp = await ai.chat.completions.create(
        model=AI_MODEL,
        messages=[{"role": "system", "content": system}, *messages],
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return (resp.choices[0].message.content or "").strip()


def extract_json(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


async def ask_json(prompt: str, tries: int = 2, system: str = PERSONA, max_tokens: int = 1200) -> dict:
    """Demande du JSON à l'IA, avec un nouvel essai si le JSON est cassé."""
    last: Optional[Exception] = None
    for _ in range(tries):
        try:
            raw = await ask_ai(
                [{"role": "user", "content": prompt}], system=system, json_mode=True,
                temperature=0.8, max_tokens=max_tokens,
            )
            return extract_json(raw)
        except ValueError as e:
            last = e
            log.warning("JSON invalide, nouvel essai : %s", e)
    raise ValueError("JSON invalide après plusieurs essais") from last


def split_text(text: str, limit: int = 1900) -> list[str]:
    """Découpe sur les sauts de ligne (puis les espaces) plutôt qu'au milieu d'un mot."""
    chunks, current = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            cut = line.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:cut])
            line = line[cut:].lstrip()
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks or [""]


def plain(s: str) -> str:
    """Minuscules, sans accents ni ponctuation, mots séparés par un espace."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\W+", " ", s).strip()


def fail_msg(e: Exception) -> str:
    log.error("Erreur IA : %r", e)
    if isinstance(e, openai.RateLimitError):
        return "😮‍💨 J'ai trop parlé, laisse-moi souffler une minute."
    return "😅 J'ai buggé, réessaie !"


# ---------- Recherche web ----------
WEB_HINTS = re.compile(
    r"\b(actu\w*|derni[eè]re?s?|nouve\w+|sorti\w*|tourn[ée]e|concerts?|billets?|classement|"
    r"aujourd'hui|ce soir|cette semaine|en ce moment|202\d|prix|résultats?|scores?)\b",
    re.I,
)


def web_search(query: str, n: int = 5) -> list[dict]:
    with DDGS() as ddgs:
        return list(ddgs.text(query, region="fr-fr", max_results=n))


async def web_context(query: str) -> str:
    try:
        results = await asyncio.wait_for(asyncio.to_thread(web_search, query[:200]), timeout=10)
    except Exception as e:  # noqa: BLE001
        log.warning("Recherche web échouée : %s", e)
        return ""
    if not results:
        return ""
    lines = [f"- {r.get('title', '')}: {r.get('body', '')[:200]}" for r in results]
    return (
        "Infos trouvées sur le web (peuvent être incomplètes ; résume en 1-2 phrases, ne recopie pas) :\n"
        + "\n".join(lines)
    )


# ---------- Mode protectrice : douceur automatique quand quelqu'un semble aller mal ----------
DOWN_HINTS = re.compile(
    r"(j'en peux plus|je n'en peux plus|je me sens (mal|seul\w*|nul\w*|vide)|ça va pas|ca va pas|"
    r"je vais pas bien|je ne vais pas bien|je déprime|déprim\w+|dépressi\w+|envie de pleurer|je pleure|"
    r"je suis (triste|mal|épuisé\w*|anxieu\w+|angoissé\w*|au bout)|angoisse\w*|crise d'angoisse|"
    r"harcel\w+|personne (ne )?(m'aime|me parle)|je suis seul\w*|mal dans ma peau|journée de merde|"
    r"j'suis mal|jsuis mal|j'ai plus la force)",
    re.I,
)
CRISIS_HINTS = re.compile(
    r"(me suicider|je veux mourir|envie de mourir|en finir avec (la vie|tout)|plus envie de vivre|"
    r"me faire du mal|me tuer|je veux disparaître)",
    re.I,
)
PROTECT_MODE = (
    "\n\nMODE PROTECTRICE (prioritaire sur tout le reste) : cette personne semble aller mal. Plus de vannes, plus de "
    "flirt, plus de sous-entendus, plus de domination : tu es douce, chaleureuse et rassurante, comme une grande "
    "sœur qui s'inquiète. 2 à 4 phrases. Tu reconnais ce qu'elle ressent sans dramatiser, tu l'invites à en dire "
    "plus si elle veut, et tu proposes une petite chose simple (respirer, boire de l'eau, en parler à un proche). "
    "Pas de diagnostic, pas de leçon de morale, pas de liste, au plus un emoji doux (💜). Si en fait c'est "
    "clairement de la déconne ou un simple râlage sur un jeu, reste légère mais plus douce que d'habitude."
)
CRISIS_MODE = (
    "\nLa personne parle peut-être de se faire du mal ou de mourir : reste calme et présente, prends-la au sérieux, "
    "ne minimise pas, ne juge pas, et encourage-la à parler MAINTENANT à quelqu'un de confiance ou à un service "
    "d'écoute. Ne pose pas de questions qui l'enfoncent."
)
CRISIS_NOTE = (
    "\n\n💜 Si tu penses à te faire du mal, tu n'es pas seul(e) : en France, le 3114 est gratuit et joignable "
    "24h/24. Si tu es en danger immédiat, appelle le 112. Ailleurs, contacte le numéro d'urgence ou d'écoute de ton pays."
)


def seems_crisis(text: str) -> bool:
    return bool(CRISIS_HINTS.search(text.replace("’", "'")))


def seems_down(text: str) -> bool:
    t = text.replace("’", "'")
    return bool(CRISIS_HINTS.search(t) or DOWN_HINTS.search(t))


# ---------- Génération de réponse de chat ----------
async def generate_reply(
    channel_id: int,
    author_name: str,
    user_id: int,
    text: str,
    *,
    guild_id: Optional[int] = None,
    detail: bool = False,
    web: bool = False,
    nsfw: bool = False,
) -> str:
    style = await get_style(guild_id)
    system = persona(nsfw, style)
    down = seems_down(text)
    crisis = seems_crisis(text)
    if down:
        system += PROTECT_MODE
        if crisis:
            system += CRISIS_MODE
    if web or WEB_HINTS.search(text):
        ctx = await web_context(text)
        if ctx:
            system += "\n\n" + ctx
    if detail:
        system += (
            "\n\nLà, la personne veut une réponse détaillée : tu peux développer (max ~1500 caractères), "
            "mais reste claire, structurée et sans blabla."
        )
    user_msg = f"{author_name} : {text}"
    history = await get_history(channel_id)
    answer = await ask_ai([*history, {"role": "user", "content": user_msg}], system=system)
    answer = re.sub(rf"^{re.escape(BOT_NAME)}\s*:\s*", "", answer).strip()  # évite le préfixe "Nom :"
    if not answer:
        raise ValueError("réponse vide")
    # on n'enregistre qu'après un succès : pas de message orphelin dans l'historique
    await add_history(channel_id, "user", user_msg)
    await add_history(channel_id, "assistant", answer)
    if crisis:
        answer += CRISIS_NOTE
    return answer


NAME_RE = re.compile(rf"\b{re.escape(plain(BOT_NAME))}\b")


def name_called(text: str) -> bool:
    """True si le prénom du bot est écrit dans le message (« Mika tu en penses quoi ? »), sans mention."""
    return bool(NAME_TRIGGER and NAME_RE.search(plain(text)))


def clean_text(message: discord.Message) -> str:
    """Retire la mention du bot (et son prénom en début de phrase) et rend les autres mentions lisibles par l'IA."""
    text = re.sub(rf"<@!?{bot.user.id}>", "", message.content)
    text = re.sub(rf"(?i)^\s*{re.escape(BOT_NAME)}\b[\s,:;!?.\-]*", "", text)
    for m in message.mentions:
        text = text.replace(f"<@{m.id}>", f"@{m.display_name}").replace(f"<@!{m.id}>", f"@{m.display_name}")
    return text.strip()


def is_reply_to_bot(message: discord.Message) -> bool:
    ref = message.reference.resolved if message.reference else None
    return isinstance(ref, discord.Message) and ref.author.id == bot.user.id


# =====================================================================
# LOGS STAFF : sanctions + commandes du bot (salon défini avec /logs)
# =====================================================================
async def mod_log(guild: discord.Guild, embed: discord.Embed, cat: Optional[str] = None) -> bool:
    """Envoie un embed dans le salon de logs du serveur (False si pas de salon / type coupé / envoi impossible)."""
    if not await log_cat_enabled(guild.id, cat or guess_log_cat(embed)):
        return False
    try:
        cid = int(await get_setting(guild.id, "log_channel", "0") or 0)
    except ValueError:
        return False
    ch = guild.get_channel(cid) if cid else None
    if ch is None:
        return False
    try:
        await ch.send(embed=embed, allowed_mentions=NO_PINGS)
        return True
    except discord.HTTPException:
        return False


# Commandes qui écrivent déjà leur propre log détaillé (évite les doublons)
LOG_SKIP = {"envoyer", "punition deban", "purge", "annonce", "supprimersalon", "role creer", "role supprimer"}


def _opt_value(v) -> str:
    if isinstance(v, discord.Attachment):
        return v.filename
    if hasattr(v, "mention"):
        return v.mention
    return str(v)


def options_str(interaction: discord.Interaction) -> str:
    """Options saisies par l'utilisateur, lisibles (pour les logs)."""
    try:
        items = list(interaction.namespace)
    except Exception:  # noqa: BLE001
        return ""
    lines = []
    for k, v in items:
        txt = _opt_value(v).replace("\n", " ")
        lines.append(f"`{k}` : {txt[:150]}")
    return "\n".join(lines)[:900]


async def log_cmd(interaction: discord.Interaction, name: str, details: str = "", status: str = "✅ Exécutée"):
    """Log d'une commande du bot (slash, panel admin...) dans le salon de logs."""
    guild = interaction.guild
    if guild is None:
        return
    try:
        color = COLOR_PURPLE if status.startswith("✅") else COLOR_DARK
        e = discord.Embed(title="📋 Commande du bot", color=color)
        e.add_field(name="Commande", value=f"`/{name}`", inline=True)
        e.add_field(name="Membre", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
        ch = interaction.channel
        e.add_field(name="Salon", value=getattr(ch, "mention", None) or "—", inline=True)
        e.add_field(name="Statut", value=status, inline=True)
        if details:
            e.add_field(name="Détails", value=details[:1000], inline=False)
        e.timestamp = discord.utils.utcnow()
        await mod_log(guild, e)
    except Exception:  # noqa: BLE001 : un log raté ne doit jamais casser une commande
        log.exception("log_cmd a échoué")


# =====================================================================
# COOLDOWN + GESTION D'ERREURS DES COMMANDES
# =====================================================================
def ai_cd():
    """Cooldown : 1 utilisation / 8 s / utilisateur (protège ton quota d'API)."""
    return app_commands.checks.cooldown(1, 8.0, key=lambda i: i.user.id)


@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    status = None
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ Doucement mon chou, réessaie dans {error.retry_after:.0f}s."
    elif isinstance(error, app_commands.MissingPermissions):
        msg = "🚫 Tu n'as pas la permission pour ça."
        status = "🚫 Refusée (permissions manquantes)"
    else:
        log.error("Erreur de commande", exc_info=error)
        msg = "😅 Y'a eu un bug, réessaie."
        status = f"❌ Erreur ({type(error).__name__})"
    if status and interaction.command is not None:
        spawn(log_cmd(interaction, interaction.command.qualified_name, options_str(interaction), status))
    send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
    await send(msg, ephemeral=True)


@bot.event
async def on_app_command_completion(interaction: discord.Interaction, command):
    """Chaque commande slash terminée est tracée dans le salon de logs."""
    if interaction.guild is None:
        return
    name = command.qualified_name
    if name in LOG_SKIP:
        return
    spawn(log_cmd(interaction, name, options_str(interaction)))


# =====================================================================
# COMMANDES : IA
# =====================================================================
@bot.tree.command(name="ask", description="Pose-moi une question 💬")
@app_commands.describe(
    question="Ta question",
    detail="Réponse détaillée (sinon je reste courte)",
    web="Chercher sur le web avant de répondre",
)
@ai_cd()
async def ask(interaction: discord.Interaction, question: str, detail: bool = False, web: bool = False):
    await interaction.response.defer(thinking=True)
    try:
        answer = await generate_reply(
            interaction.channel_id, interaction.user.display_name, interaction.user.id, question,
            guild_id=interaction.guild_id, detail=detail, web=web, nsfw=is_nsfw(interaction.channel),
        )
    except Exception as e:  # noqa: BLE001
        return await interaction.followup.send(fail_msg(e))
    for c in split_text(answer):
        await interaction.followup.send(c, allowed_mentions=NO_PINGS)


@bot.tree.command(name="recherche", description="Cherche sur le web et donne des liens 🔎")
@app_commands.describe(requete="Ce que tu cherches")
@ai_cd()
async def recherche(interaction: discord.Interaction, requete: str):
    await interaction.response.defer(thinking=True)
    try:
        results = await asyncio.to_thread(web_search, requete)
    except Exception as e:  # noqa: BLE001
        log.warning("Recherche échouée : %s", e)
        return await interaction.followup.send("😅 La recherche a échoué, réessaie.")
    if not results:
        return await interaction.followup.send("Je n'ai rien trouvé 🤷")
    embed = emb(f"🔎 Résultats pour « {requete[:200]} »", color=COLOR_DARK)
    for r in results:
        embed.add_field(
            name=r["title"][:256], value=f"{r['body'][:200]}\n{r['href']}"[:1024], inline=False
        )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="roast", description="Je chambre quelqu'un 😈")
@app_commands.describe(membre="La victime", contexte="Un détail pour m'inspirer (optionnel)")
@ai_cd()
async def roast(interaction: discord.Interaction, membre: discord.Member, contexte: Optional[str] = None):
    await interaction.response.defer(thinking=True)
    prompt = (
        f"Fais une vanne courte (2 phrases max) sur {membre.display_name}, dans ton style de dominatrice taquine : "
        "absurde, très exagérée, un peu provocante. Pas de haine, rien de crédible ni de vrai : de la déconne entre potes."
    )
    if contexte:
        prompt += f" Détail pour t'inspirer : {contexte[:200]}"
    style = await get_style(interaction.guild_id)
    try:
        answer = await ask_ai(
            [{"role": "user", "content": prompt}],
            system=persona(is_nsfw(interaction.channel), style), max_tokens=600,
        )
    except Exception as e:  # noqa: BLE001
        return await interaction.followup.send(fail_msg(e))
    await interaction.followup.send(f"{membre.mention} {answer}"[:1900], allowed_mentions=USER_PINGS)


@bot.tree.command(name="blague", description="Une blague coquine (sous-entendus, jamais explicite) 😏")
@app_commands.describe(theme="Un thème ou une cible (optionnel)")
@ai_cd()
async def blague(interaction: discord.Interaction, theme: Optional[str] = None):
    await interaction.response.defer(thinking=True)
    prompt = (
        "Raconte UNE blague coquine, courte (2-3 phrases max), avec du double sens et des sous-entendus mais "
        "JAMAIS explicite, dans ton style de dominatrice taquine. Elle doit avoir une vraie chute."
    )
    if theme:
        prompt += f" Thème : {theme[:80]}."
    style = await get_style(interaction.guild_id)
    try:
        answer = await ask_ai(
            [{"role": "user", "content": prompt}],
            system=persona(is_nsfw(interaction.channel), style), max_tokens=700, temperature=1.0,
        )
    except Exception as e:  # noqa: BLE001
        return await interaction.followup.send(fail_msg(e))
    await interaction.followup.send(answer[:1900], allowed_mentions=NO_PINGS)


# ---------- /8ball et /choisir (sans IA : pas de quota consommé) ----------
BALL_YES = [
    "Oui, évidemment 😏", "Sans aucun doute, petit chat 🖤", "Carrément ✨", "Ça sent le oui 😈",
    "Obligé. Même moi j'en suis sûre 💋", "Les astres disent oui, et moi aussi 🔮",
]
BALL_MAYBE = [
    "Hmm… redemande-moi ça quand j'aurai de meilleures vibes 🔮",
    "Concentre-toi très fort et repose la question 😏",
    "Ça dépend de toi, mon chou 🎀",
    "Peut-être… je réfléchis, ne me presse pas 🖤",
]
BALL_NO = [
    "Non. Même pas en rêve 😈", "Aucune chance, mon chou 💀", "Mon instinct dit non 🖤",
    "Laisse tomber, c'est mort 😬", "Négatif. Retente ta chance dans une autre vie ✨",
]


@bot.tree.command(name="8ball", description="Pose-moi une question fermée, je tranche 🔮")
@app_commands.describe(question="Une question à laquelle on répond par oui ou non")
async def eightball(interaction: discord.Interaction, question: str):
    pool = random.choices([BALL_YES, BALL_MAYBE, BALL_NO], weights=[40, 20, 40])[0]
    embed = emb("🔮 8ball", f"**{question[:300]}**\n\n{random.choice(pool)}", COLOR_PURPLE)
    await interaction.response.send_message(embed=embed)


CHOICE_SPLIT = re.compile(r"\s*(?:,|;|\||/|\bou\b)\s*", re.I)
CHOICE_LINES = [
    "Mon choix est fait : **{x}**. Discute pas 😈",
    "**{x}**, évidemment. Fallait même pas demander 😏",
    "Mommy a décidé : **{x}** 🖤",
    "Les astres (et moi) disent **{x}** ✨",
    "**{x}**. Et que ça saute 💋",
]


@bot.tree.command(name="choisir", description="Je tranche à ta place entre plusieurs options 🎲")
@app_commands.describe(options="Tes options, séparées par une virgule ou « ou » (ex : pizza, tacos ou burger)")
async def choisir(interaction: discord.Interaction, options: str):
    items = [o.strip() for o in CHOICE_SPLIT.split(options) if o.strip()]
    items = list(dict.fromkeys(items))  # enlève les doublons en gardant l'ordre
    if len(items) < 2:
        return await interaction.response.send_message(
            "Donne-moi au moins 2 options, séparées par une virgule ou « ou » 😏", ephemeral=True
        )
    if len(items) > 20:
        return await interaction.response.send_message("20 options max, t'es indécis(e) à ce point ? 😅", ephemeral=True)
    pick = random.choice(items)
    line = random.choice(CHOICE_LINES).format(x=pick[:200])
    await interaction.response.send_message(
        embed=emb("🎲 Je choisis", f"{line}\n\n_Parmi : {', '.join(i[:40] for i in items)}_"[:4000], COLOR_PINK)
    )


# =====================================================================
# COMMANDES SOCIALES (/kiss, /hug, /pat, /slap, /bonk, /gift)
#   "lines" = salons normaux ; "spicy" = ajoutées dans les salons NSFW (jamais explicites)
# =====================================================================
ACTIONS = {
    "kiss": dict(
        desc="Fais un bisou à quelqu'un 💋", emoji="💋", positive=True, color=COLOR_PINK,
        lines=[
            "{a} vole un bisou à {b}… et {b} n'a même pas le temps de protester",
            "{a} attrape {b} par le col et l'embrasse. Autoritaire, j'adore 😈",
            "{a} laisse une trace de rouge à lèvres sur la joue de {b}",
            "Petit bisou sur le front de {b} par {a}… bon chat, reste sage 🖤",
            "{a} embrasse {b} sur la joue, puis s'enfuit en riant 💋",
            "{a} dépose un baiser sur la main de {b} comme un vrai gentleman/une vraie lady ✨",
            "{a} prend le visage de {b} entre ses mains et l'embrasse. {b} ne bouge plus 😳",
            "Smack ! {a} claque un gros bisou sonore sur le front de {b} 💋",
            "{a} envoie un baiser volant à {b}… qui rougit jusqu'aux oreilles 🎀",
            "{a} embrasse {b} par surprise, devant tout le monde. Quel culot 😏",
            "Un bisou de {a} pour {b} : à utiliser avec modération 🖤",
            "{a} fait un petit bisou sur le nez de {b}. Trop mignon, c'est écœurant 🥰",
        ],
        spicy=[
            "{a} plaque {b} contre le mur et l'embrasse longuement… on vous laisse un peu d'intimité 😈",
            "{a} mordille la lèvre de {b} avant de l'embrasser. Dangereux 🖤",
            "{a} embrasse {b} dans le cou, doucement, et {b} frissonne 😏",
            "Un baiser langoureux de {a}… {b} a oublié comment respirer 💋",
            "{a} attire {b} par le col pour un baiser qui promet beaucoup plus 😈",
        ],
    ),
    "hug": dict(
        desc="Fais un câlin à quelqu'un 🖤", emoji="🖤", positive=True, color=COLOR_PURPLE,
        lines=[
            "{a} serre {b} dans ses bras… impossible de s'échapper",
            "{a} enroule {b} dans un câlin bien trop long, et personne ne s'en plaint 😌",
            "Câlin forcé de {a} sur {b}. Pas de négociation 😈",
            "{a} attire {b} contre lui/elle et refuse de le/la lâcher",
            "{a} saute dans les bras de {b} sans prévenir 🖤",
            "{a} fait un gros câlin à {b} : « tu as une tête à en avoir besoin »",
            "{a} serre {b} fort et lui souffle « ça va aller » ✨",
            "Câlin collectif imposé : {a} embarque {b} dans ses bras, ce n'est pas négociable 😌",
            "{a} pose sa tête sur l'épaule de {b} et ne bouge plus 🎀",
            "{a} fait un câlin à {b}. Même les plus coriaces fondent 🖤",
            "{a} soulève {b} du sol dans un câlin d'ours 🐻",
            "{a} offre un câlin gratuit à {b}. Offre limitée, profites-en 😏",
        ],
        spicy=[
            "{a} serre {b} très fort, très près… trop près, peut-être 😏",
            "{a} enlace {b} par derrière et lui murmure quelque chose à l'oreille 🖤",
            "{a} garde {b} contre lui/elle bien plus longtemps que nécessaire 😈",
            "{a} plaque {b} contre son torse : « tu restes là, c'est un ordre »",
            "{a} se blottit tout contre {b}. La température monte 🔥",
            "{a} invite {b} à venir se blottir tout contre mommy 😏",
            "{a} souffle à {b} : « ne t'emballe pas trop vite… tu vas voir » 😌",
        ],
    ),
    "pat": dict(
        desc="Fais un headpat à quelqu'un 🎀", emoji="🎀", positive=True, color=COLOR_PINK,
        lines=[
            "{a} caresse la tête de {b} : « c'est bien, bon petit chat »",
            "{a} fait des headpats à {b}, qui se met à ronronner",
            "*pat pat* — {a} récompense {b} d'avoir été sage ✨",
            "{a} ébouriffe les cheveux de {b} : « bon petit chat »",
            "*pat pat pat* — {b} ferme les yeux et savoure 🎀",
            "{a} tapote la tête de {b} avec beaucoup trop de sérieux 😌",
            "{a} gratouille le menton de {b}, qui ronronne de bonheur",
            "Headpat officiel de {a} pour {b} : bonne conduite validée ✨",
            "{a} caresse doucement la tête de {b} : « tu t'en es bien sorti(e) »",
            "{b} reçoit un headpat de {a} et fait semblant de ne pas aimer ça 😏",
        ],
        spicy=[
            "{a} caresse les cheveux de {b} : « continue d'être sage et tu auras ta récompense » 😏",
            "*pat pat* — {a} murmure à {b} : « bon chat… on en reparle plus tard » 😈",
            "{a} passe la main dans la nuque de {b}, qui frissonne 🖤",
            "{a} tire doucement les cheveux de {b} : « regarde-moi quand je te parle » 😏",
            "{a} fait des headpats à {b} puis le/la fixe droit dans les yeux… 😈",
        ],
    ),
    "slap": dict(
        desc="Colle une gifle (pour rire) à quelqu'un ⛓️", emoji="⛓️", positive=False, color=COLOR_DARK,
        lines=[
            "{a} colle un coup de bilf à {b}. Ça t'apprendra à faire le malin 😈",
            "{a} sort la tong de la mort sur {b} 🩴",
            "*SLAP* — {b} l'avait cherché, {a} ne fait que son devoir",
            "{a} met une claque sur les fesses de {b}… et {b} a l'air d'avoir aimé, bizarre 👀",
            "{a} gifle {b} avec une baguette de pain. Française, évidemment 🥖",
            "{a} claque {b} avec un poisson mouillé 🐟",
            "*CLAC* — {a} remet {b} à sa place 😈",
            "{a} lève la main sur {b}… puis ajoute « la prochaine fois, c'est pire »",
            "{a} colle une tape derrière la tête de {b} : « réveille-toi »",
            "{a} donne une claque magistrale à {b}. Le serveur entier a entendu 👀",
            "{a} sort le gant de velours (et la main de fer) pour {b} 🧤",
        ],
        spicy=[
            "{a} colle une petite claque sur les fesses de {b}. « Ça, c'est pour la provoc » 😏",
            "{a} attrape le menton de {b} : « tu recommences et ce sera pire… ou mieux » 😈",
            "{a} sort la cravache : {b} déglutit 👀",
            "{a} claque doucement la cuisse de {b} : « au pied » 😈",
            "{a} gifle {b} du bout des doigts, un sourire en coin 😏",
        ],
    ),
    "bonk": dict(
        desc="Bonk ! Au coin et réfléchis 🔨", emoji="🔨", positive=False, color=COLOR_DARK,
        lines=[
            "{a} bonk {b}. Au coin, et réfléchis à ce que t'as fait.",
            "BONK ! {b} part direct en prison des relous 🚔",
            "{a} sort le gros marteau : {b} a fait une bêtise",
            "{a} envoie {b} réfléchir au coin : ça va t'apprendre 🔨",
            "{a} bonk {b} avec une batte en mousse. Direction le coin 🔨",
            "{a} bonk {b} sur la tête : « horny jail, tout de suite »",
            "{a} sort le marteau géant : {b} n'a rien vu venir 💥",
            "{b} a fait une bêtise, {a} distribue un bonk bien mérité",
            "*BONK* — {a} fait tinter la tête de {b}. Ça résonne 🔔",
            "{a} bonk {b} avec un oreiller. Ça fait plus de bruit que de mal 🛏️",
        ],
        spicy=[
            "{a} met {b} au coin, mains dans le dos, et le/la surveille de près 😈",
            "{a} sort les menottes : {b} a été très, très vilain(e) ⛓️",
            "BONK ! Puis {a} attrape {b} par le col : « tu t'excuses, maintenant » 😏",
            "{a} met {b} à genoux : « réfléchis à ce que tu as fait » 😈",
            "{a} bonk {b} puis lui chuchote « tu l'as bien cherché » 🖤",
        ],
    ),
    "gift": dict(
        desc="Offre un cadeau à quelqu'un 🎁", emoji="🎁", positive=True, color=COLOR_PINK,
        lines=[
            "{a} offre un bouquet de roses noires à {b} 🖤",
            "{a} tend un petit paquet cadeau à {b} : « ouvre-le, petit chat » 🎁",
            "{a} offre à {b} un abonnement « câlins illimités ». Valable à vie ✨",
            "{a} dépose une boîte de chocolats devant {b} et vérifie qu'il/elle les partage 🍫",
            "{a} offre à {b} un ticket « bon pour un bisou ». À utiliser sans modération 💋",
            "{a} offre une peluche de chat à {b}, avec un ruban rose 🎀",
            "{a} offre à {b} un jeton « bonne conduite ». À collectionner 🪙",
            "{a} glisse un cadeau emballé dans les mains de {b} : « c'est pour te remercier d'exister »",
            "{a} offre à {b} une couronne en plastique : « t'es le roi / la reine du serveur » 👑",
        ],
        spicy=[
            "{a} offre à {b} un collier de chat avec une clochette… et vérifie qu'il/elle le porte bien 😈",
            "{a} tend une boîte noire à {b} : « tu l'ouvriras en privé » 😏",
            "{a} offre à {b} un ruban de satin rouge. À toi de deviner l'usage 😈",
            "{a} offre à {b} un coupon « une faveur de mommy ». Valable ce soir seulement 🖤",
        ],
    ),
}


def make_action(name: str, cfg: dict):
    @app_commands.describe(membre="La personne visée")
    async def cb(interaction: discord.Interaction, membre: discord.Member):
        a, b = interaction.user.mention, membre.mention
        nsfw = is_nsfw(interaction.channel)
        phrase = None
        if membre.id == bot.user.id:
            if cfg["positive"]:
                phrase = mommy_phrase(nsfw)  # câlin/bisou/pat sur le bot → il répond avec une phrase
                line = f"{a} vient chercher un peu d'attention auprès de {BOT_NAME}… 😏"
            else:
                line = f"{a} ose lever la main sur {BOT_NAME} ? 😈 Tu vas le regretter, petit chat."
        elif membre.id == interaction.user.id:
            line = (
                f"{a} se fait ça tout seul… viens là, {BOT_NAME} s'occupe de toi 🖤"
                if cfg["positive"]
                else f"{a} s'inflige ça tout seul… masochiste va 👀"
            )
        else:
            pool = cfg["lines"] + (cfg.get("spicy", []) if nsfw else [])
            line = random.choice(pool).format(a=a, b=b)

        desc = f"{cfg['emoji']} {line}"
        if phrase:
            desc += f"\n\n**{BOT_NAME}** : « {phrase} »"
        embed = emb(description=desc, color=cfg["color"])
        await interaction.response.send_message(
            content=None if membre.bot else b, embed=embed, allowed_mentions=USER_PINGS
        )

    bot.tree.add_command(app_commands.Command(name=name, description=cfg["desc"], callback=cb))


for _name, _cfg in ACTIONS.items():
    make_action(_name, _cfg)


# =====================================================================
# MARIAGE (/marie, /mariage, /divorce) — jusqu'à 3 personnes par mariage
# =====================================================================
MAX_SPOUSES = 3


def join_names(ids: list[int]) -> str:
    ms = [f"<@{i}>" for i in ids]
    return ms[0] if len(ms) == 1 else ", ".join(ms[:-1]) + " et " + ms[-1]


async def get_marriage(guild_id: int, user_id: int) -> Optional[tuple[int, list[int], int]]:
    """Renvoie (id du mariage, membres, date) ou None si la personne n'est pas mariée sur ce serveur."""
    rows = await db_all(
        "SELECT marriage_id FROM marriage_members WHERE guild_id=? AND user_id=?", (guild_id, user_id)
    )
    if not rows:
        return None
    mid = rows[0][0]
    members = [
        r[0] for r in await db_all("SELECT user_id FROM marriage_members WHERE marriage_id=? ORDER BY rowid", (mid,))
    ]
    srows = await db_all("SELECT since FROM marriages WHERE id=?", (mid,))
    return mid, members, (srows[0][0] if srows else int(time.time()))


async def create_marriage(guild_id: int, members: list[int]) -> int:
    cur = await bot.db.execute("INSERT INTO marriages(guild_id, since) VALUES (?,?)", (guild_id, int(time.time())))
    mid = cur.lastrowid
    await bot.db.executemany(
        "INSERT INTO marriage_members(guild_id, user_id, marriage_id) VALUES (?,?,?)",
        [(guild_id, u, mid) for u in members],
    )
    await bot.db.commit()
    return mid


async def add_to_marriage(guild_id: int, mid: int, users: list[int]):
    await bot.db.executemany(
        "INSERT INTO marriage_members(guild_id, user_id, marriage_id) VALUES (?,?,?)",
        [(guild_id, u, mid) for u in users],
    )
    await bot.db.commit()


async def leave_marriage(guild_id: int, user_id: int) -> Optional[list[int]]:
    """None = pas marié(e) ; [] = mariage dissous ; sinon la liste de ceux qui restent mariés."""
    cur = await get_marriage(guild_id, user_id)
    if not cur:
        return None
    mid, members, _ = cur
    await bot.db.execute("DELETE FROM marriage_members WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    rest = [m for m in members if m != user_id]
    if len(rest) < 2:  # un mariage tout seul n'existe pas
        await bot.db.execute("DELETE FROM marriage_members WHERE marriage_id=?", (mid,))
        await bot.db.execute("DELETE FROM marriages WHERE id=?", (mid,))
        rest = []
    await bot.db.commit()
    return rest


class MarryView(discord.ui.View):
    """Demande en mariage : tous les concernés doivent accepter (les invités + les conjoints déjà en place)."""

    def __init__(self, proposer_id: int, newcomers: list[int], mid: Optional[int], current: list[int], voters: list[int]):
        super().__init__(timeout=180)
        self.proposer_id, self.newcomers, self.mid = proposer_id, newcomers, mid
        self.current = current  # conjoints actuels (ou juste le demandeur s'il est célibataire)
        self.voters = voters
        self.accepted: set[int] = set()
        self.closed = False
        self.message: Optional[discord.Message] = None

    @property
    def final(self) -> list[int]:
        return self.current + self.newcomers

    def build_embed(self) -> discord.Embed:
        if self.mid:
            head = (
                f"<@{self.proposer_id}> propose d'accueillir {join_names(self.newcomers)} "
                f"dans son mariage ({join_names(self.current)})."
            )
        else:
            head = f"<@{self.proposer_id}> demande {join_names(self.newcomers)} en mariage."
        if len(self.final) == MAX_SPOUSES:
            head += "\n✨ Un mariage à trois, rien que ça."
        status = "\n".join(f"{'✅' if v in self.accepted else '⏳'} <@{v}>" for v in self.voters)
        e = emb("💍 Demande en mariage", f"{head}\n\n{status}", COLOR_PINK)
        e.set_footer(text=f"Tout le monde doit accepter • 3 minutes • {BOT_NAME} 🖤")
        return e

    def _close(self):
        self.closed = True
        for item in self.children:
            item.disabled = True
        self.stop()

    async def _validate_and_apply(self, guild_id: int) -> Optional[str]:
        """Revérifie tout au moment de valider (les choses ont pu changer). Renvoie une erreur ou None."""
        if self.mid is None:
            for uid in self.final:
                if await get_marriage(guild_id, uid):
                    return f"<@{uid}> s'est marié(e) entre-temps."
            await create_marriage(guild_id, self.final)
            return None
        cur = await get_marriage(guild_id, self.proposer_id)
        if not cur or cur[0] != self.mid:
            return "Le mariage de départ n'existe plus."
        if len(cur[1]) + len(self.newcomers) > MAX_SPOUSES:
            return "Il n'y a plus assez de place dans ce mariage."
        for uid in self.newcomers:
            if await get_marriage(guild_id, uid):
                return f"<@{uid}> s'est marié(e) entre-temps."
        await add_to_marriage(guild_id, self.mid, self.newcomers)
        return None

    @discord.ui.button(label="Accepter", emoji="💍", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in self.voters:
            return await interaction.response.send_message("Cette demande ne te concerne pas 😏", ephemeral=True)
        if uid in self.accepted:
            return await interaction.response.send_message("T'as déjà dit oui, patience 😌", ephemeral=True)
        self.accepted.add(uid)
        if not self.accepted >= set(self.voters):
            return await interaction.response.edit_message(embed=self.build_embed(), view=self)

        error = await self._validate_and_apply(interaction.guild_id)
        self._close()
        if error:
            e = emb("💔 Mariage annulé", error, COLOR_DARK)
        else:
            extra = (
                "Un mariage à trois, validé. Plus on est de fous… 😏"
                if len(self.final) == MAX_SPOUSES
                else f"{BOT_NAME} vous bénit 🖤"
            )
            e = emb("💍 Félicitations !", f"{join_names(self.final)} sont maintenant mariés !\n{extra}", COLOR_PINK)
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="Refuser", emoji="💔", style=discord.ButtonStyle.danger)
    async def refuse(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in self.voters and uid != self.proposer_id:
            return await interaction.response.send_message("Cette demande ne te concerne pas 😏", ephemeral=True)
        self._close()
        txt = "Demande annulée." if uid == self.proposer_id else f"<@{uid}> a dit non. Aïe 💔"
        await interaction.response.edit_message(embed=emb("💔 Mariage annulé", txt, COLOR_DARK), view=self)

    async def on_timeout(self):
        if self.closed or not self.message:
            return
        self._close()
        try:
            await self.message.edit(embed=emb("⌛ Demande expirée", "Personne n'a répondu à temps.", COLOR_DARK), view=self)
        except discord.HTTPException:
            pass


@bot.tree.command(name="marie", description="Demande quelqu'un en mariage 💍 (jusqu'à 3 dans un mariage)")
@app_commands.describe(
    membre="La personne à épouser",
    membre2="Une 2e personne pour un mariage à trois (optionnel)",
)
@app_commands.guild_only()
async def marie(interaction: discord.Interaction, membre: discord.Member, membre2: Optional[discord.Member] = None):
    user, gid = interaction.user, interaction.guild_id
    targets = list(dict.fromkeys(m for m in (membre, membre2) if m is not None))

    if any(t.id == bot.user.id for t in targets):
        return await interaction.response.send_message(
            f"{user.mention} veut m'épouser ? 😏 Mignon… mais moi je ne me marie pas, je collectionne.",
            allowed_mentions=NO_PINGS,
        )
    if any(t.bot for t in targets):
        return await interaction.response.send_message("Les bots ne se marient pas 🤖", ephemeral=True)
    if any(t.id == user.id for t in targets):
        return await interaction.response.send_message("Tu ne peux pas t'épouser toi-même… enfin, pas ici 😏", ephemeral=True)

    cur = await get_marriage(gid, user.id)
    if cur:
        mid, current, _ = cur
        places = MAX_SPOUSES - len(current)
        if places <= 0:
            return await interaction.response.send_message(
                f"Ton mariage est déjà complet ({MAX_SPOUSES} personnes max) 😅", ephemeral=True
            )
        if len(targets) > places:
            return await interaction.response.send_message(
                f"Il ne reste que {places} place(s) dans ton mariage 😏", ephemeral=True
            )
        voters = [t.id for t in targets] + [c for c in current if c != user.id]
    else:
        mid, current = None, [user.id]
        voters = [t.id for t in targets]

    for t in targets:
        if await get_marriage(gid, t.id):
            return await interaction.response.send_message(
                f"{t.display_name} est déjà marié(e) 💔 (il/elle peut faire `/divorce` d'abord).", ephemeral=True
            )

    view = MarryView(user.id, [t.id for t in targets], mid, current, voters)
    await interaction.response.send_message(
        content=" ".join(f"<@{v}>" for v in voters), embed=view.build_embed(), view=view, allowed_mentions=USER_PINGS
    )
    view.message = await interaction.original_response()


@bot.tree.command(name="mariage", description="Affiche le mariage de quelqu'un 💍")
@app_commands.describe(membre="Voir le mariage d'un autre (optionnel)")
@app_commands.guild_only()
async def mariage(interaction: discord.Interaction, membre: Optional[discord.Member] = None):
    cible = membre or interaction.user
    cur = await get_marriage(interaction.guild_id, cible.id)
    if not cur:
        txt = (
            "Tu es célibataire. Essaie `/marie` 😏" if cible.id == interaction.user.id
            else f"{cible.display_name} est célibataire 👀"
        )
        return await interaction.response.send_message(txt, ephemeral=True)
    _, members, since = cur
    kind = "Mariage à trois ✨" if len(members) == MAX_SPOUSES else "Mariage 💍"
    await interaction.response.send_message(
        embed=emb(kind, f"{join_names(members)}\n\nMariés depuis le <t:{since}:D>", COLOR_PINK),
        allowed_mentions=NO_PINGS,
    )


@bot.tree.command(name="divorce", description="Quitte ton mariage 💔")
@app_commands.describe(confirmer="Mets True pour confirmer")
@app_commands.guild_only()
async def divorce(interaction: discord.Interaction, confirmer: bool = False):
    if not confirmer:
        return await interaction.response.send_message("Mets `confirmer:True` si t'es sûr(e) 💔", ephemeral=True)
    rest = await leave_marriage(interaction.guild_id, interaction.user.id)
    if rest is None:
        return await interaction.response.send_message("Tu n'es pas marié(e) 😏", ephemeral=True)
    if rest:
        txt = f"💔 {interaction.user.mention} quitte le mariage. {join_names(rest)} restent mariés."
    else:
        txt = f"💔 {interaction.user.mention} divorce. Le mariage est dissous."
    await interaction.response.send_message(txt, allowed_mentions=NO_PINGS)


# =====================================================================
# MINI-JEUX
# =====================================================================
PFC = {"pierre": "🪨", "feuille": "📄", "ciseaux": "✂️"}
BEATS = {"pierre": "ciseaux", "feuille": "pierre", "ciseaux": "feuille"}
CARD_BACK = "🎴"  # dos de carte (U+1F0A0 n'est pas un emoji valide pour Discord)


@bot.tree.command(name="pfc", description="Pierre-feuille-ciseaux contre moi ✂️")
@app_commands.choices(
    choix=[app_commands.Choice(name=f"{e} {n.capitalize()}", value=n) for n, e in PFC.items()]
)
async def pfc(interaction: discord.Interaction, choix: app_commands.Choice[str]):
    mine, theirs = choix.value, random.choice(list(PFC))
    if mine == theirs:
        res, outcome = "Égalité… on se regarde dans les yeux 😏", "draw"
    elif BEATS[mine] == theirs:
        res, outcome = "Tu gagnes… j'ai laissé faire, t'es mignon", "win"
    else:
        res, outcome = f"Perdu ! {BOT_NAME} gagne. Sois bon perdant 😈", "loss"
    await interaction.response.send_message(f"{PFC[mine]} vs {PFC[theirs]} — {res}")
    spawn(record_many(interaction.guild_id, "pfc", {interaction.user.id: outcome}))


@bot.tree.command(name="ship", description="Compatibilité entre deux personnes 💘")
@app_commands.describe(a="Première personne", b="Deuxième personne")
async def ship(interaction: discord.Interaction, a: discord.Member, b: discord.Member):
    ids = sorted([a.id, b.id])
    pct = int(hashlib.md5(f"{ids[0]}-{ids[1]}".encode()).hexdigest(), 16) % 101
    filled = pct // 10
    verdict = (
        "Zéro alchimie. Même moi je peux rien y faire 💀" if pct < 20
        else "Bof… restez potes, c'est mieux pour tout le monde 😬" if pct < 40
        else "Y'a du potentiel… je garde un œil sur vous 👀" if pct < 60
        else "Ça sent la tension qui monte 😏" if pct < 80
        else "Vous êtes foutus. Je vous donne ma bénédiction 😈"
    )
    await interaction.response.send_message(
        embed=emb(
            "💘 Ship",
            f"**{a.display_name}** × **{b.display_name}**\n`{'█' * filled}{'░' * (10 - filled)}` **{pct}%**\n{verdict}",
            COLOR_PINK,
        )
    )


# ---------- Quiz ----------
QUIZ_THEMES = [
    "culture générale", "cinéma", "séries TV", "jeux vidéo", "animé & manga", "histoire", "science",
    "géographie", "musique", "internet & memes", "sport", "cuisine", "animaux", "mythologie",
]
QUIZ_SYSTEM = "Tu es un générateur de quiz de culture générale fiable. Tu réponds uniquement en JSON valide."


class QuizButton(discord.ui.Button):
    def __init__(self, label: str, correct: bool):
        super().__init__(label=(label.strip() or "—")[:80], style=discord.ButtonStyle.secondary)
        self.correct = correct

    async def callback(self, interaction: discord.Interaction):
        view: "QuizView" = self.view
        uid = interaction.user.id
        if view.done:
            return await interaction.response.send_message("Trop tard, quelqu'un a déjà gagné 😏", ephemeral=True)
        if uid == view.author_id:
            return await interaction.response.send_message("C'est ton propre quiz, laisse jouer les autres 😏", ephemeral=True)
        if uid in view.rates:
            return await interaction.response.send_message("T'as déjà tenté, laisse les autres jouer 😌", ephemeral=True)
        if not self.correct:
            view.rates.add(uid)
            if view.ranked:
                spawn(record_many(interaction.guild_id, "quiz", {uid: "loss"}))
            return await interaction.response.send_message("Raté 😏", ephemeral=True)
        view.done = True
        if view.ranked:
            spawn(record_many(interaction.guild_id, "quiz", {uid: "win"}))
        view.reveal()
        await interaction.response.edit_message(
            content=(
                f"{view.header}\n\n🏆 {interaction.user.mention} a trouvé : **{view.bonne}**. Bon chat 😏"
                f"\n_{view.anecdote}_"
            ),
            view=view,
        )
        view.stop()


class QuizView(discord.ui.View):
    def __init__(self, header: str, bonne: str, choix: list[str], anecdote: str, author_id: int = 0, ranked: bool = True):
        super().__init__(timeout=30)
        self.header, self.bonne, self.anecdote = header, bonne, anecdote
        self.author_id, self.ranked = author_id, ranked
        self.done = False
        self.rates: set[int] = set()
        self.message: Optional[discord.Message] = None
        for c in choix:
            self.add_item(QuizButton(c, c == bonne))

    def reveal(self):
        for item in self.children:
            item.disabled = True
            if isinstance(item, QuizButton) and item.correct:
                item.style = discord.ButtonStyle.success

    async def on_timeout(self):
        if self.done or not self.message:
            return
        self.reveal()
        try:
            await self.message.edit(
                content=f"{self.header}\n\n⌛ Personne ? Vous me décevez… c'était **{self.bonne}**.\n_{self.anecdote}_",
                view=self,
            )
        except discord.HTTPException:
            pass


@bot.tree.command(name="quiz", description="Un quiz rapide : le premier qui trouve gagne 🧠")
@app_commands.describe(theme="Le thème (au hasard si tu ne mets rien)")
@ai_cd()
async def quiz(interaction: discord.Interaction, theme: Optional[str] = None):
    await interaction.response.defer(thinking=True)
    theme = (theme or random.choice(QUIZ_THEMES)).strip()[:60]
    prompt = (
        f"Pose une question de culture sur le thème : {theme}. Niveau moyen, UNE seule bonne réponse, "
        'réponses courtes. JSON : {"question": "", "bonne_reponse": "", "mauvaises": ["", "", ""], '
        '"anecdote": "max 15 mots"}'
    )
    try:
        data = await ask_json(prompt, system=QUIZ_SYSTEM)
        bonne = str(data["bonne_reponse"])
        mauvaises = [str(x) for x in data["mauvaises"] if str(x) != bonne][:3]
        if len(mauvaises) < 3:
            raise ValueError("pas assez de mauvaises réponses")
        question = str(data["question"])
    except Exception as e:  # noqa: BLE001
        return await interaction.followup.send(fail_msg(e))
    choix = [bonne, *mauvaises]
    random.shuffle(choix)
    header = f"🧠 **Quiz — {theme}**\n{question}\n*(30 s, le premier qui trouve gagne)*"
    view = QuizView(header, bonne, choix, str(data.get("anecdote", "")))
    view.message = await interaction.followup.send(header, view=view, wait=True)


# =====================================================================
# BLACKJACK : solo contre Mika ou à la table (jusqu'à 5 joueurs, tour par tour)
# =====================================================================
BJ_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
BJ_SUITS = ["♠", "♥", "♦", "♣"]
BJ_MAX_PLAYERS = 5
BJ_TURN_TIMEOUT = 45

BJ_MIKA_WINS = [
    "Mommy rafle tout. Sois bon perdant 😈",
    "La maison gagne toujours, petit chat 🖤",
    "Aucune pitié à ma table 😏",
]
BJ_MIKA_LOSES = [
    "Hmpf… vous avez eu de la chance. Une revanche ? 😤",
    "Bon, je vous laisse celle-là… une seule 😏",
    "Impressionnant. Mommy est presque fière 🖤",
]
BJ_MIXED = [
    "Certains ont été sages, d'autres beaucoup moins 😈",
    "Des gagnants, des perdants… c'est ça, mon casino 🖤",
    "Pas mal du tout. Qui veut rejouer ? 😏",
]


def bj_deck() -> list[tuple[str, str]]:
    deck = [(r, s) for r in BJ_RANKS for s in BJ_SUITS] * 2  # 2 paquets
    random.shuffle(deck)
    return deck


def bj_value(hand: list[tuple[str, str]]) -> int:
    total, aces = 0, 0
    for r, _ in hand:
        if r == "A":
            total += 11
            aces += 1
        elif r in ("J", "Q", "K"):
            total += 10
        else:
            total += int(r)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def bj_cards(hand: list[tuple[str, str]], hide_second: bool = False) -> str:
    if hide_second:
        return f"`{hand[0][0]}{hand[0][1]}` {CARD_BACK}"
    return " ".join(f"`{r}{s}`" for r, s in hand)


class BJTable:
    """État d'une partie. status : play / stand / bust / bj."""

    def __init__(self, ids: list[int], names: dict[int, str], guild_id: Optional[int] = None, bet: int = 0):
        self.ids, self.names, self.guild_id, self.bet = ids, names, guild_id, bet
        self.deck = bj_deck()
        self.hands = {i: [self.deck.pop(), self.deck.pop()] for i in ids}
        self.dealer = [self.deck.pop(), self.deck.pop()]
        self.status = {i: ("bj" if bj_value(self.hands[i]) == 21 else "play") for i in ids}
        self.results: dict[int, str] = {}
        self.afk: set[int] = set()
        self.message: Optional[discord.Message] = None

    def current(self) -> Optional[int]:
        return next((i for i in self.ids if self.status[i] == "play"), None)

    def play_dealer(self):
        if any(s in ("stand", "bj") for s in self.status.values()):
            while bj_value(self.dealer) < 17:
                self.dealer.append(self.deck.pop())
        dv = bj_value(self.dealer)
        dealer_bj = len(self.dealer) == 2 and dv == 21
        payouts = {}
        for pid in self.ids:
            v, st = bj_value(self.hands[pid]), self.status[pid]
            if st == "bust":
                res = "💀 Perdu (sauté)"
            elif st == "bj":
                res = "🤝 Égalité (double blackjack)" if dealer_bj else "✨ Blackjack ! 🏆 Gagné"
            elif dealer_bj:
                res = "💀 Perdu (blackjack de Mika)"
            elif dv > 21:
                res = "🏆 Gagné (Mika saute)"
            elif v > dv:
                res = "🏆 Gagné"
            elif v == dv:
                res = "🤝 Égalité"
            else:
                res = "💀 Perdu"
            if st == "bj" and "🏆" in res:
                pay = self.bet * 5 // 2      # blackjack naturel : x2,5
            elif "🏆" in res:
                pay = self.bet * 2           # victoire : x2
            elif "🤝" in res:
                pay = self.bet               # égalité : mise rendue
            else:
                pay = 0
            payouts[pid] = pay
            if self.bet:
                res += f" • {pay - self.bet:+d} {COIN}"
            if pid in self.afk:
                res += " • 💤 AFK"
            self.results[pid] = res
        if self.guild_id:
            outcomes = {
                pid: ("win" if "🏆" in r else "draw" if "🤝" in r else "loss") for pid, r in self.results.items()
            }
            spawn(record_many(self.guild_id, "blackjack", outcomes))
            if self.bet:
                for pid, pay in payouts.items():
                    if pay:
                        spawn(eco_add(self.guild_id, pid, pay))

    def embed(self, final: bool = False) -> discord.Embed:
        cur = self.current()
        if final:
            wins = sum("🏆" in r for r in self.results.values())
            losses = sum("💀" in r for r in self.results.values())
            if losses == len(self.ids):
                desc = random.choice(BJ_MIKA_WINS)
            elif wins == len(self.ids):
                desc = random.choice(BJ_MIKA_LOSES)
            else:
                desc = random.choice(BJ_MIXED)
            color = COLOR_PINK
        else:
            desc = f"👉 C'est au tour de <@{cur}>" if cur else ""
            color = COLOR_PURPLE
        e = emb("🃏 Blackjack", desc, color)
        if self.bet:
            e.description = (e.description or "") + f"\n💰 Mise : **{self.bet}** {COIN} par joueur"
        dv = bj_value(self.dealer)
        if final:
            dline = f"{bj_cards(self.dealer)} → **{dv}**" + (" 💥" if dv > 21 else "")
        else:
            dline = bj_cards(self.dealer, hide_second=True)
        e.add_field(name=f"😈 {BOT_NAME} (croupier)", value=dline, inline=False)
        for pid in self.ids:
            h, v, st = self.hands[pid], bj_value(self.hands[pid]), self.status[pid]
            if final:
                tag = self.results[pid]
            elif pid == cur:
                tag = "👉 À toi de jouer"
            else:
                tag = {"bust": "💥 Sauté", "stand": "✋ Reste", "bj": "✨ Blackjack", "play": "⏳ Attend son tour"}[st]
            e.add_field(name=self.names[pid][:50], value=f"{bj_cards(h)} → **{v}**\n{tag}", inline=len(self.ids) > 1)
        if not final:
            e.set_footer(text=f"Mika tire jusqu'à 17 • {BJ_TURN_TIMEOUT}s par tour • {BOT_NAME} 🖤")
        return e

    async def start(self, interaction: discord.Interaction, from_lobby: bool = False):
        if self.current() is None:  # tout le monde a un blackjack naturel
            self.play_dealer()
            embed, view = self.embed(final=True), None
        else:
            embed, view = self.embed(), BJTurnView(self)
        if from_lobby:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            kw = {"view": view} if view else {}
            await interaction.response.send_message(embed=embed, **kw)
        self.message = await interaction.original_response()

    async def advance(self, interaction: Optional[discord.Interaction] = None):
        if self.current() is None:
            self.play_dealer()
            embed, view = self.embed(final=True), None
        else:
            embed, view = self.embed(), BJTurnView(self)
        if interaction:
            await interaction.response.edit_message(embed=embed, view=view)
        elif self.message:
            try:
                await self.message.edit(embed=embed, view=view)
            except discord.HTTPException:
                pass


class BJTurnView(discord.ui.View):
    def __init__(self, table: BJTable):
        super().__init__(timeout=BJ_TURN_TIMEOUT)
        self.table = table
        self.pid = table.current()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.pid:
            await interaction.response.send_message("Ce n'est pas ton tour, petit chat 😏", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Tirer", emoji="🃏", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        t = self.table
        t.hands[self.pid].append(t.deck.pop())
        v = bj_value(t.hands[self.pid])
        if v > 21:
            t.status[self.pid] = "bust"
        elif v == 21:
            t.status[self.pid] = "stand"
        self.stop()
        await t.advance(interaction)

    @discord.ui.button(label="Rester", emoji="✋", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.table.status[self.pid] = "stand"
        self.stop()
        await self.table.advance(interaction)

    async def on_timeout(self):
        self.table.status[self.pid] = "stand"
        self.table.afk.add(self.pid)
        await self.table.advance(None)


class BJLobby(discord.ui.View):
    def __init__(self, host: discord.abc.User, bet: int = 0):
        super().__init__(timeout=120)
        self.host_id = host.id
        self.bet = bet
        self.players: dict[int, str] = {host.id: host.display_name}
        self.started = False
        self.message: Optional[discord.Message] = None

    def embed(self) -> discord.Embed:
        lines = "\n".join(f"{'👑' if pid == self.host_id else '🎴'} <@{pid}>" for pid in self.players)
        e = emb(
            "🃏 Blackjack — table ouverte",
            f"Hôte : <@{self.host_id}>\nClique sur **Rejoindre** pour jouer contre {BOT_NAME} "
            f"(max {BJ_MAX_PLAYERS}).\n\n**Joueurs ({len(self.players)}/{BJ_MAX_PLAYERS})**\n{lines}",
            COLOR_PURPLE,
        )
        if self.bet:
            e.description += f"\n\n💰 **Mise : {self.bet}** {COIN} par joueur (prélevée au lancement)"
        e.set_footer(text=f"L'hôte lance la partie • 2 minutes • {BOT_NAME} 🖤")
        return e

    @discord.ui.button(label="Rejoindre", emoji="🎴", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid in self.players:
            return await interaction.response.send_message("T'es déjà à la table 😌", ephemeral=True)
        if len(self.players) >= BJ_MAX_PLAYERS:
            return await interaction.response.send_message("Table complète 😅", ephemeral=True)
        if self.bet and await eco_balance(interaction.guild_id, uid) < self.bet:
            return await interaction.response.send_message(f"💸 Il te faut {self.bet} {COIN} pour rejoindre.", ephemeral=True)
        self.players[uid] = interaction.user.display_name
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Quitter", emoji="🚪", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in self.players:
            return await interaction.response.send_message("Tu n'es pas à la table 😏", ephemeral=True)
        if uid == self.host_id:
            self.started = True
            self.stop()
            return await interaction.response.edit_message(
                embed=emb("🃏 Table fermée", "L'hôte est parti, la table est annulée.", COLOR_DARK), view=None
            )
        del self.players[uid]
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Lancer", emoji="▶️", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            return await interaction.response.send_message("Seul l'hôte peut lancer la partie 😏", ephemeral=True)
        self.started = True
        self.stop()
        players, refused = await collect_bets(interaction.guild_id, self.players, self.bet)
        if not players:
            return await interaction.response.edit_message(
                embed=emb("🃏 Table annulée", "Personne n'a assez de pièces pour la mise.", COLOR_DARK), view=None
            )
        table = BJTable(list(players), dict(players), interaction.guild_id, self.bet)
        await table.start(interaction, from_lobby=True)
        if refused:
            await interaction.followup.send(
                "💸 Pas assez de pièces, retirés de la table : " + ", ".join(f"<@{u}>" for u in refused),
                allowed_mentions=NO_PINGS,
            )

    async def on_timeout(self):
        if self.started or not self.message:
            return
        try:
            await self.message.edit(
                embed=emb("⌛ Table expirée", "Personne n'a lancé la partie à temps.", COLOR_DARK), view=None
            )
        except discord.HTTPException:
            pass


@bot.tree.command(name="blackjack", description="Blackjack contre moi, seul ou à plusieurs 🃏")
@app_commands.describe(
    mode="Solo contre Mika, ou une table ouverte aux autres",
    mise="Mise en pièces (0 = sans mise). Il faut activer l'économie avec /ecopanel",
)
@app_commands.choices(mode=[
    app_commands.Choice(name="🃏 Solo contre Mika", value="solo"),
    app_commands.Choice(name="👥 À la table (multi, jusqu'à 5)", value="table"),
])
@app_commands.guild_only()
async def blackjack(
    interaction: discord.Interaction, mode: app_commands.Choice[str],
    mise: app_commands.Range[int, 0, 1_000_000_000] = 0,
):
    user = interaction.user
    err = await bet_error(interaction.guild_id, user.id, mise)
    if err:
        return await interaction.response.send_message(err, ephemeral=True)
    if mode.value == "solo":
        if mise and not await eco_charge(interaction.guild_id, user.id, mise):
            return await interaction.response.send_message("💸 Pas assez de pièces.", ephemeral=True)
        table = BJTable([user.id], {user.id: user.display_name}, interaction.guild_id, mise)
        return await table.start(interaction)
    lobby = BJLobby(user, mise)
    await interaction.response.send_message(embed=lobby.embed(), view=lobby)
    lobby.message = await interaction.original_response()


# =====================================================================
# POKER — Texas Hold'em simplifié (mises optionnelles) : 1 à 6 joueurs contre Mika, qui joue aussi
#   Chaque tour (pré-flop, flop, turn, river) : « Suivre » ou « Se coucher ». Meilleure main à l'abattage.
# =====================================================================
PK_RANKS = "23456789TJQKA"
PK_SUITS = ["♠", "♥", "♦", "♣"]
PK_MAX_PLAYERS = 6
PK_TURN_TIMEOUT = 45
PK_STAGES = ["Pré-flop", "Flop", "Turn", "River"]
PK_BOARD_N = [0, 3, 4, 5]
PK_HANDS = ["Carte haute", "Paire", "Double paire", "Brelan", "Quinte", "Couleur", "Full", "Carré", "Quinte flush"]
MIKA_ID = 0


def pk_card(c: tuple) -> str:
    r = PK_RANKS[c[0] - 2]
    return f"`{'10' if r == 'T' else r}{c[1]}`"


def pk_cards(cs: list) -> str:
    return " ".join(pk_card(c) for c in cs)


def pk_score5(cards: list) -> tuple:
    """Score d'une main de 5 cartes : (catégorie, départages…). Plus grand = meilleur."""
    ranks = sorted((c[0] for c in cards), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    counts = Counter(ranks)
    groups = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    uniq = sorted(set(ranks), reverse=True)
    straight = None
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight = uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:  # la roue (A-2-3-4-5)
            straight = 5
    if straight and flush:
        return (8, straight)
    if groups[0][1] == 4:
        return (7, groups[0][0], groups[1][0])
    if groups[0][1] == 3 and groups[1][1] == 2:
        return (6, groups[0][0], groups[1][0])
    if flush:
        return (5, *ranks)
    if straight:
        return (4, straight)
    if groups[0][1] == 3:
        return (3, groups[0][0], *[g[0] for g in groups[1:]])
    if groups[0][1] == 2 and groups[1][1] == 2:
        return (2, groups[0][0], groups[1][0], groups[2][0])
    if groups[0][1] == 2:
        return (1, groups[0][0], *[g[0] for g in groups[1:]])
    return (0, *ranks)


def pk_best(cards: list) -> Optional[tuple]:
    """Meilleure main de 5 cartes parmi 5 à 7 cartes (None s'il y en a moins de 5)."""
    if len(cards) < 5:
        return None
    return max(pk_score5(list(c)) for c in combinations(cards, 5))


PK_MAX_RAISES = 2  # relances max par tour de mise


class PokerGame:
    def __init__(self, ids: list, names: dict, guild_id: Optional[int], bet: int = 0):
        self.bet = bet
        self.ids = list(ids)
        self.names = dict(names)
        self.names[MIKA_ID] = BOT_NAME
        self.seats = self.ids + [MIKA_ID]
        self.guild_id = guild_id
        deck = [(r, s) for r in range(2, 15) for s in PK_SUITS]
        random.shuffle(deck)
        self.hands = {p: [deck.pop(), deck.pop()] for p in self.seats}
        self.board = [deck.pop() for _ in range(5)]
        self.folded: set = set()
        self.afk: set = set()
        self.stage = 0
        self.mika_note = ""
        self.winners: list = []
        self.final_text = ""
        self.message: Optional[discord.Message] = None
        # --- relances : ce que chacun a mis dans le pot (Mika = la maison) ---
        self.contrib = {p: bet for p in self.seats}
        self.current_bet = bet          # niveau de mise à atteindre pour rester dans la main
        self.raises = 0                 # relances faites pendant ce tour
        self.view: Optional["PKRoundView"] = None

    @property
    def pot(self) -> int:
        return sum(self.contrib.values())

    # ---- état ----
    def active(self) -> list:
        return [p for p in self.seats if p not in self.folded]

    def active_humans(self) -> list:
        return [p for p in self.ids if p not in self.folded]

    def visible_board(self) -> list:
        return self.board[:PK_BOARD_N[min(self.stage, 3)]]

    def _mika_folds(self) -> bool:
        hand = self.hands[MIKA_ID]
        if self.stage == 0:
            hi = max(hand[0][0], hand[1][0])
            lo = min(hand[0][0], hand[1][0])
            strong = hi == lo or hi >= 12 or (hand[0][1] == hand[1][1] and hi >= 10) or (hi >= 9 and hi - lo <= 2)
            return not strong and random.random() < 0.30
        cat = pk_best(hand + self.visible_board())[0]
        p = {0: 0.35 + 0.10 * self.stage, 1: 0.10}.get(cat, 0.0)
        return random.random() < p

    def _mika_folds_raise(self) -> bool:
        """Mika face à une relance : plus prudente que d'habitude."""
        hand = self.hands[MIKA_ID]
        if self.stage == 0:
            hi = max(hand[0][0], hand[1][0])
            strong = hand[0][0] == hand[1][0] or hi >= 12 or (hand[0][1] == hand[1][1] and hi >= 10)
            return random.random() < (0.15 if strong else 0.55)
        cat = pk_best(hand + self.visible_board())[0]
        return random.random() < {0: 0.65, 1: 0.35, 2: 0.10}.get(cat, 0.03)

    def mika_respond_raise(self):
        if MIKA_ID in self.folded:
            return
        if self._mika_folds_raise():
            self.folded.add(MIKA_ID)
            self.mika_note = f"🏳️ {BOT_NAME} se couche face à la relance."
        else:
            self.contrib[MIKA_ID] = self.current_bet  # la maison suit
            self.mika_note = f"😈 {BOT_NAME} suit la relance ({self.current_bet} {COIN})."

    async def raise_limits(self) -> tuple[int, int]:
        """(relance min, relance max). Max = ce que le joueur le plus pauvre peut encore suivre."""
        room = None
        for p in self.active_humans():
            bal = await eco_balance(self.guild_id, p)
            r = bal + self.contrib[p] - self.current_bet
            room = r if room is None else min(room, r)
        hi = min(max(room or 0, 0), await eco_cfg(self.guild_id, "max_bet"))
        return max(1, self.bet), hi

    # ---- affichage ----
    def embed(self, view: Optional["PKRoundView"] = None, final: bool = False) -> discord.Embed:
        shown = 5 if final else len(self.visible_board())
        board = " ".join([pk_card(c) for c in self.board[:shown]] + [CARD_BACK] * (5 - shown))
        if final:
            desc = self.final_text
            color = COLOR_PINK
        else:
            how = "suis, relance ou couche-toi" if self.bet else "suis ou couche-toi"
            desc = f"**{PK_STAGES[self.stage]}** — {how} ({PK_TURN_TIMEOUT}s)."
            if self.mika_note:
                desc += f"\n{self.mika_note}"
            if self.bet:
                desc += f"\n💰 Pot : **{self.pot}** {COIN}"
                if self.current_bet > self.bet:
                    desc += f" • mise à suivre : **{self.current_bet}** {COIN} chacun"
            color = COLOR_PURPLE
        e = emb("♠️ Poker — Texas Hold'em", desc, color)
        e.add_field(name="🃏 Tableau", value=board, inline=False)
        for p in self.seats:
            name = self.names[p][:50]
            if final:
                if p in self.folded:
                    val = "🏳️ Couché(e)" + (" • 💤 AFK" if p in self.afk else "")
                else:
                    sc = pk_best(self.hands[p] + self.board)
                    crown = " 🏆" if p in self.winners else ""
                    val = f"{pk_cards(self.hands[p])}\n**{PK_HANDS[sc[0]]}**{crown}"
            elif p in self.folded:
                val = "🏳️ Couché(e)"
            elif p == MIKA_ID:
                val = f"{CARD_BACK} {CARD_BACK}\n😏 Reste"
            else:
                st = view.decided.get(p) if view else None
                val = {"call": "✅ Suit", "raise": "🔼 Relance", "fold": "🏳️ Couché(e)"}.get(st, "⏳ Réfléchit…")
            e.add_field(name=name, value=val, inline=True)
        if not final:
            e.set_footer(text=f"« Mes cartes » pour voir ta main (privé) • {BOT_NAME} 🖤")
        return e

    # ---- déroulé ----
    def enter_round(self):
        self.mika_note = ""
        self.raises = 0
        if MIKA_ID not in self.folded and len(self.active_humans()) >= 2 and self._mika_folds():
            self.folded.add(MIKA_ID)
            self.mika_note = f"🏳️ {BOT_NAME} se couche."
        view = PKRoundView(self, self.active_humans())
        self.view = view
        return self.embed(view), view

    async def start(self, interaction: discord.Interaction):
        embed, view = self.enter_round()
        await interaction.response.edit_message(embed=embed, view=view)
        self.message = await interaction.original_response()

    async def advance(self, interaction: Optional[discord.Interaction] = None):
        if len(self.active()) <= 1 or self.stage >= 3:
            embed, view = self.finish(), None
        else:
            self.stage += 1
            embed, view = self.enter_round()
        if interaction:
            await interaction.response.edit_message(embed=embed, view=view)
        elif self.message:
            try:
                await self.message.edit(embed=embed, view=view)
            except discord.HTTPException:
                pass

    def finish(self) -> discord.Embed:
        act = self.active()
        if not act:
            self.winners = []
            self.final_text = "🏳️ Tout le monde s'est couché : la main est annulée."
            if self.bet and self.guild_id:  # mises rendues (ante + relances déjà payées)
                for p in self.ids:
                    spawn(eco_add(self.guild_id, p, self.contrib[p]))
                self.final_text += f"\n💰 Mises rendues ({COIN})."
            return self.embed(final=True)  # pas de stats pour une main annulée
        if len(act) == 1:
            self.winners = act
            w = act[0]
            who = f"**{BOT_NAME}**" if w == MIKA_ID else f"<@{w}>"
            self.final_text = f"🏆 {who} remporte la main : tous les autres se sont couchés."
        else:
            scores = {p: pk_best(self.hands[p] + self.board) for p in act}
            top = max(scores.values())
            self.winners = [p for p in act if scores[p] == top]
            names = ", ".join(f"**{BOT_NAME}**" if p == MIKA_ID else f"<@{p}>" for p in self.winners)
            hand = PK_HANDS[top[0]]
            if len(self.winners) > 1:
                self.final_text = f"🤝 Égalité entre {names} ({hand}) — le pot est partagé."
            elif self.winners[0] == MIKA_ID:
                self.final_text = f"😈 {names} rafle tout avec **{hand}**. Sois bon perdant."
            else:
                self.final_text = f"🏆 {names} gagne avec **{hand}** ! Mommy est impressionnée 🖤"
        outcomes = {}
        for p in self.ids:
            if p in self.winners:
                outcomes[p] = "win" if len(self.winners) == 1 else "draw"
            else:
                outcomes[p] = "loss"
        spawn(record_many(self.guild_id, "poker", outcomes))
        if self.bet and self.guild_id:
            pot = self.pot  # ante + relances de tout le monde (Mika comprise)
            humans = [p for p in self.winners if p != MIKA_ID]
            if humans:
                share = pot // len(self.winners)
                for p in humans:
                    spawn(eco_add(self.guild_id, p, share))
                self.final_text += f"\n💰 Pot de **{pot}** {COIN} : **{share}** {COIN} pour chaque gagnant."
            else:
                self.final_text += f"\n💰 {BOT_NAME} empoche le pot de **{pot}** {COIN}."
        return self.embed(final=True)

# ---------- Poker : boutons d'un tour, relance, lobby, commande ----------
class PKRaiseModal(discord.ui.Modal):
    def __init__(self, pkview: "PKRoundView", lo: int, hi: int):
        super().__init__(title="🔼 Relancer", timeout=120)
        self.pkview = pkview
        self.montant = discord.ui.TextInput(label=f"Relance ({lo} à {hi})"[:45], default=str(lo), max_length=10)
        self.add_item(self.montant)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.montant.value.strip()
        if not raw.isdigit():
            return await interaction.response.send_message("🔢 Mets un nombre entier positif.", ephemeral=True)
        await self.pkview.do_raise(interaction, int(raw))

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.error("Erreur du modal de relance", exc_info=error)
        send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        await send("😅 Y'a eu un bug, réessaie.", ephemeral=True)


class PKRoundView(discord.ui.View):
    """Un tour de mise : chaque joueur encore en jeu choisit Suivre / Relancer / Se coucher."""

    def __init__(self, game: "PokerGame", players: list):
        super().__init__(timeout=PK_TURN_TIMEOUT)
        self.game = game
        self.players = list(players)
        self.decided: dict = {}
        self.lock = game.__dict__.setdefault("_lock", asyncio.Lock())
        if not game.bet:
            self.remove_item(self.b_raise)          # pas de mise : pas de relance
        elif game.raises >= PK_MAX_RAISES:
            self.b_raise.disabled = True

    async def _check(self, interaction: discord.Interaction) -> bool:
        """Vérifie que l'action est encore possible pour ce joueur (à appeler sous le verrou)."""
        uid = interaction.user.id
        if self.game.view is not self:
            await interaction.response.send_message("⌛ Ce tour est déjà terminé.", ephemeral=True)
            return False
        if uid not in self.players:
            msg = "Tu es couché(e) ou tu ne joues pas ici 😏" if uid not in self.game.ids else "Tu es déjà couché(e) 😏"
            await interaction.response.send_message(msg, ephemeral=True)
            return False
        if uid in self.decided:
            await interaction.response.send_message("T'as déjà décidé, patience 😌", ephemeral=True)
            return False
        return True

    async def _after(self, interaction: discord.Interaction):
        g = self.game
        if all(p in self.decided for p in self.players):
            self.stop()
            await g.advance(interaction)
        else:
            await interaction.response.edit_message(embed=g.embed(self), view=self)

    @discord.ui.button(label="Suivre", emoji="✅", style=discord.ButtonStyle.success, row=0)
    async def b_call(self, interaction: discord.Interaction, button: discord.ui.Button):
        g, uid = self.game, interaction.user.id
        async with self.lock:
            if not await self._check(interaction):
                return
            diff = g.current_bet - g.contrib[uid]
            if diff > 0:
                if not await eco_charge(g.guild_id, uid, diff):
                    return await interaction.response.send_message(
                        f"💸 Il te faut **{diff}** {COIN} pour suivre : couche-toi ou trouve des pièces.", ephemeral=True
                    )
                g.contrib[uid] = g.current_bet
            self.decided[uid] = "call"
            await self._after(interaction)

    @discord.ui.button(label="Relancer", emoji="🔼", style=discord.ButtonStyle.primary, row=0)
    async def b_raise(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = self.game
        async with self.lock:
            if not await self._check(interaction):
                return
            if g.raises >= PK_MAX_RAISES:
                return await interaction.response.send_message("🔼 Relances max atteintes pour ce tour.", ephemeral=True)
            lo, hi = await g.raise_limits()
            if hi < lo:
                return await interaction.response.send_message(
                    "💸 Impossible de relancer : un joueur n'aurait plus assez de pièces pour suivre.", ephemeral=True
                )
        await interaction.response.send_modal(PKRaiseModal(self, lo, hi))

    async def do_raise(self, interaction: discord.Interaction, amount: int):
        g, uid = self.game, interaction.user.id
        async with self.lock:
            if not await self._check(interaction):
                return
            if g.raises >= PK_MAX_RAISES:
                return await interaction.response.send_message("🔼 Relances max atteintes pour ce tour.", ephemeral=True)
            lo, hi = await g.raise_limits()  # les soldes ont pu changer depuis l'ouverture du modal
            if not lo <= amount <= hi:
                return await interaction.response.send_message(
                    f"🔢 La relance doit être comprise entre **{lo}** et **{hi}** {COIN}.", ephemeral=True
                )
            new_bet = g.current_bet + amount
            if not await eco_charge(g.guild_id, uid, new_bet - g.contrib[uid]):
                return await interaction.response.send_message("💸 Pas assez de pièces.", ephemeral=True)
            g.current_bet = new_bet
            g.contrib[uid] = new_bet
            g.raises += 1
            g.mika_respond_raise()
            self.stop()
            humans = g.active_humans()
            nxt = PKRoundView(g, humans)
            nxt.decided[uid] = "raise"
            if all(p in nxt.decided for p in humans):  # tous les autres se sont couchés
                return await g.advance(interaction)
            g.view = nxt
            await interaction.response.edit_message(embed=g.embed(nxt), view=nxt)

    @discord.ui.button(label="Se coucher", emoji="🏳️", style=discord.ButtonStyle.danger, row=0)
    async def b_fold(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with self.lock:
            if not await self._check(interaction):
                return
            self.game.folded.add(interaction.user.id)
            self.decided[interaction.user.id] = "fold"
            await self._after(interaction)

    @discord.ui.button(label="Mes cartes", emoji="🃏", style=discord.ButtonStyle.secondary, row=1)
    async def b_cards(self, interaction: discord.Interaction, button: discord.ui.Button):
        g, uid = self.game, interaction.user.id
        if uid not in g.ids:
            return await interaction.response.send_message("Tu ne joues pas cette main 😏", ephemeral=True)
        hand, board = g.hands[uid], g.visible_board()
        txt = f"🃏 Tes cartes : {pk_cards(hand)}\n🎴 Tableau : {pk_cards(board) if board else '—'}"
        best = pk_best(hand + board)
        if best:
            txt += f"\n✨ Main actuelle : **{PK_HANDS[best[0]]}**"
        await interaction.response.send_message(txt, ephemeral=True)

    async def on_timeout(self):
        g = self.game
        async with self.lock:
            if g.view is not self:
                return
            for p in self.players:
                if p not in self.decided:
                    self.decided[p] = "fold"
                    g.folded.add(p)
                    g.afk.add(p)
            await g.advance(None)


class PKLobby(discord.ui.View):
    def __init__(self, host: discord.abc.User, bet: int = 0):
        super().__init__(timeout=120)
        self.host_id = host.id
        self.bet = bet
        self.players: dict[int, str] = {host.id: host.display_name}
        self.started = False
        self.message: Optional[discord.Message] = None

    def embed(self) -> discord.Embed:
        lines = "\n".join(f"{'👑' if pid == self.host_id else '🎴'} <@{pid}>" for pid in self.players)
        e = emb(
            "♠️ Poker — table ouverte",
            f"Hôte : <@{self.host_id}>\nClique sur **Rejoindre** pour jouer contre {BOT_NAME} "
            f"(max {PK_MAX_PLAYERS}). L'hôte peut aussi lancer seul.\n\n"
            f"**Joueurs ({len(self.players)}/{PK_MAX_PLAYERS})**\n{lines}",
            COLOR_PURPLE,
        )
        if self.bet:
            e.description += f"\n\n💰 **Mise : {self.bet}** {COIN} par joueur (prélevée au lancement, {BOT_NAME} mise aussi)"
        e.set_footer(text=f"L'hôte lance la partie • 2 minutes • {BOT_NAME} 🖤")
        return e

    @discord.ui.button(label="Rejoindre", emoji="🎴", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid in self.players:
            return await interaction.response.send_message("T'es déjà à la table 😌", ephemeral=True)
        if len(self.players) >= PK_MAX_PLAYERS:
            return await interaction.response.send_message("Table complète 😅", ephemeral=True)
        if self.bet and await eco_balance(interaction.guild_id, uid) < self.bet:
            return await interaction.response.send_message(f"💸 Il te faut {self.bet} {COIN} pour rejoindre.", ephemeral=True)
        self.players[uid] = interaction.user.display_name
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Quitter", emoji="🚪", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in self.players:
            return await interaction.response.send_message("Tu n'es pas à la table 😏", ephemeral=True)
        if uid == self.host_id:
            self.started = True
            self.stop()
            return await interaction.response.edit_message(
                embed=emb("♠️ Table fermée", "L'hôte est parti, la table est annulée.", COLOR_DARK), view=None
            )
        del self.players[uid]
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Lancer", emoji="▶️", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            return await interaction.response.send_message("Seul l'hôte peut lancer la partie 😏", ephemeral=True)
        self.started = True
        self.stop()
        players, refused = await collect_bets(interaction.guild_id, self.players, self.bet)
        if not players:
            return await interaction.response.edit_message(
                embed=emb("♠️ Table annulée", "Personne n'a assez de pièces pour la mise.", COLOR_DARK), view=None
            )
        game = PokerGame(list(players), dict(players), interaction.guild_id, self.bet)
        await game.start(interaction)
        if refused:
            await interaction.followup.send(
                "💸 Pas assez de pièces, retirés de la table : " + ", ".join(f"<@{u}>" for u in refused),
                allowed_mentions=NO_PINGS,
            )

    async def on_timeout(self):
        if self.started or not self.message:
            return
        try:
            await self.message.edit(
                embed=emb("⌛ Table expirée", "Personne n'a lancé la partie à temps.", COLOR_DARK), view=None
            )
        except discord.HTTPException:
            pass


@bot.tree.command(name="poker", description="Texas Hold'em contre moi, seul ou à plusieurs ♠️")
@app_commands.describe(mise="Mise en pièces (0 = sans mise). Il faut activer l'économie avec /ecopanel")
@app_commands.guild_only()
async def poker(interaction: discord.Interaction, mise: app_commands.Range[int, 0, 1_000_000_000] = 0):
    err = await bet_error(interaction.guild_id, interaction.user.id, mise)
    if err:
        return await interaction.response.send_message(err, ephemeral=True)
    lobby = PKLobby(interaction.user, mise)
    await interaction.response.send_message(embed=lobby.embed(), view=lobby)
    lobby.message = await interaction.original_response()

# =====================================================================
# STATS DES JEUX : /classement, /stat
# =====================================================================
def _winrate(w: int, d: int, l: int) -> str:
    total = w + d + l
    return f"{100 * w / total:.0f}%" if total else "–"


def _kd(w: int, l: int) -> str:
    if l == 0:
        return "∞" if w else "–"
    return f"{w / l:.2f}"


@bot.tree.command(name="classement", description="Le classement des jeux du serveur 🏆")
@app_commands.describe(jeu="Un jeu précis (sinon : tous les jeux cumulés)")
@app_commands.choices(jeu=[app_commands.Choice(name="🏆 Tous les jeux", value="all")]
                      + [app_commands.Choice(name=n, value=k) for k, n in GAMES.items()])
@app_commands.guild_only()
async def classement(interaction: discord.Interaction, jeu: Optional[app_commands.Choice[str]] = None):
    key = jeu.value if jeu and jeu.value != "all" else None
    rows = await leaderboard(interaction.guild_id, key)
    title = f"🏆 Classement — {GAMES[key] if key else 'tous les jeux'}"
    if not rows:
        return await interaction.response.send_message(
            embed=emb(title, "Personne n'a encore joué. Lance un `/blackjack`, un `/poker`… 😏", COLOR_PINK)
        )
    total = len(rows)
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (uid, w, d, l, pts) in enumerate(rows[:10]):
        rank = medals[i] if i < 3 else f"`#{i + 1}`"
        lines.append(f"{rank} <@{uid}> — **{pts} pts** • {w}V / {l}D / {d}N • {_winrate(w, d, l)}")
    desc = "\n".join(lines)
    me = next((i for i, r in enumerate(rows) if r[0] == interaction.user.id), None)
    if me is None:
        desc += "\n\n_Tu n'es pas encore classé(e) : joue un peu, petit chat 😏_"
    else:
        pct = max(1, math.ceil((me + 1) * 100 / total))
        desc += f"\n\n🎯 Toi : **#{me + 1}** sur {total} joueurs — **top {pct}%**"
    desc += f"\n\n_Barème : victoire {POINTS['win']} pts, égalité {POINTS['draw']}, participation {POINTS['loss']}._"
    await interaction.response.send_message(embed=emb(title, desc, COLOR_PURPLE), allowed_mentions=NO_PINGS)


@bot.tree.command(name="stat", description="Les stats de jeu de quelqu'un : victoires, défaites, K/D 📊")
@app_commands.describe(joueur="Le joueur (toi par défaut)")
@app_commands.guild_only()
async def stat(interaction: discord.Interaction, joueur: Optional[discord.Member] = None):
    target = joueur or interaction.user
    if target.bot:
        return await interaction.response.send_message("Les bots ne jouent pas (enfin, moi je triche 😏).", ephemeral=True)
    rows = await db_all(
        "SELECT game, wins, draws, losses, points FROM game_stats WHERE guild_id=? AND user_id=?",
        (interaction.guild_id, target.id),
    )
    if not rows:
        who = "Tu n'as" if target.id == interaction.user.id else f"{target.display_name} n'a"
        return await interaction.response.send_message(f"{who} encore joué à rien 😏", ephemeral=True)
    W = sum(r[1] for r in rows)
    D = sum(r[2] for r in rows)
    L = sum(r[3] for r in rows)
    P = sum(r[4] for r in rows)
    board = await leaderboard(interaction.guild_id)
    pos = next((i for i, r in enumerate(board) if r[0] == target.id), None)
    desc = (
        f"🏆 **{W}** gagnées • 💀 **{L}** perdues • 🤝 **{D}** nulles\n"
        f"⚔️ **K/D : {_kd(W, L)}** • 📈 Victoires : **{_winrate(W, D, L)}**\n"
        f"⭐ **{P} points**"
    )
    if pos is not None:
        pct = max(1, math.ceil((pos + 1) * 100 / len(board)))
        desc += f" • #{pos + 1}/{len(board)} (top {pct}%)"
    e = emb(f"📊 Stats — {target.display_name}", desc, COLOR_PINK)
    e.set_thumbnail(url=target.display_avatar.url)
    for game, w, d, l, pts in sorted(rows, key=lambda r: -r[4]):
        e.add_field(
            name=GAMES.get(game, game),
            value=f"{w}V / {l}D / {d}N\nK/D {_kd(w, l)} • {pts} pts",
            inline=True,
        )
    await interaction.response.send_message(embed=e)


# =====================================================================
# ADMIN / DIVERS
# =====================================================================
@bot.tree.command(name="style", description="(admin) Change ma personnalité sur ce serveur 🎭")
@app_commands.describe(style="Le style à utiliser")
@app_commands.choices(style=[app_commands.Choice(name=label, value=key) for key, (label, _) in STYLES.items()])
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
async def style_cmd(interaction: discord.Interaction, style: app_commands.Choice[str]):
    await set_setting(interaction.guild_id, "style", style.value)
    await interaction.response.send_message(f"🎭 Style changé : **{style.name}**", ephemeral=True)


@bot.tree.command(name="reset", description="Efface ma mémoire de ce salon 🧼")
async def reset(interaction: discord.Interaction):
    await db_run("DELETE FROM history WHERE channel_id=?", (interaction.channel_id,))
    await interaction.response.send_message("🧼 Mémoire de ce salon effacée, on repart à zéro 😏")


@bot.tree.command(name="sync", description="(owner) Synchroniser les commandes")
async def sync(interaction: discord.Interaction):
    app = await bot.application_info()
    owner_ids = {m.id for m in app.team.members} if app.team else {app.owner.id}
    if interaction.user.id not in owner_ids:
        return await interaction.response.send_message("Non 😏", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    await bot.tree.sync()
    await interaction.followup.send("✅ Commandes synchronisées")


# ---------- /ping ----------
@bot.tree.command(name="ping", description="Vérifie ma latence 🏓")
async def ping(interaction: discord.Interaction):
    ws = bot.latency * 1000
    t0 = time.perf_counter()
    await interaction.response.send_message("🏓 Pong…")
    api = (time.perf_counter() - t0) * 1000
    e = emb("🏓 Pong !", None, COLOR_PURPLE)
    e.add_field(name="📡 Websocket", value=f"**{ws:.0f} ms**", inline=True)
    e.add_field(name="⚡ API Discord", value=f"**{api:.0f} ms**", inline=True)
    await interaction.edit_original_response(content=None, embed=e)


# ---------- Salon de logs (mod_log et log_cmd sont définis plus haut) ----------
@bot.tree.command(name="logs", description="(admin) Salon des logs : sanctions + commandes du bot 📜")
@app_commands.describe(salon="Le salon de logs", desactiver="Mets True pour couper les logs")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
async def logs_cmd(interaction: discord.Interaction, salon: Optional[discord.TextChannel] = None, desactiver: bool = False):
    gid = interaction.guild_id
    if desactiver:
        # on trace la coupure AVANT de désactiver, sinon elle ne serait vue nulle part
        await log_cmd(interaction, "logs", "Logs désactivés")
        await set_setting(gid, "log_channel", "0")
        return await interaction.response.send_message("📜 Logs désactivés.", ephemeral=True)
    if salon is None:
        cid = int(await get_setting(gid, "log_channel", "0") or 0)
        txt = f"📜 Salon de logs actuel : <#{cid}>" if cid else "📜 Aucun salon de logs. Utilise `/logs salon:#ton-salon`."
        return await interaction.response.send_message(txt, ephemeral=True)
    p = salon.permissions_for(interaction.guild.me)
    if not (p.send_messages and p.embed_links):
        return await interaction.response.send_message(
            f"🚫 Il me manque « Envoyer des messages » et « Intégrer des liens » dans {salon.mention}.", ephemeral=True
        )
    await set_setting(gid, "log_channel", str(salon.id))
    await interaction.response.send_message(f"📜 Logs activés dans {salon.mention}.", ephemeral=True)


# ---------- Mode silence : /silence <durée> ----------
async def is_silenced(guild_id: int) -> bool:
    try:
        return float(await get_setting(guild_id, "silence_until", "0")) > time.time()
    except ValueError:
        return False


@bot.tree.command(name="silence", description="(staff) Je me tais un moment 🤫 (« off » pour annuler)")
@app_commands.describe(duree="Ex : 10, 30m, 2h, 1j — ou « off » pour me réactiver")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
async def silence(interaction: discord.Interaction, duree: str):
    gid = interaction.guild_id
    if duree.strip().lower() in ("off", "stop", "fin", "non", "0"):
        await set_setting(gid, "silence_until", "0")
        return await interaction.response.send_message("🔊 Je reprends la parole. Vous m'avez manqué 😏")
    minutes = parse_minutes(duree)
    if minutes is None:
        return await interaction.response.send_message(
            "⏱️ Durée invalide. Exemples : `10`, `30m`, `2h`, `1j` (max 28 jours), ou `off`.", ephemeral=True
        )
    until = int(time.time()) + minutes * 60
    await set_setting(gid, "silence_until", str(until))
    await interaction.response.send_message(
        f"🤫 Motus et bouche cousue pendant **{fmt_duration(minutes)}** (jusqu'à <t:{until}:t>). "
        "Je ne réponds plus dans le chat ; les commandes slash restent actives. `/silence off` pour annuler."
    )


# ---------- Role-reaction : panneau de boutons, persistant après redémarrage ----------
_DANGEROUS = (
    "administrator", "manage_guild", "manage_roles", "manage_channels", "kick_members", "ban_members",
    "moderate_members", "manage_messages", "manage_webhooks", "mention_everyone", "view_audit_log",
    "manage_nicknames", "manage_threads", "mute_members", "deafen_members", "move_members",
)


def role_problem(role: discord.Role, guild: discord.Guild) -> Optional[str]:
    if role.is_default():
        return "@everyone ne peut pas être un rôle à choisir."
    if role.managed:
        return f"« {role.name} » est géré par un bot / une intégration."
    me = guild.me
    if me and role >= me.top_role:
        return f"« {role.name} » est au-dessus de mon rôle : monte mon rôle dans la hiérarchie."
    bad = [p for p in _DANGEROUS if getattr(role.permissions, p, False)]
    if bad:
        return f"« {role.name} » a des permissions sensibles ({bad[0]}…) : je ne l'attribue pas en libre-service."
    return None


class RoleButton(discord.ui.DynamicItem[discord.ui.Button], template=r"rr:(?P<role_id>[0-9]+)"):
    def __init__(self, role_id: int, label: str = "Rôle"):
        super().__init__(discord.ui.Button(
            label=(label.strip() or "—")[:80], style=discord.ButtonStyle.secondary, custom_id=f"rr:{role_id}",
        ))
        self.role_id = role_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match, /):
        return cls(int(match["role_id"]))

    async def callback(self, interaction: discord.Interaction):
        guild, member = interaction.guild, interaction.user
        role = guild.get_role(self.role_id) if guild else None
        if role is None or not isinstance(member, discord.Member):
            return await interaction.response.send_message("Ce rôle n'existe plus 😅", ephemeral=True)
        problem = role_problem(role, guild)
        if problem:
            return await interaction.response.send_message(f"🚫 {problem}", ephemeral=True)
        added = None
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Role-reaction")
                msg, added = f"➖ Rôle **{role.name}** retiré.", False
            else:
                await member.add_roles(role, reason="Role-reaction")
                msg, added = f"➕ Rôle **{role.name}** ajouté. Bon chat 🖤", True
        except discord.Forbidden:
            msg = "🚫 Je n'ai pas la permission de gérer ce rôle."
        except discord.HTTPException:
            msg = "😅 Discord a refusé, réessaie."
        await interaction.response.send_message(msg, ephemeral=True)
        if added is not None:  # trace dans les logs : rôle pris / retiré via un panneau
            le = discord.Embed(
                title="🎭 Rôle (panneau)" if added else "🎭 Rôle retiré (panneau)", color=COLOR_PINK
            )
            le.add_field(name="Membre", value=f"{member.mention} (`{member.id}`)", inline=True)
            le.add_field(name="Rôle", value=role.mention, inline=True)
            le.add_field(name="Action", value="➕ Ajouté" if added else "➖ Retiré", inline=True)
            le.timestamp = discord.utils.utcnow()
            spawn(mod_log(guild, le))


@bot.tree.command(name="rolereaction", description="(admin) Crée un panneau pour choisir ses rôles 🎭")
@app_commands.describe(
    roles="Les rôles à proposer : mentionne-les (@Role1 @Role2 …, 25 max)",
    titre="Titre du panneau", description="Texte d'explication", salon="Salon où poster (ici par défaut)",
)
@app_commands.guild_only()
@app_commands.default_permissions(manage_roles=True)
@app_commands.checks.has_permissions(manage_roles=True)
async def rolereaction(
    interaction: discord.Interaction, roles: str, titre: str = "🎭 Choisis tes rôles",
    description: Optional[str] = None, salon: Optional[discord.TextChannel] = None,
):
    guild = interaction.guild
    ids = list(dict.fromkeys(int(x) for x in re.findall(r"<@&(\d+)>", roles)))
    if not ids:
        return await interaction.response.send_message("Mentionne au moins un rôle (ex : `@Gamer @Artiste`).", ephemeral=True)
    if len(ids) > 25:
        return await interaction.response.send_message("25 rôles maximum par panneau.", ephemeral=True)
    found = []
    for rid in ids:
        role = guild.get_role(rid)
        if role is None:
            return await interaction.response.send_message("Un des rôles est introuvable.", ephemeral=True)
        problem = role_problem(role, guild)
        if problem:
            return await interaction.response.send_message(f"🚫 {problem}", ephemeral=True)
        found.append(role)
    channel = salon or interaction.channel
    view = discord.ui.View(timeout=None)
    for role in found:
        view.add_item(RoleButton(role.id, role.name))
    body = (description or "Clique sur un bouton pour obtenir (ou retirer) le rôle.").replace("\\n", "\n")
    body += "\n\n" + "\n".join(f"🎀 {r.mention}" for r in found)
    embed = emb(titre[:250], body[:4000], COLOR_PINK)
    try:
        await channel.send(embed=embed, view=view, allowed_mentions=NO_PINGS)
    except (discord.Forbidden, discord.HTTPException, AttributeError):
        return await interaction.response.send_message(f"🚫 Je ne peux pas écrire dans {channel.mention}.", ephemeral=True)
    await interaction.response.send_message(f"✅ Panneau posté dans {channel.mention}.", ephemeral=True)


# ---------- /aide (public : aucune commande admin) ----------
@bot.tree.command(name="aide", description="Tout ce que je sais faire 🖤")
async def aide(interaction: discord.Interaction):
    me = BOT_NAME
    embed = emb(
        f"🖤 {me} — mode d'emploi",
        f"Je suis la bot du serveur : je discute, je vanne, je joue avec vous… "
        f"et je mène la danse 😈\nVoilà tout ce que je sais faire :",
    )
    embed.add_field(
        name="💬 Discuter avec moi",
        value=(
            f"Mentionne-moi (`@{me}`), écris simplement « {me} » dans ton message (sans ping) ou réponds à un de mes "
            "messages : je réponds en 1 à 3 phrases, "
            "avec mon caractère.\nJe retiens le fil de la discussion du salon ; `/reset` efface cette mémoire.\n"
            "Il m'arrive aussi de réagir par un emoji à vos messages.\n"
            "Dis-moi « coucou », « ça va ? » ou « tu fais quoi ? » et je te réponds.\n"
            "Essaie de me proposer un câlin ou un bisou… 😏"
        ),
        inline=False,
    )
    embed.add_field(
        name="🧠 Questions & recherche",
        value=(
            "`/ask question` → pose-moi n'importe quoi. Options : `detail` (réponse plus longue) et "
            "`web` (je cherche sur internet avant de répondre).\n"
            "`/recherche requete` → des résultats web avec les liens."
        ),
        inline=False,
    )
    embed.add_field(
        name="😈 Taquineries",
        value=(
            "`/roast @membre [contexte]` → je chambre quelqu'un.\n"
            "`/blague [thème]` → une blague coquine (sous-entendus, jamais explicite)."
        ),
        inline=False,
    )
    embed.add_field(
        name="🔮 Décisions",
        value=(
            "`/8ball question` → je réponds oui, non ou peut-être.\n"
            "`/choisir options` → je tranche entre plusieurs options (ex : `pizza, tacos ou burger`)."
        ),
        inline=False,
    )
    embed.add_field(
        name="💋 Actions",
        value=(
            "`/kiss` `/hug` `/pat` `/slap` `/bonk` `/gift` + `@membre` → une petite scène avec ping. "
            "Essaie d'en faire un sur moi… 😏"
        ),
        inline=False,
    )
    embed.add_field(
        name="💍 Mariage",
        value=(
            "`/marie @membre [@membre2]` → demande en mariage ; tout le monde doit accepter. "
            "Jusqu'à **3 personnes** par mariage : déjà marié(e) ? Tu peux inviter une 3e personne.\n"
            "`/mariage [@membre]` → voir un mariage.\n"
            "`/divorce` → quitter son mariage (à 3, les deux autres restent mariés)."
        ),
        inline=False,
    )
    embed.add_field(
        name="🎮 Jeux",
        value=(
            "`/pfc` → pierre-feuille-ciseaux contre moi.\n"
            "`/blackjack` → blackjack solo contre moi, ou à la table jusqu'à 5 joueurs.\n"
            "`/poker` → Texas Hold'em, seul ou jusqu'à 6 joueurs (je joue aussi).\n"
            "`/quiz [thème]` → question à 4 choix, le plus rapide gagne.\n"
            "`/ship @a @b` → la compatibilité de deux personnes.\n"
            "`/jeux [mise]` → tous les jeux au même endroit (boutons).\n"
            "`/classement [jeu]` • `/statu [@membre]` → profil : statut, points, K/D et argent.\n"
            "`/pfcduel @membre [mise]` → duel pierre-feuille-ciseaux contre un joueur.\n"
            "`/quizperso creer|jouer|liste|supprimer` → les quiz créés par les membres.\n"
            "`/kahoot creer|generer|lancer|liste|supprimer` → des Kahoot (quiz live multi-joueurs), créés par toi ou par l'IA.\n"
        ),
        inline=False,
    )
    embed.add_field(
        name="🌤️ Météo",
        value=(
            "`/meteo ville` → la vraie météo (maintenant + 3 jours).\n"
            f"Ou écris simplement « météo Lyon » dans le chat, ou « {me}, la météo à Paris ? »."
        ),
        inline=False,
    )
    embed.add_field(
        name="💰 Économie",
        value=(
            "`/solde [@membre]` • `/daily` (bonus quotidien) • `/donner @membre montant` • `/richesse` (top 10).\n"
            "Dans `/blackjack` et `/poker`, l'option `mise` te fait jouer des pièces (si l'économie est activée)."
        ),
        inline=False,
    )
    embed.add_field(
        name="📖 Règles",
        value="`/regleblackjack` • `/reglepoker` • `/main` (classement des mains de poker).",
        inline=False,
    )
    embed.add_field(
        name="🎭 Serveur",
        value=(
            "`/ping` → ma latence.\n"
            "`/statu [@membre]` → profil complet (statut, jeux, argent).\n"
            "`/emoji agrandir` → un emoji perso en grand.\n"
            "`/cc nom` ou `!nom` → commandes personnalisées du serveur.\n"
            "`/info` → les stats du serveur.\n"
            "`/vocal rejoindre|dire|ask|quitter` → je viens dans ton vocal et je parle à voix haute."
        ),
        inline=False,
    )
    embed.add_field(
        name="📊 Sondages, tickets & dev",
        value=(
            "`/sondage question options` → sondage à boutons (durée, choix multiple) ; re-clique pour retirer ton vote.\n"
            "🎫 **Tickets** → clique sur « Ouvrir un ticket » dans le salon d'assistance ; `/ticket fermer` pour clore.\n"
            "`/dev projet` → l'IA te génère un site / une app (zip prêt à lancer).\n"
            "`/dev question` → aide au code : bug, architecture, explication."
        ),
        inline=False,
    )
    embed.add_field(
        name="🎉 Giveaways & règles",
        value=(
            "Sous un giveaway, clique sur **🎉 Participer** (re-clique pour te retirer).\n"
            "`/regle afficher` → relis les règles du serveur."
        ),
        inline=False,
    )
    await interaction.response.send_message(embed=embed)


# ---------- /aideadmin (réservé aux admins) ----------
@bot.tree.command(name="aideadmin", description="(admin) Toutes les commandes réservées aux admins 🛠️")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def aideadmin(interaction: discord.Interaction):
    e = emb("🛠️ Aide admin", "Tout ce qui est réservé aux admins. Raccourci : `/adminpanel` regroupe presque tout.", COLOR_DARK)
    e.add_field(
        name="🛠️ Panel",
        value="`/adminpanel` → réglages, style, logs, silence, envoyer, punition, rôles, commandes perso et test en boutons.",
        inline=False,
    )
    e.add_field(
        name="🔨 Modération",
        value=(
            "`/punition panel @membre` → mute rapide ou perso, unmute, avertir, expulser, bannir, nettoyer, "
            "mute vocal / casque, **donner / retirer un rôle**. Mommy annonce la sanction dans le salon.\n"
            "`/punition deban` → débannir (avec log).\n"
            "`/silence durée` → je me tais un moment (`off` pour annuler).\n"
            "`/test` → vérifie que tout fonctionne."
        ),
        inline=False,
    )
    e.add_field(
        name="⚙️ Réglages",
        value=(
            "`/adminpanel` → panneau complet (fonctionnalités, modération, logs avec choix des types, économie, accueil, outils).\n"
            "`/style` → dominatrice, mommy, douce ou sarcastique.\n"
            "`/autorole definir|retirer|etat` → rôle donné automatiquement aux nouveaux (membres ou bots).\n"
            "`/interdit ajouter|retirer|liste|vider` → salons ou catégories où je ne parle plus.\n"
            "`/logs` → salon des logs : **toutes les sanctions** et **toutes les commandes du bot** y sont tracées."
        ),
        inline=False,
    )
    e.add_field(
        name="💰 Économie",
        value=(
            "`/ecopanel` → panneau : activer, réglages, donner / retirer, classement.\n"
            "`/eco config|donner|retirer|reset` → mêmes actions en commandes."
        ),
        inline=False,
    )
    e.add_field(
        name="🛡️ Auto-modération",
        value=(
            "`/automod config` → activer, sanctions automatiques on/off, règles (spam, invitations, mentions, "
            "majuscules, mots interdits, insultes envers le bot).\n"
            "`/automod mot` → liste des mots interdits • `/automod pardon @membre` • `/automod statut`."
        ),
        inline=False,
    )
    e.add_field(
        name="🏗️ Construction",
        value=(
            "`/creersalon` → salon texte, vocal ou catégorie (privé possible).\n"
            "`/creeserveur` → l'IA conçoit un serveur complet (aperçu + confirmation avant création)."
        ),
        inline=False,
    )
    e.add_field(
        name="🎭 Serveur",
        value=(
            "`/rolereaction` → panneau de rôles à boutons.\n"
            "`/envoyer` → message anonyme, sous un pseudo perso ou **avec l'identité du bot**.\n"
            "`/emoji ajouter` → ajouter un emoji au serveur.\n"
            "`/commande ajouter|modifier|supprimer|liste` → commandes perso (utilisables avec `/cc nom` ou `!nom`).\n"
            "`/sync` → (owner du bot) resynchroniser les commandes."
        ),
        inline=False,
    )
    e.add_field(
        name="📣 Annonces & ménage",
        value=(
            "`/annonce` → publie une annonce (fenêtre titre + message, ping @everyone / @here / rôle, image) — gérer le serveur.\n"
            "`/purge nombre [membre] [salon]` → supprime jusqu'à 500 messages (épinglés et > 14 j épargnés, "
            "confirmation au-delà de 100) — gérer les messages."
        ),
        inline=False,
    )
    e.add_field(
        name="👋 Bienvenue",
        value=(
            "`/bienvenue config` → salon, activer, mode **texte** ou **IA** (message unique par membre), modèle, consignes, MP.\n"
            "`/bienvenue generer ton` → l'IA écrit un modèle (aperçu + bouton pour l'adopter) • `/bienvenue tester`."
        ),
        inline=False,
    )
    e.add_field(
        name="🎫 Tickets",
        value=(
            "`/ticket config` → catégorie, rôle staff, salon de transcripts, limite par membre.\n"
            "`/ticket panel` → poste le bouton « Ouvrir un ticket ».\n"
            "`/ticket fermer|ajouter|retirer` → gérer un ticket (transcript auto à la fermeture)."
        ),
        inline=False,
    )
    e.add_field(
        name="⚡ Optimisation",
        value="`/optimiser [test_ia]` → latences, RAM, base, caches + propositions ; boutons « Optimiser la base » et « Conseils de l'IA ».",
        inline=False,
    )
    e.add_field(
        name="🗑️ Salons & rôles",
        value=(
            "`/supprimersalon salon [contenu]` → supprime un salon, un vocal, un forum ou une catégorie "
            "(`contenu:True` = supprime aussi ce qu'elle contient). Confirmation + log.\n"
            "`/role creer nom [couleur] [permissions] [affiche] [mentionnable] [membre]` → crée un rôle.\n"
            "`/role supprimer role` → supprime un rôle (confirmation + log)."
        ),
        inline=False,
    )
    e.add_field(
        name="📜 Règles obligatoires",
        value=(
            "`/regle serveur [actif] [salon] [role] [delai] [texte]` → les nouveaux membres doivent **accepter** "
            "les règles (bouton) : refus ou délai dépassé = expulsion. Le salon doit être visible des nouveaux."
        ),
        inline=False,
    )
    e.add_field(
        name="🎉 Giveaways",
        value=(
            f"`/{GW_CMD} lancer lot duree [gagnants] [salon] [role_requis]` → giveaway à bouton, tirage automatique.\n"
            f"`/{GW_CMD} terminer|relancer|annuler|liste` → les gérer (choix dans la liste)."
        ),
        inline=False,
    )
    await interaction.response.send_message(embed=e, ephemeral=True)

# =====================================================================
# COMMANDES PERSONNALISÉES : créées par les admins, utilisables par tout le monde
#   /commande ajouter|modifier|supprimer|liste  (permission Administrateur)
#   /cc nom  ou  !nom dans le chat
# =====================================================================
CC_MAX = 100          # commandes max par serveur
CC_NAME_RE = re.compile(r"^[\w-]{1,32}$")


def cc_name(raw: str) -> Optional[str]:
    name = raw.strip().lstrip("!/").lower()
    return name if CC_NAME_RE.match(name) else None


def cc_text(raw: str) -> str:
    return raw.replace("\\n", "\n").strip()  # « \n » tapé dans la commande = retour à la ligne


async def cc_get(guild_id: int, name: str) -> Optional[str]:
    rows = await db_all("SELECT response FROM custom_cmds WHERE guild_id=? AND name=?", (guild_id, name))
    return rows[0][0] if rows else None


def cc_render(response: str, user: discord.abc.User, guild: discord.Guild) -> str:
    return response.replace("{user}", user.mention).replace("{server}", guild.name)[:2000]


CC_PINGS = discord.AllowedMentions(everyone=False, roles=False, users=True, replied_user=False)
cmd_group = app_commands.Group(
    name="commande", description="(admin) Gère les commandes personnalisées 🛠️",
    guild_only=True, default_permissions=discord.Permissions(administrator=True),
)
admin_only = app_commands.checks.has_permissions(administrator=True)


async def cc_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    if not interaction.guild_id:
        return []
    prefix = re.sub(r"[^\w-]", "", current.lower()).replace("_", r"\_")
    rows = await db_all(
        "SELECT name FROM custom_cmds WHERE guild_id=? AND name LIKE ? ESCAPE '\\' ORDER BY name LIMIT 25",
        (interaction.guild_id, f"{prefix}%"),
    )
    return [app_commands.Choice(name=r[0], value=r[0]) for r in rows]


@cmd_group.command(name="ajouter", description="Crée une commande personnalisée")
@app_commands.describe(
    nom="Le nom (lettres, chiffres, - et _), utilisable avec /cc nom ou !nom",
    reponse="Ma réponse. {user} = la personne qui l'utilise, {server} = le serveur, \\n = retour à la ligne",
)
@admin_only
async def cc_add(interaction: discord.Interaction, nom: app_commands.Range[str, 1, 33], reponse: app_commands.Range[str, 1, 1500]):
    name = cc_name(nom)
    if not name:
        return await interaction.response.send_message(
            "❌ Nom invalide : 1 à 32 caractères, lettres / chiffres / `-` / `_`, sans espace.", ephemeral=True
        )
    if await cc_get(interaction.guild_id, name) is not None:
        return await interaction.response.send_message(
            f"❌ `{name}` existe déjà. Utilise `/commande modifier` pour la changer.", ephemeral=True
        )
    count = (await db_all("SELECT COUNT(*) FROM custom_cmds WHERE guild_id=?", (interaction.guild_id,)))[0][0]
    if count >= CC_MAX:
        return await interaction.response.send_message(f"❌ Limite de {CC_MAX} commandes atteinte.", ephemeral=True)
    await db_run(
        "INSERT INTO custom_cmds(guild_id, name, response, created_by) VALUES (?,?,?,?)",
        (interaction.guild_id, name, cc_text(reponse), interaction.user.id),
    )
    await interaction.response.send_message(
        f"✅ Commande **{name}** créée. Essaie `/cc {name}` ou écris `!{name}` dans un salon.", ephemeral=True
    )


@cmd_group.command(name="modifier", description="Change la réponse d'une commande personnalisée")
@app_commands.describe(nom="La commande à modifier", reponse="La nouvelle réponse")
@app_commands.autocomplete(nom=cc_autocomplete)
@admin_only
async def cc_edit(interaction: discord.Interaction, nom: str, reponse: app_commands.Range[str, 1, 1500]):
    name = cc_name(nom)
    if not name or await cc_get(interaction.guild_id, name) is None:
        return await interaction.response.send_message("❌ Cette commande n'existe pas.", ephemeral=True)
    await db_run(
        "UPDATE custom_cmds SET response=? WHERE guild_id=? AND name=?", (cc_text(reponse), interaction.guild_id, name)
    )
    await interaction.response.send_message(f"✅ Commande **{name}** modifiée.", ephemeral=True)


@cmd_group.command(name="supprimer", description="Supprime une commande personnalisée")
@app_commands.describe(nom="La commande à supprimer")
@app_commands.autocomplete(nom=cc_autocomplete)
@admin_only
async def cc_remove(interaction: discord.Interaction, nom: str):
    name = cc_name(nom)
    if not name or await cc_get(interaction.guild_id, name) is None:
        return await interaction.response.send_message("❌ Cette commande n'existe pas.", ephemeral=True)
    await db_run("DELETE FROM custom_cmds WHERE guild_id=? AND name=?", (interaction.guild_id, name))
    await interaction.response.send_message(f"🗑️ Commande **{name}** supprimée.", ephemeral=True)


@cmd_group.command(name="liste", description="Liste les commandes personnalisées du serveur")
@admin_only
async def cc_list(interaction: discord.Interaction):
    rows = await db_all("SELECT name, response FROM custom_cmds WHERE guild_id=? ORDER BY name", (interaction.guild_id,))
    if not rows:
        return await interaction.response.send_message("Aucune commande perso. Crée-en une avec `/commande ajouter`.", ephemeral=True)
    lines = [f"`{n}` — {r.replace(chr(10), ' ')[:60]}{'…' if len(r) > 60 else ''}" for n, r in rows]
    await interaction.response.send_message(
        embed=emb(f"🛠️ Commandes perso ({len(rows)})", "\n".join(lines)[:4000], COLOR_PINK), ephemeral=True
    )


bot.tree.add_command(cmd_group)


@bot.tree.command(name="cc", description="Lance une commande personnalisée du serveur 🛠️")
@app_commands.describe(nom="Le nom de la commande")
@app_commands.autocomplete(nom=cc_autocomplete)
@app_commands.guild_only()
async def cc(interaction: discord.Interaction, nom: str):
    name = cc_name(nom)
    response = await cc_get(interaction.guild_id, name) if name else None
    if response is None:
        return await interaction.response.send_message("❌ Cette commande n'existe pas.", ephemeral=True)
    await interaction.response.send_message(
        cc_render(response, interaction.user, interaction.guild), allowed_mentions=CC_PINGS
    )


# =====================================================================
# MÉTÉO : /meteo ville, ou « météo Lyon » écrit dans le chat (vraies données Open-Meteo, sans clé)
# =====================================================================
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WX_CODES = {
    0: ("☀️", "Ciel dégagé"), 1: ("🌤️", "Plutôt dégagé"), 2: ("⛅", "Partiellement nuageux"), 3: ("☁️", "Couvert"),
    45: ("🌫️", "Brouillard"), 48: ("🌫️", "Brouillard givrant"),
    51: ("🌦️", "Bruine légère"), 53: ("🌦️", "Bruine"), 55: ("🌧️", "Bruine dense"),
    56: ("🌧️", "Bruine verglaçante"), 57: ("🌧️", "Forte bruine verglaçante"),
    61: ("🌧️", "Pluie faible"), 63: ("🌧️", "Pluie"), 65: ("🌧️", "Forte pluie"),
    66: ("🌧️", "Pluie verglaçante"), 67: ("🌧️", "Forte pluie verglaçante"),
    71: ("🌨️", "Neige faible"), 73: ("🌨️", "Neige"), 75: ("❄️", "Forte neige"), 77: ("🌨️", "Grains de neige"),
    80: ("🌦️", "Averses faibles"), 81: ("🌦️", "Averses"), 82: ("⛈️", "Fortes averses"),
    85: ("🌨️", "Averses de neige"), 86: ("🌨️", "Fortes averses de neige"),
    95: ("⛈️", "Orage"), 96: ("⛈️", "Orage et grêle"), 99: ("⛈️", "Violent orage et grêle"),
}
WX_RAIN = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
WX_SNOW = {71, 73, 75, 77, 85, 86}
JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
WX_LABELS = ["Aujourd'hui", "Demain", "Après-demain"]

WX_WORD = re.compile(r"\bm[ée]t[ée]o\b", re.I)
WX_STANDALONE = re.compile(r"^\W*(?:(?:quelle|quel)\s+(?:est\s+)?)?(?:la\s+)?m[ée]t[ée]o\b", re.I)
WX_CITY = re.compile(
    r"\bm[ée]t[ée]o\b[\s,:]*(?:(?:à|a|de|du|des|en|sur|pour|dans)\s+)?([^?!.,;:\n]{2,50})", re.I
)
WX_TIME_WORDS = (
    r"aujourd['’]?hui|apr[èe]s[\s-]?demain|demain(?:\s+(?:matin|soir|midi|apr[èe]s[\s-]?midi))?|"
    r"ce\s+(?:soir|matin|midi|week-?end)|cet\s+apr[èe]s[\s-]?midi|cette\s+(?:nuit|semaine)|"
    r"maintenant|svp|stp|please|là|actuellement|en\s+ce\s+moment"
)
WX_TIME_END = re.compile(rf"(?:\s+(?:{WX_TIME_WORDS}))+\s*$", re.I)
WX_TIME_START = re.compile(
    r"^(?:aujourd['’]?hui|demain|apr[èe]s[\s-]?demain|ce\s+soir|ce\s+matin|maintenant)\s+"
    r"(?:(?:à|a|de|en|sur|pour|dans)\s+)?", re.I,
)
# premier mot qui trahit une phrase (« la météo est nulle ») et non un nom de ville
WX_NOT_CITY = {
    "est", "etait", "était", "sera", "c", "ca", "ça", "il", "elle", "me", "nous", "vous", "tu", "je", "qui", "que",
    "fait", "va", "et", "ou", "trop", "tres", "très", "pas", "nulle", "bien", "mauvaise", "belle", "toujours",
    "ici", "là", "chez", "dehors", "cette", "ce", "cet", "ces", "quoi", "comment", "comme", "quand", "pourquoi",
    "hein", "mdr", "lol", "vraiment", "encore", "déjà", "deja", "toute", "tout", "bof", "super", "horrible",
}


class CityNotFound(Exception):
    pass


def weather_request(text: str) -> Optional[str]:
    """None = ce n'est pas une demande de météo ; "" = demande sans ville ; sinon le nom de la ville."""
    if not WX_WORD.search(text):
        return None
    m = WX_CITY.search(text)
    if not m:
        return ""
    city = m.group(1).strip()
    for _ in range(3):  # retire « aujourd'hui », « demain matin »... en début / fin
        city = WX_TIME_START.sub("", city).strip()
        city = WX_TIME_END.sub("", city).strip()
    city = city.strip(" '\"«»-")
    if not city:
        return ""
    low = city.lower().replace("’", "'")
    if low in {"aujourd'hui", "aujourdhui", "demain", "ce soir", "ce matin", "maintenant"}:
        return ""
    if not re.search(r"[^\W\d_]", city):  # que des chiffres / symboles : pas une ville
        return ""
    if re.split(r"[\s']", low)[0] in WX_NOT_CITY or len(city.split()) > 5:
        return None  # c'est une phrase (« la météo est nulle »), pas une demande
    if low.startswith("au "):
        city = "Le " + city[3:]
    elif low.startswith("aux "):
        city = "Les " + city[4:]
    return city[:50]


def wx_desc(code: int) -> tuple[str, str]:
    return WX_CODES.get(code, ("🌡️", "Temps variable"))


def wx_quip(temp: float, code: int) -> str:
    if code >= 95:
        pool = ["Orage dehors… viens te blottir, je te protège 😈", "Reste à l'abri, petit chat ⛈️"]
    elif code in WX_SNOW:
        pool = ["Il neige ! Couvre-toi bien, mon chou ❄️", "De la neige… parfait pour rester au chaud avec moi 😏"]
    elif code in WX_RAIN:
        pool = ["Il pleut… prends un parapluie, ou viens sous le mien 😏", "Sale temps. Reste au sec, petit chat 🌧️"]
    elif temp >= 30:
        pool = ["Il fait une chaleur de dingue… mets-toi à l'aise 😈", "Il fait chaud, bois de l'eau petit chat 💧"]
    elif temp >= 20:
        pool = ["Un temps parfait pour sortir… ou pour rester avec moi 😏", "Il fait bon, profite ✨"]
    elif temp >= 10:
        pool = ["Un peu frais, prends une veste ~", "Ni chaud ni froid, comme un lundi 🖤"]
    elif temp > 0:
        pool = ["Il fait froid… viens, je te réchauffe 🖤", "Couvre-toi bien, je veux pas te voir malade 😤"]
    else:
        pool = ["Il gèle ! Sors couvert, mon chou ❄️", "Il fait un froid de canard, reste au chaud 🖤"]
    return random.choice(pool)


def _geo_candidates(city: str) -> list[str]:
    """« Paris France » / « Lyon, France » : si le nom complet ne donne rien, on essaie des versions plus courtes."""
    out = [city]
    first = re.split(r"\s*[,(]\s*", city)[0].strip()
    parts = first.split()
    for c in (first, " ".join(parts[:-1]) if len(parts) > 1 else "", parts[0] if len(parts) > 1 else ""):
        if len(c) >= 2 and c.lower() not in {x.lower() for x in out}:
            out.append(c)
    return out


async def _wx_get(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    """GET avec 3 essais (coupure réseau, 429, 5xx) : le service gratuit a des à-coups, surtout sur un hébergeur."""
    for attempt in range(3):
        try:
            r = await client.get(url, params=params)
        except httpx.TransportError:
            if attempt == 2:
                raise
            await asyncio.sleep(1 + attempt)
            continue
        if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            await asyncio.sleep(1 + attempt)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("météo : essais épuisés")  # inatteignable


async def fetch_weather(city: str) -> discord.Embed:
    """Géocode la ville puis récupère la météo actuelle + 3 jours (Open-Meteo, gratuit, sans clé)."""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0), headers={"User-Agent": "MikaBot-Discord"}
    ) as client:
        place = None
        for cand in _geo_candidates(city):
            g = await _wx_get(client, GEO_URL, {"name": cand, "count": 1, "language": "fr", "format": "json"})
            if g.get("results"):
                place = g["results"][0]
                break
        if place is None:
            raise CityNotFound(city)
        data = await _wx_get(client, FORECAST_URL, {
            "latitude": place["latitude"], "longitude": place["longitude"], "timezone": "auto", "forecast_days": 3,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        })

    cur, daily = data["current"], data["daily"]
    temp, code = cur["temperature_2m"], int(cur["weather_code"])
    emoji, label = wx_desc(code)
    where = place["name"] + (f" ({place['country']})" if place.get("country") else "")
    desc = (
        f"{emoji} **{label}**\n"
        f"🌡️ **{temp:.0f}°C** (ressenti {cur['apparent_temperature']:.0f}°C)\n"
        f"💧 Humidité {cur['relative_humidity_2m']:.0f}% • 💨 Vent {cur['wind_speed_10m']:.0f} km/h\n\n"
        f"_{wx_quip(temp, code)}_"
    )
    color = COLOR_PINK if temp >= 20 else COLOR_PURPLE if temp >= 5 else COLOR_DARK
    embed = emb(f"Météo — {where}", desc, color)
    for i, day in enumerate(daily["time"][:3]):
        d_emoji, d_label = wx_desc(int(daily["weather_code"][i]))
        rain = daily["precipitation_probability_max"][i]
        jour = JOURS[datetime.date.fromisoformat(day).weekday()]
        embed.add_field(
            name=f"{WX_LABELS[i]} ({jour})",
            value=f"{d_emoji} {d_label}\n{daily['temperature_2m_min'][i]:.0f}° / {daily['temperature_2m_max'][i]:.0f}°C"
                  + (f" • 🌧️ {rain}%" if rain is not None else ""),
            inline=True,
        )
    embed.set_footer(text=f"{BOT_NAME} 🖤 • données Open-Meteo")
    return embed


@bot.tree.command(name="meteo", description="La vraie météo d'une ville 🌤️")
@app_commands.describe(ville="Ex : Lyon, Paris, Fort-de-France...")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def meteo(interaction: discord.Interaction, ville: app_commands.Range[str, 2, 60]):
    await interaction.response.defer(thinking=True)
    try:
        embed = await fetch_weather(ville.strip())
    except CityNotFound:
        return await interaction.followup.send(f"Je ne trouve pas « {ville[:40]} »… vérifie l'orthographe 😏")
    except Exception as e:  # noqa: BLE001
        log.warning("Météo : %r", e)
        return await interaction.followup.send("😅 Je n'arrive pas à joindre le service météo, réessaie dans un instant.")
    await interaction.followup.send(embed=embed)


# =====================================================================
# /statu, /emoji, /envoyer
# =====================================================================
_STATUS = {
    discord.Status.online: "🟢 En ligne", discord.Status.idle: "🌙 Absent",
    discord.Status.dnd: "⛔ Ne pas déranger", discord.Status.offline: "⚫ Hors ligne / invisible",
}

@bot.tree.command(name="statu", description="Profil d'un membre : statut, stats de jeu et argent 🟢")
@app_commands.describe(pseudo="Le membre (toi par défaut)")
@app_commands.guild_only()
async def statu(interaction: discord.Interaction, pseudo: Optional[discord.Member] = None):
    target = pseudo or interaction.user
    gid = interaction.guild_id
    m = interaction.guild.get_member(target.id) or target  # le membre en cache a la présence, pas celui de l'interaction
    e = emb(f"Profil — {m.display_name}", None, COLOR_PURPLE)
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="Statut", value=_STATUS.get(m.status, "⚫ Inconnu"), inline=True)
    devices = [n for n, s in (("🖥️ PC", m.desktop_status), ("📱 Mobile", m.mobile_status), ("🌐 Web", m.web_status))
               if s != discord.Status.offline]
    if devices:
        e.add_field(name="Appareils", value=" • ".join(devices), inline=True)
    acts = []
    for a in m.activities:
        if isinstance(a, discord.CustomActivity):
            txt = " ".join(x for x in (str(a.emoji) if a.emoji else "", a.name or "") if x)
            if txt:
                acts.append(f"💬 {txt}")
        elif isinstance(a, discord.Spotify):
            acts.append(f"🎵 Écoute **{a.title}** — {a.artist}")
        elif isinstance(a, discord.Streaming):
            acts.append(f"📺 En live : **{a.name}**")
        else:
            t = getattr(a, "type", None)
            verb = {discord.ActivityType.listening: "🎧 Écoute", discord.ActivityType.watching: "📺 Regarde",
                    discord.ActivityType.competing: "🏆 Participe à"}.get(t, "🎮 Joue à")
            acts.append(f"{verb} **{a.name}**")
    if acts:
        e.add_field(name="Activité", value="\n".join(acts)[:1000], inline=False)
    if m.voice and m.voice.channel:
        flags = (" 🎙️❌" if m.voice.mute or m.voice.self_mute else "") + (" 🎧❌" if m.voice.deaf or m.voice.self_deaf else "")
        e.add_field(name="Vocal", value=f"🔊 {m.voice.channel.mention}{flags}", inline=False)
    if m.is_timed_out():
        e.add_field(name="Sanction", value=f"🤐 Muté jusqu'à <t:{int(m.timed_out_until.timestamp())}:R>", inline=False)

    # ---- stats de jeu + argent (pas pour les bots) ----
    if not m.bot:
        rows = await db_all(
            "SELECT game, wins, draws, losses, points FROM game_stats WHERE guild_id=? AND user_id=?", (gid, m.id)
        )
        if rows:
            W, D, L, P = (sum(r[i] for r in rows) for i in (1, 2, 3, 4))
            board = await leaderboard(gid)
            pos = next((i for i, r in enumerate(board) if r[0] == m.id), None)
            desc = (
                f"🏆 **{W}** gagnées • 💀 **{L}** perdues • 🤝 **{D}** nulles\n"
                f"⚔️ **K/D : {_kd(W, L)}** • 📈 Victoires : **{_winrate(W, D, L)}**\n⭐ **{P} points**"
            )
            if pos is not None:
                pct = max(1, math.ceil((pos + 1) * 100 / len(board)))
                desc += f" • #{pos + 1}/{len(board)} (top {pct}%)"
            e.add_field(name="🎮 Stats de jeu", value=desc, inline=False)
            for game, w, d, l, pts in sorted(rows, key=lambda r: -r[4]):
                e.add_field(
                    name=GAMES.get(game, game),
                    value=f"{w}V / {l}D / {d}N\nK/D {_kd(w, l)} • {pts} pts",
                    inline=True,
                )
        else:
            e.add_field(name="🎮 Stats de jeu", value="Aucune partie jouée pour l'instant 😏", inline=False)
        if await eco_on(gid):
            e.add_field(name="💰 Argent", value=f"**{await eco_balance(gid, m.id)}** {COIN}", inline=True)
    if not bot.intents.presences:
        e.set_footer(text="⚠️ Intent « Présences » désactivé : statut et activité ne sont pas fiables.")
    await interaction.response.send_message(embed=e)



EMOJI_RE = re.compile(r"<(a?):(\w{2,32}):(\d{15,25})>")
emoji_group = app_commands.Group(name="emoji", description="Agrandir ou ajouter des emojis 🎭", guild_only=True)


def _emoji_url(animated: bool, eid: str) -> str:
    return f"https://cdn.discordapp.com/emojis/{eid}.{'gif' if animated else 'png'}?size=256"


@emoji_group.command(name="agrandir", description="Affiche un emoji perso en grand 🔍")
@app_commands.describe(emoji="Colle un emoji personnalisé (d'ici ou d'un autre serveur)")
async def emoji_big(interaction: discord.Interaction, emoji: str):
    m = EMOJI_RE.search(emoji)
    if not m:
        return await interaction.response.send_message(
            "Colle un emoji **personnalisé** (les emojis Unicode sont déjà affichables 😏).", ephemeral=True
        )
    animated, name, eid = bool(m.group(1)), m.group(2), m.group(3)
    e = emb(f":{name}:", f"ID `{eid}` • {'animé' if animated else 'statique'}", COLOR_PINK)
    e.set_image(url=_emoji_url(animated, eid))
    await interaction.response.send_message(embed=e)


@emoji_group.command(name="ajouter", description="(admin) Ajoute un emoji au serveur 🎭")
@app_commands.describe(
    emoji="Un emoji perso à copier (d'un autre serveur)", image="…ou une image (PNG/JPG/GIF, 256 Ko max)",
    nom="Nom de l'emoji (2 à 32 caractères : lettres, chiffres, _)",
)
async def emoji_add(
    interaction: discord.Interaction, emoji: Optional[str] = None,
    image: Optional[discord.Attachment] = None, nom: Optional[str] = None,
):
    p = interaction.permissions
    if not (p.administrator or getattr(p, "manage_expressions", False) or getattr(p, "manage_emojis_and_stickers", False)):
        return await interaction.response.send_message("🚫 Il te manque la permission « Gérer les expressions ».", ephemeral=True)
    if bool(emoji) == bool(image):
        return await interaction.response.send_message("Donne **soit** un `emoji`, **soit** une `image`.", ephemeral=True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    default_name = "emoji"
    try:
        if emoji:
            m = EMOJI_RE.search(emoji)
            if not m:
                return await interaction.followup.send("Colle un emoji personnalisé valide.", ephemeral=True)
            default_name = m.group(2)
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(_emoji_url(bool(m.group(1)), m.group(3)).replace("?size=256", ""))
            if r.status_code != 200:
                return await interaction.followup.send("😅 Je n'arrive pas à récupérer cet emoji.", ephemeral=True)
            data = r.content
        else:
            if not (image.content_type or "").startswith(("image/png", "image/jpeg", "image/gif", "image/webp")):
                return await interaction.followup.send("Format non supporté : PNG, JPG, GIF ou WEBP.", ephemeral=True)
            if image.size > 256 * 1024:
                return await interaction.followup.send("Image trop lourde : 256 Ko maximum.", ephemeral=True)
            default_name = image.filename.rsplit(".", 1)[0]
            data = await image.read()
    except (httpx.HTTPError, discord.HTTPException):
        return await interaction.followup.send("😅 Téléchargement impossible, réessaie.", ephemeral=True)
    if len(data) > 256 * 1024:
        return await interaction.followup.send("Image trop lourde : 256 Ko maximum.", ephemeral=True)
    name = re.sub(r"\W", "", nom or default_name)[:32]
    if len(name) < 2:
        name = "emoji_" + str(random.randint(100, 999))
    try:
        created = await interaction.guild.create_custom_emoji(
            name=name, image=data, reason=f"/emoji ajouter par {interaction.user}"
        )
    except discord.Forbidden:
        return await interaction.followup.send("🚫 Il me manque la permission « Gérer les expressions ».", ephemeral=True)
    except discord.HTTPException as e:
        return await interaction.followup.send(f"😅 Discord a refusé : {str(e.text)[:150]} (limite d'emojis atteinte ?)", ephemeral=True)
    await interaction.followup.send(f"✅ Emoji ajouté : {created} `:{created.name}:`", ephemeral=True)


bot.tree.add_command(emoji_group)

RELAY_NAME = "Mika Relay"


async def get_relay_webhook(channel):
    thread = None
    base = channel
    if isinstance(channel, discord.Thread):
        thread, base = channel, channel.parent
    for h in await base.webhooks():
        if h.name == RELAY_NAME and h.token and h.user and h.user.id == bot.user.id:
            return h, thread
    return await base.create_webhook(name=RELAY_NAME, reason="Relais pour /envoyer"), thread


@bot.tree.command(name="envoyer", description="(admin) Envoie un message anonyme, sous un pseudo perso ou en tant que bot ✉️")
@app_commands.describe(
    message="Le message (\\n = retour à la ligne)",
    identite="Qui apparaît comme expéditeur",
    pseudo="Le pseudo à afficher (pour « Pseudo perso »)",
    salon="Salon d'envoi (ici par défaut)",
    avatar="URL d'une image d'avatar (optionnel, https ; ignoré avec l'identité du bot)",
)
@app_commands.choices(identite=[
    app_commands.Choice(name="🕶️ Anonyme", value="anon"),
    app_commands.Choice(name="🎭 Pseudo perso", value="perso"),
    app_commands.Choice(name="🤖 Identité du bot", value="bot"),
])
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def envoyer(
    interaction: discord.Interaction, message: app_commands.Range[str, 1, 2000], identite: app_commands.Choice[str],
    pseudo: Optional[app_commands.Range[str, 1, 32]] = None, salon: Optional[discord.TextChannel] = None,
    avatar: Optional[str] = None,
):
    channel = salon or interaction.channel
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        return await interaction.response.send_message("Je ne peux pas écrire dans ce type de salon.", ephemeral=True)
    as_bot = identite.value == "bot"
    if as_bot:
        name = BOT_NAME  # le message part directement du compte du bot (pas de webhook)
    else:
        name = "Anonyme" if identite.value == "anon" else (pseudo or "").strip()
        if not name:
            return await interaction.response.send_message("Donne un `pseudo` pour l'identité « Pseudo perso ».", ephemeral=True)
        if any(w in name.lower() for w in ("discord", "clyde")):
            return await interaction.response.send_message("Discord interdit « discord » et « clyde » dans un pseudo.", ephemeral=True)
        if avatar and not (avatar.startswith("https://") and len(avatar) <= 300):
            return await interaction.response.send_message("L'avatar doit être une URL https valide.", ephemeral=True)
    text = message.replace("\\n", "\n")[:2000]
    allowed = discord.AllowedMentions(everyone=False, roles=False, users=True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        if as_bot:
            await channel.send(text, allowed_mentions=allowed)
        else:
            hook, thread = await get_relay_webhook(channel)
            await hook.send(
                content=text, username=name[:80], avatar_url=avatar or discord.utils.MISSING,
                allowed_mentions=allowed, thread=thread or discord.utils.MISSING,
            )
    except discord.Forbidden:
        if as_bot:
            return await interaction.followup.send(f"🚫 Je ne peux pas écrire dans {channel.mention}.", ephemeral=True)
        if identite.value == "anon":
            try:
                await channel.send(text, allowed_mentions=allowed)
            except discord.HTTPException:
                return await interaction.followup.send("🚫 Je ne peux pas écrire ici.", ephemeral=True)
        else:
            return await interaction.followup.send(
                "🚫 Il me faut la permission « Gérer les webhooks » dans ce salon pour changer d'identité.", ephemeral=True
            )
    except discord.HTTPException as e:
        log.warning("/envoyer : %s", e)
        return await interaction.followup.send("😅 Discord a refusé l'envoi (pseudo ou avatar invalide ?).", ephemeral=True)
    who = f"**{name}** (identité du bot)" if as_bot else f"**{name}**"
    await interaction.followup.send(f"✅ Envoyé dans {channel.mention} en tant que {who}.", ephemeral=True)
    # trace pour le staff : l'anonymat vaut vis-à-vis des membres, pas des admins
    le = discord.Embed(title="✉️ /envoyer utilisé", color=COLOR_DARK)
    le.add_field(name="Admin", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
    le.add_field(name="Identité", value=f"{name} (bot)" if as_bot else name, inline=True)
    le.add_field(name="Salon", value=channel.mention, inline=True)
    le.add_field(name="Message", value=text[:1000], inline=False)
    le.timestamp = discord.utils.utcnow()
    await mod_log(interaction.guild, le)


# =====================================================================
# MODÉRATION : /punition panel | deban (mute, unmute, avertir, expulser, bannir, nettoyer, mute vocal, casque, rôles)
#   Toutes les sanctions sont envoyées dans le salon de logs (/logs).
# =====================================================================
MAX_TIMEOUT_MIN = 28 * 24 * 60  # limite Discord pour un mute (timeout) : 28 jours

PUNISH_PERM = {
    "mute": "moderate_members", "unmute": "moderate_members", "warn": "moderate_members",
    "kick": "kick_members", "ban": "ban_members", "purge": "manage_messages",
}
PERM_LABEL = {
    "moderate_members": "Exclure temporairement des membres", "kick_members": "Expulser des membres",
    "ban_members": "Bannir des membres", "manage_messages": "Gérer les messages",
}
PUNISH_LABEL = {
    "mute": "Mute", "unmute": "Unmute", "warn": "Avertir", "kick": "Expulser", "ban": "Bannir", "purge": "Nettoyer",
}
PUNISH_STYLE = {  # (emoji, titre, couleur) des annonces publiques
    "mute": ("🤐", "Silence !", 0x9B6BFF),
    "unmute": ("🔊", "Parole rendue", 0x7ED6A5),
    "warn": ("⚠️", "Avertissement", 0xFFB347),
    "kick": ("👢", "Expulsion", 0xFF7A7A),
    "ban": ("🔨", "Bannissement", 0xD7263D),
    "purge": ("🧹", "Grand ménage", COLOR_PINK),
}

MSG_MUTE = [
    "🤐 Mommy a étouffé la bouche de {user} avec ses cuisses pendant **{duree}**.",
    "🤐 Mommy a étouffé la bouche de {user} avec ses cuisses pendant **{duree}**… et ce n'est pas négociable.",
    "🤐 Mommy a étouffé la bouche de {user} avec ses cuisses pendant **{duree}**. Au coin, petit chat.",
]
MSG_UNMUTE = [
    "🔊 Mommy a enlevé ses cuisses de la bouche de {user}. Ne me fais pas regretter ça.",
    "🔊 Mommy a enlevé ses cuisses de la bouche de {user}. Sois sage maintenant.",
]
MSG_WARN = [
    "⚠️ Mommy a un avertissement pour {user}. Fais attention à toi.",
    "⚠️ {user}, mommy te surveille de près. Dernier avertissement avant la fessée.",
]
MSG_KICK = [
    "👢 Mommy a mis {user} à la porte. Reviens quand tu seras sage.",
    "👢 Mommy a expulsé {user}. Réfléchis à ce que tu as fait.",
]
MSG_BAN = [
    "🔨 Mommy a mis en cage {user}. Définitivement.",
    "🔨 Mommy a mis en cage {user}. Fin de l'histoire.",
]
MSG_PURGE = [
    "🧹 Mommy a fait le ménage : **{n}** message(s) de {user} effacé(s).",
    "🧹 Mommy a nettoyé derrière {user} : **{n}** message(s) en moins.",
]

DUR_RE = re.compile(r"^\s*(\d{1,6})\s*([a-zéèû]*)\s*$", re.I)


def parse_minutes(text: str) -> Optional[int]:
    """« 10 » / « 30m » / « 2h » / « 1j » → minutes (None si invalide ou hors limites)."""
    m = DUR_RE.match(text or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    if unit in ("", "m", "min", "mins", "minute", "minutes"):
        mult = 1
    elif unit in ("h", "heure", "heures"):
        mult = 60
    elif unit in ("j", "d", "jour", "jours"):
        mult = 1440
    else:
        return None
    total = n * mult
    return total if 1 <= total <= MAX_TIMEOUT_MIN else None


def fmt_duration(minutes: int) -> str:
    d, rest = divmod(minutes, 1440)
    h, m = divmod(rest, 60)
    parts = []
    if d:
        parts.append(f"{d} jour{'s' if d > 1 else ''}")
    if h:
        parts.append(f"{h} heure{'s' if h > 1 else ''}")
    if m:
        parts.append(f"{m} minute{'s' if m > 1 else ''}")
    return " ".join(parts) or "0 minute"


def punish_block_reason(interaction: discord.Interaction, target: discord.Member) -> Optional[str]:
    """Renvoie la raison pour laquelle on ne peut pas punir cette personne, ou None si c'est OK."""
    guild = interaction.guild
    if guild is None:
        return "Cette commande ne marche que sur un serveur."
    inv = interaction.user
    if target.id == inv.id:
        return "Tu ne peux pas te punir toi-même 😏"
    if bot.user and target.id == bot.user.id:
        return "Mommy ne se punit pas toute seule 😈"
    if target.id == guild.owner_id:
        return "Impossible de punir le propriétaire du serveur."
    if inv.id != guild.owner_id and hasattr(inv, "top_role") and target.top_role >= inv.top_role:
        return "Cette personne est au même niveau que toi (ou au-dessus) dans la hiérarchie des rôles."
    me = guild.me
    if me and target.top_role >= me.top_role:
        return f"Mon rôle n'est pas assez haut : place le rôle de {BOT_NAME} au-dessus de celui de cette personne."
    return None


async def run_punishment(
    interaction: discord.Interaction, action: str, target: discord.Member,
    reason: str = "", minutes: Optional[int] = None, count: Optional[int] = None,
):
    """Vérifie les droits, exécute la sanction, la LOG, puis annonce « Mommy a … » dans le salon."""
    perms = interaction.permissions
    need = PUNISH_PERM[action]
    if not (perms.administrator or getattr(perms, need, False)):
        return await interaction.response.send_message(
            f"🚫 Il te manque la permission « {PERM_LABEL[need]} » pour ça.", ephemeral=True
        )
    block = punish_block_reason(interaction, target)
    if block:
        return await interaction.response.send_message(f"🚫 {block}", ephemeral=True)

    await interaction.response.defer(ephemeral=True, thinking=True)
    audit = f"{interaction.user} via {BOT_NAME} : {reason or 'sans raison'}"[:500]
    user = target.mention
    purged: Optional[int] = None
    try:
        if action == "mute":
            await target.timeout(timedelta(minutes=minutes), reason=audit)
            text = random.choice(MSG_MUTE).format(user=user, duree=fmt_duration(minutes))
        elif action == "unmute":
            await target.timeout(None, reason=audit)
            text = random.choice(MSG_UNMUTE).format(user=user)
        elif action == "warn":
            text = random.choice(MSG_WARN).format(user=user)
        elif action == "kick":
            await target.kick(reason=audit)
            text = random.choice(MSG_KICK).format(user=user)
        elif action == "ban":
            await target.ban(reason=audit, delete_message_seconds=0)
            text = random.choice(MSG_BAN).format(user=user)
        else:
            channel = interaction.channel
            if not hasattr(channel, "purge"):
                return await interaction.followup.send("😅 Impossible de nettoyer dans ce type de salon.", ephemeral=True)
            remaining = count or 10

            def check(m: discord.Message) -> bool:
                nonlocal remaining
                if remaining > 0 and m.author.id == target.id:
                    remaining -= 1
                    return True
                return False

            deleted = await channel.purge(limit=300, check=check, reason=audit)
            purged = len(deleted)
            text = random.choice(MSG_PURGE).format(user=user, n=purged)
    except discord.Forbidden:
        return await interaction.followup.send(
            "🚫 Discord me refuse ça : vérifie mes permissions et que mon rôle est au-dessus du sien.", ephemeral=True
        )
    except discord.HTTPException as e:
        log.warning("Punition %s échouée : %s", action, e)
        return await interaction.followup.send("😅 Discord a refusé l'action, réessaie.", ephemeral=True)

    icon, title, color = PUNISH_STYLE[action]

    # ---- LOG staff de la sanction ----
    le = discord.Embed(title=f"{icon} Sanction — {PUNISH_LABEL[action]}", color=color)
    le.set_thumbnail(url=target.display_avatar.url)
    le.add_field(name="Cible", value=f"{target.mention} (`{target.id}`)", inline=True)
    le.add_field(name="Staff", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
    le.add_field(name="Salon", value=getattr(interaction.channel, "mention", "—"), inline=True)
    if action == "mute" and minutes:
        le.add_field(name="Durée", value=fmt_duration(minutes), inline=True)
    if action == "purge":
        le.add_field(name="Messages effacés", value=str(purged or 0), inline=True)
    le.add_field(name="Raison", value=reason[:500] or "—", inline=False)
    le.timestamp = discord.utils.utcnow()
    await mod_log(interaction.guild, le)

    announce = discord.Embed(title=f"{icon} {title}", description=text, color=color)
    announce.set_thumbnail(url=target.display_avatar.url)
    if reason and action != "purge":
        announce.add_field(name="📝 Raison", value=reason[:200], inline=False)
    announce.set_footer(
        text=f"Par {interaction.user.display_name} • {BOT_NAME} 🖤",
        icon_url=interaction.user.display_avatar.url,
    )
    ping = None if action in ("kick", "ban") else target.mention
    try:
        await interaction.channel.send(content=ping, embed=announce, allowed_mentions=USER_PINGS)
        await interaction.followup.send("✅ C'est fait.", ephemeral=True)
    except (AttributeError, discord.HTTPException):
        await interaction.followup.send(embed=announce, ephemeral=True)


class PunishModal(discord.ui.Modal):
    def __init__(self, action: str, target: discord.Member):
        super().__init__(title=f"{PUNISH_LABEL[action]} · {target.display_name}"[:45], timeout=300)
        self.action, self.target = action, target
        self.duree: Optional[discord.ui.TextInput] = None
        self.nombre: Optional[discord.ui.TextInput] = None
        self.raison: Optional[discord.ui.TextInput] = None
        if action == "mute":
            self.duree = discord.ui.TextInput(label="Durée (10, 30m, 2h, 1j…)", default="10", max_length=10)
            self.add_item(self.duree)
        if action == "purge":
            self.nombre = discord.ui.TextInput(label="Nombre de messages à effacer (1 à 100)", default="10", max_length=3)
            self.add_item(self.nombre)
        else:
            self.raison = discord.ui.TextInput(
                label="Raison" if action == "warn" else "Raison (optionnel)",
                required=(action == "warn"), max_length=200, style=discord.TextStyle.paragraph,
            )
            self.add_item(self.raison)

    async def on_submit(self, interaction: discord.Interaction):
        minutes = count = None
        if self.duree is not None:
            minutes = parse_minutes(self.duree.value)
            if minutes is None:
                return await interaction.response.send_message(
                    "⏱️ Durée invalide. Exemples : `10`, `30m`, `2h`, `1j` (maximum 28 jours).", ephemeral=True
                )
        if self.nombre is not None:
            raw = self.nombre.value.strip()
            if not raw.isdigit() or not 1 <= int(raw) <= 100:
                return await interaction.response.send_message("🔢 Mets un nombre entre 1 et 100.", ephemeral=True)
            count = int(raw)
        reason = self.raison.value.strip() if self.raison is not None else ""
        await run_punishment(interaction, self.action, self.target, reason, minutes, count)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.error("Erreur du panel de punition", exc_info=error)
        send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        await send("😅 Y'a eu un bug, réessaie.", ephemeral=True)


# ---------- Actions vocales (mute micro / casque) ----------
VOICE_META = {
    "vmute": ("mute_members", "Rendre muet en vocal", "🎙️", "Muet en vocal", 0x9B6BFF),
    "deafen": ("deafen_members", "Couper le casque", "🎧", "Casque coupé", 0x6B8BFF),
    "vfree": ("mute_members", "Libérer en vocal", "🔊", "Voix rendue", 0x7ED6A5),
}
VOICE_PERM_LABEL = {"mute_members": "Rendre muets les membres", "deafen_members": "Mettre en sourdine les membres"}
MSG_VMUTE = [
    "🎙️ Mommy a bâillonné {user} en vocal {duree}. Plus un mot, petit chat.",
    "🎙️ Mommy a coupé le micro de {user} {duree}. Chut.",
]
MSG_DEAFEN = [
    "🎧 Mommy a coupé le casque de {user} {duree}. Plus rien à entendre.",
    "🎧 Mommy a bouché les oreilles de {user} {duree}. Réfléchis dans le silence.",
]
MSG_VFREE = [
    "🔊 Mommy rend la voix et le son à {user}. Sois sage, maintenant.",
    "🔊 Mommy libère {user} en vocal. Ne me fais pas regretter ça.",
]


async def run_voice_action(
    interaction: discord.Interaction, action: str, target: discord.Member,
    reason: str = "", minutes: Optional[int] = None,
):
    need, label, icon, title, color = VOICE_META[action]
    perms = interaction.permissions
    needs = ["mute_members", "deafen_members"] if action == "vfree" else [need]
    missing = [VOICE_PERM_LABEL[n] for n in needs if not (perms.administrator or getattr(perms, n, False))]
    if missing:
        return await interaction.response.send_message(f"🚫 Il te manque : « {missing[0]} ».", ephemeral=True)
    block = punish_block_reason(interaction, target)
    if block:
        return await interaction.response.send_message(f"🚫 {block}", ephemeral=True)
    guild = interaction.guild
    member = guild.get_member(target.id) or target
    if member.voice is None or member.voice.channel is None:
        return await interaction.response.send_message(
            f"🔇 {member.display_name} n'est pas en vocal (ou je ne le vois pas : active l'intent « Membres »).", ephemeral=True
        )
    await interaction.response.defer(ephemeral=True, thinking=True)
    audit = f"{interaction.user} via {BOT_NAME} : {reason or 'sans raison'}"[:500]
    user = member.mention
    duree = f"pendant **{fmt_duration(minutes)}**" if minutes else "jusqu'à nouvel ordre"
    try:
        if action == "vmute":
            await member.edit(mute=True, reason=audit)
            text = random.choice(MSG_VMUTE).format(user=user, duree=duree)
        elif action == "deafen":
            await member.edit(deafen=True, reason=audit)
            text = random.choice(MSG_DEAFEN).format(user=user, duree=duree)
        else:
            await member.edit(mute=False, deafen=False, reason=audit)
            text = random.choice(MSG_VFREE).format(user=user)
    except discord.Forbidden:
        return await interaction.followup.send(
            "🚫 Discord me refuse ça : il me faut « Rendre muets / Mettre en sourdine » et un rôle au-dessus du sien.", ephemeral=True
        )
    except discord.HTTPException as e:
        log.warning("Action vocale %s échouée : %s", action, e)
        return await interaction.followup.send("😅 Discord a refusé l'action (il a peut-être quitté le vocal).", ephemeral=True)

    kind = {"vmute": "mute", "deafen": "deaf"}.get(action)
    if action == "vfree":
        await db_run("DELETE FROM voice_timers WHERE guild_id=? AND user_id=?", (guild.id, member.id))
    elif minutes:
        await db_run(
            "INSERT OR REPLACE INTO voice_timers(guild_id,user_id,kind,until) VALUES (?,?,?,?)",
            (guild.id, member.id, kind, int(time.time()) + minutes * 60),
        )
    else:
        await db_run("DELETE FROM voice_timers WHERE guild_id=? AND user_id=? AND kind=?", (guild.id, member.id, kind))

    announce = discord.Embed(title=f"{icon} {title}", description=text, color=color)
    announce.set_thumbnail(url=member.display_avatar.url)
    if reason:
        announce.add_field(name="📝 Raison", value=reason[:200], inline=False)
    announce.set_footer(text=f"Par {interaction.user.display_name} • {BOT_NAME} 🖤", icon_url=interaction.user.display_avatar.url)
    le = discord.Embed(title=f"{icon} Sanction vocale — {title}", color=color)
    le.set_thumbnail(url=member.display_avatar.url)
    le.add_field(name="Cible", value=f"{member.mention} (`{member.id}`)", inline=True)
    le.add_field(name="Staff", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
    le.add_field(name="Durée", value=fmt_duration(minutes) if minutes else "—", inline=True)
    le.add_field(name="Raison", value=reason[:500] or "—", inline=False)
    le.timestamp = discord.utils.utcnow()
    await mod_log(guild, le)
    try:
        await interaction.channel.send(content=member.mention, embed=announce, allowed_mentions=USER_PINGS)
        await interaction.followup.send("✅ C'est fait.", ephemeral=True)
    except (AttributeError, discord.HTTPException):
        await interaction.followup.send(embed=announce, ephemeral=True)


class VoiceModal(discord.ui.Modal):
    def __init__(self, action: str, target: discord.Member):
        super().__init__(title=f"{VOICE_META[action][1]} · {target.display_name}"[:45], timeout=300)
        self.action, self.target = action, target
        self.duree = discord.ui.TextInput(
            label="Durée (10, 30m, 2h, 1j…) · vide = illimité", required=False, max_length=10,
        )
        self.raison = discord.ui.TextInput(
            label="Raison (optionnel)", required=False, max_length=200, style=discord.TextStyle.paragraph
        )
        self.add_item(self.duree)
        self.add_item(self.raison)

    async def on_submit(self, interaction: discord.Interaction):
        minutes = None
        if self.duree.value.strip():
            minutes = parse_minutes(self.duree.value)
            if minutes is None:
                return await interaction.response.send_message(
                    "⏱️ Durée invalide. Exemples : `10`, `30m`, `2h`, `1j` (maximum 28 jours).", ephemeral=True
                )
        await run_voice_action(interaction, self.action, self.target, self.raison.value.strip(), minutes)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.error("Erreur du modal vocal", exc_info=error)
        send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        await send("😅 Y'a eu un bug, réessaie.", ephemeral=True)


# ---------- Donner / retirer un rôle (depuis le panel) ----------
async def run_role_change(interaction: discord.Interaction, target: discord.Member, role: discord.Role, give: bool):
    perms = interaction.permissions
    if not (perms.administrator or perms.manage_roles):
        return await interaction.response.send_message("🚫 Il te manque la permission « Gérer les rôles ».", ephemeral=True)
    block = punish_block_reason(interaction, target)
    if block:
        return await interaction.response.send_message(f"🚫 {block}", ephemeral=True)
    guild, me, inv = interaction.guild, interaction.guild.me, interaction.user
    if role.is_default() or role.managed:
        problem = "Ce rôle ne peut pas être attribué (@everyone ou rôle géré par une intégration)."
    elif me and role >= me.top_role:
        problem = f"« {role.name} » est au-dessus de mon rôle : monte mon rôle dans la hiérarchie."
    elif inv.id != guild.owner_id and role >= inv.top_role:
        problem = f"« {role.name} » est au même niveau que ton rôle, ou au-dessus."
    else:
        problem = None
    if problem:
        return await interaction.response.send_message(f"🚫 {problem}", ephemeral=True)
    member = guild.get_member(target.id) or target
    if give and role in member.roles:
        return await interaction.response.send_message(f"😏 {member.display_name} a déjà ce rôle.", ephemeral=True)
    if not give and role not in member.roles:
        return await interaction.response.send_message(f"😏 {member.display_name} n'a pas ce rôle.", ephemeral=True)

    await interaction.response.defer(ephemeral=True, thinking=True)
    audit = f"{inv} via {BOT_NAME} : rôle {'ajouté' if give else 'retiré'}"[:500]
    try:
        if give:
            await member.add_roles(role, reason=audit)
        else:
            await member.remove_roles(role, reason=audit)
    except discord.Forbidden:
        return await interaction.followup.send(
            "🚫 Discord me refuse ça : vérifie mes permissions et ma place dans la hiérarchie.", ephemeral=True
        )
    except discord.HTTPException as e:
        log.warning("Changement de rôle échoué : %s", e)
        return await interaction.followup.send("😅 Discord a refusé l'action, réessaie.", ephemeral=True)

    if give:
        icon, title, color = "🎀", "Rôle offert", 0x7ED6A5
        text = f"🎀 Mommy a offert le rôle {role.mention} à {member.mention}. Sois digne de lui."
    else:
        icon, title, color = "✂️", "Rôle retiré", 0xFFB347
        text = f"✂️ Mommy a retiré le rôle {role.mention} à {member.mention}. Fallait être plus sage."
    announce = discord.Embed(title=f"{icon} {title}", description=text, color=color)
    announce.set_thumbnail(url=member.display_avatar.url)
    announce.set_footer(text=f"Par {inv.display_name} • {BOT_NAME} 🖤", icon_url=inv.display_avatar.url)
    le = discord.Embed(title=f"{icon} {title}", color=color)
    le.set_thumbnail(url=member.display_avatar.url)
    le.add_field(name="Cible", value=f"{member.mention} (`{member.id}`)", inline=True)
    le.add_field(name="Rôle", value=role.mention, inline=True)
    le.add_field(name="Staff", value=f"{inv.mention} (`{inv.id}`)", inline=True)
    le.timestamp = discord.utils.utcnow()
    await mod_log(guild, le)
    try:
        await interaction.channel.send(embed=announce, allowed_mentions=NO_PINGS)
        await interaction.followup.send("✅ C'est fait.", ephemeral=True)
    except (AttributeError, discord.HTTPException):
        await interaction.followup.send(embed=announce, ephemeral=True)


class RoleChangeView(discord.ui.View):
    def __init__(self, invoker_id: int, target: discord.Member, give: bool):
        super().__init__(timeout=120)
        self.invoker_id, self.target, self.give = invoker_id, target, give

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("Ce menu n'est pas pour toi 😏", ephemeral=True)
            return False
        return True

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="🎭 Choisis le rôle…", min_values=1, max_values=1)
    async def pick(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        await run_role_change(interaction, self.target, select.values[0], self.give)


# ---------- Panel ----------
def punish_panel_embed(m: discord.Member) -> discord.Embed:
    top = m.top_role.mention if m.top_role != m.guild.default_role else "Aucun"
    e = discord.Embed(
        title="🔨 Panel de modération",
        description=f"### {m.display_name}\n{m.mention} • `{m.id}`",
        color=COLOR_DARK,
    )
    e.set_thumbnail(url=m.display_avatar.url)
    e.add_field(name="📅 Compte créé", value=f"<t:{int(m.created_at.timestamp())}:R>", inline=True)
    if m.joined_at:
        e.add_field(name="📥 A rejoint", value=f"<t:{int(m.joined_at.timestamp())}:R>", inline=True)
    e.add_field(name="🎭 Rôle principal", value=top, inline=True)
    if m.is_timed_out():
        state = f"🤐 Muté, fin <t:{int(m.timed_out_until.timestamp())}:R>"
    else:
        state = "🟢 Aucune sanction en cours"
    e.add_field(name="📊 État", value=state, inline=False)
    e.add_field(
        name="🛠️ Actions",
        value=(
            "🤐 **Mute rapide** via le menu, ou personnalisé avec le bouton\n"
            "⚠️ **Avertir** • 🔊 **Unmute**\n"
            "👢 **Expulser** • 🔨 **Bannir** • 🧹 **Nettoyer**\n"
            "🎙️ **Mute voc** • 🎧 **Casque** • 🔊 **Libérer voc**\n"
            "🎀 **Donner rôle** • ✂️ **Retirer rôle**\n"
            "🔓 Pour débannir : `/punition deban`\n"
            "📜 Chaque sanction est enregistrée dans les logs."
        ),
        inline=False,
    )
    e.set_footer(text=f"Panel privé • expire dans 3 min • {BOT_NAME} 🖤")
    return e


class QuickMuteSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="🤐 Mute rapide : choisis une durée…",
            options=[
                discord.SelectOption(label="5 minutes", value="5", emoji="⏱️"),
                discord.SelectOption(label="10 minutes", value="10", emoji="⏱️"),
                discord.SelectOption(label="1 heure", value="60", emoji="⏳"),
                discord.SelectOption(label="1 jour", value="1440", emoji="📅"),
                discord.SelectOption(label="1 semaine", value="10080", emoji="🗓️"),
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await run_punishment(interaction, "mute", self.view.target, "", int(self.values[0]))


class PunitionView(discord.ui.View):
    def __init__(self, invoker_id: int, target: discord.Member):
        super().__init__(timeout=180)
        self.invoker_id, self.target = invoker_id, target
        self.origin: Optional[discord.Interaction] = None
        self.add_item(QuickMuteSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("Ce panel n'est pas pour toi 😏", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.origin:
            try:
                await self.origin.edit_original_response(view=self)
            except discord.HTTPException:
                pass

    # ligne 1 : sanctions douces
    @discord.ui.button(label="Avertir", emoji="⚠️", style=discord.ButtonStyle.primary, row=1)
    async def b_warn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PunishModal("warn", self.target))

    @discord.ui.button(label="Mute perso", emoji="🤐", style=discord.ButtonStyle.primary, row=1)
    async def b_mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PunishModal("mute", self.target))

    @discord.ui.button(label="Unmute", emoji="🔊", style=discord.ButtonStyle.success, row=1)
    async def b_unmute(self, interaction: discord.Interaction, button: discord.ui.Button):
        await run_punishment(interaction, "unmute", self.target)

    # ligne 2 : sanctions lourdes
    @discord.ui.button(label="Expulser", emoji="👢", style=discord.ButtonStyle.danger, row=2)
    async def b_kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PunishModal("kick", self.target))

    @discord.ui.button(label="Bannir", emoji="🔨", style=discord.ButtonStyle.danger, row=2)
    async def b_ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PunishModal("ban", self.target))

    @discord.ui.button(label="Nettoyer", emoji="🧹", style=discord.ButtonStyle.secondary, row=2)
    async def b_purge(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PunishModal("purge", self.target))

    # ligne 3 : vocal
    @discord.ui.button(label="Mute voc", emoji="🎙️", style=discord.ButtonStyle.primary, row=3)
    async def b_vmute(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VoiceModal("vmute", self.target))

    @discord.ui.button(label="Casque", emoji="🎧", style=discord.ButtonStyle.primary, row=3)
    async def b_deafen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VoiceModal("deafen", self.target))

    @discord.ui.button(label="Libérer voc", emoji="🔊", style=discord.ButtonStyle.success, row=3)
    async def b_vfree(self, interaction: discord.Interaction, button: discord.ui.Button):
        await run_voice_action(interaction, "vfree", self.target)

    # ligne 4 : rôles + fermer
    @discord.ui.button(label="Donner rôle", emoji="🎀", style=discord.ButtonStyle.success, row=4)
    async def b_addrole(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"Quel rôle donner à **{self.target.display_name}** ?",
            view=RoleChangeView(interaction.user.id, self.target, True), ephemeral=True,
        )

    @discord.ui.button(label="Retirer rôle", emoji="✂️", style=discord.ButtonStyle.danger, row=4)
    async def b_removerole(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"Quel rôle retirer à **{self.target.display_name}** ?",
            view=RoleChangeView(interaction.user.id, self.target, False), ephemeral=True,
        )

    @discord.ui.button(label="Fermer le panel", emoji="✖️", style=discord.ButtonStyle.secondary, row=4)
    async def b_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            embed=emb("🔨 Panel fermé", "À la prochaine, petit chat 🖤", COLOR_DARK), view=None
        )


punition_group = app_commands.Group(name="punition", description="Outils de punition du staff 🔨", guild_only=True)


@punition_group.command(name="panel", description="Ouvre le panel de punitions du staff 🔨")
@app_commands.describe(membre="La personne à punir")
async def punition_panel(interaction: discord.Interaction, membre: discord.Member):
    p = interaction.permissions
    if not (p.administrator or p.moderate_members or p.kick_members or p.ban_members or p.manage_messages
            or p.mute_members or p.deafen_members or p.manage_roles):
        return await interaction.response.send_message("🚫 Réservé au staff, petit chat 😏", ephemeral=True)
    block = punish_block_reason(interaction, membre)
    if block:
        return await interaction.response.send_message(f"🚫 {block}", ephemeral=True)
    view = PunitionView(interaction.user.id, membre)
    await interaction.response.send_message(embed=punish_panel_embed(membre), view=view, ephemeral=True)
    view.origin = interaction


async def ban_autocomplete(interaction: discord.Interaction, current: str):
    guild = interaction.guild
    if guild is None or not (interaction.permissions.administrator or interaction.permissions.ban_members):
        return []
    cur = current.lower().strip()
    out = []
    try:
        async for entry in guild.bans(limit=1000):
            u = entry.user
            hay = f"{u.name} {u.global_name or ''} {u.id}".lower()
            if cur in hay:
                out.append(app_commands.Choice(name=f"{u.global_name or u.name} ({u.id})"[:100], value=str(u.id)))
                if len(out) >= 25:
                    break
    except discord.HTTPException:
        return []
    return out


@punition_group.command(name="deban", description="Débannit quelqu'un (avec log automatique) 🔓")
@app_commands.describe(utilisateur="L'utilisateur banni (choisis dans la liste ou colle son ID)", raison="Raison (optionnel)")
@app_commands.autocomplete(utilisateur=ban_autocomplete)
async def punition_deban(interaction: discord.Interaction, utilisateur: str, raison: Optional[str] = None):
    p = interaction.permissions
    if not (p.administrator or p.ban_members):
        return await interaction.response.send_message("🚫 Il te manque la permission « Bannir des membres ».", ephemeral=True)
    m = re.search(r"\d{15,25}", utilisateur)
    if not m:
        return await interaction.response.send_message("ID invalide : choisis dans la liste ou colle l'ID.", ephemeral=True)
    guild, uid = interaction.guild, int(m.group())
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        entry = await guild.fetch_ban(discord.Object(id=uid))
    except discord.NotFound:
        return await interaction.followup.send("😏 Cette personne n'est pas bannie.", ephemeral=True)
    except discord.Forbidden:
        return await interaction.followup.send("🚫 Je n'ai pas la permission de voir / gérer les bans.", ephemeral=True)
    user = entry.user
    reason = (raison or "").strip()
    audit = f"{interaction.user} via {BOT_NAME} : {reason or 'sans raison'}"[:500]
    try:
        await guild.unban(user, reason=audit)
    except discord.Forbidden:
        return await interaction.followup.send("🚫 Il me faut la permission « Bannir des membres ».", ephemeral=True)
    except discord.HTTPException as e:
        log.warning("Deban échoué : %s", e)
        return await interaction.followup.send("😅 Discord a refusé l'action, réessaie.", ephemeral=True)

    le = discord.Embed(title="🔓 Sanction — Débannissement", color=0x7ED6A5)
    le.set_thumbnail(url=user.display_avatar.url)
    le.add_field(name="Utilisateur", value=f"{user} (`{user.id}`)", inline=True)
    le.add_field(name="Staff", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
    le.add_field(name="Raison du deban", value=reason[:500] or "—", inline=False)
    le.add_field(name="Raison du ban d'origine", value=(entry.reason or "—")[:500], inline=False)
    le.timestamp = discord.utils.utcnow()
    logged = await mod_log(guild, le)

    announce = discord.Embed(
        title="🔓 Cage ouverte",
        description=f"Mommy a ouvert la cage de **{user}**. Il/elle peut revenir… s'il/elle est sage 🖤",
        color=0x7ED6A5,
    )
    announce.set_footer(text=f"Par {interaction.user.display_name} • {BOT_NAME} 🖤", icon_url=interaction.user.display_avatar.url)
    try:
        await interaction.channel.send(embed=announce, allowed_mentions=NO_PINGS)
    except (AttributeError, discord.HTTPException):
        pass
    note = "" if logged else "\n⚠️ Aucun salon de logs configuré : utilise `/logs` pour en définir un."
    await interaction.followup.send(f"✅ **{user}** est débanni(e).{note}", ephemeral=True)


bot.tree.add_command(punition_group)


# ---------- Fin automatique des mute vocal / casque temporaires ----------
@tasks.loop(seconds=30)
async def voice_timer_loop():
    try:
        rows = await db_all("SELECT guild_id, user_id, kind, until FROM voice_timers WHERE until<=?", (int(time.time()),))
    except Exception:  # noqa: BLE001
        log.exception("voice_timer_loop : lecture impossible")
        return
    for gid, uid, kind, until in rows:
        done = "DELETE FROM voice_timers WHERE guild_id=? AND user_id=? AND kind=?"
        guild = bot.get_guild(gid)
        if guild is None:
            continue
        member = guild.get_member(uid)
        if member is None:
            await db_run(done, (gid, uid, kind))
            continue
        if member.voice is None:
            if time.time() - until > 7 * 86400:
                await db_run(done, (gid, uid, kind))
            continue
        try:
            await member.edit(**({"mute": False} if kind == "mute" else {"deafen": False}), reason="Fin de la sanction vocale")
        except discord.Forbidden:
            log.warning("Fin de sanction vocale : permission manquante sur %s", gid)
            await db_run(done, (gid, uid, kind))
            continue
        except discord.HTTPException:
            continue
        await db_run(done, (gid, uid, kind))
        le = discord.Embed(
            title="🔊 Fin de sanction vocale",
            description=f"{member.mention} : {'micro' if kind == 'mute' else 'casque'} rétabli (durée écoulée).",
            color=0x7ED6A5,
        )
        le.timestamp = discord.utils.utcnow()
        await mod_log(guild, le)


@voice_timer_loop.before_loop
async def _before_voice_timer():
    await bot.wait_until_ready()


# =====================================================================
# /test : auto-diagnostic (admin)
# =====================================================================
EXPECTED_COMMANDS = {
    "ask", "recherche", "roast", "blague", "8ball", "choisir", "kiss", "hug", "pat", "slap", "bonk", "gift",
    "marie", "mariage", "divorce", "pfc", "ship", "quiz", "blackjack", "poker", "classement", "stat",
    "style", "reset", "sync", "aide", "aideadmin", "adminpanel", "ping", "punition", "test",
    "commande", "cc", "meteo", "statu", "emoji", "envoyer", "logs", "silence", "rolereaction",
    "solde", "daily", "donner", "richesse", "eco", "ecopanel", "reglepoker", "regleblackjack", "main",
    "creersalon", "creeserveur", "info", "automod",
    "optimiser", "dev", "bienvenue", "sondage", "ticket", "annonce", "purge", "kahoot", "jeux",
    "regle", GW_CMD, "autorole", "interdit", "vocal",
}
REMOVED_COMMANDS = {"musique", "gouts", "favori", "inventaire", "stat"}


async def _t_db() -> str:
    await db_run(
        "INSERT INTO settings(guild_id, key, value) VALUES (-1,'test','ok') "
        "ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value"
    )
    rows = await db_all("SELECT value FROM settings WHERE guild_id=-1 AND key='test'")
    await db_run("DELETE FROM settings WHERE guild_id=-1 AND key='test'")
    assert rows and rows[0][0] == "ok", "relecture incorrecte"
    for table in ("history", "settings", "marriages", "marriage_members", "custom_cmds", "game_stats",
                  "voice_timers", "economy", "automod_strikes", "giveaways", "giveaway_entries", "rules_pending"):
        await db_all(f"SELECT 1 FROM {table} LIMIT 1")
    return "lecture / écriture OK"


async def _t_ai() -> str:
    out = await asyncio.wait_for(
        ask_ai([{"role": "user", "content": "Réponds uniquement : OK"}], system="Tu réponds très court.",
               max_tokens=300, temperature=0),
        timeout=30,
    )
    assert out, "réponse vide"
    return f"réponse reçue ({AI_MODEL})"


async def _t_json() -> str:
    data = await asyncio.wait_for(
        ask_json('Réponds en JSON : {"ok": true}', system="Tu réponds uniquement en JSON valide."), timeout=40
    )
    assert isinstance(data, dict), "pas un objet JSON"
    return "JSON valide (utilisé par /quiz...)"


async def _t_web() -> str:
    results = await asyncio.wait_for(asyncio.to_thread(web_search, "discord", 3), timeout=15)
    assert results, "aucun résultat"
    return f"{len(results)} résultats (utilisé par /recherche et /ask web)"


async def _t_phrases() -> str:
    assert greeting_reply("coucou ça va") and greeting_reply("bonne nuit"), "salutations"
    assert (not NAME_TRIGGER or name_called(f"{BOT_NAME} tu en penses quoi ?")) and not name_called("rien à voir ici"), \
        "détection du prénom"
    assert mommy_phrase(False) and mommy_phrase(True), "phrases mommy"
    return f"salutations, prénom « {BOT_NAME} » et {len(MOMMY_SOFT) + len(MOMMY_SPICY)} phrases mommy OK"


async def _t_actions() -> str:
    bad = []
    for name, cfg in ACTIONS.items():
        for line in cfg["lines"] + cfg.get("spicy", []):
            try:
                line.format(a="@a", b="@b")
            except (ValueError, KeyError, IndexError):
                bad.append(f"/{name}")
    assert not bad, "phrase mal formée dans " + ", ".join(sorted(set(bad)))
    return f"{len(ACTIONS)} commandes ({', '.join('/' + n for n in ACTIONS)})"


async def _t_modo() -> str:
    assert parse_minutes("10") == 10 and parse_minutes("2h") == 120 and parse_minutes("1j") == 1440, "durées"
    assert parse_minutes("abc") is None and parse_minutes("0") is None and parse_minutes("99999j") is None, "durées invalides"
    assert fmt_duration(1) == "1 minute" and fmt_duration(61) == "1 heure 1 minute", "format de durée"
    return "durées et annonces OK (le panel s'essaie avec /punition panel)"


async def _t_blackjack() -> str:
    assert bj_value([("A", "♠"), ("K", "♥")]) == 21, "blackjack naturel"
    assert bj_value([("A", "♠"), ("A", "♥"), ("9", "♦")]) == 21, "as multiples"
    assert bj_value([("K", "♠"), ("Q", "♥"), ("5", "♦")]) == 25, "dépassement"
    t = BJTable([1, 2], {1: "a", 2: "b"})
    t.status = {1: "stand", 2: "bust"}
    t.play_dealer()
    assert set(t.results) == {1, 2} and "💀" in t.results[2], "résolution de la partie"
    return "valeurs, as et résolution OK (la partie s'essaie avec /blackjack)"


async def _t_poker() -> str:
    flush = [(14, "♠"), (13, "♠"), (12, "♠"), (11, "♠"), (10, "♠")]
    pair = [(14, "♠"), (14, "♥"), (9, "♦"), (7, "♣"), (3, "♠")]
    wheel = [(14, "♠"), (2, "♥"), (3, "♦"), (4, "♣"), (5, "♠")]
    assert pk_score5(flush)[0] == 8, "quinte flush"
    assert pk_score5(pair)[0] == 1, "paire"
    assert pk_score5(wheel) == (4, 5), "quinte à l'as bas"
    assert pk_score5(flush) > pk_score5(pair), "comparaison"
    assert pk_best(pair + [(2, "♦"), (8, "♣")])[0] == 1, "meilleure main sur 7 cartes"
    return "évaluation des mains OK (la partie s'essaie avec /poker)"


async def _t_cc() -> str:
    gid, name = -1, "zz_test"
    await db_run(
        "INSERT OR REPLACE INTO custom_cmds(guild_id, name, response, created_by) VALUES (?,?,?,0)",
        (gid, name, "salut {user} sur {server}"),
    )
    got = await cc_get(gid, name)
    await db_run("DELETE FROM custom_cmds WHERE guild_id=? AND name=?", (gid, name))
    assert got == "salut {user} sur {server}", "relecture incorrecte"
    assert cc_name("!Test-1") == "test-1" and cc_name("a b") is None and cc_name("") is None, "noms"
    return "création / lecture / suppression OK (/commande, /cc, !nom)"


async def _t_stats() -> str:
    gid = -1
    await record_many(gid, "pfc", {123: "win", 456: "loss"})
    rows = await leaderboard(gid, "pfc")
    await db_run("DELETE FROM game_stats WHERE guild_id=?", (gid,))
    assert rows and rows[0][0] == 123 and rows[0][4] == POINTS["win"], "classement incorrect"
    return "enregistrement et classement OK (/classement, /stat)"


async def _t_weather_parse() -> str:
    cases = {
        "météo Lyon": "Lyon", "Quelle est la météo à Paris aujourd'hui ?": "Paris",
        "météo à Fort-de-France": "Fort-de-France", "il fait quoi comme météo à Nice demain": "Nice",
        "la météo": "", "la météo est nulle aujourd'hui": None, "bonjour": None,
        "la météo à Paris demain matin": "Paris", "météo à La Rochelle ce week-end": "La Rochelle",
        "la météo ici est horrible": None, "météo 2024": "",
    }
    for text, expected in cases.items():
        got = weather_request(text)
        assert got == expected, f"« {text} » → {got!r} au lieu de {expected!r}"
    return f"{len(cases)} phrases analysées correctement"


async def _t_weather_net() -> str:
    embed = await asyncio.wait_for(fetch_weather("Paris"), timeout=15)
    return f"données reçues ({embed.title})"


async def _t_commands() -> str:
    names = {c.name for c in bot.tree.get_commands()}
    missing, extra = EXPECTED_COMMANDS - names, REMOVED_COMMANDS & names
    assert not missing, "manquantes : " + ", ".join(sorted(missing))
    assert not extra, "à retirer : " + ", ".join(sorted(extra))
    return f"{len(names)} commandes enregistrées"


def _t_perms(channel, me) -> tuple[str, str]:
    p = channel.permissions_for(me)
    base = {
        "send_messages": "Envoyer des messages", "embed_links": "Intégrer des liens",
        "add_reactions": "Ajouter des réactions", "read_message_history": "Voir les anciens messages",
    }
    modo = {
        "moderate_members": "Exclure temporairement des membres", "kick_members": "Expulser des membres",
        "ban_members": "Bannir des membres", "manage_messages": "Gérer les messages",
        "mute_members": "Rendre muets les membres", "deafen_members": "Mettre en sourdine les membres",
        "manage_roles": "Gérer les rôles",
    }
    miss_base = [label for k, label in base.items() if not getattr(p, k)]
    miss_modo = [label for k, label in modo.items() if not getattr(p, k)]
    if miss_base:
        return "fail", "manque : " + ", ".join(miss_base)
    if miss_modo:
        return "warn", "modération limitée, il manque : " + ", ".join(miss_modo)
    return "ok", "toutes les permissions nécessaires sont là"


async def _t_logs(guild: discord.Guild) -> str:
    cid = int(await get_setting(guild.id, "log_channel", "0") or 0)
    assert cid, "aucun salon de logs : utilise /logs salon:#ton-salon"
    ch = guild.get_channel(cid)
    assert ch is not None, "le salon de logs configuré n'existe plus"
    p = ch.permissions_for(guild.me)
    assert p.send_messages and p.embed_links, f"permissions manquantes dans #{ch.name}"
    return f"salon <#{cid}> prêt (sanctions + commandes)"


@bot.tree.command(name="test", description="(admin) Vérifie que tout fonctionne ✅")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
async def test(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    checks = [
        ("Base de données", "fail", _t_db),
        ("IA (texte)", "fail", _t_ai),
        ("IA (JSON)", "fail", _t_json),
        ("Recherche web", "warn", _t_web),
        ("Salutations / prénom / phrases", "fail", _t_phrases),
        ("Actions sociales", "fail", _t_actions),
        ("Modération (/punition)", "fail", _t_modo),
        ("Blackjack", "fail", _t_blackjack),
        ("Poker", "fail", _t_poker),
        ("Stats et classement", "fail", _t_stats),
        ("Commandes perso", "fail", _t_cc),
        ("Météo (analyse du texte)", "fail", _t_weather_parse),
        ("Météo (service Open-Meteo)", "warn", _t_weather_net),
        ("Commandes enregistrées", "fail", _t_commands),
        ("Salon de logs", "warn", lambda: _t_logs(interaction.guild)),
    ]
    icon = {"ok": "✅", "warn": "⚠️", "fail": "❌"}
    lines, worst = [], "ok"
    for name, level, fn in checks:
        t0 = time.perf_counter()
        try:
            detail, status = await fn(), "ok"
        except Exception as e:  # noqa: BLE001 : on veut tout afficher
            detail, status = f"{type(e).__name__} : {str(e)[:120] or 'erreur'}", level
        dt = time.perf_counter() - t0
        lines.append(f"{icon[status]} **{name}** — {detail} *({dt:.1f}s)*")
        if status == "fail" or (status == "warn" and worst == "ok"):
            worst = status

    status, detail = _t_perms(interaction.channel, interaction.guild.me)
    lines.append(f"{icon[status]} **Permissions du bot ici** — {detail}")
    if status == "fail" or (status == "warn" and worst == "ok"):
        worst = status
    intent_ok = bot.intents.message_content
    lines.append(
        f"{'✅' if intent_ok else '❌'} **Intent contenu des messages** — "
        + ("activé dans le code (vérifie aussi le Developer Portal)" if intent_ok else "désactivé")
    )
    lines.append(f"✅ **Connexion Discord** — latence {bot.latency * 1000:.0f} ms")

    verdict = {
        "ok": "Tout est bon 🖤", "warn": "Ça marche, avec quelques réserves ⚠️", "fail": "Il y a des soucis ❌",
    }[worst if intent_ok else "fail"]
    color = {"ok": COLOR_PURPLE, "warn": COLOR_PINK, "fail": COLOR_DARK}[worst]
    await interaction.followup.send(embed=emb(f"🧪 Auto-diagnostic — {verdict}", "\n".join(lines)[:4000], color), ephemeral=True)


# =====================================================================
# PANEL ADMIN : /adminpanel (toutes les commandes admin au même endroit)
#   Les actions faites via les boutons / menus sont aussi tracées dans les logs.
# =====================================================================
ADMIN_TOGGLES = [
    ("reactions", "Réactions", True),
    ("spontane", "Spontané", False),
    ("salutations", "Salutations", True),
    ("nom", "Prénom", True),
    ("automod", "Auto-modération", False),
]


async def admin_panel_embed(guild: discord.Guild) -> discord.Embed:
    gid = guild.id
    onoff = lambda b: "on" if b else "off"  # noqa: E731
    flags = {k: await get_flag(gid, k, d) for k, _, d in ADMIN_TOGGLES}
    cid = int(await get_setting(gid, "log_channel", "0") or 0)
    try:
        until = int(float(await get_setting(gid, "silence_until", "0")))
    except ValueError:
        until = 0
    e = emb("🛠️ Panel admin", "Tout le staff admin au même endroit. Les boutons du haut changent les réglages en direct.", COLOR_DARK)
    e.add_field(
        name="⚙️ Réglages",
        value="\n".join(f"{label} : **{onoff(flags[k])}**" for k, label, _ in ADMIN_TOGGLES),
        inline=True,
    )
    e.add_field(name="🎭 Style", value=STYLES[await get_style(gid)][0], inline=True)
    e.add_field(name="📜 Logs", value=f"<#{cid}>" if cid else "Désactivés", inline=True)
    e.add_field(name="🤫 Silence", value=f"Jusqu'à <t:{until}:R>" if until > time.time() else "Inactif", inline=True)
    e.set_footer(text=f"Panel privé • expire dans 5 min • {BOT_NAME} 🖤")
    return e


class AdminStyleSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="🎭 Changer mon style…",
            options=[discord.SelectOption(label=label, value=key) for key, (label, _) in STYLES.items()],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        await style_cmd.callback(interaction, app_commands.Choice(name=STYLES[key][0], value=key))
        spawn(log_cmd(interaction, "adminpanel › style", f"`style` : {STYLES[key][0]}"))


class AdminLogSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="📜 Choisir le salon de logs…", channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1, row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.values[0].id)
        await logs_cmd.callback(interaction, channel, False)
        spawn(log_cmd(interaction, "adminpanel › logs", f"`salon` : {getattr(channel, 'mention', '—')}"))


class ToggleBtn(discord.ui.Button):
    def __init__(self, key: str, label: str, state: bool):
        super().__init__(row=2)
        self.key, self.base, self.state = key, label, state
        self._refresh()

    def _refresh(self):
        self.label = f"{self.base} : {'on' if self.state else 'off'}"
        self.style = discord.ButtonStyle.success if self.state else discord.ButtonStyle.secondary

    async def callback(self, interaction: discord.Interaction):
        self.state = not self.state
        await set_flag(interaction.guild_id, self.key, self.state)
        self._refresh()
        await interaction.response.edit_message(embed=await admin_panel_embed(interaction.guild), view=self.view)
        spawn(log_cmd(interaction, "adminpanel › réglage", f"`{self.base}` : {'on' if self.state else 'off'}"))


class SilenceModal(discord.ui.Modal, title="🤫 Mode silence"):
    duree = discord.ui.TextInput(label="Durée (10, 30m, 2h, 1j) ou off", max_length=10)

    async def on_submit(self, interaction: discord.Interaction):
        await silence.callback(interaction, self.duree.value)
        spawn(log_cmd(interaction, "adminpanel › silence", f"`durée` : {self.duree.value}"))


class SendModal(discord.ui.Modal, title="✉️ Envoyer un message"):
    message = discord.ui.TextInput(label="Message (\\n = retour à la ligne)", style=discord.TextStyle.paragraph, max_length=2000)
    pseudo = discord.ui.TextInput(
        label="Pseudo (vide = anonyme, bot = moi)", required=False, max_length=32,
        placeholder="Vide = Anonyme • « bot » = j'envoie avec l'identité du bot",
    )
    avatar = discord.ui.TextInput(label="URL d'avatar https (optionnel)", required=False, max_length=300)

    async def on_submit(self, interaction: discord.Interaction):
        pseudo = self.pseudo.value.strip()
        ident = app_commands.Choice(name="", value="bot" if pseudo.lower() == "bot" else "perso" if pseudo else "anon")
        # /envoyer écrit déjà son propre log détaillé
        await envoyer.callback(
            interaction, self.message.value, ident, pseudo or None, None, self.avatar.value.strip() or None
        )


class CCAddModal(discord.ui.Modal, title="🛠️ Nouvelle commande perso"):
    nom = discord.ui.TextInput(label="Nom (sans espace)", max_length=32)
    reponse = discord.ui.TextInput(label="Réponse ({user}, {server}, \\n)", style=discord.TextStyle.paragraph, max_length=1500)

    async def on_submit(self, interaction: discord.Interaction):
        await cc_add.callback(interaction, self.nom.value, self.reponse.value)
        spawn(log_cmd(interaction, "adminpanel › commande ajouter", f"`nom` : {self.nom.value}"))


class CCDelModal(discord.ui.Modal, title="🗑️ Supprimer une commande perso"):
    nom = discord.ui.TextInput(label="Nom de la commande", max_length=32)

    async def on_submit(self, interaction: discord.Interaction):
        await cc_remove.callback(interaction, self.nom.value)
        spawn(log_cmd(interaction, "adminpanel › commande supprimer", f"`nom` : {self.nom.value}"))


class _OwnerView(discord.ui.View):
    def __init__(self, invoker_id: int):
        super().__init__(timeout=120)
        self.invoker_id = invoker_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("Ce menu n'est pas pour toi 😏", ephemeral=True)
            return False
        return True


class PickMemberView(_OwnerView):
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="👤 Qui veux-tu punir ?", min_values=1, max_values=1)
    async def pick(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        m = select.values[0]
        if not isinstance(m, discord.Member):
            return await interaction.response.send_message("Cette personne n'est pas sur le serveur.", ephemeral=True)
        await punition_panel.callback(interaction, m)
        spawn(log_cmd(interaction, "adminpanel › punition panel", f"`membre` : {m.mention}"))


class PickRolesView(_OwnerView):
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="🎭 Rôles à proposer (25 max)…", min_values=1, max_values=25)
    async def pick(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        mentions = " ".join(r.mention for r in select.values)
        await rolereaction.callback(interaction, mentions)
        spawn(log_cmd(interaction, "adminpanel › rolereaction", f"`roles` : {mentions}"))


class AdminPanel(discord.ui.View):
    def __init__(self, invoker_id: int, states: dict):
        super().__init__(timeout=300)
        self.invoker_id = invoker_id
        self.origin: Optional[discord.Interaction] = None
        self.add_item(AdminStyleSelect())
        self.add_item(AdminLogSelect())
        for key, label, _ in ADMIN_TOGGLES:
            self.add_item(ToggleBtn(key, label, states[key]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("Ce panel n'est pas pour toi 😏", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.origin:
            try:
                await self.origin.edit_original_response(view=self)
            except discord.HTTPException:
                pass

    # ligne 3
    @discord.ui.button(label="Silence", emoji="🤫", style=discord.ButtonStyle.primary, row=3)
    async def b_silence(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SilenceModal())

    @discord.ui.button(label="Envoyer", emoji="✉️", style=discord.ButtonStyle.primary, row=3)
    async def b_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SendModal())

    @discord.ui.button(label="Punition", emoji="🔨", style=discord.ButtonStyle.danger, row=3)
    async def b_punish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Qui veux-tu punir ?", view=PickMemberView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label="Panneau de rôles", emoji="🎭", style=discord.ButtonStyle.primary, row=3)
    async def b_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Quels rôles proposer ? Le panneau sera posté **dans ce salon**.",
            view=PickRolesView(interaction.user.id), ephemeral=True,
        )

    @discord.ui.button(label="Couper les logs", emoji="📜", style=discord.ButtonStyle.secondary, row=3)
    async def b_logsoff(self, interaction: discord.Interaction, button: discord.ui.Button):
        await logs_cmd.callback(interaction, None, True)  # trace la coupure avant de désactiver

    # ligne 4
    @discord.ui.button(label="Créer cmd", emoji="🛠️", style=discord.ButtonStyle.success, row=4)
    async def b_ccadd(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CCAddModal())

    @discord.ui.button(label="Suppr. cmd", emoji="🗑️", style=discord.ButtonStyle.danger, row=4)
    async def b_ccdel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CCDelModal())

    @discord.ui.button(label="Liste cmds", emoji="📋", style=discord.ButtonStyle.secondary, row=4)
    async def b_cclist(self, interaction: discord.Interaction, button: discord.ui.Button):
        await cc_list.callback(interaction)
        spawn(log_cmd(interaction, "adminpanel › commande liste"))

    @discord.ui.button(label="Test", emoji="🧪", style=discord.ButtonStyle.secondary, row=4)
    async def b_test(self, interaction: discord.Interaction, button: discord.ui.Button):
        await test.callback(interaction)
        spawn(log_cmd(interaction, "adminpanel › test"))

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary, row=4)
    async def b_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(embed=emb("🛠️ Panel fermé", "À la prochaine 🖤", COLOR_DARK), view=None)


# =====================================================================
# ÉCONOMIE : porte-monnaie, /daily, /donner, /richesse, mises blackjack & poker
#   Activée par un admin (/eco config actif:True ou /ecopanel). Mise optionnelle dans les jeux (mise:0 = sans mise).
# =====================================================================
COIN = "🪙"
ECO_DEFAULTS = {"start": 1000, "daily": 200, "min_bet": 10, "max_bet": 5000}
ECO_LABELS = {
    "start": "Solde de départ", "daily": "Bonus /daily", "min_bet": "Mise minimum", "max_bet": "Mise maximum",
}
ECO_MAX = 1_000_000_000


async def eco_on(gid: Optional[int]) -> bool:
    return await get_flag(gid, "eco", False)


async def eco_cfg(gid: Optional[int], key: str) -> int:
    raw = await get_setting(gid, f"eco_{key}", str(ECO_DEFAULTS[key]))
    try:
        return int(raw)
    except ValueError:
        return ECO_DEFAULTS[key]


async def eco_balance(gid: int, uid: int) -> int:
    """Solde du joueur (le compte est créé avec le solde de départ au premier accès)."""
    rows = await db_all("SELECT balance FROM economy WHERE guild_id=? AND user_id=?", (gid, uid))
    if rows:
        return rows[0][0]
    start = await eco_cfg(gid, "start")
    await db_run("INSERT OR IGNORE INTO economy(guild_id,user_id,balance) VALUES (?,?,?)", (gid, uid, start))
    rows = await db_all("SELECT balance FROM economy WHERE guild_id=? AND user_id=?", (gid, uid))
    return rows[0][0]


async def eco_charge(gid: int, uid: int, amount: int) -> bool:
    """Retire `amount` pièces si le solde suffit (atomique). False si pas assez."""
    await eco_balance(gid, uid)
    cur = await bot.db.execute(
        "UPDATE economy SET balance=balance-? WHERE guild_id=? AND user_id=? AND balance>=?",
        (amount, gid, uid, amount),
    )
    await bot.db.commit()
    return cur.rowcount == 1


async def eco_add(gid: int, uid: int, amount: int):
    if amount <= 0 or uid <= 0:
        return
    await eco_balance(gid, uid)
    await db_run("UPDATE economy SET balance=balance+? WHERE guild_id=? AND user_id=?", (amount, gid, uid))


async def eco_remove(gid: int, uid: int, amount: int):
    await eco_balance(gid, uid)
    await db_run("UPDATE economy SET balance=MAX(balance-?,0) WHERE guild_id=? AND user_id=?", (amount, gid, uid))


async def bet_error(gid: Optional[int], uid: int, mise: int) -> Optional[str]:
    """None si la mise est valide (ou nulle), sinon le message d'erreur à afficher."""
    if mise <= 0:
        return None
    if not gid or not await eco_on(gid):
        return f"💸 L'économie est désactivée sur ce serveur : joue sans mise (`mise:0`)."
    lo, hi = await eco_cfg(gid, "min_bet"), await eco_cfg(gid, "max_bet")
    if not lo <= mise <= hi:
        return f"💸 La mise doit être comprise entre **{lo}** et **{hi}** {COIN}."
    bal = await eco_balance(gid, uid)
    if bal < mise:
        return f"💸 Il te faut **{mise}** {COIN}, tu n'en as que **{bal}**."
    return None


async def collect_bets(gid: Optional[int], players: dict, bet: int) -> tuple[dict, list]:
    """Prélève la mise de chaque joueur au lancement. Renvoie (ceux qui ont payé, ceux refusés)."""
    if bet <= 0 or not gid:
        return dict(players), []
    paid, refused = {}, []
    for uid, name in players.items():
        if await eco_charge(gid, uid, bet):
            paid[uid] = name
        else:
            refused.append(uid)
    return paid, refused


@bot.tree.command(name="solde", description="Ton porte-monnaie 🪙")
@app_commands.describe(membre="Voir le solde d'un autre (optionnel)")
@app_commands.guild_only()
async def solde(interaction: discord.Interaction, membre: Optional[discord.Member] = None):
    if not await eco_on(interaction.guild_id):
        return await interaction.response.send_message("💸 L'économie n'est pas activée sur ce serveur.", ephemeral=True)
    target = membre or interaction.user
    if target.bot:
        return await interaction.response.send_message("Les bots n'ont pas de porte-monnaie 🤖", ephemeral=True)
    bal = await eco_balance(interaction.guild_id, target.id)
    await interaction.response.send_message(
        embed=emb(f"👛 {target.display_name}", f"**{bal}** {COIN}", COLOR_PINK)
    )


@bot.tree.command(name="daily", description="Récupère ton bonus quotidien 🎁")
@app_commands.guild_only()
async def daily(interaction: discord.Interaction):
    gid, uid = interaction.guild_id, interaction.user.id
    if not await eco_on(gid):
        return await interaction.response.send_message("💸 L'économie n'est pas activée sur ce serveur.", ephemeral=True)
    amount = await eco_cfg(gid, "daily")
    now = int(time.time())
    await eco_balance(gid, uid)
    cur = await bot.db.execute(
        "UPDATE economy SET balance=balance+?, last_daily=? WHERE guild_id=? AND user_id=? AND last_daily<=?",
        (amount, now, gid, uid, now - 86400),
    )
    await bot.db.commit()
    if cur.rowcount == 0:
        rows = await db_all("SELECT last_daily FROM economy WHERE guild_id=? AND user_id=?", (gid, uid))
        nxt = rows[0][0] + 86400
        return await interaction.response.send_message(
            f"⏳ Déjà récupéré, petit chat. Reviens <t:{nxt}:R> 😏", ephemeral=True
        )
    bal = await eco_balance(gid, uid)
    await interaction.response.send_message(
        embed=emb("🎁 Bonus quotidien", f"+**{amount}** {COIN} pour toi. Solde : **{bal}** {COIN}", COLOR_PINK)
    )


@bot.tree.command(name="donner", description="Donne des pièces à quelqu'un 💸")
@app_commands.describe(membre="Le destinataire", montant="Combien de pièces")
@app_commands.guild_only()
async def donner(interaction: discord.Interaction, membre: discord.Member, montant: app_commands.Range[int, 1, ECO_MAX]):
    gid = interaction.guild_id
    if not await eco_on(gid):
        return await interaction.response.send_message("💸 L'économie n'est pas activée sur ce serveur.", ephemeral=True)
    if membre.bot or membre.id == interaction.user.id:
        return await interaction.response.send_message("Choisis quelqu'un d'autre que toi (et pas un bot) 😏", ephemeral=True)
    if not await eco_charge(gid, interaction.user.id, montant):
        bal = await eco_balance(gid, interaction.user.id)
        return await interaction.response.send_message(f"💸 Tu n'as que **{bal}** {COIN}.", ephemeral=True)
    await eco_add(gid, membre.id, montant)
    await interaction.response.send_message(
        f"💸 {interaction.user.mention} offre **{montant}** {COIN} à {membre.mention}. Quelle générosité 🖤",
        allowed_mentions=USER_PINGS,
    )


@bot.tree.command(name="richesse", description="Les plus riches du serveur 💰")
@app_commands.guild_only()
async def richesse(interaction: discord.Interaction):
    if not await eco_on(interaction.guild_id):
        return await interaction.response.send_message("💸 L'économie n'est pas activée sur ce serveur.", ephemeral=True)
    rows = await db_all(
        "SELECT user_id, balance FROM economy WHERE guild_id=? ORDER BY balance DESC, user_id ASC LIMIT 10",
        (interaction.guild_id,),
    )
    if not rows:
        return await interaction.response.send_message("Personne n'a encore de pièces 😏", ephemeral=True)
    medals = ["🥇", "🥈", "🥉"]
    lines = [f"{medals[i] if i < 3 else f'`#{i + 1}`'} <@{u}> — **{b}** {COIN}" for i, (u, b) in enumerate(rows)]
    await interaction.response.send_message(
        embed=emb("💰 Les plus riches", "\n".join(lines), COLOR_PURPLE), allowed_mentions=NO_PINGS
    )


# ---------- Commandes admin : /eco config|donner|retirer|reset ----------
eco_group = app_commands.Group(
    name="eco", description="(admin) Gère l'économie du serveur 💰",
    guild_only=True, default_permissions=discord.Permissions(administrator=True),
)


@eco_group.command(name="config", description="Active l'économie et règle les montants")
@app_commands.describe(
    actif="Activer / désactiver l'économie", depart="Solde de départ", daily="Montant du /daily",
    mise_min="Mise minimum", mise_max="Mise maximum",
)
@admin_only
async def eco_config(
    interaction: discord.Interaction, actif: Optional[bool] = None,
    depart: Optional[app_commands.Range[int, 0, ECO_MAX]] = None,
    daily: Optional[app_commands.Range[int, 0, ECO_MAX]] = None,
    mise_min: Optional[app_commands.Range[int, 1, ECO_MAX]] = None,
    mise_max: Optional[app_commands.Range[int, 1, ECO_MAX]] = None,
):
    gid = interaction.guild_id
    lo = mise_min if mise_min is not None else await eco_cfg(gid, "min_bet")
    hi = mise_max if mise_max is not None else await eco_cfg(gid, "max_bet")
    if lo > hi:
        return await interaction.response.send_message("🚫 La mise minimum dépasse la mise maximum.", ephemeral=True)
    if actif is not None:
        await set_flag(gid, "eco", actif)
    for key, val in (("start", depart), ("daily", daily), ("min_bet", mise_min), ("max_bet", mise_max)):
        if val is not None:
            await set_setting(gid, f"eco_{key}", str(val))
    await interaction.response.send_message(embed=await eco_panel_embed(interaction.guild), ephemeral=True)


@eco_group.command(name="donner", description="Donne des pièces à un membre")
@app_commands.describe(membre="Le membre", montant="Combien")
@admin_only
async def eco_give(interaction: discord.Interaction, membre: discord.Member, montant: app_commands.Range[int, 1, ECO_MAX]):
    if membre.bot:
        return await interaction.response.send_message("Les bots n'ont pas de porte-monnaie 🤖", ephemeral=True)
    await eco_add(interaction.guild_id, membre.id, montant)
    bal = await eco_balance(interaction.guild_id, membre.id)
    await interaction.response.send_message(f"✅ +{montant} {COIN} pour {membre.mention} (solde : {bal}).", ephemeral=True)


@eco_group.command(name="retirer", description="Retire des pièces à un membre")
@app_commands.describe(membre="Le membre", montant="Combien")
@admin_only
async def eco_take(interaction: discord.Interaction, membre: discord.Member, montant: app_commands.Range[int, 1, ECO_MAX]):
    if membre.bot:
        return await interaction.response.send_message("Les bots n'ont pas de porte-monnaie 🤖", ephemeral=True)
    await eco_remove(interaction.guild_id, membre.id, montant)
    bal = await eco_balance(interaction.guild_id, membre.id)
    await interaction.response.send_message(f"✅ −{montant} {COIN} pour {membre.mention} (solde : {bal}).", ephemeral=True)


@eco_group.command(name="reset", description="Remet un membre au solde de départ")
@app_commands.describe(membre="Le membre")
@admin_only
async def eco_reset(interaction: discord.Interaction, membre: discord.Member):
    start = await eco_cfg(interaction.guild_id, "start")
    await eco_balance(interaction.guild_id, membre.id)
    await db_run("UPDATE economy SET balance=? WHERE guild_id=? AND user_id=?", (start, interaction.guild_id, membre.id))
    await interaction.response.send_message(f"✅ {membre.mention} repart avec {start} {COIN}.", ephemeral=True)


bot.tree.add_command(eco_group)


# ---------- Panneau admin de l'économie ----------
async def eco_panel_embed(guild: discord.Guild) -> discord.Embed:
    gid = guild.id
    rows = await db_all("SELECT COUNT(*), COALESCE(SUM(balance),0) FROM economy WHERE guild_id=?", (gid,))
    n, total = rows[0]
    e = emb("💰 Panel économie", "L'argent du serveur et les mises du blackjack / poker.", COLOR_DARK)
    e.add_field(name="État", value="🟢 Activée" if await eco_on(gid) else "🔴 Désactivée", inline=True)
    for key, label in ECO_LABELS.items():
        e.add_field(name=label, value=f"{await eco_cfg(gid, key)} {COIN}", inline=True)
    e.add_field(name="📈 En circulation", value=f"{total} {COIN} • {n} joueur(s)", inline=False)
    e.set_footer(text=f"Panel privé • expire dans 5 min • {BOT_NAME} 🖤")
    return e


class EcoConfigModal(discord.ui.Modal, title="⚙️ Réglages de l'économie"):
    def __init__(self, panel: "EcoPanel", current: dict):
        super().__init__(timeout=300)
        self.panel = panel
        self.fields: dict[str, discord.ui.TextInput] = {}
        for key, label in ECO_LABELS.items():
            ti = discord.ui.TextInput(label=label, default=str(current[key]), max_length=10)
            self.fields[key] = ti
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction):
        vals = {}
        for key, ti in self.fields.items():
            raw = ti.value.strip()
            if not raw.isdigit() or int(raw) > ECO_MAX:
                return await interaction.response.send_message(f"🔢 « {ECO_LABELS[key]} » : nombre entier invalide.", ephemeral=True)
            vals[key] = int(raw)
        if vals["min_bet"] < 1 or vals["min_bet"] > vals["max_bet"]:
            return await interaction.response.send_message("🔢 La mise minimum doit être ≥ 1 et ≤ à la mise maximum.", ephemeral=True)
        for key, val in vals.items():
            await set_setting(interaction.guild_id, f"eco_{key}", str(val))
        await interaction.response.send_message("✅ Réglages enregistrés.", ephemeral=True)
        spawn(log_cmd(interaction, "ecopanel › réglages", ", ".join(f"`{k}` : {v}" for k, v in vals.items())))
        await self.panel.refresh()


class EcoAmountModal(discord.ui.Modal):
    def __init__(self, panel: "EcoPanel", target, give: bool):
        super().__init__(title=f"{'Donner à' if give else 'Retirer à'} {target.display_name}"[:45], timeout=300)
        self.panel, self.target, self.give = panel, target, give
        self.montant = discord.ui.TextInput(label="Montant", max_length=10)
        self.add_item(self.montant)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.montant.value.strip()
        if not raw.isdigit() or not 1 <= int(raw) <= ECO_MAX:
            return await interaction.response.send_message("🔢 Mets un nombre entier positif.", ephemeral=True)
        amount, gid = int(raw), interaction.guild_id
        if self.give:
            await eco_add(gid, self.target.id, amount)
        else:
            await eco_remove(gid, self.target.id, amount)
        bal = await eco_balance(gid, self.target.id)
        sign = "+" if self.give else "−"
        await interaction.response.send_message(
            f"✅ {sign}{amount} {COIN} pour {self.target.mention} (solde : {bal}).", ephemeral=True
        )
        spawn(log_cmd(interaction, "ecopanel › " + ("donner" if self.give else "retirer"),
                      f"`membre` : {self.target.mention}\n`montant` : {amount}"))
        await self.panel.refresh()


class PickEcoMemberView(_OwnerView):
    def __init__(self, invoker_id: int, give: bool, panel: "EcoPanel"):
        super().__init__(invoker_id)
        self.give, self.panel = give, panel

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="👤 Choisis le membre…", min_values=1, max_values=1)
    async def pick(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        m = select.values[0]
        if getattr(m, "bot", False):
            return await interaction.response.send_message("Les bots n'ont pas de porte-monnaie 🤖", ephemeral=True)
        await interaction.response.send_modal(EcoAmountModal(self.panel, m, self.give))


class EcoPanel(_OwnerView):
    def __init__(self, invoker_id: int, guild: discord.Guild):
        super().__init__(invoker_id)
        self.timeout = 300
        self.guild = guild
        self.origin: Optional[discord.Interaction] = None

    async def refresh(self):
        if self.origin:
            try:
                await self.origin.edit_original_response(embed=await eco_panel_embed(self.guild), view=self)
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.origin:
            try:
                await self.origin.edit_original_response(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Activer / désactiver", emoji="🔁", style=discord.ButtonStyle.primary, row=0)
    async def b_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid = interaction.guild_id
        on = not await eco_on(gid)
        await set_flag(gid, "eco", on)
        await interaction.response.edit_message(embed=await eco_panel_embed(interaction.guild), view=self)
        spawn(log_cmd(interaction, "ecopanel › économie", f"État : {'on' if on else 'off'}"))

    @discord.ui.button(label="Réglages", emoji="⚙️", style=discord.ButtonStyle.secondary, row=0)
    async def b_cfg(self, interaction: discord.Interaction, button: discord.ui.Button):
        cur = {k: await eco_cfg(interaction.guild_id, k) for k in ECO_DEFAULTS}
        await interaction.response.send_modal(EcoConfigModal(self, cur))

    @discord.ui.button(label="Donner", emoji="➕", style=discord.ButtonStyle.success, row=1)
    async def b_give(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "À qui donner des pièces ?", view=PickEcoMemberView(interaction.user.id, True, self), ephemeral=True
        )

    @discord.ui.button(label="Retirer", emoji="➖", style=discord.ButtonStyle.danger, row=1)
    async def b_take(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "À qui retirer des pièces ?", view=PickEcoMemberView(interaction.user.id, False, self), ephemeral=True
        )

    @discord.ui.button(label="Classement", emoji="💰", style=discord.ButtonStyle.secondary, row=1)
    async def b_top(self, interaction: discord.Interaction, button: discord.ui.Button):
        rows = await db_all(
            "SELECT user_id, balance FROM economy WHERE guild_id=? ORDER BY balance DESC LIMIT 10", (interaction.guild_id,)
        )
        txt = "\n".join(f"`#{i + 1}` <@{u}> — **{b}** {COIN}" for i, (u, b) in enumerate(rows)) or "Personne pour l'instant."
        await interaction.response.send_message(embed=emb("💰 Top 10", txt, COLOR_PURPLE), ephemeral=True, allowed_mentions=NO_PINGS)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary, row=2)
    async def b_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(embed=emb("💰 Panel fermé", "À la prochaine 🖤", COLOR_DARK), view=None)


@bot.tree.command(name="ecopanel", description="(admin) Panneau de l'économie et des mises 💰")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def ecopanel(interaction: discord.Interaction):
    view = EcoPanel(interaction.user.id, interaction.guild)
    await interaction.response.send_message(embed=await eco_panel_embed(interaction.guild), view=view, ephemeral=True)
    view.origin = interaction


# =====================================================================
# RÈGLES : /reglepoker, /regleblackjack  +  /main (classement des mains de poker)
# =====================================================================
async def _bet_rules(gid: Optional[int]) -> str:
    if not gid or not await eco_on(gid):
        return "Les mises sont désactivées sur ce serveur (un admin peut les activer avec `/ecopanel`)."
    lo, hi = await eco_cfg(gid, "min_bet"), await eco_cfg(gid, "max_bet")
    return f"Mise optionnelle via `mise:` (de **{lo}** à **{hi}** {COIN}). `mise:0` = partie pour le fun."


@bot.tree.command(name="regleblackjack", description="Les règles du blackjack 🃏")
async def regleblackjack(interaction: discord.Interaction):
    e = emb("🃏 Règles du blackjack", "Battre Mika sans dépasser **21**.", COLOR_PURPLE)
    e.add_field(
        name="🎯 But",
        value="Avoir une main plus proche de 21 que celle de Mika, sans la dépasser (sinon tu sautes et tu perds).",
        inline=False,
    )
    e.add_field(
        name="🂡 Valeur des cartes",
        value="Cartes 2 à 10 : leur valeur • Valet / Dame / Roi : 10 • As : 11 ou 1 (le mieux pour toi).",
        inline=False,
    )
    e.add_field(
        name="▶️ Déroulé",
        value=(
            "Chacun reçoit 2 cartes, Mika en montre une seule.\n"
            "À ton tour : **Tirer** (une carte de plus) ou **Rester**. À 21 pile, tu restes automatiquement.\n"
            f"Tu as **{BJ_TURN_TIMEOUT} s** par tour : sinon tu restes (et tu es marqué AFK).\n"
            "Ensuite Mika tire jusqu'à atteindre **17** minimum."
        ),
        inline=False,
    )
    e.add_field(
        name="🏆 Résultat",
        value=(
            "Blackjack naturel (As + figure/10 d'entrée) : bat tout, sauf un blackjack de Mika (égalité).\n"
            "Si Mika saute, tous les joueurs encore en jeu gagnent. Même total = égalité.\n"
            "Pas de doublement ni de séparation dans cette version."
        ),
        inline=False,
    )
    e.add_field(
        name="💰 Mises",
        value=(
            f"{await _bet_rules(interaction.guild_id)}\n"
            "Victoire : **×2** • Blackjack naturel : **×2,5** • Égalité : mise rendue • Défaite : mise perdue.\n"
            "À la table, l'hôte fixe la mise : elle est prélevée au lancement."
        ),
        inline=False,
    )
    e.add_field(name="👥 Modes", value=f"`/blackjack` solo contre Mika, ou table ouverte (jusqu'à {BJ_MAX_PLAYERS} joueurs).", inline=False)
    await interaction.response.send_message(embed=e)


@bot.tree.command(name="reglepoker", description="Les règles du poker 🂡")
async def reglepoker(interaction: discord.Interaction):
    e = emb("♠️ Règles du poker (Texas Hold'em simplifié)", "Fais la meilleure main de 5 cartes.", COLOR_PURPLE)
    e.add_field(
        name="▶️ Déroulé",
        value=(
            "Chaque joueur (et Mika) reçoit 2 cartes privées ; 5 cartes communes sont révélées en 3 temps.\n"
            "4 tours : **Pré-flop**, **Flop** (3 cartes), **Turn** (4e), **River** (5e).\n"
            f"À chaque tour : **Suivre** ou **Se coucher** ({PK_TURN_TIMEOUT} s, sinon tu es couché et marqué AFK). "
            "Avec une mise active, **Relancer** ajoute des pièces au pot (2 relances max par tour) :\n "
            "tous les autres doivent re-décider (suivre la relance ou se coucher). "
            "Le bouton **Mes cartes** te montre ta main en privé."
        ),
        inline=False,
    )
    e.add_field(
        name="🏁 Abattage",
        value=(
            "Il y a abattage après la River : la meilleure combinaison de 5 cartes parmi tes 2 cartes + les 5 communes gagne.\n"
            "Si tout le monde se couche sauf un, il gagne direct. Mika peut aussi se coucher 😏\n"
            "Égalité parfaite : le pot est partagé. Voir `/main` pour l'ordre des combinaisons."
        ),
        inline=False,
    )
    e.add_field(
        name="💰 Mises",
        value=(
            f"{await _bet_rules(interaction.guild_id)}\n"
            f"Chaque joueur mise une fois ; **{BOT_NAME} mise autant que les autres** (la maison). "
            "Le pot est donc `mise × (joueurs + Mika)` : le gagnant le remporte, les gagnants à égalité le partagent. "
            f"Si c'est Mika qui gagne, elle empoche tout. Main annulée (tout le monde se couche) : mises rendues."
            "Avec une mise : bouton **Relancer** (2 max par tour)."
        ),
        inline=False,
    )
    e.add_field(name="👥 Joueurs", value=f"`/poker` : table ouverte, de 1 à {PK_MAX_PLAYERS} joueurs contre Mika.", inline=False)
    await interaction.response.send_message(embed=e)


POKER_EXAMPLES = [  # du plus fort au plus faible (même ordre que PK_HANDS inversé)
    ("Quinte flush", "A♠ K♠ Q♠ J♠ 10♠", "5 cartes qui se suivent, de la même couleur"),
    ("Carré", "9♠ 9♥ 9♦ 9♣ K♠", "4 cartes de même valeur"),
    ("Full", "Q♠ Q♥ Q♦ 7♣ 7♠", "un brelan + une paire"),
    ("Couleur", "A♥ J♥ 8♥ 5♥ 2♥", "5 cartes de la même couleur"),
    ("Quinte", "10♠ 9♥ 8♦ 7♣ 6♠", "5 cartes qui se suivent (l'as peut valoir 1 : A-2-3-4-5)"),
    ("Brelan", "8♠ 8♥ 8♦ K♣ 4♠", "3 cartes de même valeur"),
    ("Double paire", "J♠ J♥ 4♦ 4♣ A♠", "deux paires"),
    ("Paire", "10♠ 10♥ A♦ 7♣ 3♠", "2 cartes de même valeur"),
    ("Carte haute", "A♠ J♥ 8♦ 5♣ 2♠", "rien du tout : la plus haute carte compte"),
]


@bot.tree.command(name="main", description="Le classement des mains de poker, de la meilleure à la pire 🏆")
async def main_cmd(interaction: discord.Interaction):
    lines = [
        f"**{i}. {name}** — `{ex}`\n└ _{desc}_" for i, (name, ex, desc) in enumerate(POKER_EXAMPLES, start=1)
    ]
    e = emb("🏆 Les mains au poker", "\n".join(lines), COLOR_PINK)
    e.add_field(
        name="⚖️ Départage",
        value="À combinaison égale, la valeur des cartes décide (ex : paire de rois > paire de dames), puis les cartes restantes.",
        inline=False,
    )
    await interaction.response.send_message(embed=e)


# =====================================================================
# CRÉATION DE SALONS : /creersalon (texte, vocal ou catégorie)
# =====================================================================
@bot.tree.command(name="creersalon", description="(staff) Crée un salon texte, vocal ou une catégorie ➕")
@app_commands.describe(
    genre="Ce que tu veux créer", nom="Le nom (100 caractères max)",
    categorie="La catégorie où le ranger (texte / vocal)",
    prive="Caché pour tout le monde sauf le staff (et le rôle choisi)", role="Rôle qui peut voir le salon si privé",
    sujet="Description du salon (texte)", limite="Places max (vocal, 0 = illimité)", nsfw="Salon 18+ (texte)",
)
@app_commands.choices(genre=[
    app_commands.Choice(name="💬 Salon texte", value="texte"),
    app_commands.Choice(name="🔊 Salon vocal", value="vocal"),
    app_commands.Choice(name="📁 Catégorie", value="categorie"),
])
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.has_permissions(manage_channels=True)
async def creersalon(
    interaction: discord.Interaction, genre: app_commands.Choice[str], nom: app_commands.Range[str, 1, 100],
    categorie: Optional[discord.CategoryChannel] = None, prive: bool = False, role: Optional[discord.Role] = None,
    sujet: Optional[app_commands.Range[str, 1, 1024]] = None, limite: app_commands.Range[int, 0, 99] = 0,
    nsfw: bool = False,
):
    guild = interaction.guild
    if not guild.me.guild_permissions.manage_channels:
        return await interaction.response.send_message("🚫 Il me manque la permission « Gérer les salons ».", ephemeral=True)
    if len(guild.channels) >= 500:
        return await interaction.response.send_message("🚫 Le serveur a atteint la limite de 500 salons.", ephemeral=True)
    ow: dict = {}
    if prive:
        ow[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
        ow[guild.me] = discord.PermissionOverwrite(view_channel=True)
        if role is not None and not role.is_default():
            ow[role] = discord.PermissionOverwrite(view_channel=True)
    reason = f"/creersalon par {interaction.user}"[:500]
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        if genre.value == "texte":
            ch = await guild.create_text_channel(
                nom, category=categorie, topic=sujet, nsfw=nsfw, overwrites=ow, reason=reason
            )
        elif genre.value == "vocal":
            ch = await guild.create_voice_channel(
                nom, category=categorie, user_limit=limite, overwrites=ow, reason=reason
            )
        else:
            ch = await guild.create_category(nom, overwrites=ow, reason=reason)
    except discord.Forbidden:
        return await interaction.followup.send("🚫 Discord me refuse ça : vérifie mes permissions.", ephemeral=True)
    except discord.HTTPException as e:
        log.warning("/creersalon : %s", e)
        return await interaction.followup.send(f"😅 Discord a refusé : {str(e.text)[:150]}", ephemeral=True)
    lock = " 🔒" if prive else ""
    await interaction.followup.send(f"✅ Créé : {ch.mention}{lock}", ephemeral=True)


# =====================================================================
# /info : statistiques du serveur
# =====================================================================
@bot.tree.command(name="info", description="Les stats du serveur 📊")
@app_commands.guild_only()
async def info(interaction: discord.Interaction):
    g = interaction.guild
    bots = sum(1 for m in g.members if m.bot)
    humans = (g.member_count or len(g.members)) - bots
    online = sum(1 for m in g.members if not m.bot and m.status != discord.Status.offline)
    e = emb(f"📊 {g.name}", g.description, COLOR_PURPLE)
    if g.icon:
        e.set_thumbnail(url=g.icon.url)
    if g.banner:
        e.set_image(url=g.banner.url)
    e.add_field(name="👑 Propriétaire", value=f"<@{g.owner_id}>", inline=True)
    e.add_field(name="📅 Créé", value=f"<t:{int(g.created_at.timestamp())}:D>\n<t:{int(g.created_at.timestamp())}:R>", inline=True)
    e.add_field(name="🆔 ID", value=f"`{g.id}`", inline=True)
    e.add_field(name="👥 Membres", value=f"**{humans}** humains • **{bots}** bots\n🟢 {online} en ligne", inline=True)
    e.add_field(
        name="📺 Salons",
        value=(
            f"💬 {len(g.text_channels)} texte • 🔊 {len(g.voice_channels)} vocal\n"
            f"📁 {len(g.categories)} catégories • 🧵 {len(g.forums)} forums"
        ),
        inline=True,
    )
    e.add_field(name="🎭 Rôles", value=str(max(len(g.roles) - 1, 0)), inline=True)
    e.add_field(name="😀 Emojis", value=f"{len(g.emojis)}/{g.emoji_limit}", inline=True)
    e.add_field(name="🚀 Boosts", value=f"Niveau {g.premium_tier} • {g.premium_subscription_count} boost(s)", inline=True)
    e.add_field(name="🛡️ Vérification", value=str(g.verification_level).replace("_", " ").capitalize(), inline=True)
    if await eco_on(g.id):
        rows = await db_all("SELECT COUNT(*), COALESCE(SUM(balance),0) FROM economy WHERE guild_id=?", (g.id,))
        e.add_field(name="💰 Économie", value=f"{rows[0][1]} {COIN} • {rows[0][0]} joueur(s)", inline=True)
    if await get_flag(g.id, "automod", False):
        e.add_field(name="🤖 Auto-modération", value="Activée", inline=True)
    await interaction.response.send_message(embed=e)


# =====================================================================
# /creeserveur : l'IA conçoit un serveur complet (rôles, catégories, salons, permissions)
#   Sécurité : aperçu + confirmation obligatoires, rien n'est supprimé, aucun rôle Administrateur n'est créé.
# =====================================================================
def _perm(**kw) -> discord.Permissions:
    return discord.Permissions(**kw)


_BASE_PERMS = dict(
    view_channel=True, send_messages=True, read_message_history=True, add_reactions=True, embed_links=True,
    attach_files=True, use_external_emojis=True, connect=True, speak=True, use_voice_activation=True,
    change_nickname=True,
)
ROLE_PRESETS = {
    "membre": _perm(**_BASE_PERMS),
    "vip": _perm(**_BASE_PERMS, create_public_threads=True),
    "staff": _perm(
        **_BASE_PERMS, manage_messages=True, kick_members=True, moderate_members=True, mute_members=True,
        deafen_members=True, move_members=True, manage_nicknames=True,
    ),
    "muet": _perm(view_channel=True, read_message_history=True),
}
CREESERVEUR_SYSTEM = (
    "Tu es un architecte de serveurs Discord expérimenté. Tu réponds uniquement en JSON valide, sans texte autour."
)
ACCES = {"public", "lecture", "staff", "roles"}


def _clean_name(s, maxlen: int = 100) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()[:maxlen]


def normalize_plan(data: dict, max_channels: int, max_roles: int) -> dict:
    """Nettoie / borne le plan renvoyé par l'IA (on ne lui fait jamais confiance aveuglément)."""
    roles, seen = [], set()
    for r in (data.get("roles") or [])[:max_roles]:
        if not isinstance(r, dict):
            continue
        name = _clean_name(r.get("nom"))
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        preset = str(r.get("permissions", "membre")).lower()
        if preset not in ROLE_PRESETS:
            preset = "membre"
        hexa = str(r.get("couleur", "")).lstrip("#")
        try:
            color = int(hexa, 16) if len(hexa) == 6 else 0
        except ValueError:
            color = 0
        roles.append({"nom": name, "couleur": color, "preset": preset, "affiche": bool(r.get("affiche", preset == "staff"))})
    cats, total = [], 0
    for c in (data.get("categories") or [])[:10]:
        if not isinstance(c, dict):
            continue
        chans = []
        for s in c.get("salons") or []:
            if total >= max_channels:
                break
            if not isinstance(s, dict):
                continue
            name = _clean_name(s.get("nom"))
            if not name:
                continue
            kind = "vocal" if str(s.get("type", "texte")).lower().startswith("voc") else "texte"
            acces = str(s.get("acces", "public")).lower()
            if acces not in ACCES:
                acces = "public"
            if kind == "texte":
                name = name.lower().replace(" ", "-")
            chans.append({
                "nom": name, "type": kind, "acces": acces,
                "sujet": _clean_name(s.get("sujet"), 200) if kind == "texte" else "",
                "roles": [_clean_name(x, 100) for x in (s.get("roles") or []) if isinstance(x, str)][:5],
            })
            total += 1
        if chans:
            cats.append({"nom": _clean_name(c.get("nom")) or "Salons", "salons": chans})
    if not cats:
        raise ValueError("plan vide")
    return {"roles": roles, "categories": cats, "total": total}


def plan_embed(plan: dict, theme: str, compact: bool = False) -> discord.Embed:
    """Aperçu du serveur. Version aérée par défaut ; `compact` = ancienne mise en page (si l'embed est trop gros)."""
    gap = 0 if compact else 1
    nb_r, nb_c, nb_s = len(plan["roles"]), len(plan["categories"]), plan["total"]
    e = emb(
        "🏗️ Aperçu du serveur",
        airy([
            f"🎨 Thème : **{theme[:100]}**",
            f"🎭 **{nb_r}** rôle(s)  •  📁 **{nb_c}** catégorie(s)  •  💬 **{nb_s}** salon(s)",
            "🔒 **Rien n'est créé tant que tu n'as pas confirmé.**\n_Rien n'est supprimé non plus._",
        ], gap),
        COLOR_PINK,
    )
    tail = "" if compact else "\n" + SP
    if plan["roles"]:
        txt = fit_lines([f"▫️ **{r['nom']}** — {r['preset']}" for r in plan["roles"]], 1000, gap)
        e.add_field(name="🎭 Rôles", value=txt + tail, inline=False)
    cats = plan["categories"][:10]
    for c in cats:
        lines = []
        for s_ in c["salons"]:
            icon = "🔊" if s_["type"] == "vocal" else "💬"
            tag = "🔒" if s_["acces"] in ("staff", "roles") else "📖" if s_["acces"] == "lecture" else ""
            lines.append(f"{icon}{tag}  {s_['nom']}")
        e.add_field(
            name=f"📁 {c['nom']}"[:256],
            value=fit_lines(lines, 1000, gap) + tail,
            inline=compact,
        )
    if len(plan["categories"]) > len(cats):
        e.add_field(name=SP, value=f"_… et {len(plan['categories']) - len(cats)} autre(s) catégorie(s)_", inline=False)
    e.set_footer(text="💬 texte  •  🔊 vocal  •  🔒 privé  •  📖 lecture seule")
    if not compact and len(e) > 5800:  # limite Discord = 6000 caractères par embed
        return plan_embed(plan, theme, compact=True)
    return e


def build_overwrites(guild, acces, kind, staff_roles, listed) -> dict:
    ow: dict = {}
    if acces == "public":
        return ow
    if acces == "lecture":
        if kind == "texte":
            ow[guild.default_role] = discord.PermissionOverwrite(send_messages=False, create_public_threads=False)
            for r in staff_roles:
                ow[r] = discord.PermissionOverwrite(send_messages=True)
        return ow
    ow[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
    for r in (staff_roles if acces == "staff" else listed):
        ow[r] = discord.PermissionOverwrite(view_channel=True)
    if guild.me:
        ow[guild.me] = discord.PermissionOverwrite(view_channel=True)
    return ow


async def build_server(guild: discord.Guild, plan: dict, invoker: discord.abc.User, stats: dict):
    """Crée rôles, catégories et salons. `stats` est mis à jour au fil de l'eau (Forbidden remonte à l'appelant)."""
    reason = f"/creeserveur par {invoker}"[:500]
    by_name = {r.name.lower(): r for r in guild.roles if not r.is_default()}
    staff_roles = []
    for r in plan["roles"]:
        role = by_name.get(r["nom"].lower())
        if role is None:
            kw = dict(name=r["nom"], colour=discord.Colour(r["couleur"]), hoist=r["affiche"], mentionable=False, reason=reason)
            try:
                role = await guild.create_role(permissions=ROLE_PRESETS[r["preset"]], **kw)
            except discord.Forbidden:  # je n'ai pas moi-même ces permissions : on crée le rôle sans permissions
                role = await guild.create_role(permissions=discord.Permissions.none(), **kw)
                stats["errors"].append(f"Rôle « {r['nom']} » créé sans permissions (il me les manque).")
            stats["roles"] += 1
            by_name[r["nom"].lower()] = role
            await asyncio.sleep(0.3)
        if r["preset"] == "staff":
            staff_roles.append(role)
    for c in plan["categories"]:
        try:
            cat = await guild.create_category(c["nom"], reason=reason)
        except discord.Forbidden:
            raise
        except discord.HTTPException as e:
            stats["errors"].append(f"Catégorie « {c['nom']} » : {str(e.text)[:60]}")
            continue
        stats["cats"] += 1
        await asyncio.sleep(0.3)
        for s in c["salons"]:
            listed = [by_name[x.lower()] for x in s["roles"] if x.lower() in by_name]
            ow = build_overwrites(guild, s["acces"], s["type"], staff_roles, listed)
            try:
                if s["type"] == "vocal":
                    await guild.create_voice_channel(s["nom"], category=cat, overwrites=ow, reason=reason)
                else:
                    await guild.create_text_channel(
                        s["nom"], category=cat, topic=s["sujet"] or None, overwrites=ow, reason=reason
                    )
                stats["chans"] += 1
            except discord.Forbidden:
                raise
            except discord.HTTPException as e:
                stats["errors"].append(f"Salon « {s['nom']} » : {str(e.text)[:60]}")
            await asyncio.sleep(0.3)


class ServerPlanView(discord.ui.View):
    def __init__(self, invoker_id: int, plan: dict, theme: str):
        super().__init__(timeout=180)
        self.invoker_id, self.plan, self.theme = invoker_id, plan, theme
        self.running = False
        self.origin: Optional[discord.Interaction] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("Ce menu n'est pas pour toi 😏", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.running or not self.origin:
            return
        try:
            await self.origin.edit_original_response(
                embed=emb("⌛ Aperçu expiré", "Relance `/creeserveur` si tu veux réessayer.", COLOR_DARK), view=None
            )
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Créer le serveur", emoji="✅", style=discord.ButtonStyle.success)
    async def ok(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.running:
            return await interaction.response.send_message("C'est déjà en cours 😏", ephemeral=True)
        self.running = True
        self.stop()
        await interaction.response.edit_message(
            embed=emb("⏳ Construction en cours…", "Je crée les rôles et les salons, ça peut prendre une minute.", COLOR_PURPLE),
            view=None,
        )
        guild = interaction.guild
        stats = {"roles": 0, "cats": 0, "chans": 0, "errors": []}
        try:
            await build_server(guild, self.plan, interaction.user, stats)
        except discord.Forbidden:
            stats["errors"].append("Permissions manquantes (« Gérer les salons » / « Gérer les rôles ») : construction interrompue.")
        except Exception:  # noqa: BLE001
            log.exception("/creeserveur")
            stats["errors"].append("Erreur inattendue : construction interrompue.")
        desc = f"🎭 **{stats['roles']}** rôle(s) • 📁 **{stats['cats']}** catégorie(s) • 💬 **{stats['chans']}** salon(s) créés."
        if stats["errors"]:
            desc += "\n\n⚠️ " + "\n⚠️ ".join(stats["errors"][:6])
        done = emb("🏗️ Serveur construit" if not stats["errors"] else "🏗️ Construction terminée (avec réserves)", desc, COLOR_PINK)
        try:
            await interaction.edit_original_response(embed=done, view=None)
        except discord.HTTPException:
            pass
        le = discord.Embed(title="🏗️ /creeserveur", color=COLOR_PURPLE)
        le.add_field(name="Admin", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
        le.add_field(name="Thème", value=self.theme[:200], inline=True)
        le.add_field(name="Résultat", value=desc[:1000], inline=False)
        le.timestamp = discord.utils.utcnow()
        await mod_log(guild, le)

    @discord.ui.button(label="Annuler", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(embed=emb("✖️ Annulé", "Rien n'a été créé.", COLOR_DARK), view=None)


@bot.tree.command(name="creeserveur", description="(admin) L'IA génère un serveur complet : rôles, salons, permissions 🏗️")
@app_commands.describe(
    theme="L'ambiance / le thème (ex : serveur gaming FR, communauté d'artistes, serveur d'étude…)",
    salons="Nombre de salons à créer (5 à 40)", roles="Nombre de rôles à créer (1 à 12)",
)
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@ai_cd()
async def creeserveur(
    interaction: discord.Interaction, theme: app_commands.Range[str, 3, 200],
    salons: app_commands.Range[int, 5, 40] = 15, roles: app_commands.Range[int, 1, 12] = 5,
):
    guild = interaction.guild
    mp = guild.me.guild_permissions
    if not (mp.manage_channels and mp.manage_roles):
        return await interaction.response.send_message(
            "🚫 Il me faut « Gérer les salons » et « Gérer les rôles » pour construire un serveur.", ephemeral=True
        )
    if len(guild.channels) + salons + 10 > 500 or len(guild.roles) + roles > 250:
        return await interaction.response.send_message("🚫 Pas assez de place sur ce serveur (limites Discord).", ephemeral=True)
    prompt = (
        f"Conçois la structure d'un serveur Discord sur le thème : {theme}.\n"
        f"Contraintes : exactement {roles} rôles et environ {salons} salons au total (texte + vocal), répartis dans "
        "3 à 8 catégories logiques (accueil, discussion, vocal, staff…). Noms courts, en français, avec un emoji au "
        "début des catégories si ça colle au thème. Noms de salons texte en minuscules avec des tirets.\n"
        'Rôles : "permissions" ∈ membre | vip | staff | muet ; "couleur" au format #RRGGBB.\n'
        'Salons : "type" ∈ texte | vocal ; "acces" ∈ public | lecture | staff | roles '
        '("lecture" = tout le monde lit mais seul le staff écrit ; "roles" = réservé aux rôles listés dans "roles").\n'
        "Prévois un salon de règles en lecture seule, et un salon réservé au staff s'il y a un rôle staff.\n"
        'JSON attendu : {"roles":[{"nom":"","couleur":"#RRGGBB","permissions":"membre","affiche":false}],'
        '"categories":[{"nom":"","salons":[{"nom":"","type":"texte","sujet":"max 80 caractères","acces":"public","roles":[]}]}]}'
    )
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        data = await ask_json(prompt, system=CREESERVEUR_SYSTEM, max_tokens=4500)
        plan = normalize_plan(data, salons, roles)
    except Exception as e:  # noqa: BLE001
        return await interaction.followup.send(fail_msg(e), ephemeral=True)
    view = ServerPlanView(interaction.user.id, plan, theme)
    await interaction.followup.send(embed=plan_embed(plan, theme), view=view, ephemeral=True)
    view.origin = interaction


# =====================================================================
# AUTO-MODÉRATION : suppression automatique + sanctions progressives (activables / désactivables)
#   /automod config|mot|pardon  (ou le bouton « Auto-modération » du /adminpanel)
#   Le staff (admin, gérer les messages, exclure des membres) n'est jamais sanctionné.
# =====================================================================
AM_RULES = [  # (clé du réglage, libellé, valeur par défaut)
    ("am_spam", "Anti-spam (5 messages en 6 s)", True),
    ("am_liens", "Invitations Discord", True),
    ("am_mentions", "Mentions de masse (5+)", True),
    ("am_majuscules", "Majuscules abusives", False),
    ("am_mots", "Mots interdits", True),
    ("am_insulte_bot", "Insultes envers le bot", True),
]
AM_LADDER = [0, 0, 5, 30, 360]  # minutes de mute selon le n° d'infraction (1 = avertissement seulement)
AM_DECAY = 24 * 3600            # les infractions sont remises à zéro après 24 h sans récidive
AM_MAX_WORDS = 100
INVITE_RE = re.compile(r"(?:discord\.gg|discord(?:app)?\.com/invite|dsc\.gg)/[\w-]+", re.I)
_am_hist: dict = defaultdict(lambda: deque(maxlen=8))

# ---------- Insultes envers le bot ----------
_BOT_INSULTS_STRONG = (
    "connard", "connasse", "salope", "pute", "encule", "enculee", "fdp", "ntm", "nique", "tg", "batard", "batarde",
    "abruti", "abrutie", "cretin", "cretine", "ordure", "bouffon", "bouffonne", "pouffiasse", "garce", "tocard",
    "tocarde", "ferme ta gueule", "ta gueule", "va te faire foutre", "va te faire enculer", "va chier",
    "bot de merde", "sale bot", "sous merde", "merdique", "degueulasse",
)
BOT_INSULT_STRONG_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in sorted(_BOT_INSULTS_STRONG, key=len, reverse=True)) + r")\b"
)
BOT_INSULT_SOFT_RE = re.compile(
    r"\b(?:t es|tu es|tu)\s+(?:(?:vraiment|trop|tellement|completement|si|bien|super)\s+)?"
    r"(?:nul|nulle|naze|inutile|pourri|pourrie|debile|stupide|idiot|idiote|bete|con|conne)\b"
)
BOT_ADDRESS_RE = re.compile(r"\b(?:ce|le|ton|cette|la|sale|espece de) bot\b")


def insults_bot(message: discord.Message) -> bool:
    t = plain(message.content)
    if not t:
        return False
    if any(u.id != bot.user.id for u in message.mentions):  # vise sans doute quelqu'un d'autre
        return False
    addressed = (
        bot.user in message.mentions or is_reply_to_bot(message)
        or name_called(message.content) or bool(BOT_ADDRESS_RE.search(t))
    )
    return addressed and bool(BOT_INSULT_STRONG_RE.search(t) or BOT_INSULT_SOFT_RE.search(t))


async def am_words(gid: int) -> list[str]:
    try:
        data = json.loads(await get_setting(gid, "automod_words", "[]"))
        return [str(w) for w in data] if isinstance(data, list) else []
    except ValueError:
        return []


async def am_detect(message: discord.Message) -> Optional[str]:
    gid, c = message.guild.id, message.content
    if await get_flag(gid, "am_spam", True):
        dq = _am_hist[(gid, message.author.id)]
        now = time.time()
        dq.append(now)
        if len(dq) >= 5 and now - dq[-5] <= 6:
            dq.clear()
            return "spam"
    if await get_flag(gid, "am_liens", True) and INVITE_RE.search(c):
        return "invitation Discord"
    if await get_flag(gid, "am_mentions", True) and (
        len(message.mentions) + len(message.role_mentions) >= 5 or message.mention_everyone
    ):
        return "mentions de masse"
    if await get_flag(gid, "am_majuscules", False):
        letters = [ch for ch in c if ch.isalpha()]
        if len(letters) >= 15 and sum(ch.isupper() for ch in letters) / len(letters) > 0.7:
            return "trop de majuscules"
            
    if await get_flag(gid, "am_insulte_bot", True) and insults_bot(message):
        return "insulte envers le bot"
        
    if await get_flag(gid, "am_mots", True):
        words = await am_words(gid)
        if words:
            t = f" {plain(c)} "
            if any(plain(w) and f" {plain(w)} " in t for w in words):
                return "mot interdit"
    return None


async def automod_check(message: discord.Message) -> bool:
    """True si le message a été traité (donc inutile de continuer à le lire)."""
    g, m = message.guild, message.author
    if g is None or not isinstance(m, discord.Member) or not await get_flag(g.id, "automod", False):
        return False
    p = m.guild_permissions
    if p.administrator or p.manage_messages or p.moderate_members:
        return False
    try:
        reason = await am_detect(message)
    except Exception:  # noqa: BLE001
        log.exception("automod : détection")
        return False
    if not reason:
        return False
    try:
        await message.delete()
        deleted = True
    except discord.HTTPException:
        deleted = False

    now = int(time.time())
    rows = await db_all("SELECT strikes, last_at FROM automod_strikes WHERE guild_id=? AND user_id=?", (g.id, m.id))
    strikes = (rows[0][0] if rows and now - rows[0][1] < AM_DECAY else 0) + 1
    await db_run(
        "INSERT INTO automod_strikes(guild_id,user_id,strikes,last_at) VALUES (?,?,?,?) "
        "ON CONFLICT(guild_id,user_id) DO UPDATE SET strikes=excluded.strikes, last_at=excluded.last_at",
        (g.id, m.id, strikes, now),
    )
    minutes = AM_LADDER[min(strikes, len(AM_LADDER) - 1)] if await get_flag(g.id, "automod_sanctions", True) else 0
    sanction = f"Avertissement n°{strikes}"
    if minutes:
        me = g.me
        if (me and m.top_role >= me.top_role) or m.id == g.owner_id:
            sanction = f"Infraction n°{strikes} (mute impossible : hiérarchie des rôles)"
        else:
            try:
                await m.timeout(timedelta(minutes=minutes), reason=f"Auto-modération : {reason}")
                sanction = f"Infraction n°{strikes} • mute **{fmt_duration(minutes)}**"
            except discord.HTTPException:
                sanction = f"Infraction n°{strikes} (mute impossible : permissions)"
                
    if reason == "insulte envers le bot":
        text = f"{m.mention}, on ne parle pas comme ça à mommy 😈\n{sanction}. Sois poli(e) 🖤"
    else:
        text = f"{m.mention}, mommy a tout vu : **{reason}**.\n{sanction}. Sois sage 🖤"
    ann = discord.Embed(title="🛡️ Auto-modération", description=text, color=0xFFB347)
    try:
        await message.channel.send(embed=ann, allowed_mentions=USER_PINGS, delete_after=15)
    except discord.HTTPException:
        pass
    le = discord.Embed(title="🛡️ Auto-modération", color=0xFFB347)
    le.set_thumbnail(url=m.display_avatar.url)
    le.add_field(name="Membre", value=f"{m.mention} (`{m.id}`)", inline=True)
    le.add_field(name="Salon", value=getattr(message.channel, "mention", "—"), inline=True)
    le.add_field(name="Motif", value=reason, inline=True)
    le.add_field(name="Sanction", value=sanction, inline=False)
    le.add_field(name="Message supprimé", value="Oui" if deleted else "Non (permission manquante)", inline=True)
    if reason != "mot interdit" and message.content:
        le.add_field(name="Contenu", value=message.content[:500], inline=False)
    le.timestamp = discord.utils.utcnow()
    await mod_log(g, le)
    return True


async def automod_embed(gid: int) -> discord.Embed:
    on = await get_flag(gid, "automod", False)
    sanc = await get_flag(gid, "automod_sanctions", True)
    e = emb(
        "🛡️ Auto-modération",
        f"État : **{'🟢 activée' if on else '🔴 désactivée'}**\n"
        f"Sanctions automatiques : **{'oui (mute progressif)' if sanc else 'non (suppression + avertissement)'}**",
        COLOR_DARK,
    )
    lines = [f"{'✅' if await get_flag(gid, k, d) else '❌'} {label}" for k, label, d in AM_RULES]
    e.add_field(name="Règles", value="\n".join(lines), inline=False)
    e.add_field(
        name="📈 Échelle des sanctions",
        value="1ʳᵉ infraction : avertissement • 2ᵉ : mute 5 min • 3ᵉ : mute 30 min • 4ᵉ et + : mute 6 h\n"
              "Remise à zéro après 24 h sans récidive. Jamais de kick / ban automatique.",
        inline=False,
    )
    e.add_field(name="🚫 Mots interdits", value=f"{len(await am_words(gid))} mot(s) — gérés avec `/automod mot`", inline=False)
    return e


automod_group = app_commands.Group(
    name="automod", description="(admin) Auto-modération 🛡️",
    guild_only=True, default_permissions=discord.Permissions(administrator=True),
)


@automod_group.command(name="config", description="Active / règle l'auto-modération")
@app_commands.describe(
    actif="Activer / désactiver l'auto-modération",
    sanctions="Sanctions automatiques (mute progressif). Sinon : suppression + avertissement seulement",
    spam="Anti-spam", liens="Invitations Discord", mentions="Mentions de masse",
    majuscules="Majuscules abusives", mots="Mots interdits", insultes_bot="Insultes envers le bot",
)
@admin_only
async def automod_config(
    interaction: discord.Interaction, actif: Optional[bool] = None, sanctions: Optional[bool] = None,
    spam: Optional[bool] = None, liens: Optional[bool] = None, mentions: Optional[bool] = None,
    majuscules: Optional[bool] = None, mots: Optional[bool] = None, insultes_bot: Optional[bool] = None,
):
    gid = interaction.guild_id
    for key, val in (
        ("automod", actif), ("automod_sanctions", sanctions), ("am_spam", spam), ("am_liens", liens),
        ("am_mentions", mentions), ("am_majuscules", majuscules), ("am_mots", mots),
        ("am_insulte_bot", insultes_bot),
    ):
        if val is not None:
            await set_flag(gid, key, val)
    await interaction.response.send_message(embed=await automod_embed(gid), ephemeral=True)


@automod_group.command(name="mot", description="Gère la liste des mots interdits")
@app_commands.describe(action="Ajouter, retirer ou lister", mot="Le mot ou l'expression (pour ajouter / retirer)")
@app_commands.choices(action=[
    app_commands.Choice(name="➕ Ajouter", value="ajouter"),
    app_commands.Choice(name="➖ Retirer", value="retirer"),
    app_commands.Choice(name="📋 Lister", value="liste"),
])
@admin_only
async def automod_word(
    interaction: discord.Interaction, action: app_commands.Choice[str], mot: Optional[app_commands.Range[str, 2, 40]] = None
):
    gid = interaction.guild_id
    words = await am_words(gid)
    if action.value == "liste":
        txt = ", ".join(f"||{w}||" for w in words) or "Aucun mot interdit."
        return await interaction.response.send_message(f"🚫 **Mots interdits** : {txt}"[:1900], ephemeral=True)
    if not mot or not plain(mot):
        return await interaction.response.send_message("Donne un mot (`mot:`).", ephemeral=True)
    key = plain(mot)
    if action.value == "ajouter":
        if any(plain(w) == key for w in words):
            return await interaction.response.send_message("Déjà dans la liste 😏", ephemeral=True)
        if len(words) >= AM_MAX_WORDS:
            return await interaction.response.send_message(f"Liste pleine ({AM_MAX_WORDS} max).", ephemeral=True)
        words.append(mot.strip())
        msg = f"✅ Ajouté : ||{mot.strip()}||"
    else:
        rest = [w for w in words if plain(w) != key]
        if len(rest) == len(words):
            return await interaction.response.send_message("Ce mot n'est pas dans la liste.", ephemeral=True)
        words, msg = rest, "✅ Retiré."
    await set_setting(gid, "automod_words", json.dumps(words, ensure_ascii=False))
    await interaction.response.send_message(msg, ephemeral=True)


@automod_group.command(name="pardon", description="Remet à zéro les infractions d'un membre")
@app_commands.describe(membre="Le membre à pardonner")
@admin_only
async def automod_pardon(interaction: discord.Interaction, membre: discord.Member):
    await db_run("DELETE FROM automod_strikes WHERE guild_id=? AND user_id=?", (interaction.guild_id, membre.id))
    await interaction.response.send_message(f"🕊️ Infractions de {membre.mention} effacées.", ephemeral=True)


@automod_group.command(name="statut", description="Affiche l'état de l'auto-modération")
@admin_only
async def automod_status(interaction: discord.Interaction):
    await interaction.response.send_message(embed=await automod_embed(interaction.guild_id), ephemeral=True)


bot.tree.add_command(automod_group)


# =====================================================================
# NOUVEAUTÉS : /optimiser • /dev • /bienvenue • /sondage • /ticket • /annonce • /purge
#   Tout est persistant (boutons actifs après un redémarrage) et tracé dans le salon de /logs.
# =====================================================================
BOOT_TIME = time.time()


async def get_int(gid: Optional[int], key: str) -> int:
    """Réglage numérique (id de salon, de rôle...) ; 0 si absent ou invalide."""
    try:
        return int(await get_setting(gid, key, "0") or 0)
    except ValueError:
        return 0


class SafeModal(discord.ui.Modal):
    """Modal qui prévient l'utilisateur au lieu de planter en silence."""

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        log.error("Erreur de modal", exc_info=error)
        send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        try:
            await send("😅 Y'a eu un bug, réessaie.", ephemeral=True)
        except discord.HTTPException:
            pass


# =====================================================================
# ⚡ /optimiser : analyse des performances + propositions d'améliorations
# =====================================================================
def fmt_uptime(sec: float) -> str:
    d, r = divmod(int(sec), 86400)
    h, r = divmod(r, 3600)
    parts = [f"{d} j" if d else "", f"{h} h" if h else "", f"{r // 60} min"]
    return " ".join(p for p in parts if p)


def mem_mb() -> Optional[float]:
    """Mémoire utilisée par le bot (psutil si dispo, sinon resource ; None si impossible, ex. Windows)."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1048576
    except Exception:  # noqa: BLE001
        pass
    try:
        import resource
        import sys
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / (1048576 if sys.platform == "darwin" else 1024)
    except Exception:  # noqa: BLE001
        return None


def db_size_mb() -> float:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        try:
            total += os.path.getsize(DB_PATH + suffix)
        except OSError:
            pass
    return total / 1048576


def cache_entries() -> int:
    return len(_settings) + len(last_chat) + len(last_react) + len(last_spont) + len(last_weather) + len(last_greet)


def prune_caches(max_age: float = 3600) -> int:
    """Retire des caches anti-spam les entrées inactives depuis plus de max_age secondes."""
    now, removed = time.time(), 0
    for d in (last_chat, last_react, last_spont, last_weather, last_greet):
        for k in [k for k, t in d.items() if now - t > max_age]:
            del d[k]
            removed += 1
    return removed


PERF_TABLES = ("history", "custom_cmds", "game_stats", "polls", "poll_votes", "tickets", "automod_strikes")


async def perf_metrics(test_ai: bool) -> dict:
    m: dict = {
        "ws_ms": bot.latency * 1000,
        "uptime": time.time() - BOOT_TIME,
        "guilds": len(bot.guilds),
        "members": sum(g.member_count or 0 for g in bot.guilds),
        "mem_mb": mem_mb(),
        "db_mb": db_size_mb(),
        "cache": cache_entries(),
        "tasks": len(_bg),
        "rows": {},
    }
    t0 = time.perf_counter()
    for table in PERF_TABLES:  # noms constants : pas d'injection possible
        m["rows"][table] = (await db_all(f"SELECT COUNT(*) FROM {table}"))[0][0]
    m["db_ms"] = (time.perf_counter() - t0) * 1000 / len(PERF_TABLES)
    if test_ai:
        t0 = time.perf_counter()
        try:
            await ask_ai([{"role": "user", "content": "Réponds juste : ok"}], system="Réponds en un mot.",
                         max_tokens=64, temperature=0)
            m["ai_ms"] = (time.perf_counter() - t0) * 1000
        except Exception as e:  # noqa: BLE001
            m["ai_err"] = type(e).__name__
    return m


def perf_advice(m: dict) -> list[str]:
    out: list[str] = []
    if m["ws_ms"] > 250:
        out.append(f"📡 Latence websocket élevée ({m['ws_ms']:.0f} ms) : héberge le bot plus près des serveurs Discord ou vérifie le réseau.")
    if m.get("db_ms", 0) > 30:
        out.append(f"🗄️ La base répond lentement ({m['db_ms']:.0f} ms/requête) : utilise un disque SSD et lance « Optimiser la base ».")
    if m.get("ai_ms", 0) > 6000:
        out.append(f"🤖 L'IA met {m['ai_ms'] / 1000:.1f} s à répondre : choisis un modèle plus léger via `AI_MODEL`.")
    if m.get("ai_err"):
        out.append(f"🤖 Le test IA a échoué ({m['ai_err']}) : vérifie `AI_API_KEY`, `AI_BASE_URL` et ton quota.")
    if m["db_mb"] > 100:
        out.append(f"💾 Base volumineuse ({m['db_mb']:.0f} Mo) : « Optimiser la base » compacte le fichier (VACUUM).")
    if m["mem_mb"] and m["mem_mb"] > 500:
        out.append(f"🧠 Mémoire élevée ({m['mem_mb']:.0f} Mo) : redémarre le bot de temps en temps ou purge les caches.")
    if m["cache"] > 5000:
        out.append(f"🧹 {m['cache']} entrées en cache : « Optimiser la base » purge les entrées inactives.")
    stale = m["rows"].get("poll_votes", 0) + m["rows"].get("tickets", 0)
    if stale > 20000:
        out.append("📦 Beaucoup de votes / tickets archivés : « Optimiser la base » supprime les anciens.")
    return out


async def server_advice(guild: discord.Guild) -> list[str]:
    gid, out = guild.id, []
    if not await get_int(gid, "log_channel"):
        out.append("📜 Aucun salon de logs : active-le avec `/logs` pour tracer sanctions et commandes.")
    if not await get_flag(gid, "automod", False):
        out.append("🛡️ Auto-modération coupée : `/automod config actif:True` (spam, invitations, mentions).")
    if not await get_flag(gid, "welcome_on", False):
        out.append("👋 Pas de message de bienvenue : `/bienvenue config` ou `/bienvenue generer`.")
    if not await get_int(gid, "ticket_category"):
        out.append("🎫 Pas de tickets : `/ticket config` puis `/ticket panel`.")
    if await get_flag(gid, "spontane", False) and await get_flag(gid, "reactions", True):
        out.append("⚡ Rebonds spontanés + réactions IA actifs : ça consomme du quota IA, coupe `spontane` si besoin.")
    perms = guild.me.guild_permissions
    labels = (("manage_messages", "`/purge`"), ("manage_channels", "les tickets"),
              ("manage_roles", "les rôles"), ("moderate_members", "les mutes"))
    missing = [lab for attr, lab in labels if not getattr(perms, attr)]
    if missing:
        out.append("🔑 Il me manque des permissions pour : " + ", ".join(missing) + ".")
    return out


def perf_embed(m: dict, advice: list[str]) -> discord.Embed:
    e = emb("⚡ Analyse des performances", f"Sur **{m['guilds']}** serveur(s) • **{m['members']}** membres", COLOR_PURPLE)
    lat = f"Websocket **{m['ws_ms']:.0f} ms**\nBase **{m['db_ms']:.1f} ms**/requête"
    if "ai_ms" in m:
        lat += f"\nIA **{m['ai_ms'] / 1000:.1f} s**"
    elif "ai_err" in m:
        lat += f"\nIA ❌ {m['ai_err']}"
    e.add_field(name="📡 Latence", value=lat, inline=True)
    mem = f"{m['mem_mb']:.0f} Mo" if m["mem_mb"] else "n/a"
    e.add_field(
        name="🖥️ Ressources",
        value=f"En ligne depuis **{fmt_uptime(m['uptime'])}**\nRAM **{mem}**\nBase **{m['db_mb']:.1f} Mo**\n"
              f"Caches **{m['cache']}** • tâches **{m['tasks']}**",
        inline=True,
    )
    e.add_field(name="📦 Données", value="\n".join(f"`{k}` : {v}" for k, v in m["rows"].items()), inline=True)
    e.add_field(
        name="💡 Propositions d'amélioration",
        value=("\n".join(advice) or "✅ Rien à signaler, tout est fluide 🖤")[:1024],
        inline=False,
    )
    return e


class OptimView(_OwnerView):
    def __init__(self, invoker_id: int, metrics: dict, advice: list[str]):
        super().__init__(invoker_id)
        self.metrics, self.advice, self.ai_done = metrics, advice, False

    @discord.ui.button(label="Optimiser la base", emoji="🧹", style=discord.ButtonStyle.primary)
    async def b_db(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        before, now = db_size_mb(), int(time.time())
        removed = 0
        for sql, params in (
            ("DELETE FROM polls WHERE closed=1 AND ends_at>0 AND ends_at<?", (now - 30 * 86400,)),
            ("DELETE FROM poll_votes WHERE poll_id NOT IN (SELECT id FROM polls)", ()),
            ("DELETE FROM tickets WHERE status='closed' AND closed_at>0 AND closed_at<?", (now - 90 * 86400,)),
            ("DELETE FROM automod_strikes WHERE last_at<?", (now - 30 * 86400,)),
            ("DELETE FROM giveaways WHERE status!='open' AND ends_at<?", (now - 60 * 86400,)),
            ("DELETE FROM giveaway_entries WHERE giveaway_id NOT IN (SELECT id FROM giveaways)", ()),
        ):
            cur = await bot.db.execute(sql, params)
            removed += max(cur.rowcount, 0)
        await bot.db.commit()
        await bot.db.execute("VACUUM")  # hors transaction : on vient de commit
        await bot.db.execute("PRAGMA optimize")
        pruned = prune_caches()
        await interaction.followup.send(
            f"🧹 **Base optimisée** : {before:.2f} → {db_size_mb():.2f} Mo • {removed} ligne(s) obsolète(s) supprimée(s) "
            f"• {pruned} entrée(s) de cache purgée(s).", ephemeral=True,
        )

    @discord.ui.button(label="Conseils de l'IA", emoji="🤖", style=discord.ButtonStyle.secondary)
    async def b_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ai_done:
            return await interaction.response.send_message("Les conseils sont déjà au-dessus 😏", ephemeral=True)
        self.ai_done = True
        await interaction.response.defer(ephemeral=True, thinking=True)
        m = self.metrics
        snapshot = (
            f"Latence WS {m['ws_ms']:.0f} ms, base {m['db_mb']:.1f} Mo ({m['db_ms']:.1f} ms/requête), "
            f"RAM {m['mem_mb'] or 'inconnue'} Mo, uptime {fmt_uptime(m['uptime'])}, {m['guilds']} serveurs, "
            f"{m['members']} membres, {m['cache']} entrées de cache, lignes : {m['rows']}. "
            f"Constats : {' | '.join(self.advice) or 'aucun'}."
        )
        try:
            text = await ask_ai(
                [{"role": "user", "content": snapshot}],
                system=(
                    "Tu es un ingénieur fiabilité qui audite un bot Discord Python (discord.py, SQLite, API IA). "
                    "À partir des mesures, donne 4 à 6 améliorations concrètes et priorisées (hébergement, base, "
                    "caches, quota IA, config Discord). Français, une puce par ligne, 1 phrase chacune, sans intro."
                ),
                max_tokens=900, temperature=0.4,
            )
        except Exception as e:  # noqa: BLE001
            self.ai_done = False
            return await interaction.followup.send(fail_msg(e), ephemeral=True)
        await interaction.followup.send(embed=emb("🤖 Conseils d'optimisation", text[:3900], COLOR_PINK), ephemeral=True)


@bot.tree.command(name="optimiser", description="(admin) Analyse mes performances et propose des améliorations ⚡")
@app_commands.describe(test_ia="Mesurer aussi la vitesse de l'IA (consomme 1 requête)")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@admin_only
@app_commands.checks.cooldown(1, 15.0, key=lambda i: i.guild_id)
async def optimiser(interaction: discord.Interaction, test_ia: bool = False):
    await interaction.response.defer(ephemeral=True, thinking=True)
    m = await perf_metrics(test_ia)
    advice = perf_advice(m) + await server_advice(interaction.guild)
    await interaction.followup.send(
        embed=perf_embed(m, advice), view=OptimView(interaction.user.id, m, advice), ephemeral=True
    )


# =====================================================================
# 💻 /dev projet | question : assistance pour créer sites web et applications
# =====================================================================
DEV_SYSTEM = (
    "Tu es un développeur senior full-stack qui aide des gens à créer des sites web et des applications. "
    "Tu écris du code propre, moderne, commenté juste ce qu'il faut, et qui FONCTIONNE sans modification. "
    "Tu réponds en français (le code et les noms de fichiers restent en anglais). "
    "Tu refuses de produire du code malveillant (malware, vol de données, outils d'attaque)."
)
DEV_PROJECT_FORMAT = (
    "\n\nFORMAT DE RÉPONSE OBLIGATOIRE pour un projet :\n"
    "1) Un court résumé en français (2 à 4 lignes) : ce que tu as construit et comment le lancer.\n"
    "2) Puis CHAQUE fichier, complet, sous la forme :\n"
    "=== FILE: chemin/relatif/du/fichier.ext ===\n"
    "<contenu brut du fichier, SANS bloc markdown ```>\n"
    "3) Termine par la ligne : === END ===\n"
    "Règles : 15 fichiers maximum, chemins relatifs simples (pas de ..), inclus un README.md avec les étapes "
    "d'installation et de lancement. Privilégie la simplicité : pour un site, HTML/CSS/JS sans build si possible."
)
DEV_FILE_RE = re.compile(r"^=== FILE: (.+?) ===[ \t]*$", re.M)
DEV_PATH_RE = re.compile(r"^[\w.\- ]+(?:/[\w.\- ]+)*$")
DEV_MAX_FILES = 15
DEV_MAX_BYTES = 600_000
DEV_MAX_TOKENS = int(os.getenv("DEV_MAX_TOKENS", "8000"))  # baisse-le si ton modèle limite la sortie
dev_sem = asyncio.Semaphore(2)  # au plus 2 générations lourdes en même temps (protège le quota et la RAM)


def safe_rel_path(raw: str) -> Optional[str]:
    """Chemin relatif sûr (pas de .., pas de chemin absolu) ou None."""
    p = posixpath.normpath(raw.strip().strip("`'\"").replace("\\", "/"))
    segments = p.split("/")
    if len(p) > 100 or len(segments) > 5 or any(s in ("", ".", "..") for s in segments):
        return None
    return p if DEV_PATH_RE.match(p) else None


def strip_fences(text: str) -> str:
    t = text.strip("\n")
    m = re.match(r"^```[\w+-]*\n(.*?)\n```\s*$", t, re.S)
    return m.group(1) if m else t


def parse_dev_files(raw: str) -> tuple[str, dict[str, str]]:
    """Découpe la réponse de l'IA en (résumé, {chemin: contenu})."""
    parts = DEV_FILE_RE.split(raw)
    summary = parts[0].strip()
    files: dict[str, str] = {}
    total = 0
    for i in range(1, len(parts) - 1, 2):
        name = safe_rel_path(parts[i])
        body = re.sub(r"^=== END ===[ \t]*$", "", parts[i + 1], flags=re.M)
        body = strip_fences(body).strip("\n")
        if not name or not body.strip() or name in files:
            continue
        if len(files) >= DEV_MAX_FILES or total + len(body) > DEV_MAX_BYTES:
            break
        files[name] = body + "\n"
        total += len(body)
    return summary, files


def build_zip(files: dict[str, str], root: str) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(f"{root}/{name}", content)
    buf.seek(0)
    return buf


def slugify(text: str, default: str = "projet") -> str:
    return "-".join(plain(text).split()[:4])[:30] or default


async def dev_complete(system: str, prompt: str, *, max_tokens: int, effort: str = "low") -> tuple[str, str]:
    """Appel IA « long » (timeout élargi) pour le code. Renvoie (texte, finish_reason)."""
    kwargs = {}
    if "gpt-oss" in AI_MODEL:
        kwargs["extra_body"] = {"reasoning_effort": effort}
    async with dev_sem:
        resp = await ai.with_options(timeout=150, max_retries=1).chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=0.4, max_tokens=max_tokens, **kwargs,
        )
    choice = resp.choices[0]
    return (choice.message.content or "").strip(), choice.finish_reason or ""


dev_group = app_commands.Group(name="dev", description="Assistance dev : sites web, applications, code 💻")
DEV_KINDS = [
    app_commands.Choice(name="🌐 Site web", value="site web (HTML/CSS/JS)"),
    app_commands.Choice(name="🧩 Application web", value="application web"),
    app_commands.Choice(name="📱 Application mobile", value="application mobile"),
    app_commands.Choice(name="🤖 Bot Discord", value="bot Discord"),
    app_commands.Choice(name="⚙️ API / backend", value="API / backend"),
    app_commands.Choice(name="🛠️ Script / outil", value="script / outil en ligne de commande"),
]


@dev_group.command(name="projet", description="L'IA génère les fichiers d'un site ou d'une application (zip) 🏗️")
@app_commands.describe(
    description="Ce que tu veux créer (sois précis : pages, fonctions, style, public…)",
    kind="Type de projet", stack="Langage / framework voulu (sinon je choisis le plus simple)",
)
@app_commands.rename(kind="type")
@app_commands.choices(kind=DEV_KINDS)
@app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
async def dev_projet(
    interaction: discord.Interaction,
    description: app_commands.Range[str, 10, 1500],
    kind: Optional[app_commands.Choice[str]] = None,
    stack: Optional[app_commands.Range[str, 2, 80]] = None,
):
    await interaction.response.defer(thinking=True)
    prompt = (
        f"Crée ce projet : {description}\n"
        f"Type : {kind.value if kind else 'au choix selon la demande'}\n"
        f"Stack : {stack or 'au choix, la plus simple et adaptée'}"
    )
    try:
        raw, finish = await dev_complete(DEV_SYSTEM + DEV_PROJECT_FORMAT, prompt, max_tokens=DEV_MAX_TOKENS, effort="medium")
    except Exception as e:  # noqa: BLE001
        return await interaction.followup.send(fail_msg(e))
    summary, files = parse_dev_files(raw)
    if not files:
        if not raw:
            return await interaction.followup.send("😅 L'IA n'a rien renvoyé, réessaie avec une description plus claire.")
        return await interaction.followup.send(
            "😅 Je n'ai pas réussi à découper les fichiers, voici la réponse brute :",
            file=discord.File(io.BytesIO(raw.encode("utf-8")), filename="reponse.md"),
        )
    root = slugify(description)
    listing = "\n".join(f"📄 `{n}` ({len(c) / 1024:.1f} Ko)" for n, c in files.items())
    e = emb("🏗️ Projet prêt !", (summary or "Voilà ton projet.")[:1500], COLOR_PINK)
    e.add_field(name=f"📁 {len(files)} fichier(s)", value=listing[:1000], inline=False)
    if finish == "length":
        e.add_field(
            name="⚠️ Réponse tronquée",
            value="L'IA a atteint sa limite : le dernier fichier peut être incomplet. Relance avec une demande plus ciblée.",
            inline=False,
        )
    if len(files) == 1:
        name, content = next(iter(files.items()))
        attach = discord.File(io.BytesIO(content.encode("utf-8")), filename=posixpath.basename(name))
    else:
        attach = discord.File(build_zip(files, root), filename=f"{root}.zip")
    await interaction.followup.send(embed=e, file=attach)


@dev_group.command(name="question", description="Pose une question de dev : code, bug, architecture 🧑‍💻")
@app_commands.describe(question="Ta question", code="Du code à analyser ou corriger (optionnel)")
@ai_cd()
async def dev_question(
    interaction: discord.Interaction,
    question: app_commands.Range[str, 5, 1500],
    code: Optional[app_commands.Range[str, 1, 3000]] = None,
):
    await interaction.response.defer(thinking=True)
    prompt = question + (f"\n\nCode :\n```\n{code}\n```" if code else "")
    try:
        text, _ = await dev_complete(
            DEV_SYSTEM + "\n\nRéponds directement et clairement ; mets le code dans des blocs markdown avec leur langage.",
            prompt, max_tokens=3000,
        )
    except Exception as e:  # noqa: BLE001
        return await interaction.followup.send(fail_msg(e))
    for chunk in split_text(text or "😅 Pas de réponse, reformule ta question."):
        await interaction.followup.send(chunk, allowed_mentions=NO_PINGS)


bot.tree.add_command(dev_group)


# =====================================================================
# 👋 /bienvenue config | generer | tester : messages de bienvenue personnalisés
#   Mode « texte » : modèle avec {user} {nom} {serveur} {membres}.
#   Mode « ia »   : un message unique écrit par l'IA pour chaque nouvel arrivant.
# =====================================================================
DEFAULT_WELCOME = "Bienvenue {user} sur **{serveur}** ! Tu es notre {membres}ᵉ membre 🖤 Fais comme chez toi."
WELCOME_VARS = "{user} {nom} {serveur} {membres}"
_join_times: dict[int, deque] = defaultdict(lambda: deque(maxlen=10))


def welcome_render(tpl: str, member: discord.Member) -> str:
    g = member.guild
    return (
        tpl.replace("{user}", member.mention).replace("{nom}", member.display_name)
        .replace("{serveur}", g.name).replace("{membres}", str(g.member_count or len(g.members)))
    )[:1900]


async def welcome_ai_template(guild: discord.Guild, member_name: str, count: int, theme: str, style: str) -> str:
    system = (
        persona(False, style)
        + "\n\nTu écris un message d'ACCUEIL pour un nouveau membre du serveur : 1 à 3 phrases, avec ton caractère. "
        "Écris exactement {user} à l'endroit où mentionner le membre (une seule fois). "
        "Aucun @everyone/@here, aucun lien."
    )
    prompt = (
        f"Serveur : {guild.name}. Pseudo du nouveau : {member_name}. Il y a maintenant {count} membres. "
        f"Consignes du staff : {theme or 'aucune'}."
    )
    out = (await ask_ai([{"role": "user", "content": prompt}], system=system, max_tokens=400)).strip()
    out = out.replace("@everyone", "everyone").replace("@here", "here")
    if not out:
        raise ValueError("message vide")
    return out if "{user}" in out else "{user} " + out


async def build_welcome(member: discord.Member, *, allow_ai: bool = True) -> str:
    gid = member.guild.id
    tpl = await get_setting(gid, "welcome_text", "") or DEFAULT_WELCOME
    if allow_ai and await get_setting(gid, "welcome_mode", "texte") == "ia":
        now = time.time()
        recent = [t for t in _join_times[gid] if now - t < 60]
        if len(recent) < 5:  # anti-raid : pas d'appel IA quand 5+ personnes arrivent en une minute
            try:
                tpl = await welcome_ai_template(
                    member.guild, member.display_name, member.guild.member_count or 0,
                    await get_setting(gid, "welcome_theme", ""), await get_style(gid),
                )
            except Exception as e:  # noqa: BLE001
                log.warning("Bienvenue IA : %r", e)
    return welcome_render(tpl, member)


@bot.event
async def on_member_join(member: discord.Member):
    spawn(autorole_apply(member))  # rôle automatique (membres ou bots) : indépendant de l'accueil
    if member.bot:
        return
    gid = member.guild.id
    _join_times[gid].append(time.time())
    spawn(join_log(member))
    spawn(rules_on_join(member))  # règles à accepter (si activées) : indépendant du message de bienvenue
    if not await get_flag(gid, "welcome_on", False):
        return
    ch = member.guild.get_channel(await get_int(gid, "welcome_channel"))
    if ch is None or not ch.permissions_for(member.guild.me).send_messages:
        return
    text = await build_welcome(member)
    try:
        await ch.send(text, allowed_mentions=discord.AllowedMentions(users=[member], roles=False, everyone=False))
    except discord.HTTPException:
        log.warning("Bienvenue : envoi impossible dans %s", ch.id)
    if await get_flag(gid, "welcome_dm", False):
        try:
            await member.send(text)
        except discord.HTTPException:
            pass  # MP fermés


bienvenue_group = app_commands.Group(
    name="bienvenue", description="(staff) Messages de bienvenue personnalisés 👋",
    guild_only=True, default_permissions=discord.Permissions(manage_guild=True),
)
staff_only = app_commands.checks.has_permissions(manage_guild=True)


async def welcome_state_embed(guild: discord.Guild) -> discord.Embed:
    gid = guild.id
    on = await get_flag(gid, "welcome_on", False)
    cid = await get_int(gid, "welcome_channel")
    mode = await get_setting(gid, "welcome_mode", "texte")
    e = emb("👋 Messages de bienvenue", None, COLOR_PINK)
    e.add_field(name="État", value="✅ Activé" if on else "⛔ Désactivé", inline=True)
    e.add_field(name="Salon", value=f"<#{cid}>" if cid else "— (à définir)", inline=True)
    e.add_field(name="Mode", value="🤖 IA (un message unique par membre)" if mode == "ia" else "📝 Texte (modèle fixe)", inline=True)
    e.add_field(name="MP au nouveau", value="oui" if await get_flag(gid, "welcome_dm", False) else "non", inline=True)
    theme = await get_setting(gid, "welcome_theme", "")
    if theme:
        e.add_field(name="Consignes pour l'IA", value=theme[:300], inline=False)
    e.add_field(name="Modèle", value=(await get_setting(gid, "welcome_text", "") or DEFAULT_WELCOME)[:600], inline=False)
    e.add_field(name="Variables", value=f"`{WELCOME_VARS}`", inline=False)
    return e


@bienvenue_group.command(name="config", description="Règle les messages de bienvenue")
@app_commands.describe(
    salon="Salon où accueillir les nouveaux", actif="Activer / désactiver l'accueil",
    mode="texte = modèle fixe • ia = message unique écrit par l'IA",
    message="Modèle de message (variables : {user} {nom} {serveur} {membres})",
    theme="Consignes pour l'IA (ton, ambiance, infos à rappeler…)", mp="Envoyer aussi le message en MP",
)
@app_commands.choices(mode=[
    app_commands.Choice(name="📝 Texte (modèle fixe)", value="texte"),
    app_commands.Choice(name="🤖 IA (message unique par membre)", value="ia"),
])
@staff_only
async def bienvenue_config(
    interaction: discord.Interaction, salon: Optional[discord.TextChannel] = None, actif: Optional[bool] = None,
    mode: Optional[app_commands.Choice[str]] = None, message: Optional[app_commands.Range[str, 1, 1000]] = None,
    theme: Optional[app_commands.Range[str, 1, 300]] = None, mp: Optional[bool] = None,
):
    gid = interaction.guild_id
    if salon is not None:
        p = salon.permissions_for(interaction.guild.me)
        if not p.send_messages:
            return await interaction.response.send_message(f"🚫 Je ne peux pas écrire dans {salon.mention}.", ephemeral=True)
        await set_setting(gid, "welcome_channel", str(salon.id))
    if mode is not None:
        await set_setting(gid, "welcome_mode", mode.value)
    if message is not None:
        await set_setting(gid, "welcome_text", message.replace("\\n", "\n"))
    if theme is not None:
        await set_setting(gid, "welcome_theme", theme)
    if mp is not None:
        await set_flag(gid, "welcome_dm", mp)
    if actif is not None:
        if actif and not await get_int(gid, "welcome_channel"):
            return await interaction.response.send_message("Définis d'abord un `salon` pour l'accueil 😏", ephemeral=True)
        await set_flag(gid, "welcome_on", actif)
    await interaction.response.send_message(embed=await welcome_state_embed(interaction.guild), ephemeral=True)


# =====================================================================
# 🎀 RÔLE AUTOMATIQUE À L'ARRIVÉE : /autorole definir | retirer | etat
# =====================================================================
async def autorole_apply(member: discord.Member):
    """Donne le rôle automatique (membres ou bots). Un échec ne doit jamais gêner l'arrivée : on log et on passe."""
    try:
        guild = member.guild
        rid = await get_int(guild.id, "autorole_bot" if member.bot else "autorole")
        if not rid:
            return
        role, me = guild.get_role(rid), guild.me
        if role is None or me is None or not me.guild_permissions.manage_roles:
            log.warning("Rôle auto : rôle introuvable ou permission « Gérer les rôles » manquante sur %s", guild.id)
            return
        if role.is_default() or role.managed or role >= me.top_role:
            log.warning("Rôle auto : « %s » est au-dessus de mon rôle sur %s", role.name, guild.id)
            return
        if role in member.roles:
            return
        await member.add_roles(role, reason="Rôle automatique à l'arrivée")
        le = discord.Embed(title="🎀 Rôle automatique", color=0x7ED6A5)
        le.set_thumbnail(url=member.display_avatar.url)
        le.add_field(name="Membre", value=f"{member.mention} (`{member.id}`)", inline=True)
        le.add_field(name="Rôle", value=role.mention, inline=True)
        le.timestamp = discord.utils.utcnow()
        await mod_log(guild, le)
    except discord.HTTPException as e:
        log.warning("Rôle auto : Discord a refusé (%s)", e)
    except Exception:  # noqa: BLE001
        log.exception("autorole_apply")


autorole_group = app_commands.Group(
    name="autorole", description="(staff) Rôle donné automatiquement aux nouveaux 🎀",
    guild_only=True, default_permissions=discord.Permissions(manage_guild=True),
)
AUTOROLE_CIBLES = [
    app_commands.Choice(name="👤 Membres", value="membres"),
    app_commands.Choice(name="🤖 Bots", value="bots"),
]


def _autorole_target(cible: Optional[app_commands.Choice[str]]) -> tuple[str, str]:
    return ("autorole_bot", "bots") if cible is not None and cible.value == "bots" else ("autorole", "membres")


def _autorole_problem(interaction: discord.Interaction, role: discord.Role) -> Optional[str]:
    guild, me, inv = interaction.guild, interaction.guild.me, interaction.user
    if role.is_default() or role.managed:
        return "Ce rôle ne peut pas être attribué (@everyone ou rôle géré par une intégration)."
    if me is None or not me.guild_permissions.manage_roles:
        return "Il me faut la permission « Gérer les rôles »."
    if role >= me.top_role:
        return f"« {role.name} » est au-dessus de mon rôle : monte mon rôle dans la hiérarchie."
    if inv.id != guild.owner_id and role >= inv.top_role:
        return f"« {role.name} » est au même niveau que ton rôle, ou au-dessus."
    return None


@autorole_group.command(name="definir", description="Choisis le rôle donné à chaque arrivée")
@app_commands.describe(role="Le rôle à donner automatiquement", cible="Pour qui : membres (par défaut) ou bots")
@app_commands.choices(cible=AUTOROLE_CIBLES)
@staff_only
async def autorole_definir(
    interaction: discord.Interaction, role: discord.Role, cible: Optional[app_commands.Choice[str]] = None,
):
    problem = _autorole_problem(interaction, role)
    if problem:
        return await interaction.response.send_message(f"🚫 {problem}", ephemeral=True)
    key, label = _autorole_target(cible)
    await set_setting(interaction.guild_id, key, str(role.id))
    await interaction.response.send_message(
        f"🎀 Les **{label}** qui arrivent recevront {role.mention}.", ephemeral=True, allowed_mentions=NO_PINGS
    )


@autorole_group.command(name="retirer", description="Arrête de donner un rôle automatique")
@app_commands.describe(cible="Pour qui : membres (par défaut) ou bots")
@app_commands.choices(cible=AUTOROLE_CIBLES)
@staff_only
async def autorole_retirer(interaction: discord.Interaction, cible: Optional[app_commands.Choice[str]] = None):
    key, label = _autorole_target(cible)
    if not await get_int(interaction.guild_id, key):
        return await interaction.response.send_message(f"Il n'y a pas de rôle automatique pour les {label} 😏", ephemeral=True)
    await set_setting(interaction.guild_id, key, "0")
    await interaction.response.send_message(f"✂️ Plus de rôle automatique pour les **{label}**.", ephemeral=True)


@autorole_group.command(name="etat", description="Voir les rôles automatiques en place")
@staff_only
async def autorole_etat(interaction: discord.Interaction):
    guild = interaction.guild
    lines = []
    for key, label in (("autorole", "👤 Membres"), ("autorole_bot", "🤖 Bots")):
        rid = await get_int(guild.id, key)
        role = guild.get_role(rid) if rid else None
        if not rid:
            val = "— aucun"
        elif role is None:
            val = "⚠️ ce rôle n'existe plus"
        elif role >= guild.me.top_role or not guild.me.guild_permissions.manage_roles:
            val = f"{role.mention} ⚠️ je ne peux pas le donner (permissions ou hiérarchie)"
        else:
            val = f"{role.mention} ✅"
        lines.append(f"**{label}** : {val}")
    await interaction.response.send_message(embed=emb("🎀 Rôles automatiques", "\n".join(lines), COLOR_PINK), ephemeral=True)


# =====================================================================
# 🚫 SALONS INTERDITS AU BOT : /interdit ajouter | retirer | liste | vider
# =====================================================================
BAN_KEY = "banned_channels"
INTERDIT_EXEMPT = {"interdit"}  # toujours utilisable : sinon impossible de lever une interdiction
MAX_BANNED = 50
BanTarget = Union[
    discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.CategoryChannel, discord.ForumChannel
]


async def banned_ids(gid: Optional[int]) -> set[int]:
    if not gid:
        return set()
    raw = await get_setting(gid, BAN_KEY, "")
    return {int(x) for x in raw.split(",") if x.strip().isdigit()}


async def _save_banned(gid: int, ids: set[int]):
    await set_setting(gid, BAN_KEY, ",".join(str(i) for i in sorted(ids)))


def channel_chain(channel) -> set[int]:
    """Le salon + son parent (fil → salon) + sa catégorie : interdire une catégorie interdit tous ses salons."""
    ids: set[int] = set()
    if channel is None:
        return ids
    ids.add(channel.id)
    pid = getattr(channel, "parent_id", None)  # fil de discussion
    if pid:
        ids.add(pid)
    base = getattr(channel, "parent", None) or channel
    cat = getattr(base, "category_id", None)
    if cat:
        ids.add(cat)
    return ids


async def channel_banned(channel, gid: Optional[int] = None) -> bool:
    gid = gid or getattr(getattr(channel, "guild", None), "id", None)
    if not gid:
        return False
    banned = await banned_ids(gid)
    return bool(banned and banned & channel_chain(channel))


interdit_group = app_commands.Group(
    name="interdit", description="(staff) Salons où je ne dois plus parler 🚫",
    guild_only=True, default_permissions=discord.Permissions(manage_guild=True),
)


@interdit_group.command(name="ajouter", description="Je ne réponds plus dans ce salon ou cette catégorie")
@app_commands.describe(salon="Salon, vocal, forum ou catégorie à interdire")
@staff_only
async def interdit_ajouter(interaction: discord.Interaction, salon: BanTarget):
    gid = interaction.guild_id
    ids = await banned_ids(gid)
    if salon.id in ids:
        return await interaction.response.send_message(f"😏 {salon.mention} est déjà interdit.", ephemeral=True)
    if len(ids) >= MAX_BANNED:
        return await interaction.response.send_message(f"🚫 Maximum {MAX_BANNED} interdictions : retire-en une d'abord.", ephemeral=True)
    ids.add(salon.id)
    await _save_banned(gid, ids)
    is_cat = getattr(salon, "type", None) == discord.ChannelType.category
    where = f"la catégorie {salon.mention} (et tous ses salons)" if is_cat else salon.mention
    await interaction.response.send_message(
        f"🚫 Je ne parlerai plus dans {where} : ni réponses, ni réactions, ni commandes. "
        "(L'auto-modération continue de veiller.) `/interdit retirer` pour annuler.",
        ephemeral=True,
    )


@interdit_group.command(name="retirer", description="Je peux de nouveau parler dans ce salon ou cette catégorie")
@app_commands.describe(salon="Salon, vocal, forum ou catégorie à autoriser de nouveau")
@staff_only
async def interdit_retirer(interaction: discord.Interaction, salon: BanTarget):
    gid = interaction.guild_id
    ids = await banned_ids(gid)
    if salon.id not in ids:
        return await interaction.response.send_message(f"😏 {salon.mention} n'est pas interdit.", ephemeral=True)
    ids.discard(salon.id)
    await _save_banned(gid, ids)
    await interaction.response.send_message(f"✅ Je peux de nouveau parler dans {salon.mention}.", ephemeral=True)


@interdit_group.command(name="liste", description="Voir les salons où je n'ai pas le droit de parler")
@staff_only
async def interdit_liste(interaction: discord.Interaction):
    ids = await banned_ids(interaction.guild_id)
    if not ids:
        return await interaction.response.send_message("Aucun salon interdit : je parle partout 😏", ephemeral=True)
    lines = "\n".join(f"• <#{i}>" for i in sorted(ids))
    await interaction.response.send_message(
        embed=emb(f"🚫 Salons interdits ({len(ids)})", lines[:4000], COLOR_DARK), ephemeral=True
    )


@interdit_group.command(name="vider", description="Lève toutes les interdictions")
@staff_only
async def interdit_vider(interaction: discord.Interaction):
    if not await banned_ids(interaction.guild_id):
        return await interaction.response.send_message("Il n'y a aucune interdiction 😏", ephemeral=True)
    await _save_banned(interaction.guild_id, set())
    await interaction.response.send_message("✅ Toutes les interdictions sont levées.", ephemeral=True)


# =====================================================================
# 🎙️ MIKA EN VOCAL : /vocal rejoindre | quitter | dire | ask
# Prérequis (pip) : PyNaCl, edge-tts et imageio-ffmpeg (fournit ffmpeg tout seul). Voix : MIKA_VOICE dans .env.
# =====================================================================
VOICE_TTS = os.getenv("MIKA_VOICE", "fr-FR-DeniseNeural")
VOICE_MAX_CHARS = 350
_voice_locks: dict[int, asyncio.Lock] = {}
_TTS_CUSTOM_EMOJI = re.compile(r"<a?:\w+:\d+>")
_TTS_MENTION = re.compile(r"<(?:@!?|@&|#)\d+>")
_TTS_URL = re.compile(r"https?://\S+")
_TTS_EMOJI = re.compile("[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F\u200D]")


def tts_clean(text: str) -> str:
    """Texte lisible à voix haute : sans mentions, liens, markdown ni emojis."""
    t = _TTS_CUSTOM_EMOJI.sub(" ", text)
    t = _TTS_MENTION.sub(" ", t)
    t = _TTS_URL.sub(" lien ", t)
    t = discord.utils.remove_markdown(t)
    t = _TTS_EMOJI.sub("", t)
    return re.sub(r"\s+", " ", t).strip()[:VOICE_MAX_CHARS]


def ffmpeg_path() -> Optional[str]:
    """ffmpeg installé sur la machine, sinon celui fourni par le paquet pip « imageio-ffmpeg » (rien à installer à la main)."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def voice_missing() -> Optional[str]:
    """None si tout est prêt, sinon la liste de ce qui manque sur l'hébergement."""
    missing = []
    if ffmpeg_path() is None:
        missing.append("ffmpeg (ajoute `imageio-ffmpeg` au requirements.txt)")
    try:
        import nacl  # noqa: F401
    except ImportError:
        missing.append("PyNaCl")
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        missing.append("edge-tts")
    return ", ".join(missing) or None


async def tts_speak(guild: discord.Guild, text: str) -> bool:
    """Génère la voix (edge-tts) puis la joue dans le vocal où je suis. Les phrases passent l'une après l'autre."""
    text = tts_clean(text)
    vc = guild.voice_client
    if not text or vc is None or not vc.is_connected():
        return False
    import edge_tts

    lock = _voice_locks.setdefault(guild.id, asyncio.Lock())
    async with lock:
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            await asyncio.wait_for(edge_tts.Communicate(text, VOICE_TTS).save(path), timeout=30)
            vc = guild.voice_client
            if vc is None or not vc.is_connected():
                return False
            loop = asyncio.get_running_loop()
            done: asyncio.Future = loop.create_future()

            def _after(err):
                loop.call_soon_threadsafe(lambda: done.done() or done.set_result(err))

            vc.play(discord.FFmpegPCMAudio(path, executable=ffmpeg_path() or "ffmpeg"), after=_after)
            try:
                await asyncio.wait_for(done, timeout=120)
            except asyncio.TimeoutError:
                vc.stop()
                return False
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("Voix : %r", e)
            return False
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


async def voice_auto_leave(guild: discord.Guild):
    try:
        vc = guild.voice_client
        if vc is None or not vc.is_connected() or any(not m.bot for m in vc.channel.members):
            return
        await asyncio.sleep(20)
        vc = guild.voice_client
        if vc is not None and vc.is_connected() and not any(not m.bot for m in vc.channel.members):
            await vc.disconnect()
    except Exception:  # noqa: BLE001
        log.exception("voice_auto_leave")


vocal_group = app_commands.Group(
    name="vocal", description="Je rejoins ton vocal et je parle à voix haute 🎙️", guild_only=True,
)


async def _voice_gate(interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
    """Vérifie qu'on peut me faire parler : outils présents, moi en vocal, toi dans le même salon."""
    missing = voice_missing()
    if missing:
        await interaction.response.send_message(
            f"🔧 Je ne peux pas parler : il manque sur l'hébergement **{missing}**. Voir `requirements.txt` / ffmpeg.",
            ephemeral=True,
        )
        return None
    vc = interaction.guild.voice_client
    if vc is None or not vc.is_connected():
        await interaction.response.send_message("Je ne suis dans aucun vocal. Fais `/vocal rejoindre` 😏", ephemeral=True)
        return None
    voice = interaction.user.voice
    if voice is None or voice.channel is None or voice.channel.id != vc.channel.id:
        await interaction.response.send_message(f"Viens d'abord dans {vc.channel.mention}, petit chat 😏", ephemeral=True)
        return None
    return vc


@vocal_group.command(name="rejoindre", description="Je rejoins ton salon vocal 🎧")
@ai_cd()
async def vocal_rejoindre(interaction: discord.Interaction):
    missing = voice_missing()
    if missing:
        return await interaction.response.send_message(
            f"🔧 Je ne peux pas parler : il manque sur l'hébergement **{missing}**. Voir `requirements.txt` / ffmpeg.",
            ephemeral=True,
        )
    guild, voice = interaction.guild, interaction.user.voice
    if voice is None or voice.channel is None:
        return await interaction.response.send_message("Rejoins d'abord un salon vocal, petit chat 😏", ephemeral=True)
    ch = voice.channel
    if await channel_banned(ch, guild.id):
        return await interaction.response.send_message("🚫 Je n'ai pas le droit de venir dans ce vocal.", ephemeral=True)
    perms = ch.permissions_for(guild.me)
    if not (perms.connect and perms.speak):
        return await interaction.response.send_message(
            f"🚫 Il me faut « Se connecter » et « Parler » dans {ch.mention}.", ephemeral=True
        )
    await interaction.response.defer(thinking=True)
    try:
        vc = guild.voice_client
        if vc is not None and vc.is_connected():
            if vc.channel.id != ch.id:
                await vc.move_to(ch)
        else:
            await ch.connect(timeout=20, self_deaf=True)
    except (asyncio.TimeoutError, discord.ClientException, discord.HTTPException) as e:
        log.warning("Vocal : connexion impossible (%r)", e)
        return await interaction.followup.send("😅 Je n'arrive pas à me connecter au vocal, réessaie dans un instant.")
    await interaction.followup.send(
        f"🎧 Je suis dans {ch.mention}. `/vocal dire` pour me faire parler, `/vocal ask` pour me poser une question."
    )
    spawn(tts_speak(guild, f"Coucou, c'est {BOT_NAME}. Je suis là."))


@vocal_group.command(name="quitter", description="Je quitte le vocal 👋")
async def vocal_quitter(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc is None or not vc.is_connected():
        return await interaction.response.send_message("Je ne suis dans aucun vocal 😏", ephemeral=True)
    me_in = interaction.user.voice is not None and interaction.user.voice.channel == vc.channel
    p = interaction.permissions
    if not (me_in or p.administrator or p.move_members):
        return await interaction.response.send_message(f"Viens dans {vc.channel.mention} pour me renvoyer 😏", ephemeral=True)
    await vc.disconnect()
    await interaction.response.send_message("👋 Je m'en vais. À plus, petit chat 🖤")


@vocal_group.command(name="dire", description="Je dis ça à voix haute 🗣️")
@app_commands.describe(texte="Ce que je dois dire")
@ai_cd()
async def vocal_dire(interaction: discord.Interaction, texte: app_commands.Range[str, 1, 300]):
    if await _voice_gate(interaction) is None:
        return
    if not tts_clean(texte):
        return await interaction.response.send_message("Je n'ai rien à lire dans ça 😏", ephemeral=True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    ok = await tts_speak(interaction.guild, texte)
    await interaction.followup.send("🗣️ C'est dit." if ok else "😅 Je n'ai pas réussi à parler, réessaie.", ephemeral=True)


@vocal_group.command(name="ask", description="Pose-moi une question, je réponds à voix haute 💬")
@app_commands.describe(question="Ta question")
@ai_cd()
async def vocal_ask(interaction: discord.Interaction, question: app_commands.Range[str, 1, 300]):
    if await _voice_gate(interaction) is None:
        return
    await interaction.response.defer(thinking=True)
    try:
        answer = await generate_reply(
            interaction.channel_id, interaction.user.display_name, interaction.user.id, question,
            guild_id=interaction.guild_id, nsfw=is_nsfw(interaction.channel),
        )
    except Exception as e:  # noqa: BLE001
        return await interaction.followup.send(fail_msg(e))
    for c in split_text(answer):
        await interaction.followup.send(c, allowed_mentions=NO_PINGS)
    await tts_speak(interaction.guild, answer)


class WelcomePreview(_OwnerView):
    def __init__(self, invoker_id: int, template: str):
        super().__init__(invoker_id)
        self.template = template

    @discord.ui.button(label="Utiliser ce message", emoji="✅", style=discord.ButtonStyle.success)
    async def b_use(self, interaction: discord.Interaction, button: discord.ui.Button):
        await set_setting(interaction.guild_id, "welcome_text", self.template)
        await set_setting(interaction.guild_id, "welcome_mode", "texte")
        await interaction.response.edit_message(
            content="✅ Modèle enregistré (mode texte). Active l'accueil avec `/bienvenue config actif:True salon:#…`.",
            embed=None, view=None,
        )

    @discord.ui.button(label="Annuler", emoji="❌", style=discord.ButtonStyle.secondary)
    async def b_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Annulé 😏", embed=None, view=None)


@bienvenue_group.command(name="generer", description="L'IA écrit un modèle de bienvenue à ton goût ✨")
@app_commands.describe(ton="Ambiance voulue : chaleureux, gaming, drôle, sobre, e-girl…")
@staff_only
@ai_cd()
async def bienvenue_generer(interaction: discord.Interaction, ton: app_commands.Range[str, 3, 200]):
    await interaction.response.defer(ephemeral=True, thinking=True)
    system = (
        persona(False, await get_style(interaction.guild_id))
        + f"\n\nTu écris un MODÈLE réutilisable de message de bienvenue (2 à 4 phrases). Utilise ces variables telles quelles : "
        f"{WELCOME_VARS}. Pas de @everyone/@here, pas de lien. Réponds avec le message seul."
    )
    try:
        tpl = await ask_ai([{"role": "user", "content": f"Ambiance voulue : {ton}"}], system=system, max_tokens=500)
    except Exception as e:  # noqa: BLE001
        return await interaction.followup.send(fail_msg(e), ephemeral=True)
    tpl = tpl.strip().replace("@everyone", "everyone").replace("@here", "here")[:1000]
    if not tpl:
        return await interaction.followup.send("😅 Rien de généré, réessaie.", ephemeral=True)
    preview = welcome_render(tpl, interaction.user)
    e = emb(
        "✨ Aperçu du message de bienvenue",
        airy(["_Voilà ce que verront les nouveaux :_", quote_block(preview, 2500)]),
        COLOR_PINK,
    )
    e.add_field(name="📝 Modèle enregistrable", value=f"{SP}\n```{tpl[:900]}```", inline=False)
    await interaction.followup.send(embed=e, view=WelcomePreview(interaction.user.id, tpl), ephemeral=True)


@bienvenue_group.command(name="tester", description="Voir à quoi ressemblera l'accueil (aperçu privé)")
@staff_only
@ai_cd()
async def bienvenue_tester(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    text = await build_welcome(interaction.user)
    await interaction.followup.send(
        embed=emb("👋 Aperçu de l'accueil", airy(["_Voilà ce que verra un nouvel arrivant :_", quote_block(text)]), COLOR_PINK),
        ephemeral=True,
    )


bot.tree.add_command(bienvenue_group)
bot.tree.add_command(autorole_group)
bot.tree.add_command(interdit_group)
bot.tree.add_command(vocal_group)


# =====================================================================
# 📊 /sondage : sondages interactifs à boutons (votes persistants, fin automatique)
# =====================================================================
POLL_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


async def poll_get(pid: int) -> Optional[dict]:
    rows = await db_all(
        "SELECT id, guild_id, channel_id, message_id, creator_id, question, options, multiple, ends_at, closed "
        "FROM polls WHERE id=?", (pid,),
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "id": r[0], "guild_id": r[1], "channel_id": r[2], "message_id": r[3], "creator_id": r[4],
        "question": r[5], "options": json.loads(r[6]), "multiple": bool(r[7]), "ends_at": r[8], "closed": bool(r[9]),
    }


async def poll_counts(pid: int, n: int) -> tuple[list[int], int]:
    counts = [0] * n
    for opt, c in await db_all("SELECT opt, COUNT(*) FROM poll_votes WHERE poll_id=? GROUP BY opt", (pid,)):
        if 0 <= opt < n:
            counts[opt] = c
    voters = (await db_all("SELECT COUNT(DISTINCT user_id) FROM poll_votes WHERE poll_id=?", (pid,)))[0][0]
    return counts, voters


def poll_embed(poll: dict, counts: list[int], voters: int, closed: bool = False) -> discord.Embed:
    total, best = sum(counts), max(counts, default=0)
    lines = []
    for i, (opt, c) in enumerate(zip(poll["options"], counts)):
        pct = c / total * 100 if total else 0
        filled = round(pct / 100 * 12)
        crown = " 👑" if closed and best > 0 and c == best else ""
        lines.append(f"{POLL_EMOJI[i]} **{opt}**{crown}\n`{'▰' * filled}{'▱' * (12 - filled)}` {pct:.0f}% · {c} vote{'s' if c > 1 else ''}")
    if closed:
        head = "🔒 **Sondage terminé**"
    elif poll["ends_at"]:
        head = f"⏳ Fin <t:{poll['ends_at']}:R>"
    else:
        head = "♾️ Sans limite de temps"
    e = discord.Embed(
        title=f"📊 {poll['question']}"[:250], description=head + "\n\n" + "\n\n".join(lines),
        color=COLOR_DARK if closed else COLOR_PURPLE,
    )
    e.set_footer(text=f"Sondage #{poll['id']} • {'plusieurs choix' if poll['multiple'] else 'un seul choix'} • {voters} votant{'s' if voters > 1 else ''}")
    return e


class PollVote(discord.ui.DynamicItem[discord.ui.Button], template=r"poll:(?P<pid>[0-9]+):(?P<idx>[0-9]+)"):
    def __init__(self, pid: int, idx: int, label: str = "Option"):
        super().__init__(discord.ui.Button(
            label=f"{idx + 1}. {label}"[:80], style=discord.ButtonStyle.secondary, custom_id=f"poll:{pid}:{idx}",
        ))
        self.pid, self.idx = pid, idx

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match, /):
        return cls(int(match["pid"]), int(match["idx"]))

    async def callback(self, interaction: discord.Interaction):
        poll = await poll_get(self.pid)
        if poll is None or poll["closed"] or (poll["ends_at"] and poll["ends_at"] <= time.time()):
            return await interaction.response.send_message("🔒 Ce sondage est terminé.", ephemeral=True)
        if self.idx >= len(poll["options"]):
            return await interaction.response.send_message("Cette option n'existe plus 😅", ephemeral=True)
        uid = interaction.user.id
        have = {r[0] for r in await db_all("SELECT opt FROM poll_votes WHERE poll_id=? AND user_id=?", (self.pid, uid))}
        if self.idx in have:  # re-cliquer retire son vote
            await bot.db.execute("DELETE FROM poll_votes WHERE poll_id=? AND user_id=? AND opt=?", (self.pid, uid, self.idx))
        else:
            if not poll["multiple"]:
                await bot.db.execute("DELETE FROM poll_votes WHERE poll_id=? AND user_id=?", (self.pid, uid))
            await bot.db.execute("INSERT OR IGNORE INTO poll_votes(poll_id, user_id, opt) VALUES (?,?,?)", (self.pid, uid, self.idx))
        await bot.db.commit()
        counts, voters = await poll_counts(self.pid, len(poll["options"]))
        await interaction.response.edit_message(embed=poll_embed(poll, counts, voters))


class PollEnd(discord.ui.DynamicItem[discord.ui.Button], template=r"poll_end:(?P<pid>[0-9]+)"):
    def __init__(self, pid: int):
        super().__init__(discord.ui.Button(
            label="Terminer", emoji="🔒", style=discord.ButtonStyle.danger, custom_id=f"poll_end:{pid}",
        ))
        self.pid = pid

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match, /):
        return cls(int(match["pid"]))

    async def callback(self, interaction: discord.Interaction):
        poll = await poll_get(self.pid)
        if poll is None or poll["closed"]:
            return await interaction.response.send_message("🔒 Ce sondage est déjà terminé.", ephemeral=True)
        if interaction.user.id != poll["creator_id"] and not interaction.permissions.manage_messages:
            return await interaction.response.send_message("Seul l'auteur ou le staff peut terminer ce sondage 😏", ephemeral=True)
        await poll_close(self.pid)
        await interaction.response.send_message("🔒 Sondage terminé.", ephemeral=True)


def poll_view(pid: int, options: list[str]) -> discord.ui.View:
    v = discord.ui.View(timeout=None)
    for i, opt in enumerate(options):
        v.add_item(PollVote(pid, i, opt))
    v.add_item(PollEnd(pid))
    return v


async def poll_close(pid: int) -> bool:
    """Termine un sondage : verrouille les votes, fige l'embed, annonce le résultat."""
    poll = await poll_get(pid)
    if poll is None or poll["closed"]:
        return False
    await db_run("UPDATE polls SET closed=1 WHERE id=?", (pid,))
    counts, voters = await poll_counts(pid, len(poll["options"]))
    ch = bot.get_channel(poll["channel_id"])
    if ch is None:
        try:
            ch = await bot.fetch_channel(poll["channel_id"])
        except discord.HTTPException:
            return True
    try:
        await ch.get_partial_message(poll["message_id"]).edit(embed=poll_embed(poll, counts, voters, closed=True), view=None)
    except discord.HTTPException:
        pass
    total, best = sum(counts), max(counts, default=0)
    if total == 0:
        verdict = "Personne n'a voté 😅"
    else:
        winners = [o for o, c in zip(poll["options"], counts) if c == best]
        verdict = ("Égalité : " if len(winners) > 1 else "Gagnant : ") + " / ".join(f"**{w}**" for w in winners) + f" ({best} vote{'s' if best > 1 else ''})"
    try:
        await ch.send(f"📊 Sondage terminé : **{poll['question']}**\n{verdict}", allowed_mentions=NO_PINGS)
    except discord.HTTPException:
        pass
    return True


@tasks.loop(seconds=30)
async def poll_loop():
    try:
        rows = await db_all("SELECT id FROM polls WHERE closed=0 AND ends_at>0 AND ends_at<=?", (int(time.time()),))
    except Exception:  # noqa: BLE001
        log.exception("poll_loop : lecture impossible")
        return
    for (pid,) in rows:
        try:
            await poll_close(pid)
        except Exception:  # noqa: BLE001
            log.exception("poll_loop : fermeture du sondage %s impossible", pid)


@poll_loop.before_loop
async def _before_poll_loop():
    await bot.wait_until_ready()


@bot.tree.command(name="sondage", description="Crée un sondage interactif à boutons 📊")
@app_commands.describe(
    question="La question posée",
    options="2 à 10 choix séparés par | (sinon : Oui | Non)",
    duree="Durée : 30m, 2h, 1j… (défaut : 1j) — « off » = sans limite",
    multiple="Autoriser plusieurs choix par personne",
)
@app_commands.guild_only()
@app_commands.checks.cooldown(1, 20.0, key=lambda i: i.user.id)
async def sondage(
    interaction: discord.Interaction, question: app_commands.Range[str, 3, 200],
    options: Optional[str] = None, duree: str = "1j", multiple: bool = False,
):
    opts = list(dict.fromkeys(o.strip() for o in re.split(r"[|;\n]", options or "👍 Oui | 👎 Non") if o.strip()))
    if not 2 <= len(opts) <= 10 or any(len(o) > 70 for o in opts):
        return await interaction.response.send_message(
            "📊 Il faut **2 à 10** choix différents (70 caractères max chacun), séparés par `|`.", ephemeral=True
        )
    if duree.strip().lower() in ("off", "non", "0", "aucune", "illimite", "illimité"):
        ends_at = 0
    else:
        minutes = parse_minutes(duree)
        if minutes is None:
            return await interaction.response.send_message("⏱️ Durée invalide : `30m`, `2h`, `1j` (max 28 jours) ou `off`.", ephemeral=True)
        ends_at = int(time.time()) + minutes * 60
    cur = await bot.db.execute(
        "INSERT INTO polls(guild_id, channel_id, creator_id, question, options, multiple, ends_at) VALUES (?,?,?,?,?,?,?)",
        (interaction.guild_id, interaction.channel_id, interaction.user.id, question, json.dumps(opts, ensure_ascii=False),
         int(multiple), ends_at),
    )
    await bot.db.commit()
    pid = cur.lastrowid
    poll = await poll_get(pid)
    try:
        await interaction.response.send_message(embed=poll_embed(poll, [0] * len(opts), 0), view=poll_view(pid, opts))
        msg = await interaction.original_response()
    except discord.HTTPException:
        await db_run("DELETE FROM polls WHERE id=?", (pid,))
        raise
    await db_run("UPDATE polls SET message_id=? WHERE id=?", (msg.id, pid))


# =====================================================================
# 🎫 /ticket : système de tickets d'assistance (salon privé + transcript)
#   Staff : /ticket config puis /ticket panel.  Membres : bouton « Ouvrir un ticket ».
# =====================================================================
_tk_busy: set[tuple[int, int]] = set()  # (serveur, membre) en cours de création : évite les doublons


async def tk_config(gid: int) -> dict:
    try:
        limit = max(1, int(await get_setting(gid, "ticket_limit", "1")))
    except ValueError:
        limit = 1
    return {
        "category": await get_int(gid, "ticket_category"), "staff": await get_int(gid, "ticket_staff"),
        "log": await get_int(gid, "ticket_log"), "limit": limit,
    }


def is_ticket_staff(member: discord.abc.User, staff_role_id: int) -> bool:
    if not isinstance(member, discord.Member):
        return False
    p = member.guild_permissions
    return p.administrator or p.manage_channels or (bool(staff_role_id) and any(r.id == staff_role_id for r in member.roles))


async def ticket_by_channel(cid: int) -> Optional[dict]:
    rows = await db_all(
        "SELECT id, guild_id, user_id, subject, status, claimed_by, created_at FROM tickets WHERE channel_id=?", (cid,)
    )
    if not rows:
        return None
    r = rows[0]
    return {"id": r[0], "guild_id": r[1], "user_id": r[2], "subject": r[3], "status": r[4], "claimed_by": r[5], "created_at": r[6]}


async def ticket_log(guild: discord.Guild, embed: discord.Embed, file: Optional[discord.File] = None) -> bool:
    """Log des tickets : salon dédié (/ticket config) sinon salon de logs général."""
    if not await log_cat_enabled(guild.id, "tickets"):
        return False
    for key in ("ticket_log", "log_channel"):
        ch = guild.get_channel(await get_int(guild.id, key))
        if ch is not None:
            try:
                await ch.send(embed=embed, file=file, allowed_mentions=NO_PINGS)
                return True
            except discord.HTTPException:
                return False
    return False


async def ticket_transcript(channel: discord.TextChannel, t: dict) -> bytes:
    lines = [
        f"Transcript du ticket #{t['id']:04d} — {channel.guild.name}",
        f"Sujet : {t['subject']}", f"Ouvert par : {t['user_id']}", "-" * 40,
    ]
    try:
        async for m in channel.history(limit=1000, oldest_first=True):
            body = m.content or ""
            for e in m.embeds:
                if e.description:
                    body += f"\n  [embed] {e.title or ''} {e.description}".rstrip()
            for a in m.attachments:
                body += f"\n  [fichier] {a.url}"
            lines.append(f"[{m.created_at:%Y-%m-%d %H:%M}] {m.author.display_name}: {body}")
    except discord.HTTPException:
        lines.append("(historique incomplet : accès refusé)")
    return "\n".join(lines).encode("utf-8")


async def close_ticket(channel: discord.TextChannel, closer: discord.abc.User, reason: Optional[str] = None) -> bool:
    t = await ticket_by_channel(channel.id)
    if t is None or t["status"] != "open":
        return False
    cur = await bot.db.execute(
        "UPDATE tickets SET status='closed', closed_at=? WHERE id=? AND status='open'", (int(time.time()), t["id"])
    )
    await bot.db.commit()
    if cur.rowcount == 0:  # une autre fermeture est déjà en cours
        return False
    guild = channel.guild
    desc = f"Fermé par {closer.mention}." + (f"\n**Raison :** {reason}" if reason else "") + "\nCe salon sera supprimé dans quelques secondes."
    try:
        await channel.send(embed=emb("🔒 Ticket fermé", desc, COLOR_DARK), allowed_mentions=NO_PINGS)
    except discord.HTTPException:
        pass
    data, fname = await ticket_transcript(channel, t), f"ticket-{t['id']:04d}.txt"
    le = discord.Embed(title=f"🎫 Ticket #{t['id']:04d} fermé", color=COLOR_DARK)
    le.add_field(name="Auteur", value=f"<@{t['user_id']}>", inline=True)
    le.add_field(name="Fermé par", value=closer.mention, inline=True)
    if t["claimed_by"]:
        le.add_field(name="Pris en charge par", value=f"<@{t['claimed_by']}>", inline=True)
    le.add_field(name="Sujet", value=t["subject"][:200], inline=False)
    if reason:
        le.add_field(name="Raison", value=reason[:300], inline=False)
    le.timestamp = discord.utils.utcnow()
    await ticket_log(guild, le, discord.File(io.BytesIO(data), filename=fname))
    opener = guild.get_member(t["user_id"])
    if opener is not None:
        try:
            await opener.send(
                f"🎫 Ton ticket **#{t['id']:04d}** sur **{guild.name}** est fermé. Voici le transcript :",
                file=discord.File(io.BytesIO(data), filename=fname),
            )
        except discord.HTTPException:
            pass  # MP fermés
    await asyncio.sleep(8)
    try:
        await channel.delete(reason=f"Ticket #{t['id']} fermé par {closer}")
    except discord.HTTPException:
        log.warning("Ticket #%s : suppression du salon impossible", t["id"])
    return True


@bot.event
async def on_guild_channel_delete(channel):
    """Salon de ticket supprimé à la main : on libère le membre."""
    await db_run("UPDATE tickets SET status='closed', closed_at=? WHERE channel_id=? AND status='open'", (int(time.time()), channel.id))


class TicketConfirm(_OwnerView):
    def __init__(self, invoker_id: int, channel: discord.TextChannel):
        super().__init__(invoker_id)
        self.channel = channel

    @discord.ui.button(label="Oui, fermer", emoji="🔒", style=discord.ButtonStyle.danger)
    async def b_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🔒 Fermeture en cours…", view=None)
        spawn(close_ticket(self.channel, interaction.user))

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def b_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Ticket conservé 🖤", view=None)


class TicketClose(discord.ui.DynamicItem[discord.ui.Button], template=r"ticket:close"):
    def __init__(self):
        super().__init__(discord.ui.Button(label="Fermer", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="ticket:close"))

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match, /):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        t = await ticket_by_channel(interaction.channel_id)
        if t is None or t["status"] != "open":
            return await interaction.response.send_message("Ce ticket est déjà fermé.", ephemeral=True)
        cfg = await tk_config(interaction.guild_id)
        if interaction.user.id != t["user_id"] and not is_ticket_staff(interaction.user, cfg["staff"]):
            return await interaction.response.send_message("Seuls l'auteur et le staff peuvent fermer ce ticket 😏", ephemeral=True)
        await interaction.response.send_message(
            "Fermer ce ticket ? Un transcript sera sauvegardé puis le salon sera supprimé.",
            view=TicketConfirm(interaction.user.id, interaction.channel), ephemeral=True,
        )


class TicketClaim(discord.ui.DynamicItem[discord.ui.Button], template=r"ticket:claim"):
    def __init__(self):
        super().__init__(discord.ui.Button(label="Prendre en charge", emoji="🙋", style=discord.ButtonStyle.success, custom_id="ticket:claim"))

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match, /):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        t = await ticket_by_channel(interaction.channel_id)
        if t is None or t["status"] != "open":
            return await interaction.response.send_message("Ce ticket est fermé.", ephemeral=True)
        cfg = await tk_config(interaction.guild_id)
        if not is_ticket_staff(interaction.user, cfg["staff"]):
            return await interaction.response.send_message("Réservé au staff 😏", ephemeral=True)
        if t["claimed_by"]:
            return await interaction.response.send_message(f"Déjà pris en charge par <@{t['claimed_by']}>.", ephemeral=True)
        await db_run("UPDATE tickets SET claimed_by=? WHERE id=?", (interaction.user.id, t["id"]))
        await interaction.response.send_message(f"🙋 {interaction.user.mention} prend ce ticket en charge.", allowed_mentions=NO_PINGS)


def ticket_controls() -> discord.ui.View:
    v = discord.ui.View(timeout=None)
    v.add_item(TicketClaim())
    v.add_item(TicketClose())
    return v


class TicketModal(SafeModal, title="🎫 Ouvrir un ticket"):
    sujet = discord.ui.TextInput(label="Sujet", placeholder="En quelques mots…", max_length=80)
    details = discord.ui.TextInput(
        label="Détails", style=discord.TextStyle.paragraph, required=False, max_length=800,
        placeholder="Explique ta demande ou ton problème.",
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild, member = interaction.guild, interaction.user
        await interaction.response.defer(ephemeral=True)
        key = (guild.id, member.id)
        if key in _tk_busy:
            return await interaction.followup.send("⏳ Ton ticket est en cours de création…", ephemeral=True)
        _tk_busy.add(key)
        try:
            await self._create(interaction, guild, member)
        finally:
            _tk_busy.discard(key)

    async def _create(self, interaction: discord.Interaction, guild: discord.Guild, member: discord.Member):
        cfg = await tk_config(guild.id)
        if not guild.me.guild_permissions.manage_channels:
            return await interaction.followup.send("🚫 Il me manque la permission « Gérer les salons ».", ephemeral=True)
        alive = []
        for tid, cid in await db_all("SELECT id, channel_id FROM tickets WHERE guild_id=? AND user_id=? AND status='open'", (guild.id, member.id)):
            if guild.get_channel(cid) is None:
                await db_run("UPDATE tickets SET status='closed', closed_at=? WHERE id=?", (int(time.time()), tid))
            else:
                alive.append(cid)
        if len(alive) >= cfg["limit"]:
            return await interaction.followup.send(f"🎫 Tu as déjà un ticket ouvert : <#{alive[0]}>", ephemeral=True)
        staff_role = guild.get_role(cfg["staff"]) if cfg["staff"] else None
        user_perm = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, attach_files=True, embed_links=True, read_message_history=True
        )
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: user_perm,
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True, manage_messages=True,
                embed_links=True, attach_files=True, read_message_history=True,
            ),
        }
        if staff_role is not None:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True, attach_files=True, read_message_history=True
            )
        cur = await bot.db.execute(
            "INSERT INTO tickets(guild_id, channel_id, user_id, subject, created_at) VALUES (?,?,?,?,?)",
            (guild.id, 0, member.id, str(self.sujet)[:80], int(time.time())),
        )
        await bot.db.commit()
        tid = cur.lastrowid
        slug = "-".join(plain(member.display_name).split())[:20]
        category = guild.get_channel(cfg["category"]) if cfg["category"] else None
        try:
            channel = await guild.create_text_channel(
                f"ticket-{tid:04d}" + (f"-{slug}" if slug else ""),
                category=category if isinstance(category, discord.CategoryChannel) else None,
                overwrites=overwrites, topic=f"Ticket de {member} • {str(self.sujet)[:80]}",
                reason=f"Ticket #{tid} ouvert par {member}",
            )
        except discord.HTTPException as e:
            await db_run("DELETE FROM tickets WHERE id=?", (tid,))
            return await interaction.followup.send(f"🚫 Impossible de créer le salon ({e.text or 'erreur Discord'}).", ephemeral=True)
        await db_run("UPDATE tickets SET channel_id=? WHERE id=?", (channel.id, tid))
        e = emb(f"🎫 Ticket #{tid:04d} — {str(self.sujet)[:200]}", str(self.details) or "*Pas de détails fournis.*", COLOR_PINK)
        e.add_field(name="Auteur", value=member.mention, inline=True)
        e.set_footer(text="Un membre du staff va te répondre • bouton « Fermer » quand c'est réglé")
        ping = (staff_role.mention + " " if staff_role else "") + member.mention
        await channel.send(
            ping, embed=e, view=ticket_controls(),
            allowed_mentions=discord.AllowedMentions(users=[member], roles=[staff_role] if staff_role else False, everyone=False),
        )
        le = discord.Embed(title=f"🎫 Ticket #{tid:04d} ouvert", color=COLOR_PURPLE)
        le.add_field(name="Auteur", value=f"{member.mention} (`{member.id}`)", inline=True)
        le.add_field(name="Salon", value=channel.mention, inline=True)
        le.add_field(name="Sujet", value=str(self.sujet)[:200], inline=False)
        le.timestamp = discord.utils.utcnow()
        spawn(ticket_log(guild, le))
        await interaction.followup.send(f"🎫 Ticket créé : {channel.mention}", ephemeral=True)


class TicketOpen(discord.ui.DynamicItem[discord.ui.Button], template=r"ticket:open"):
    def __init__(self):
        super().__init__(discord.ui.Button(label="Ouvrir un ticket", emoji="🎫", style=discord.ButtonStyle.primary, custom_id="ticket:open"))

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match, /):
        return cls()

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketModal())


ticket_group = app_commands.Group(name="ticket", description="Système de tickets d'assistance 🎫", guild_only=True)


@ticket_group.command(name="config", description="(staff) Règle le système de tickets")
@app_commands.describe(
    categorie="Catégorie où créer les tickets", role_staff="Rôle qui gère les tickets",
    salon_logs="Salon des transcripts (sinon le salon de /logs)", limite="Tickets ouverts max par membre (1 par défaut)",
)
@staff_only
async def ticket_config(
    interaction: discord.Interaction, categorie: Optional[discord.CategoryChannel] = None,
    role_staff: Optional[discord.Role] = None, salon_logs: Optional[discord.TextChannel] = None,
    limite: Optional[app_commands.Range[int, 1, 5]] = None,
):
    gid = interaction.guild_id
    if categorie is not None:
        await set_setting(gid, "ticket_category", str(categorie.id))
    if role_staff is not None:
        await set_setting(gid, "ticket_staff", str(role_staff.id))
    if salon_logs is not None:
        await set_setting(gid, "ticket_log", str(salon_logs.id))
    if limite is not None:
        await set_setting(gid, "ticket_limit", str(limite))
    cfg = await tk_config(gid)
    e = emb("🎫 Réglages des tickets", None, COLOR_PINK)
    e.add_field(name="Catégorie", value=f"<#{cfg['category']}>" if cfg["category"] else "— (salons à la racine)", inline=True)
    e.add_field(name="Rôle staff", value=f"<@&{cfg['staff']}>" if cfg["staff"] else "— (admins / gestion des salons)", inline=True)
    e.add_field(name="Transcripts", value=f"<#{cfg['log']}>" if cfg["log"] else "salon de `/logs`", inline=True)
    e.add_field(name="Limite par membre", value=str(cfg["limit"]), inline=True)
    e.add_field(name="Étape suivante", value="`/ticket panel` poste le bouton « Ouvrir un ticket ». Le transcript est envoyé au staff et en MP à l'auteur à la fermeture.", inline=False)
    await interaction.response.send_message(embed=e, ephemeral=True)


@ticket_group.command(name="panel", description="(staff) Poste le panneau avec le bouton « Ouvrir un ticket »")
@app_commands.describe(salon="Salon où poster (ici par défaut)", titre="Titre du panneau", description="Texte d'explication")
@staff_only
async def ticket_panel(
    interaction: discord.Interaction, salon: Optional[discord.TextChannel] = None,
    titre: str = "🎫 Besoin d'aide ?", description: Optional[str] = None,
):
    channel = salon or interaction.channel
    if not interaction.guild.me.guild_permissions.manage_channels:
        return await interaction.response.send_message("🚫 Il me manque la permission « Gérer les salons ».", ephemeral=True)
    body = (description or "Clique sur le bouton pour ouvrir un ticket privé : le staff te répondra dès que possible.").replace("\\n", "\n")
    view = discord.ui.View(timeout=None)
    view.add_item(TicketOpen())
    try:
        await channel.send(embed=emb(titre[:250], body[:3000], COLOR_PINK), view=view)
    except (discord.Forbidden, discord.HTTPException, AttributeError):
        return await interaction.response.send_message(f"🚫 Je ne peux pas écrire dans {channel.mention}.", ephemeral=True)
    await interaction.response.send_message(f"✅ Panneau posté dans {channel.mention}.", ephemeral=True)


@ticket_group.command(name="fermer", description="Ferme le ticket actuel (transcript sauvegardé)")
@app_commands.describe(raison="Raison de la fermeture (optionnel)")
async def ticket_fermer(interaction: discord.Interaction, raison: Optional[app_commands.Range[str, 1, 200]] = None):
    t = await ticket_by_channel(interaction.channel_id)
    if t is None or t["status"] != "open":
        return await interaction.response.send_message("Ce salon n'est pas un ticket ouvert 😏", ephemeral=True)
    cfg = await tk_config(interaction.guild_id)
    if interaction.user.id != t["user_id"] and not is_ticket_staff(interaction.user, cfg["staff"]):
        return await interaction.response.send_message("Seuls l'auteur et le staff peuvent fermer ce ticket 😏", ephemeral=True)
    await interaction.response.send_message("🔒 Fermeture du ticket…", ephemeral=True)
    spawn(close_ticket(interaction.channel, interaction.user, raison))


async def _ticket_member_edit(interaction: discord.Interaction, membre: discord.Member, add: bool):
    t = await ticket_by_channel(interaction.channel_id)
    if t is None or t["status"] != "open":
        return await interaction.response.send_message("Ce salon n'est pas un ticket ouvert 😏", ephemeral=True)
    cfg = await tk_config(interaction.guild_id)
    if not is_ticket_staff(interaction.user, cfg["staff"]):
        return await interaction.response.send_message("Réservé au staff 😏", ephemeral=True)
    if membre.id == t["user_id"] or membre.bot:
        return await interaction.response.send_message("Cette personne ne peut pas être modifiée ici.", ephemeral=True)
    try:
        if add:
            await interaction.channel.set_permissions(
                membre, view_channel=True, send_messages=True, attach_files=True, read_message_history=True,
                reason=f"Ajouté au ticket #{t['id']} par {interaction.user}",
            )
        else:
            await interaction.channel.set_permissions(membre, overwrite=None, reason=f"Retiré du ticket #{t['id']} par {interaction.user}")
    except discord.HTTPException:
        return await interaction.response.send_message("🚫 Je n'ai pas pu modifier les permissions du salon.", ephemeral=True)
    await interaction.response.send_message(
        f"{'➕' if add else '➖'} {membre.mention} {'ajouté au' if add else 'retiré du'} ticket.",
        allowed_mentions=discord.AllowedMentions(users=[membre]),
    )


@ticket_group.command(name="ajouter", description="(staff) Ajoute un membre au ticket actuel")
@app_commands.describe(membre="Le membre à ajouter")
async def ticket_ajouter(interaction: discord.Interaction, membre: discord.Member):
    await _ticket_member_edit(interaction, membre, True)


@ticket_group.command(name="retirer", description="(staff) Retire un membre du ticket actuel")
@app_commands.describe(membre="Le membre à retirer")
async def ticket_retirer(interaction: discord.Interaction, membre: discord.Member):
    await _ticket_member_edit(interaction, membre, False)


bot.tree.add_command(ticket_group)


# =====================================================================
# 📣 /annonce : publier une annonce (embed) avec mention optionnelle
# =====================================================================
class AnnonceModal(SafeModal, title="📣 Nouvelle annonce"):
    titre = discord.ui.TextInput(label="Titre", max_length=200, placeholder="Ex : Soirée gaming ce samedi !")
    texte = discord.ui.TextInput(
        label="Message", style=discord.TextStyle.paragraph, max_length=3500,
        placeholder="Le contenu de l'annonce (retours à la ligne autorisés).",
    )

    def __init__(self, salon: discord.TextChannel, ping: str, role: Optional[discord.Role], image: Optional[discord.Attachment]):
        super().__init__()
        self.salon, self.ping, self.role, self.image = salon, ping, role, image

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title=str(self.titre), description=str(self.texte), color=COLOR_PINK)
        embed.set_footer(text=f"📣 Annonce • {interaction.user.display_name}")
        embed.timestamp = discord.utils.utcnow()
        file = None
        if self.image is not None:
            try:
                file = await self.image.to_file()
                embed.set_image(url=f"attachment://{file.filename}")
            except discord.HTTPException:
                file = None
        content = {"everyone": "@everyone", "here": "@here"}.get(self.ping) or (self.role.mention if self.role else None)
        mentions = discord.AllowedMentions(
            everyone=self.ping in ("everyone", "here"), roles=[self.role] if self.role else False, users=False
        )
        try:
            msg = await self.salon.send(content=content, embed=embed, file=file, allowed_mentions=mentions)
        except discord.HTTPException:
            return await interaction.followup.send(f"🚫 Je n'ai pas pu publier dans {self.salon.mention}.", ephemeral=True)
        if self.salon.is_news():  # salon d'annonces : on diffuse aux serveurs abonnés
            try:
                await msg.publish()
            except discord.HTTPException:
                pass
        await interaction.followup.send(f"✅ Annonce publiée : {msg.jump_url}", ephemeral=True)
        await log_cmd(interaction, "annonce", f"Salon : {self.salon.mention}\nTitre : {self.titre}\nPing : {content or 'aucun'}")


@bot.tree.command(name="annonce", description="(staff) Publie une annonce dans un salon 📣")
@app_commands.describe(
    salon="Salon où publier (ici par défaut)", ping="Qui mentionner", role="Le rôle à mentionner (si ping = Un rôle)",
    image="Image à joindre (optionnel)",
)
@app_commands.choices(ping=[
    app_commands.Choice(name="Personne", value="none"), app_commands.Choice(name="@everyone", value="everyone"),
    app_commands.Choice(name="@here", value="here"), app_commands.Choice(name="Un rôle", value="role"),
])
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@staff_only
async def annonce(
    interaction: discord.Interaction, salon: Optional[discord.TextChannel] = None,
    ping: Optional[app_commands.Choice[str]] = None, role: Optional[discord.Role] = None,
    image: Optional[discord.Attachment] = None,
):
    channel = salon or interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message("📣 Choisis un salon textuel.", ephemeral=True)
    p = channel.permissions_for(interaction.guild.me)
    if not (p.send_messages and p.embed_links):
        return await interaction.response.send_message(
            f"🚫 Il me manque « Envoyer des messages » et « Intégrer des liens » dans {channel.mention}.", ephemeral=True
        )
    mode = ping.value if ping else "none"
    can_mass = interaction.user.guild_permissions.mention_everyone
    if mode in ("everyone", "here") and not can_mass:
        return await interaction.response.send_message("🚫 Il te faut la permission « Mentionner @everyone » pour ça.", ephemeral=True)
    if mode == "role":
        if role is None:
            return await interaction.response.send_message("Indique le `role` à mentionner.", ephemeral=True)
        if not role.mentionable and not can_mass:
            return await interaction.response.send_message("🚫 Ce rôle n'est pas mentionnable et tu n'as pas la permission de forcer.", ephemeral=True)
    else:
        role = None
    if image is not None and not (image.content_type or "").startswith("image/"):
        return await interaction.response.send_message("🖼️ Le fichier joint doit être une image.", ephemeral=True)
    await interaction.response.send_modal(AnnonceModal(channel, mode, role, image))


# =====================================================================
# 🧹 /purge : supprimer un nombre précis de messages
# =====================================================================
PURGE_MAX = 500


async def do_purge(channel: discord.TextChannel, nombre: int, membre: Optional[discord.Member], reason: str) -> int:
    """Supprime jusqu'à `nombre` messages (les plus récents d'abord, épinglés épargnés, < 14 jours)."""
    count = 0

    def check(m: discord.Message) -> bool:
        nonlocal count
        if m.pinned or count >= nombre or (membre is not None and m.author.id != membre.id):
            return False
        count += 1
        return True

    limit = min(1000, nombre * 10) if membre else min(1000, nombre + 50)
    after = discord.utils.utcnow() - timedelta(days=13, hours=23)  # Discord refuse la suppression en masse > 14 jours
    deleted = await channel.purge(limit=limit, check=check, after=after, oldest_first=False, reason=reason)
    return len(deleted)


async def run_purge_cmd(interaction: discord.Interaction, channel: discord.TextChannel, nombre: int, membre: Optional[discord.Member]) -> str:
    reason = f"/purge par {interaction.user} ({interaction.user.id})"
    try:
        n = await do_purge(channel, nombre, membre, reason)
        msg = f"🧹 **{n}** message(s) supprimé(s) dans {channel.mention}" + (f" (de {membre.mention})" if membre else "") + "."
        if n < nombre:
            msg += "\n*Moins que demandé : les messages épinglés et ceux de plus de 14 jours ne sont pas supprimés.*"
        status = "✅ Exécutée"
    except discord.Forbidden:
        n, msg, status = 0, "🚫 Je n'ai pas la permission de supprimer des messages ici.", "❌ Refusée par Discord"
    except discord.HTTPException:
        n, msg, status = 0, "😅 Discord a refusé la suppression, réessaie.", "❌ Erreur Discord"
    spawn(log_cmd(
        interaction, "purge",
        f"Salon : {channel.mention}\nDemandé : {nombre} • Supprimés : {n}" + (f"\nCible : {membre.mention}" if membre else ""),
        status,
    ))
    return msg


class PurgeConfirm(_OwnerView):
    def __init__(self, invoker_id: int, channel: discord.TextChannel, nombre: int, membre: Optional[discord.Member]):
        super().__init__(invoker_id)
        self.channel, self.nombre, self.membre = channel, nombre, membre

    @discord.ui.button(label="Oui, supprimer", emoji="🧹", style=discord.ButtonStyle.danger)
    async def b_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🧹 Suppression en cours…", view=None)
        msg = await run_purge_cmd(interaction, self.channel, self.nombre, self.membre)
        await interaction.edit_original_response(content=msg)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def b_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Rien n'a été supprimé 🖤", view=None)


@bot.tree.command(name="purge", description="(staff) Supprime un nombre de messages 🧹")
@app_commands.describe(
    nombre=f"Combien de messages supprimer (1 à {PURGE_MAX})",
    membre="Ne supprimer que les messages de ce membre", salon="Salon à nettoyer (ici par défaut)",
)
@app_commands.guild_only()
@app_commands.default_permissions(manage_messages=True)
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def purge_cmd(
    interaction: discord.Interaction, nombre: app_commands.Range[int, 1, PURGE_MAX],
    membre: Optional[discord.Member] = None, salon: Optional[discord.TextChannel] = None,
):
    channel = salon or interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message("🧹 Je ne peux nettoyer que des salons textuels.", ephemeral=True)
    mine, yours = channel.permissions_for(interaction.guild.me), channel.permissions_for(interaction.user)
    if not (mine.manage_messages and mine.read_message_history):
        return await interaction.response.send_message(
            f"🚫 Il me manque « Gérer les messages » et « Voir les anciens messages » dans {channel.mention}.", ephemeral=True
        )
    if not yours.manage_messages:
        return await interaction.response.send_message(f"🚫 Tu n'as pas « Gérer les messages » dans {channel.mention}.", ephemeral=True)
    if nombre > 100:  # gros nettoyage : confirmation obligatoire (irréversible)
        return await interaction.response.send_message(
            f"⚠️ Supprimer **{nombre}** messages dans {channel.mention}" + (f" de {membre.mention}" if membre else "")
            + " ? C'est irréversible.",
            view=PurgeConfirm(interaction.user.id, channel, nombre, membre), ephemeral=True,
        )
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(await run_purge_cmd(interaction, channel, nombre, membre), ephemeral=True)


# =====================================================================
# 🗑️ /supprimersalon : supprimer un salon ou une catégorie (avec confirmation + log)
# =====================================================================
def channel_kind(ch) -> str:
    if isinstance(ch, discord.CategoryChannel):
        return "📁 catégorie"
    if isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
        return "🔊 salon vocal"
    if isinstance(ch, discord.ForumChannel):
        return "🗂️ forum"
    return "💬 salon"


class ChannelDeleteConfirm(_OwnerView):
    def __init__(self, invoker_id: int, channel, sub: list):
        super().__init__(invoker_id)
        self.channel, self.sub = channel, sub  # sub = salons de la catégorie à supprimer aussi

    @discord.ui.button(label="Oui, supprimer", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def b_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🗑️ Suppression en cours…", view=None)
        guild = interaction.guild
        reason = f"/supprimersalon par {interaction.user} ({interaction.user.id})"[:500]
        deleted, errors = [], []
        for ch in [*self.sub, self.channel]:
            try:
                await ch.delete(reason=reason)
                deleted.append(f"{channel_kind(ch)} **{ch.name}**")
            except discord.Forbidden:
                errors.append(f"« {ch.name} » : permission refusée")
            except discord.HTTPException as e:
                errors.append(f"« {ch.name} » : {str(e.text)[:60]}")
            await asyncio.sleep(0.3)
        le = discord.Embed(title="🗑️ Suppression de salon", color=COLOR_DARK)
        le.add_field(name="Staff", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
        le.add_field(name="Supprimés", value=("\n".join(deleted) or "—")[:1000], inline=False)
        if errors:
            le.add_field(name="Erreurs", value="\n".join(errors)[:1000], inline=False)
        le.timestamp = discord.utils.utcnow()
        await mod_log(guild, le)
        msg = f"🗑️ Supprimé : {', '.join(deleted) or 'rien'}."
        if errors:
            msg += "\n⚠️ " + "\n⚠️ ".join(errors[:5])
        try:  # le salon où la commande a été lancée a pu être supprimé
            await interaction.edit_original_response(content=msg[:1900])
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def b_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Rien n'a été supprimé 🖤", view=None)


@bot.tree.command(name="supprimersalon", description="(staff) Supprime un salon ou une catégorie 🗑️")
@app_commands.describe(
    salon="Le salon, vocal, forum ou la catégorie à supprimer",
    contenu="Catégorie : supprimer AUSSI les salons qu'elle contient (sinon ils sont conservés, sans catégorie)",
)
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.has_permissions(manage_channels=True)
async def supprimersalon(interaction: discord.Interaction, salon: discord.abc.GuildChannel, contenu: bool = False):
    guild = interaction.guild
    if salon.id in (getattr(guild.rules_channel, "id", 0), getattr(guild.public_updates_channel, "id", 0)):
        return await interaction.response.send_message(
            "🚫 Ce salon est utilisé par la fonction Communauté de Discord (règles / mises à jour) : "
            "change-le dans les réglages du serveur avant.", ephemeral=True,
        )
    sub = list(salon.channels) if (contenu and isinstance(salon, discord.CategoryChannel)) else []
    for ch in [salon, *sub]:
        if not ch.permissions_for(guild.me).manage_channels:
            return await interaction.response.send_message(f"🚫 Il me manque « Gérer les salons » sur {ch.mention}.", ephemeral=True)
        if not ch.permissions_for(interaction.user).manage_channels:
            return await interaction.response.send_message(f"🚫 Tu n'as pas « Gérer les salons » sur {ch.mention}.", ephemeral=True)
    txt = f"⚠️ Supprimer le/la {channel_kind(salon)} **{salon.name}** ? C'est **irréversible**."
    if isinstance(salon, discord.CategoryChannel):
        if sub:
            txt += f"\n🗑️ Les **{len(sub)}** salon(s) dedans seront supprimés aussi : " + ", ".join(f"`{c.name}`" for c in sub[:15])
        elif salon.channels:
            txt += f"\n📌 Les {len(salon.channels)} salon(s) dedans seront **conservés** (ils n'auront plus de catégorie). Mets `contenu:True` pour les supprimer."
    await interaction.response.send_message(
        txt[:1900], view=ChannelDeleteConfirm(interaction.user.id, salon, sub), ephemeral=True
    )


# =====================================================================
# 🎭 /role creer | supprimer
# =====================================================================
role_group = app_commands.Group(
    name="role", description="(staff) Créer ou supprimer des rôles 🎭",
    guild_only=True, default_permissions=discord.Permissions(manage_roles=True),
)
manage_roles_only = app_commands.checks.has_permissions(manage_roles=True)
COLOR_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
ROLE_PRESET_CHOICES = [
    app_commands.Choice(name="Aucune permission (par défaut)", value="aucune"),
    app_commands.Choice(name="👤 Membre", value="membre"),
    app_commands.Choice(name="💎 VIP", value="vip"),
    app_commands.Choice(name="🛡️ Staff (modération)", value="staff"),
    app_commands.Choice(name="🤐 Muet (lecture seule)", value="muet"),
]


@role_group.command(name="creer", description="Crée un rôle")
@app_commands.describe(
    nom="Nom du rôle", couleur="Couleur hexadécimale, ex : #FF7AB8",
    permissions="Un jeu de permissions prêt à l'emploi (jamais « Administrateur »)",
    affiche="Afficher séparément dans la liste des membres", mentionnable="Tout le monde peut le mentionner",
    membre="Donner tout de suite le rôle à ce membre (optionnel)",
)
@app_commands.choices(permissions=ROLE_PRESET_CHOICES)
@manage_roles_only
async def role_creer(
    interaction: discord.Interaction, nom: app_commands.Range[str, 1, 100], couleur: Optional[str] = None,
    permissions: Optional[app_commands.Choice[str]] = None, affiche: bool = False, mentionnable: bool = False,
    membre: Optional[discord.Member] = None,
):
    guild, me, inv = interaction.guild, interaction.guild.me, interaction.user
    if not me.guild_permissions.manage_roles:
        return await interaction.response.send_message("🚫 Il me manque la permission « Gérer les rôles ».", ephemeral=True)
    if len(guild.roles) >= 250:
        return await interaction.response.send_message("🚫 Limite de 250 rôles atteinte.", ephemeral=True)
    colour = discord.Colour.default()
    if couleur:
        m = COLOR_HEX_RE.match(couleur.strip())
        if not m:
            return await interaction.response.send_message("🎨 Couleur invalide : utilise le format `#RRGGBB`.", ephemeral=True)
        colour = discord.Colour(int(m.group(1), 16))
    preset = permissions.value if permissions else "aucune"
    perms = ROLE_PRESETS.get(preset, discord.Permissions.none())
    # anti-escalade : on ne peut pas créer un rôle avec des permissions qu'on n'a pas soi-même
    if inv.id != guild.owner_id and not inv.guild_permissions.administrator and not perms.is_subset(inv.guild_permissions):
        return await interaction.response.send_message("🚫 Tu ne peux pas créer un rôle avec des permissions que tu n'as pas toi-même.", ephemeral=True)
    if not perms.is_subset(me.guild_permissions):
        return await interaction.response.send_message("🚫 Je ne peux pas donner des permissions que je n'ai pas moi-même.", ephemeral=True)
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        role = await guild.create_role(
            name=nom.strip(), colour=colour, hoist=affiche, mentionable=mentionnable, permissions=perms,
            reason=f"/role creer par {inv} ({inv.id})"[:500],
        )
    except discord.Forbidden:
        return await interaction.followup.send("🚫 Discord me refuse ça : vérifie mes permissions.", ephemeral=True)
    except discord.HTTPException as e:
        return await interaction.followup.send(f"😅 Discord a refusé : {str(e.text)[:150]}", ephemeral=True)
    note = ""
    if membre is not None:
        block = punish_block_reason(interaction, membre)
        if block:
            note = f"\n⚠️ Rôle non donné : {block}"
        else:
            try:
                await (guild.get_member(membre.id) or membre).add_roles(role, reason=f"/role creer par {inv}"[:500])
                note = f"\n🎀 Donné à {membre.mention}."
            except discord.HTTPException:
                note = "\n⚠️ Je n'ai pas pu donner le rôle."
    le = discord.Embed(title="🎭 Rôle créé", color=colour.value or COLOR_PINK)
    le.add_field(name="Rôle", value=f"{role.mention} (`{role.id}`)", inline=True)
    le.add_field(name="Staff", value=f"{inv.mention} (`{inv.id}`)", inline=True)
    le.add_field(name="Permissions", value=preset, inline=True)
    le.timestamp = discord.utils.utcnow()
    await mod_log(guild, le)
    await interaction.followup.send(
        f"✅ Rôle {role.mention} créé (en bas de la hiérarchie : remonte-le dans les réglages si besoin).{note}", ephemeral=True
    )


def role_delete_problem(interaction: discord.Interaction, role: discord.Role) -> Optional[str]:
    guild, me, inv = interaction.guild, interaction.guild.me, interaction.user
    if role.is_default():
        return "@everyone ne peut pas être supprimé."
    if role.managed:
        return f"« {role.name} » est géré par un bot / une intégration."
    if role >= me.top_role:
        return f"« {role.name} » est au-dessus de mon rôle : monte mon rôle dans la hiérarchie."
    if inv.id != guild.owner_id and role >= inv.top_role:
        return f"« {role.name} » est au même niveau que ton rôle, ou au-dessus."
    return None


class RoleDeleteConfirm(_OwnerView):
    def __init__(self, invoker_id: int, role: discord.Role):
        super().__init__(invoker_id)
        self.role = role

    @discord.ui.button(label="Oui, supprimer", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def b_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        role, guild = self.role, interaction.guild
        problem = role_delete_problem(interaction, role)
        if problem:
            return await interaction.response.edit_message(content=f"🚫 {problem}", view=None)
        n, name = len(role.members), role.name
        try:
            await role.delete(reason=f"/role supprimer par {interaction.user} ({interaction.user.id})"[:500])
        except discord.Forbidden:
            return await interaction.response.edit_message(content="🚫 Discord me refuse ça : vérifie mes permissions.", view=None)
        except discord.HTTPException as e:
            return await interaction.response.edit_message(content=f"😅 Discord a refusé : {str(e.text)[:150]}", view=None)
        le = discord.Embed(title="🎭 Rôle supprimé", color=COLOR_DARK)
        le.add_field(name="Rôle", value=f"{name} (`{role.id}`)", inline=True)
        le.add_field(name="Staff", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
        le.add_field(name="Membres concernés", value=str(n), inline=True)
        le.timestamp = discord.utils.utcnow()
        await mod_log(guild, le)
        await interaction.response.edit_message(content=f"🗑️ Rôle **{name}** supprimé ({n} membre(s) concerné(s)).", view=None)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def b_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Rôle conservé 🖤", view=None)


@role_group.command(name="supprimer", description="Supprime un rôle")
@app_commands.describe(role="Le rôle à supprimer")
@manage_roles_only
async def role_supprimer(interaction: discord.Interaction, role: discord.Role):
    problem = role_delete_problem(interaction, role)
    if problem:
        return await interaction.response.send_message(f"🚫 {problem}", ephemeral=True)
    await interaction.response.send_message(
        f"⚠️ Supprimer le rôle {role.mention} ? Il sera retiré à **{len(role.members)}** membre(s). C'est **irréversible**.\n"
        "_Les panneaux `/rolereaction` qui l'utilisent cesseront de fonctionner pour ce rôle._",
        view=RoleDeleteConfirm(interaction.user.id, role), ephemeral=True, allowed_mentions=NO_PINGS,
    )


bot.tree.add_command(role_group)


# =====================================================================
# 🧠 QUIZ PERSO : /quizperso creer | jouer | liste | supprimer
#   Les membres créent leurs quiz (1 bonne réponse + 1 à 3 mauvaises). Ils ne comptent pas dans le classement.
# =====================================================================
QUIZ_MAX_PER_USER = 20
QUIZ_MAX_PER_GUILD = 200


async def quiz_limit_error(interaction: discord.Interaction) -> Optional[str]:
    gid, uid = interaction.guild_id, interaction.user.id
    total = (await db_all("SELECT COUNT(*) FROM quizzes WHERE guild_id=?", (gid,)))[0][0]
    mine = (await db_all("SELECT COUNT(*) FROM quizzes WHERE guild_id=? AND author_id=?", (gid, uid)))[0][0]
    if total >= QUIZ_MAX_PER_GUILD:
        return f"🧠 Le serveur a atteint la limite de {QUIZ_MAX_PER_GUILD} quiz."
    if mine >= QUIZ_MAX_PER_USER and not interaction.permissions.manage_guild:
        return f"🧠 Tu as déjà {QUIZ_MAX_PER_USER} quiz : supprime-en un avec `/quizperso supprimer`."
    return None


class QuizCreateModal(SafeModal, title="🧠 Créer un quiz"):
    question = discord.ui.TextInput(label="Question", style=discord.TextStyle.paragraph, max_length=200)
    bonne = discord.ui.TextInput(label="Bonne réponse", max_length=80)
    mauvaises = discord.ui.TextInput(
        label="Mauvaises réponses (1 à 3, une par ligne)", style=discord.TextStyle.paragraph, max_length=260,
        placeholder="Une mauvaise réponse par ligne",
    )
    anecdote = discord.ui.TextInput(label="Anecdote affichée à la fin (optionnel)", required=False, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        err = await quiz_limit_error(interaction)
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        question, bonne = self.question.value.strip(), self.bonne.value.strip()
        wrongs: list[str] = []
        for w in re.split(r"[\n|;]", self.mauvaises.value):
            w = w.strip()
            if w and w.casefold() != bonne.casefold() and w.casefold() not in {x.casefold() for x in wrongs}:
                wrongs.append(w)
        if not question or not bonne:
            return await interaction.response.send_message("🧠 La question et la bonne réponse sont obligatoires.", ephemeral=True)
        if not 1 <= len(wrongs) <= 3 or any(len(w) > 80 for w in wrongs):
            return await interaction.response.send_message(
                "🧠 Il faut **1 à 3** mauvaises réponses, différentes de la bonne (80 caractères max), une par ligne.",
                ephemeral=True,
            )
        cur = await bot.db.execute(
            "INSERT INTO quizzes(guild_id, author_id, question, answer, wrongs, anecdote, created_at) VALUES (?,?,?,?,?,?,?)",
            (interaction.guild_id, interaction.user.id, question, bonne,
             json.dumps(wrongs, ensure_ascii=False), self.anecdote.value.strip(), int(time.time())),
        )
        await bot.db.commit()
        await interaction.response.send_message(
            f"✅ Quiz **#{cur.lastrowid}** créé ! Lance-le avec `/quizperso jouer numero:{cur.lastrowid}` "
            "(tu ne pourras pas y répondre toi-même 😏).", ephemeral=True,
        )


quizperso_group = app_commands.Group(name="quizperso", description="Quiz créés par les membres 🧠", guild_only=True)


@quizperso_group.command(name="creer", description="Crée ton propre quiz")
async def quizperso_creer(interaction: discord.Interaction):
    err = await quiz_limit_error(interaction)
    if err:
        return await interaction.response.send_message(err, ephemeral=True)
    await interaction.response.send_modal(QuizCreateModal())


@quizperso_group.command(name="jouer", description="Lance un quiz créé par un membre")
@app_commands.describe(numero="Numéro du quiz (au hasard si tu ne mets rien)")
@app_commands.checks.cooldown(1, 6.0, key=lambda i: i.user.id)
async def quizperso_jouer(interaction: discord.Interaction, numero: Optional[int] = None):
    cols = "SELECT id, author_id, question, answer, wrongs, anecdote FROM quizzes WHERE guild_id=?"
    if numero is not None:
        rows = await db_all(cols + " AND id=?", (interaction.guild_id, numero))
    else:
        rows = await db_all(cols + " ORDER BY RANDOM() LIMIT 1", (interaction.guild_id,))
    if not rows:
        msg = "❌ Ce quiz n'existe pas." if numero is not None else "Aucun quiz sur le serveur. Crée le premier avec `/quizperso creer` 😏"
        return await interaction.response.send_message(msg, ephemeral=True)
    qid, author, question, bonne, wrongs_json, anecdote = rows[0]
    choix = [bonne, *json.loads(wrongs_json)]
    random.shuffle(choix)
    header = f"🧠 **Quiz #{qid}** (par <@{author}>)\n{question}\n*(30 s, le premier qui trouve gagne • hors classement)*"
    view = QuizView(header, bonne, choix, anecdote, author_id=author, ranked=False)
    await interaction.response.send_message(header, view=view, allowed_mentions=NO_PINGS)
    view.message = await interaction.original_response()


@quizperso_group.command(name="liste", description="Liste les quiz du serveur")
@app_commands.describe(mes_quiz="Ne voir que les miens")
async def quizperso_liste(interaction: discord.Interaction, mes_quiz: bool = False):
    sql, params = "SELECT id, author_id, question FROM quizzes WHERE guild_id=?", (interaction.guild_id,)
    if mes_quiz:
        sql += " AND author_id=?"
        params += (interaction.user.id,)
    rows = await db_all(sql + " ORDER BY id DESC LIMIT 25", params)
    if not rows:
        return await interaction.response.send_message("Aucun quiz pour l'instant. `/quizperso creer` 😏", ephemeral=True)
    lines = [f"`#{i}` — {q.replace(chr(10), ' ')[:70]}{'…' if len(q) > 70 else ''} · <@{a}>" for i, a, q in rows]
    await interaction.response.send_message(
        embed=emb(f"🧠 Quiz du serveur ({len(rows)} derniers)", "\n".join(lines)[:4000], COLOR_PINK),
        ephemeral=True, allowed_mentions=NO_PINGS,
    )


@quizperso_group.command(name="supprimer", description="Supprime un de tes quiz (ou n'importe lequel si tu es staff)")
@app_commands.describe(numero="Numéro du quiz (voir /quizperso liste)")
async def quizperso_supprimer(interaction: discord.Interaction, numero: int):
    rows = await db_all("SELECT author_id FROM quizzes WHERE guild_id=? AND id=?", (interaction.guild_id, numero))
    if not rows:
        return await interaction.response.send_message("❌ Ce quiz n'existe pas.", ephemeral=True)
    if rows[0][0] != interaction.user.id and not interaction.permissions.manage_messages:
        return await interaction.response.send_message("🚫 Ce n'est pas ton quiz.", ephemeral=True)
    await db_run("DELETE FROM quizzes WHERE guild_id=? AND id=?", (interaction.guild_id, numero))
    await interaction.response.send_message(f"🗑️ Quiz **#{numero}** supprimé.", ephemeral=True)


bot.tree.add_command(quizperso_group)


# =====================================================================
# ✂️ /pfcduel : pierre-feuille-ciseaux contre un autre joueur (mise optionnelle)
#   Défi → l'adversaire accepte → mises prélevées → chacun choisit en secret → le gagnant empoche le pot.
#   Égalité : on rejoue (3 manches max, puis mises rendues). Pas de réponse à temps : forfait.
# =====================================================================
PFC_DUEL_TIMEOUT = 60
PFC_MAX_ROUNDS = 3


class PFCDuel:
    def __init__(self, a: discord.Member, b: discord.Member, guild_id: int, bet: int):
        self.a, self.b, self.gid, self.bet = a, b, guild_id, bet
        self.round = 1
        self.choices: dict[int, str] = {}
        self.finished = False
        self.lock = asyncio.Lock()
        self.view: Optional["PFCPlayView"] = None
        self.message: Optional[discord.Message] = None

    def embed(self, note: str = "") -> discord.Embed:
        def st(p: discord.Member) -> str:
            return "✅ a choisi" if p.id in self.choices else "⏳ réfléchit…"
        desc = (
            f"{self.a.mention} ⚔️ {self.b.mention}\n"
            f"Manche **{self.round}/{PFC_MAX_ROUNDS}** : choisis en secret avec les boutons ({PFC_DUEL_TIMEOUT}s).\n\n"
            f"{self.a.display_name} : {st(self.a)}\n{self.b.display_name} : {st(self.b)}"
        )
        if self.bet:
            desc += f"\n\n💰 Pot : **{self.bet * 2}** {COIN} (le gagnant remporte tout)"
        if note:
            desc = f"{note}\n\n{desc}"
        return emb("✂️ Duel pierre-feuille-ciseaux", desc, COLOR_PURPLE)

    async def _edit(self, interaction: Optional[discord.Interaction], embed: discord.Embed, view):
        try:
            if interaction is not None:
                await interaction.response.edit_message(embed=embed, view=view)
            elif self.message is not None:
                await self.message.edit(embed=embed, view=view)
        except discord.HTTPException:
            pass

    async def _refund_both(self):
        if self.bet:
            for p in (self.a, self.b):
                await eco_add(self.gid, p.id, self.bet)

    async def _finish(self, winner: Optional[discord.Member], interaction: Optional[discord.Interaction], recap: str):
        self.finished = True
        if winner is None:
            await self._refund_both()
            spawn(record_many(self.gid, "pfc", {self.a.id: "draw", self.b.id: "draw"}))
            desc = f"{recap}\n\n🤝 Égalité : personne ne gagne" + (" et les mises sont rendues." if self.bet else ".")
            embed = emb("🤝 Duel terminé", desc, COLOR_PINK)
        else:
            loser = self.b if winner.id == self.a.id else self.a
            if self.bet:
                await eco_add(self.gid, winner.id, self.bet * 2)
            spawn(record_many(self.gid, "pfc", {winner.id: "win", loser.id: "loss"}))
            desc = f"{recap}\n\n🏆 {winner.mention} gagne" + (f" **{self.bet * 2}** {COIN}" if self.bet else "") + " ! Sois bon perdant, " + loser.mention + " 😈"
            embed = emb("🏆 Duel terminé", desc, COLOR_PINK)
        await self._edit(interaction, embed, None)

    async def resolve(self, interaction: Optional[discord.Interaction]):
        ca, cb = self.choices[self.a.id], self.choices[self.b.id]
        recap = f"{self.a.mention} {PFC[ca]} vs {PFC[cb]} {self.b.mention}"
        if ca == cb:
            if self.round >= PFC_MAX_ROUNDS:
                return await self._finish(None, interaction, recap + f"\nÉgalité sur {PFC_MAX_ROUNDS} manches.")
            self.round += 1
            self.choices = {}
            self.view = PFCPlayView(self)
            return await self._edit(interaction, self.embed(f"🤝 {recap} : égalité, on recommence !"), self.view)
        await self._finish(self.a if BEATS[ca] == cb else self.b, interaction, recap)

    async def on_timeout(self):
        self.finished = True
        if not self.choices:
            await self._refund_both()
            return await self._edit(None, emb("⌛ Duel annulé", "Personne n'a joué à temps" + (" : mises rendues." if self.bet else "."), COLOR_DARK), None)
        self.finished = False  # _finish le remettra à True
        winner = self.a if self.a.id in self.choices else self.b
        loser = self.b if winner.id == self.a.id else self.a
        await self._finish(winner, None, f"💤 {loser.mention} n'a pas joué à temps : forfait.")


class PFCPlayView(discord.ui.View):
    def __init__(self, game: PFCDuel):
        super().__init__(timeout=PFC_DUEL_TIMEOUT)
        self.game = game

    async def _pick(self, interaction: discord.Interaction, choice: str):
        g, uid = self.game, interaction.user.id
        async with g.lock:
            if g.view is not self or g.finished:
                return await interaction.response.send_message("⌛ Cette manche est terminée.", ephemeral=True)
            if uid not in (g.a.id, g.b.id):
                return await interaction.response.send_message("Tu ne joues pas ce duel 😏", ephemeral=True)
            if uid in g.choices:
                return await interaction.response.send_message("T'as déjà choisi, patience 😌", ephemeral=True)
            g.choices[uid] = choice
            if len(g.choices) < 2:
                await interaction.response.edit_message(embed=g.embed(), view=self)
                return await interaction.followup.send(f"Tu as choisi {PFC[choice]} **{choice}**. J'attends l'autre… 🤫", ephemeral=True)
            self.stop()
            await g.resolve(interaction)

    @discord.ui.button(label="Pierre", emoji="🪨", style=discord.ButtonStyle.primary)
    async def b_pierre(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._pick(interaction, "pierre")

    @discord.ui.button(label="Feuille", emoji="📄", style=discord.ButtonStyle.primary)
    async def b_feuille(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._pick(interaction, "feuille")

    @discord.ui.button(label="Ciseaux", emoji="✂️", style=discord.ButtonStyle.primary)
    async def b_ciseaux(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._pick(interaction, "ciseaux")

    async def on_timeout(self):
        g = self.game
        async with g.lock:
            if g.view is not self or g.finished:
                return
            await g.on_timeout()


class PFCChallengeView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, bet: int):
        super().__init__(timeout=120)
        self.challenger, self.opponent, self.bet = challenger, opponent, bet
        self.done = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Accepter", emoji="✅", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("Ce défi ne t'est pas adressé 😏", ephemeral=True)
        if self.done:
            return await interaction.response.send_message("Ce défi est déjà réglé.", ephemeral=True)
        self.done = True
        self.stop()
        gid, paid = interaction.guild_id, []
        if self.bet:
            for p in (self.challenger, self.opponent):
                if await eco_charge(gid, p.id, self.bet):
                    paid.append(p)
                else:
                    for q in paid:
                        await eco_add(gid, q.id, self.bet)
                    return await interaction.response.edit_message(
                        content=None, view=None,
                        embed=emb("✂️ Défi annulé", f"{p.mention} n'a plus assez de pièces pour la mise.", COLOR_DARK),
                    )
        game = PFCDuel(self.challenger, self.opponent, gid, self.bet)
        game.view = PFCPlayView(game)
        await interaction.response.edit_message(content=None, embed=game.embed(), view=game.view)
        game.message = await interaction.original_response()

    @discord.ui.button(label="Refuser", emoji="💔", style=discord.ButtonStyle.danger)
    async def refuse(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.challenger.id, self.opponent.id):
            return await interaction.response.send_message("Ce défi ne te concerne pas 😏", ephemeral=True)
        if self.done:
            return await interaction.response.send_message("Ce défi est déjà réglé.", ephemeral=True)
        self.done = True
        self.stop()
        txt = "Défi annulé." if interaction.user.id == self.challenger.id else f"{self.opponent.mention} refuse le défi. Poule mouillée 😏"
        await interaction.response.edit_message(content=None, embed=emb("✂️ Défi refusé", txt, COLOR_DARK), view=None)

    async def on_timeout(self):
        if self.done or not self.message:
            return
        try:
            await self.message.edit(content=None, embed=emb("⌛ Défi expiré", "Personne n'a répondu à temps.", COLOR_DARK), view=None)
        except discord.HTTPException:
            pass


@bot.tree.command(name="pfcduel", description="Défie quelqu'un au pierre-feuille-ciseaux, avec mise possible ✂️")
@app_commands.describe(adversaire="La personne à défier", mise="Mise en pièces (0 = sans mise, économie à activer avec /ecopanel)")
@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def pfcduel(
    interaction: discord.Interaction, adversaire: discord.Member,
    mise: app_commands.Range[int, 0, 1_000_000_000] = 0,
):
    user, gid = interaction.user, interaction.guild_id
    if adversaire.bot:
        return await interaction.response.send_message("Pour jouer contre moi, c'est `/pfc` 😏", ephemeral=True)
    if adversaire.id == user.id:
        return await interaction.response.send_message("Tu ne peux pas te défier toi-même 😅", ephemeral=True)
    err = await bet_error(gid, user.id, mise)
    if err:
        return await interaction.response.send_message(err, ephemeral=True)
    if mise and await eco_balance(gid, adversaire.id) < mise:
        return await interaction.response.send_message(
            f"💸 {adversaire.display_name} n'a pas assez de pièces pour miser **{mise}** {COIN}.", ephemeral=True
        )
    view = PFCChallengeView(user, adversaire, mise)
    bet_txt = f" pour **{mise}** {COIN} chacun" if mise else " (pour l'honneur)"
    embed = emb("✂️ Défi pierre-feuille-ciseaux", f"{user.mention} défie {adversaire.mention}{bet_txt} !\nTu as 2 minutes pour répondre.", COLOR_PINK)
    await interaction.response.send_message(content=adversaire.mention, embed=embed, view=view, allowed_mentions=USER_PINGS)
    view.message = await interaction.original_response()


# =====================================================================
# ⚙️ CONFIG UNIFIÉ (/adminpanel) • 📜 TYPES DE LOGS • 🎯 KAHOOT • 🎮 PANEL /jeux
#   Bloc inséré automatiquement par patch_mika.py, juste avant « RÉACTIONS AUX MESSAGES ».
# =====================================================================

# ---------------------------------------------------------------------
# 📜 Types de logs sélectionnables
# ---------------------------------------------------------------------
LOG_CATS = {  # clé : (libellé, activé par défaut)
    "sanctions": ("🔨 Sanctions (mute, kick, ban, avertissement, vocal)", True),
    "commandes": ("📋 Commandes du bot (slash, panels, !nom)", True),
    "roles": ("🎭 Rôles (donnés, retirés, créés, supprimés, panneaux)", True),
    "automod": ("🛡️ Auto-modération", True),
    "tickets": ("🎫 Tickets (ouverture, fermeture, transcripts)", True),
    "admin": ("🛠️ Actions admin (envoyer, salons, serveur IA)", True),
    "arrivees": ("👋 Arrivées et départs de membres", False),
    "messages": ("💬 Messages supprimés / modifiés", False),
    "vocal": ("🎙️ Activité vocale (connexion, départ, déplacement)", False),
}


async def log_cat_enabled(gid: int, cat: str) -> bool:
    return await get_flag(gid, f"logc_{cat}", LOG_CATS.get(cat, ("", True))[1])


def guess_log_cat(embed: discord.Embed) -> str:
    """Déduit le type d'un log à partir de son titre (les anciens appels de mod_log n'ont pas à changer)."""
    t = (embed.title or "").lower()
    if "auto-mod" in t:
        return "automod"
    if "commande" in t:
        return "commandes"
    if "ticket" in t:
        return "tickets"
    if "sanction" in t:
        return "sanctions"
    if "rôle" in t or "role" in t:
        return "roles"
    return "admin"


async def join_log(member: discord.Member):
    e = discord.Embed(title="👋 Arrivée", color=COLOR_PINK)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Membre", value=f"{member.mention} (`{member.id}`)", inline=True)
    e.add_field(name="Compte créé", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
    e.timestamp = discord.utils.utcnow()
    await mod_log(member.guild, e, "arrivees")


@bot.event
async def on_member_remove(member: discord.Member):
    if member.bot:
        return
    spawn(rules_drop(member.guild.id, member.id))  # il est parti : on retire sa demande en attente
    e = discord.Embed(title="🚪 Départ", color=COLOR_DARK)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Membre", value=f"{member} (`{member.id}`)", inline=True)
    if member.joined_at:
        e.add_field(name="Était là depuis", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
    e.timestamp = discord.utils.utcnow()
    await mod_log(member.guild, e, "arrivees")


@bot.event
async def on_message_delete(message: discord.Message):
    if message.guild is None or message.author.bot:
        return
    if message.channel.id == await get_int(message.guild.id, "log_channel"):
        return
    e = discord.Embed(title="🗑️ Message supprimé", color=COLOR_DARK)
    e.add_field(name="Auteur", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
    e.add_field(name="Salon", value=getattr(message.channel, "mention", "—"), inline=True)
    e.add_field(name="Contenu", value=(message.content or "*(vide)*")[:1000], inline=False)
    if message.attachments:
        e.add_field(name="Pièces jointes", value=str(len(message.attachments)), inline=True)
    e.timestamp = discord.utils.utcnow()
    await mod_log(message.guild, e, "messages")


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if after.guild is None or after.author.bot or before.content == after.content:
        return
    e = discord.Embed(title="✏️ Message modifié", color=COLOR_PURPLE)
    e.add_field(name="Auteur", value=f"{after.author.mention} (`{after.author.id}`)", inline=True)
    e.add_field(name="Salon", value=f"{getattr(after.channel, 'mention', '—')} • [lien]({after.jump_url})", inline=True)
    e.add_field(name="Avant", value=(before.content or "*(vide)*")[:1000], inline=False)
    e.add_field(name="Après", value=(after.content or "*(vide)*")[:1000], inline=False)
    e.timestamp = discord.utils.utcnow()
    await mod_log(after.guild, e, "messages")


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    spawn(voice_auto_leave(member.guild))  # Mika quitte le vocal si elle y reste seule
    if member.bot or before.channel == after.channel:
        return
    if before.channel is None:
        txt = f"a rejoint {after.channel.mention}"
    elif after.channel is None:
        txt = f"a quitté {before.channel.mention}"
    else:
        txt = f"est passé de {before.channel.mention} à {after.channel.mention}"
    e = discord.Embed(title="🎙️ Activité vocale", description=f"{member.mention} {txt}", color=COLOR_PURPLE)
    e.timestamp = discord.utils.utcnow()
    await mod_log(member.guild, e, "vocal")


# ---------------------------------------------------------------------
# 🧩 Fonctionnalités activables / désactivables (une famille de commandes = un interrupteur)
# ---------------------------------------------------------------------
FEATURES = [  # (clé, libellé, défaut, commandes concernées)
    ("f_ia", "IA & recherche", True, {"ask", "recherche", "dev"}),
    ("f_fun", "Taquineries & décisions", True, {"roast", "blague", "8ball", "choisir", "ship"}),
    ("f_social", "Actions sociales", True, {"kiss", "hug", "pat", "slap", "bonk", "gift"}),
    ("f_mariage", "Mariage", True, {"marie", "mariage", "divorce"}),
    ("f_jeux", "Mini-jeux", True, {"pfc", "pfcduel", "blackjack", "poker", "quiz", "quizperso", "jeux",
                                   "classement", "stat", "reglepoker", "regleblackjack", "main"}),
    ("f_kahoot", "Kahoot", True, {"kahoot"}),
    ("f_meteo", "Météo", True, {"meteo"}),
    ("f_sondage", "Sondages", True, {"sondage"}),
    ("f_cc", "Commandes perso (/cc)", True, {"cc"}),
    ("f_giveaway", "Giveaways", True, {GW_CMD}),
]
_CMD_FEATURE = {c: k for k, _, _, cmds in FEATURES for c in cmds}


async def feature_gate(interaction: discord.Interaction) -> bool:
    """Vérifié avant CHAQUE commande slash : bloque celles dont la fonctionnalité est coupée dans /adminpanel."""
    if interaction.guild_id is None or interaction.command is None:
        return True
    key = _CMD_FEATURE.get(interaction.command.qualified_name.split()[0])
    if key and not await get_flag(interaction.guild_id, key, True):
        await interaction.response.send_message(
            "🚫 Cette fonctionnalité est désactivée sur ce serveur (un admin peut la réactiver avec `/adminpanel`).",
            ephemeral=True,
        )
        return False
    return True


bot.tree.interaction_check = feature_gate


async def feature_off(interaction: discord.Interaction, key: str) -> bool:
    """Pour les boutons de panels (qui n'passent pas par le contrôle des commandes)."""
    if interaction.guild_id and not await get_flag(interaction.guild_id, key, True):
        await interaction.response.send_message(
            "🚫 Cette fonctionnalité est désactivée sur ce serveur (`/adminpanel`).", ephemeral=True
        )
        return True
    return False


# ---------------------------------------------------------------------
# ⚙️ /adminpanel : panneau unique de configuration
# ---------------------------------------------------------------------
CFG_PAGES = [  # (clé, titre, description)
    ("general", "⚙️ Général", "Réactions, rebonds, salutations, réponse au prénom, style de personnalité."),
    ("fonctions", "🧩 Fonctionnalités", "Active ou coupe chaque famille de commandes du bot."),
    ("moderation", "🛡️ Modération", "Auto-modération : activation, sanctions et règles."),
    ("logs", "📜 Logs", "Salon des logs et types de logs à enregistrer."),
    ("economie", "💰 Économie & accueil", "Pièces, mises, messages de bienvenue."),
    ("outils", "🛠️ Outils", "Silence, envoi de messages, punitions, rôles, commandes perso, tests."),
]
CFG_TOGGLES = {
    "general": [("reactions", "Réactions emoji", True), ("spontane", "Rebonds spontanés", False),
                ("salutations", "Salutations", True), ("nom", "Réponse au prénom", True)],
    "fonctions": [(k, label, d) for k, label, d, _ in FEATURES],
    "moderation": [("automod", "Auto-modération", False), ("automod_sanctions", "Sanctions auto", True)]
                  + [(k, label.split(" (")[0], d) for k, label, d in AM_RULES],
    "economie": [("eco", "Économie", False), ("welcome_on", "Accueil", False), ("welcome_dm", "Accueil en MP", False)],
}


async def cfg_embed(guild: discord.Guild, page: str) -> discord.Embed:
    gid = guild.id
    meta = next(p for p in CFG_PAGES if p[0] == page)
    mark = lambda b: "✅" if b else "❌"  # noqa: E731
    e = emb(f"⚙️ Configuration — {meta[1]}", meta[2], COLOR_DARK)
    lines = []
    if page in CFG_TOGGLES:
        for key, label, default in CFG_TOGGLES[page]:
            line = f"{mark(await get_flag(gid, key, default))} **{label}**"
            if page == "fonctions":
                cmds = next(c for k, _, _, c in FEATURES if k == key)
                line += " — " + ", ".join(f"`/{c}`" for c in sorted(cmds))
            lines.append(line)
    if page == "general":
        lines.append(f"🎭 Style : **{STYLES[await get_style(gid)][0]}**")
        try:
            until = int(float(await get_setting(gid, "silence_until", "0")))
        except ValueError:
            until = 0
        lines.append(f"🤫 Silence : {f'jusqu’à <t:{until}:R>' if until > time.time() else 'inactif'}")
    elif page == "moderation":
        lines.append(f"🚫 Mots interdits : **{len(await am_words(gid))}** (liste gérée avec `/automod mot`)")
        lines.append("📈 1ʳᵉ infraction : avertissement • 2ᵉ : mute 5 min • 3ᵉ : 30 min • 4ᵉ+ : 6 h")
    elif page == "logs":
        cid = await get_int(gid, "log_channel")
        lines.append(f"📍 Salon : {f'<#{cid}>' if cid else '**aucun** (logs coupés)'}")
        lines.append("")
        for cat, (label, default) in LOG_CATS.items():
            lines.append(f"{mark(await log_cat_enabled(gid, cat))} {label}")
    elif page == "economie":
        lines.append("")
        for key, label in ECO_LABELS.items():
            lines.append(f"• {label} : **{await eco_cfg(gid, key)}** {COIN}")
        wc = await get_int(gid, "welcome_channel")
        mode = await get_setting(gid, "welcome_mode", "texte")
        lines.append(f"👋 Salon d'accueil : {f'<#{wc}>' if wc else '—'} • mode **{mode}** (détails : `/bienvenue config`)")
    elif page == "outils":
        lines += [
            "🤫 **Silence** : je me tais un moment", "✉️ **Envoyer** : message anonyme ou sous un pseudo",
            "🔨 **Punition** : panel de modération d'un membre", "🎭 **Panneau de rôles** : rôles à boutons",
            "🛠️ **Commandes perso** : créer, supprimer, lister", "🧪 **Test** et ⚡ **Optimiser**",
        ]
    e.description = (e.description or "") + "\n\n" + "\n".join(lines)
    e.set_footer(text=f"Panel privé • expire dans 10 min • {BOT_NAME} 🖤")
    return e


class CfgPageSelect(discord.ui.Select):
    def __init__(self, current: str):
        super().__init__(
            placeholder="📂 Choisir une section…", row=0,
            options=[discord.SelectOption(label=lab, value=key, description=desc[:100], default=(key == current))
                     for key, lab, desc in CFG_PAGES],
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.page = self.values[0]
        await self.view.render(interaction)


class CfgToggle(discord.ui.Button):
    def __init__(self, key: str, label: str, state: bool, row: int):
        super().__init__(
            label=f"{label} : {'on' if state else 'off'}"[:80], row=row,
            style=discord.ButtonStyle.success if state else discord.ButtonStyle.secondary,
        )
        self.key, self.base, self.state = key, label, state

    async def callback(self, interaction: discord.Interaction):
        self.state = not self.state
        await set_flag(interaction.guild_id, self.key, self.state)
        spawn(log_cmd(interaction, "config › réglage", f"`{self.base}` : {'on' if self.state else 'off'}"))
        await self.view.render(interaction)


class CfgAction(discord.ui.Button):
    def __init__(self, label: str, emoji: str, style: discord.ButtonStyle, row: int, handler):
        super().__init__(label=label, emoji=emoji, style=style, row=row)
        self.handler = handler

    async def callback(self, interaction: discord.Interaction):
        await self.handler(interaction)


class CfgStyleSelect(discord.ui.Select):
    def __init__(self, current: str, row: int):
        super().__init__(
            placeholder="🎭 Changer ma personnalité…", row=row,
            options=[discord.SelectOption(label=label, value=key, default=(key == current))
                     for key, (label, _) in STYLES.items()],
        )

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        await set_setting(interaction.guild_id, "style", key)
        spawn(log_cmd(interaction, "config › style", f"`style` : {STYLES[key][0]}"))
        await self.view.render(interaction)


class CfgLogChannel(discord.ui.ChannelSelect):
    def __init__(self, row: int):
        super().__init__(
            placeholder="📍 Choisir le salon de logs…", channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1, row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.values[0].id)
        p = channel.permissions_for(interaction.guild.me) if channel else None
        if channel is None or not (p.send_messages and p.embed_links):
            return await interaction.response.send_message(
                "🚫 Il me manque « Envoyer des messages » et « Intégrer des liens » dans ce salon.", ephemeral=True
            )
        await set_setting(interaction.guild_id, "log_channel", str(channel.id))
        spawn(log_cmd(interaction, "config › logs", f"`salon` : {channel.mention}"))
        await self.view.render(interaction)


class CfgLogCats(discord.ui.Select):
    def __init__(self, enabled: set, row: int):
        super().__init__(
            placeholder="🗂️ Types de logs à enregistrer…", min_values=0, max_values=len(LOG_CATS), row=row,
            options=[discord.SelectOption(label=label[:100], value=cat, default=(cat in enabled))
                     for cat, (label, _) in LOG_CATS.items()],
        )

    async def callback(self, interaction: discord.Interaction):
        for cat in LOG_CATS:
            await set_flag(interaction.guild_id, f"logc_{cat}", cat in self.values)
        spawn(log_cmd(interaction, "config › types de logs", ", ".join(self.values) or "aucun"))
        await self.view.render(interaction)


async def _h_silence(i: discord.Interaction):
    await i.response.send_modal(SilenceModal())


async def _h_send(i: discord.Interaction):
    await i.response.send_modal(SendModal())


async def _h_punish(i: discord.Interaction):
    await i.response.send_message("Qui veux-tu punir ?", view=PickMemberView(i.user.id), ephemeral=True)


async def _h_roles(i: discord.Interaction):
    await i.response.send_message(
        "Quels rôles proposer ? Le panneau sera posté **dans ce salon**.",
        view=PickRolesView(i.user.id), ephemeral=True,
    )


async def _h_ccadd(i: discord.Interaction):
    await i.response.send_modal(CCAddModal())


async def _h_ccdel(i: discord.Interaction):
    await i.response.send_modal(CCDelModal())


async def _h_cclist(i: discord.Interaction):
    await cc_list.callback(i)
    spawn(log_cmd(i, "config › commande liste"))


async def _h_test(i: discord.Interaction):
    await test.callback(i)
    spawn(log_cmd(i, "config › test"))


async def _h_optim(i: discord.Interaction):
    await optimiser.callback(i, False)


async def _h_ecopanel(i: discord.Interaction):
    await ecopanel.callback(i)


async def _h_welcome(i: discord.Interaction):
    await i.response.send_message(embed=await welcome_state_embed(i.guild), ephemeral=True)


class ConfigPanel(_OwnerView):
    def __init__(self, invoker_id: int, guild: discord.Guild, page: str = "general"):
        super().__init__(invoker_id)
        self.timeout = 600
        self.guild, self.page = guild, page
        self.origin: Optional[discord.Interaction] = None

    async def build(self):
        self.clear_items()
        gid, page = self.guild.id, self.page
        self.add_item(CfgPageSelect(page))
        for i, (key, label, default) in enumerate(CFG_TOGGLES.get(page, [])):
            self.add_item(CfgToggle(key, label, await get_flag(gid, key, default), 1 + i // 5))
        P, S, G, D = discord.ButtonStyle.primary, discord.ButtonStyle.secondary, discord.ButtonStyle.success, discord.ButtonStyle.danger
        if page == "general":
            self.add_item(CfgStyleSelect(await get_style(gid), 2))
        elif page == "logs":
            self.add_item(CfgLogChannel(1))
            enabled = {c for c in LOG_CATS if await log_cat_enabled(gid, c)}
            self.add_item(CfgLogCats(enabled, 2))
            self.add_item(CfgAction("Couper les logs", "📜", S, 3, self._logs_off))
        elif page == "economie":
            self.add_item(CfgAction("Panel économie", "💰", P, 2, _h_ecopanel))
            self.add_item(CfgAction("Détails de l'accueil", "👋", S, 2, _h_welcome))
        elif page == "outils":
            for label, emoji, style, row, h in (
                ("Silence", "🤫", P, 1, _h_silence), ("Envoyer", "✉️", P, 1, _h_send),
                ("Punition", "🔨", D, 1, _h_punish), ("Panneau de rôles", "🎭", P, 1, _h_roles),
                ("Créer cmd", "🛠️", G, 2, _h_ccadd), ("Suppr. cmd", "🗑️", D, 2, _h_ccdel),
                ("Liste cmds", "📋", S, 2, _h_cclist), ("Test", "🧪", S, 2, _h_test),
                ("Optimiser", "⚡", S, 3, _h_optim),
            ):
                self.add_item(CfgAction(label, emoji, style, row, h))
        self.add_item(CfgAction("Fermer", "✖️", S, 4, self._close))

    async def _logs_off(self, interaction: discord.Interaction):
        await log_cmd(interaction, "config › logs", "Logs désactivés")  # tracé AVANT la coupure
        await set_setting(interaction.guild_id, "log_channel", "0")
        await self.render(interaction)

    async def _close(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(embed=emb("⚙️ Panel fermé", "À la prochaine 🖤", COLOR_DARK), view=None)

    async def render(self, interaction: discord.Interaction):
        await self.build()
        await interaction.response.edit_message(embed=await cfg_embed(self.guild, self.page), view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.origin:
            try:
                await self.origin.edit_original_response(view=self)
            except discord.HTTPException:
                pass


async def open_config_panel(interaction: discord.Interaction, page: str = "general"):
    view = ConfigPanel(interaction.user.id, interaction.guild, page)
    await view.build()
    await interaction.response.send_message(embed=await cfg_embed(interaction.guild, page), view=view, ephemeral=True)
    view.origin = interaction


@bot.tree.command(name="adminpanel", description="(admin) Panneau de configuration complet du bot ⚙️")
@app_commands.describe(
    page="Section à ouvrir directement",
    reactions="Réactions emoji sur les messages", spontane="Rebondir de moi-même sur certains messages",
    salutations="Répondre aux « coucou / ça va ? » même sans mention", nom="Répondre quand on écrit mon prénom",
)
@app_commands.choices(page=[app_commands.Choice(name=lab, value=key) for key, lab, _ in CFG_PAGES])
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def adminpanel(
    interaction: discord.Interaction, page: Optional[app_commands.Choice[str]] = None,
    reactions: Optional[bool] = None, spontane: Optional[bool] = None,
    salutations: Optional[bool] = None, nom: Optional[bool] = None,
):
    for key, val in (("reactions", reactions), ("spontane", spontane), ("salutations", salutations), ("nom", nom)):
        if val is not None:
            await set_flag(interaction.guild_id, key, val)
    await open_config_panel(interaction, page.value if page else "general")


# ---------------------------------------------------------------------
# 🎯 /kahoot : quiz live multi-joueurs (créé à la main ou généré par l'IA)
# ---------------------------------------------------------------------
KAHOOT_MAX_Q = 20
KAHOOT_MAX_PER_USER = 10
KAHOOT_MAX_PER_GUILD = 100
KAHOOT_SHAPES = ["🔺", "🔷", "🟡", "🟩"]
KAHOOT_STYLES = [discord.ButtonStyle.danger, discord.ButtonStyle.primary,
                 discord.ButtonStyle.secondary, discord.ButtonStyle.success]
kahoot_live: dict = {}  # salon -> lobby ou partie en cours (une seule par salon)
_kahoot_gen_cd: dict[int, float] = {}


def kahoot_clean_question(raw: dict) -> Optional[dict]:
    """Valide / nettoie une question (créée à la main ou renvoyée par l'IA)."""
    try:
        q = _clean_name(raw.get("question"), 200)
        good = _clean_name(raw.get("bonne_reponse") or raw.get("bonne"), 80)
        wrongs: list[str] = []
        for w in raw.get("mauvaises") or []:
            w = _clean_name(w, 80)
            if w and w.casefold() != good.casefold() and w.casefold() not in {x.casefold() for x in wrongs}:
                wrongs.append(w)
        time_s = min(max(int(raw.get("temps", 20)), 5), 60)
    except (TypeError, ValueError, AttributeError):
        return None
    wrongs = wrongs[:3]
    if not q or not good or not wrongs:
        return None
    return {"question": q, "bonne": good, "mauvaises": wrongs, "temps": time_s}


async def kahoot_get(gid: int, kid: int) -> Optional[dict]:
    rows = await db_all("SELECT id, author_id, title, questions FROM kahoots WHERE guild_id=? AND id=?", (gid, kid))
    if not rows:
        return None
    r = rows[0]
    return {"id": r[0], "author_id": r[1], "title": r[2], "questions": json.loads(r[3])}


async def kahoot_save(gid: int, author_id: int, title: str, questions: list[dict]) -> int:
    cur = await bot.db.execute(
        "INSERT INTO kahoots(guild_id, author_id, title, questions, created_at) VALUES (?,?,?,?,?)",
        (gid, author_id, title, json.dumps(questions, ensure_ascii=False), int(time.time())),
    )
    await bot.db.commit()
    return cur.lastrowid


async def kahoot_limit_error(interaction: discord.Interaction) -> Optional[str]:
    gid, uid = interaction.guild_id, interaction.user.id
    total = (await db_all("SELECT COUNT(*) FROM kahoots WHERE guild_id=?", (gid,)))[0][0]
    mine = (await db_all("SELECT COUNT(*) FROM kahoots WHERE guild_id=? AND author_id=?", (gid, uid)))[0][0]
    if total >= KAHOOT_MAX_PER_GUILD:
        return f"🎯 Le serveur a atteint la limite de {KAHOOT_MAX_PER_GUILD} Kahoot."
    if mine >= KAHOOT_MAX_PER_USER and not interaction.permissions.manage_guild:
        return f"🎯 Tu as déjà {KAHOOT_MAX_PER_USER} Kahoot : supprime-en un avec `/kahoot supprimer`."
    return None


async def kahoot_ai_generate(theme: str, n: int, diff: str) -> tuple[str, list[dict]]:
    prompt = (
        f"Crée un quiz de type Kahoot de {n} questions sur le thème : {theme}. Difficulté : {diff}. "
        "Chaque question a UNE seule bonne réponse et 3 mauvaises réponses plausibles ; réponses courtes "
        "(60 caractères max) ; questions variées et fiables ; 'temps' = secondes pour répondre (10 à 30). "
        'JSON : {"titre": "", "questions": [{"question": "", "bonne_reponse": "", '
        '"mauvaises": ["", "", ""], "temps": 20}]}'
    )
    data = await ask_json(prompt, system=QUIZ_SYSTEM, max_tokens=min(6000, 450 * n + 600))
    title = _clean_name(data.get("titre"), 80) or f"Kahoot {theme[:60]}"
    qs = [q for q in (kahoot_clean_question(r) for r in (data.get("questions") or []) if isinstance(r, dict)) if q]
    if not qs:
        raise ValueError("aucune question valide")
    return title, qs[:n]


# ---------- Partie en direct ----------
class KahootGame:
    def __init__(self, kahoot: dict, host_id: int, channel, players: dict):
        self.k, self.host_id, self.channel = kahoot, host_id, channel
        self.players: dict[int, str] = dict(players)
        self.scores: dict[int, int] = defaultdict(int)
        self.streak: dict[int, int] = defaultdict(int)
        self.answers: dict[int, tuple[int, float]] = {}
        self.shuffled: list[str] = []
        self.correct = 0
        self.q_start = 0.0
        self.open = False
        self.cancelled = False
        self.idle = 0
        self.note = ""
        self.done_event = asyncio.Event()
        self.message: Optional[discord.Message] = None

    def ranking(self) -> list[int]:
        return sorted(self.players, key=lambda u: (-self.scores.get(u, 0), u))

    def board(self, limit: int) -> str:
        medals = ["🥇", "🥈", "🥉"]
        return "\n".join(
            f"{medals[i] if i < 3 else f'`#{i + 1}`'} <@{u}> — **{self.scores.get(u, 0)}**"
            for i, u in enumerate(self.ranking()[:limit])
        )

    async def answer(self, interaction: discord.Interaction, idx: int):
        uid = interaction.user.id
        if not self.open:
            return await interaction.response.send_message("⌛ Trop tard pour cette question.", ephemeral=True)
        if uid in self.answers:
            return await interaction.response.send_message("T'as déjà répondu, patience 😌", ephemeral=True)
        self.answers[uid] = (idx, time.monotonic() - self.q_start)
        self.players.setdefault(uid, interaction.user.display_name)
        await interaction.response.send_message(
            f"✅ Réponse enregistrée : {KAHOOT_SHAPES[idx]} **{self.shuffled[idx]}**", ephemeral=True
        )
        if all(p in self.answers for p in self.players):
            self.done_event.set()

    async def run(self):
        kahoot_live[self.channel.id] = self
        try:
            qs = self.k["questions"]
            for n, q in enumerate(qs, 1):
                await self.play_question(n, len(qs), q)
                if self.idle >= 2:
                    self.cancelled, self.note = True, "Personne ne répond depuis deux questions : j'arrête 😏"
                if self.cancelled:
                    break
                await asyncio.sleep(5 if n < len(qs) else 1)
            await self.finish()
        except Exception:  # noqa: BLE001
            log.exception("kahoot")
            try:
                await self.channel.send("😅 Le Kahoot a planté, désolé.")
            except discord.HTTPException:
                pass
        finally:
            if kahoot_live.get(self.channel.id) is self:
                kahoot_live.pop(self.channel.id, None)

    async def play_question(self, n: int, total: int, q: dict):
        answers = [q["bonne"], *q["mauvaises"]]
        random.shuffle(answers)
        self.shuffled, self.correct = answers, answers.index(q["bonne"])
        self.answers, self.done_event = {}, asyncio.Event()
        t = q["temps"]
        deadline = int(time.time()) + t
        desc = f"**Question {n}/{total}**\n\n{q['question']}\n\n" + "\n".join(
            f"{KAHOOT_SHAPES[i]} {a}" for i, a in enumerate(answers)
        ) + f"\n\n⏳ Fin <t:{deadline}:R> • plus tu réponds vite, plus tu gagnes de points !"
        embed = emb(f"🎯 {self.k['title']}", desc, COLOR_PURPLE)
        embed.set_footer(text=f"{len(self.players)} joueur(s) • ⏹️ pour arrêter (hôte / staff) • {BOT_NAME} 🖤")
        view = KahootQView(self, answers)
        if self.message is None:
            self.message = await self.channel.send(embed=embed, view=view)
        else:
            await self.message.edit(embed=embed, view=view)
        self.q_start = time.monotonic()
        self.open = True
        try:
            await asyncio.wait_for(self.done_event.wait(), timeout=t)
        except asyncio.TimeoutError:
            pass
        self.open = False
        view.stop()

        gains: dict[int, int] = {}
        for uid, (idx, elapsed) in list(self.answers.items()):
            if idx == self.correct:
                self.streak[uid] += 1
                gains[uid] = 500 + int(500 * max(0.0, 1 - elapsed / t)) + 50 * min(self.streak[uid] - 1, 4)
                self.scores[uid] += gains[uid]
            else:
                self.streak[uid] = 0
        for uid in self.players:
            if uid not in self.answers:
                self.streak[uid] = 0
        self.idle = 0 if self.answers else self.idle + 1

        counts = Counter(idx for idx, _ in self.answers.values())
        lines = [f"{KAHOOT_SHAPES[i]} {a}{' ✅' if i == self.correct else ''} — **{counts.get(i, 0)}**"
                 for i, a in enumerate(answers)]
        e = emb(f"✅ Réponse : {q['bonne']}", f"**{q['question']}**\n\n" + "\n".join(lines), COLOR_PINK)
        board = self.board(5)
        if board:
            for u, g in gains.items():
                board = board.replace(f"<@{u}> — **{self.scores[u]}**", f"<@{u}> — **{self.scores[u]}** (+{g})")
        e.add_field(name="🏆 Classement", value=board or "Personne n'a marqué de points 😏", inline=False)
        await self.message.edit(embed=e, view=None)

    async def finish(self):
        ranking = self.ranking()
        title = "⏹️ Kahoot arrêté" if self.cancelled else "🎉 Kahoot terminé"
        desc = f"**{self.k['title']}**\n\n" + (self.board(10) or "Personne n'a joué 😅")
        if self.note:
            desc += f"\n\n{self.note}"
        e = emb(title, desc, COLOR_PINK)
        try:
            if self.message:
                await self.message.edit(embed=e, view=None)
            else:
                await self.channel.send(embed=e)
        except discord.HTTPException:
            pass
        gid = getattr(getattr(self.channel, "guild", None), "id", None)
        if gid and len(ranking) >= 2 and not self.cancelled:  # pas de points en solo
            top = self.scores.get(ranking[0], 0)
            leaders = [u for u in ranking if self.scores.get(u, 0) == top and top > 0]
            outcomes = {u: ("loss" if u not in leaders else ("win" if len(leaders) == 1 else "draw")) for u in ranking}
            await record_many(gid, "kahoot", outcomes)


class KahootAnswerBtn(discord.ui.Button):
    def __init__(self, idx: int, text: str):
        super().__init__(label=text[:80], emoji=KAHOOT_SHAPES[idx], style=KAHOOT_STYLES[idx], row=idx // 2)
        self.idx = idx

    async def callback(self, interaction: discord.Interaction):
        await self.view.game.answer(interaction, self.idx)


class KahootStopBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Arrêter", emoji="⏹️", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        g = self.view.game
        if interaction.user.id != g.host_id and not interaction.permissions.manage_messages:
            return await interaction.response.send_message("Seul l'hôte ou le staff peut arrêter 😏", ephemeral=True)
        g.cancelled = True
        g.done_event.set()
        await interaction.response.send_message("⏹️ J'arrête la partie.", ephemeral=True)


class KahootQView(discord.ui.View):
    def __init__(self, game: KahootGame, answers: list[str]):
        super().__init__(timeout=None)
        self.game = game
        for i, a in enumerate(answers):
            self.add_item(KahootAnswerBtn(i, a))
        self.add_item(KahootStopBtn())


class KahootLobby(discord.ui.View):
    def __init__(self, kahoot: dict, host: discord.abc.User, channel_id: int):
        super().__init__(timeout=180)
        self.k, self.host_id, self.channel_id = kahoot, host.id, channel_id
        self.players: dict[int, str] = {host.id: host.display_name}
        self.started = False
        self.message: Optional[discord.Message] = None

    def embed(self) -> discord.Embed:
        qs = self.k["questions"]
        lines = "\n".join(f"{'👑' if u == self.host_id else '🎮'} <@{u}>" for u in self.players)
        total_t = sum(q["temps"] for q in qs)
        e = emb(
            f"🎯 Kahoot — {self.k['title']}",
            f"**{len(qs)}** question(s) • ~{max(1, total_t // 60)} min • par <@{self.k['author_id']}>\n"
            f"Clique sur **Rejoindre** (ou réponds directement une fois lancé) : plus tu réponds vite, plus tu marques !\n\n"
            f"**Joueurs ({len(self.players)})**\n{lines}",
            COLOR_PURPLE,
        )
        e.set_footer(text=f"L'hôte lance la partie • 3 minutes • {BOT_NAME} 🖤")
        return e

    def _free(self):
        if kahoot_live.get(self.channel_id) is self:
            kahoot_live.pop(self.channel_id, None)

    @discord.ui.button(label="Rejoindre", emoji="🎮", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.players:
            return await interaction.response.send_message("T'es déjà dans la partie 😌", ephemeral=True)
        self.players[interaction.user.id] = interaction.user.display_name
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Quitter", emoji="🚪", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in self.players:
            return await interaction.response.send_message("Tu n'es pas dans la partie 😏", ephemeral=True)
        if uid == self.host_id:
            self.started = True
            self.stop()
            self._free()
            return await interaction.response.edit_message(
                embed=emb("🎯 Partie annulée", "L'hôte est parti.", COLOR_DARK), view=None
            )
        del self.players[uid]
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Lancer", emoji="▶️", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.permissions.manage_messages:
            return await interaction.response.send_message("Seul l'hôte peut lancer la partie 😏", ephemeral=True)
        self.started = True
        self.stop()
        game = KahootGame(self.k, self.host_id, interaction.channel, self.players)
        kahoot_live[self.channel_id] = game
        await interaction.response.edit_message(
            embed=emb("🎯 C'est parti !", f"**{self.k['title']}** démarre : regardez le message ci-dessous 👇", COLOR_PINK),
            view=None,
        )
        spawn(game.run())

    async def on_timeout(self):
        if self.started:
            return
        self._free()
        if self.message:
            try:
                await self.message.edit(embed=emb("⌛ Lobby expiré", "Personne n'a lancé la partie.", COLOR_DARK), view=None)
            except discord.HTTPException:
                pass


async def kahoot_open_lobby(interaction: discord.Interaction, k: dict):
    ch = interaction.channel
    if ch.id in kahoot_live:
        return await interaction.response.send_message("🎯 Une partie ou un lobby est déjà en cours dans ce salon.", ephemeral=True)
    p = ch.permissions_for(interaction.guild.me)
    if not (p.send_messages and p.embed_links):
        return await interaction.response.send_message("🚫 Il me manque « Envoyer des messages » / « Intégrer des liens » ici.", ephemeral=True)
    lobby = KahootLobby(k, interaction.user, ch.id)
    kahoot_live[ch.id] = lobby
    try:
        await interaction.response.send_message(embed=lobby.embed(), view=lobby)
        lobby.message = await interaction.original_response()
    except discord.HTTPException:
        lobby._free()
        raise


# ---------- Création à la main ----------
class KahootReadyView(_OwnerView):
    def __init__(self, invoker_id: int, kahoot: dict):
        super().__init__(invoker_id)
        self.k = kahoot

    @discord.ui.button(label="Lancer ici", emoji="▶️", style=discord.ButtonStyle.success)
    async def b_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        await kahoot_open_lobby(interaction, self.k)


class KahootQuestionModal(SafeModal, title="➕ Nouvelle question"):
    question = discord.ui.TextInput(label="Question", style=discord.TextStyle.paragraph, max_length=200)
    bonne = discord.ui.TextInput(label="Bonne réponse", max_length=80)
    mauvaises = discord.ui.TextInput(
        label="Mauvaises réponses (1 à 3, une par ligne)", style=discord.TextStyle.paragraph, max_length=260,
        placeholder="Une mauvaise réponse par ligne",
    )
    temps = discord.ui.TextInput(label="Temps en secondes (5 à 60)", default="20", required=False, max_length=2)

    def __init__(self, builder: "KahootBuilder"):
        super().__init__()
        self.builder = builder

    async def on_submit(self, interaction: discord.Interaction):
        raw_t = self.temps.value.strip() or "20"
        if not raw_t.isdigit() or not 5 <= int(raw_t) <= 60:
            return await interaction.response.send_message("⏱️ Le temps doit être entre 5 et 60 secondes.", ephemeral=True)
        q = kahoot_clean_question({
            "question": self.question.value, "bonne_reponse": self.bonne.value,
            "mauvaises": re.split(r"[\n|;]", self.mauvaises.value), "temps": int(raw_t),
        })
        if q is None:
            return await interaction.response.send_message(
                "🎯 Question invalide : il faut une question, une bonne réponse et **1 à 3** mauvaises réponses différentes.",
                ephemeral=True,
            )
        self.builder.questions.append(q)
        await interaction.response.edit_message(embed=self.builder.embed(), view=self.builder)


class KahootBuilder(_OwnerView):
    def __init__(self, invoker_id: int, name: str):
        super().__init__(invoker_id)
        self.timeout = 900
        self.kname = name
        self.questions: list[dict] = []
        self.origin: Optional[discord.Interaction] = None

    def embed(self) -> discord.Embed:
        lines = [f"`{i}.`  {q['question'][:70]}\n└ ✅ {q['bonne'][:30]}  •  ⏱️ {q['temps']}s" for i, q in enumerate(self.questions, 1)]
        body = fit_lines(lines, 3500) or "Aucune question pour l'instant : clique sur **Ajouter une question**."
        return emb(f"🎯 Nouveau Kahoot — {self.kname}"[:256], airy([body, f"📝 **{len(self.questions)}/{KAHOOT_MAX_Q}** question(s)"]), COLOR_PURPLE)

    @discord.ui.button(label="Ajouter une question", emoji="➕", style=discord.ButtonStyle.primary)
    async def b_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.questions) >= KAHOOT_MAX_Q:
            return await interaction.response.send_message(f"🎯 {KAHOOT_MAX_Q} questions maximum.", ephemeral=True)
        await interaction.response.send_modal(KahootQuestionModal(self))

    @discord.ui.button(label="Retirer la dernière", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def b_undo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.questions:
            self.questions.pop()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Enregistrer", emoji="💾", style=discord.ButtonStyle.success)
    async def b_save(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.questions:
            return await interaction.response.send_message("🎯 Ajoute au moins une question d'abord.", ephemeral=True)
        err = await kahoot_limit_error(interaction)
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        kid = await kahoot_save(interaction.guild_id, interaction.user.id, self.kname, self.questions)
        k = {"id": kid, "author_id": interaction.user.id, "title": self.kname, "questions": self.questions}
        self.stop()
        await interaction.response.edit_message(
            embed=emb(f"✅ Kahoot #{kid} enregistré", f"**{self.kname}** — {len(self.questions)} question(s).\n"
                      f"Relance-le quand tu veux avec `/kahoot lancer numero:{kid}`.", COLOR_PINK),
            view=KahootReadyView(interaction.user.id, k),
        )

    @discord.ui.button(label="Annuler", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def b_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(embed=emb("✖️ Annulé", "Rien n'a été enregistré.", COLOR_DARK), view=None)


# ---------- Génération par l'IA ----------
async def kahoot_generate_flow(interaction: discord.Interaction, theme: str, n: int, diff: str):
    """À appeler APRÈS un defer(ephemeral=True)."""
    err = await kahoot_limit_error(interaction)
    if err:
        return await interaction.followup.send(err, ephemeral=True)
    try:
        title, questions = await kahoot_ai_generate(theme, n, diff)
    except Exception as e:  # noqa: BLE001
        return await interaction.followup.send(fail_msg(e), ephemeral=True)
    kid = await kahoot_save(interaction.guild_id, interaction.user.id, title, questions)
    k = {"id": kid, "author_id": interaction.user.id, "title": title, "questions": questions}
    qlines = [f"`{i}.`  {q['question'][:80]}" for i, q in enumerate(questions[:15], 1)]
    head = f"📚 **{len(questions)}** question(s)  •  🎯 thème : **{theme[:60]}**  •  🔥 niveau **{diff}**"
    e = emb(f"🤖 Kahoot #{kid} généré — {title}"[:256], airy([head, fit_lines(qlines, 3300)]), COLOR_PINK)
    await interaction.followup.send(embed=e, view=KahootReadyView(interaction.user.id, k), ephemeral=True)


def _diff(raw: str) -> str:
    raw = plain(raw)
    return raw if raw in ("facile", "moyen", "difficile") else "moyen"


class KahootGenModal(SafeModal, title="🤖 Kahoot généré par l'IA"):
    theme = discord.ui.TextInput(label="Thème", max_length=100, placeholder="Ex : Harry Potter, histoire de France…")
    nombre = discord.ui.TextInput(label="Nombre de questions (3 à 15)", default="8", max_length=2)
    difficulte = discord.ui.TextInput(label="Difficulté (facile / moyen / difficile)", default="moyen", max_length=10)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.nombre.value.strip()
        if not raw.isdigit() or not 3 <= int(raw) <= 15:
            return await interaction.response.send_message("🔢 Le nombre de questions doit être entre 3 et 15.", ephemeral=True)
        wait = 30 - (time.time() - _kahoot_gen_cd.get(interaction.user.id, 0))
        if wait > 0:
            return await interaction.response.send_message(f"⏳ Réessaie dans {wait:.0f}s.", ephemeral=True)
        _kahoot_gen_cd[interaction.user.id] = time.time()
        await interaction.response.defer(ephemeral=True, thinking=True)
        await kahoot_generate_flow(interaction, self.theme.value.strip(), int(raw), _diff(self.difficulte.value))


class KahootTitleModal(SafeModal, title="🎯 Créer un Kahoot"):
    titre = discord.ui.TextInput(label="Titre du Kahoot", max_length=80)

    async def on_submit(self, interaction: discord.Interaction):
        err = await kahoot_limit_error(interaction)
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        builder = KahootBuilder(interaction.user.id, self.titre.value.strip())
        await interaction.response.send_message(embed=builder.embed(), view=builder, ephemeral=True)
        builder.origin = interaction


class KahootHubSelect(discord.ui.Select):
    def __init__(self, rows: list):
        super().__init__(
            placeholder="▶️ Lancer un Kahoot du serveur…", row=0,
            options=[discord.SelectOption(label=f"#{i} · {t}"[:100], value=str(i),
                                          description=f"{len(json.loads(q))} question(s)") for i, t, q in rows],
        )

    async def callback(self, interaction: discord.Interaction):
        k = await kahoot_get(interaction.guild_id, int(self.values[0]))
        if k is None:
            return await interaction.response.send_message("❌ Ce Kahoot n'existe plus.", ephemeral=True)
        await kahoot_open_lobby(interaction, k)


class KahootHub(_OwnerView):
    """Menu Kahoot (ouvert depuis /jeux) : lancer, générer avec l'IA ou créer le sien."""

    def __init__(self, invoker_id: int, rows: list):
        super().__init__(invoker_id)
        if rows:
            self.add_item(KahootHubSelect(rows))

    @discord.ui.button(label="Générer avec l'IA", emoji="🤖", style=discord.ButtonStyle.primary, row=1)
    async def b_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(KahootGenModal())

    @discord.ui.button(label="Créer le mien", emoji="✍️", style=discord.ButtonStyle.success, row=1)
    async def b_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(KahootTitleModal())


async def kahoot_autocomplete(interaction: discord.Interaction, current: str):
    if not interaction.guild_id:
        return []
    like = current.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = await db_all(
        "SELECT id, title, questions FROM kahoots WHERE guild_id=? AND (title LIKE ? ESCAPE '\\' "
        "OR CAST(id AS TEXT) LIKE ? ESCAPE '\\') ORDER BY id DESC LIMIT 25",
        (interaction.guild_id, f"%{like}%", f"{like}%"),
    )
    return [app_commands.Choice(name=f"#{i} · {t} ({len(json.loads(q))} q)"[:100], value=i) for i, t, q in rows]


kahoot_group = app_commands.Group(name="kahoot", description="Quiz live multi-joueurs façon Kahoot 🎯", guild_only=True)


@kahoot_group.command(name="creer", description="Crée ton Kahoot question par question ✍️")
@app_commands.describe(titre="Le titre du Kahoot")
async def kahoot_creer(interaction: discord.Interaction, titre: app_commands.Range[str, 3, 80]):
    err = await kahoot_limit_error(interaction)
    if err:
        return await interaction.response.send_message(err, ephemeral=True)
    builder = KahootBuilder(interaction.user.id, titre.strip())
    await interaction.response.send_message(embed=builder.embed(), view=builder, ephemeral=True)
    builder.origin = interaction


@kahoot_group.command(name="generer", description="L'IA crée un Kahoot pour toi 🤖")
@app_commands.describe(theme="Le thème du quiz", nombre="Nombre de questions (3 à 15)", difficulte="Niveau de difficulté")
@app_commands.choices(difficulte=[app_commands.Choice(name=n, value=n.lower()) for n in ("Facile", "Moyen", "Difficile")])
@app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
async def kahoot_generer(
    interaction: discord.Interaction, theme: app_commands.Range[str, 2, 100],
    nombre: app_commands.Range[int, 3, 15] = 8, difficulte: Optional[app_commands.Choice[str]] = None,
):
    await interaction.response.defer(ephemeral=True, thinking=True)
    await kahoot_generate_flow(interaction, theme.strip(), nombre, difficulte.value if difficulte else "moyen")


@kahoot_group.command(name="lancer", description="Lance un Kahoot dans ce salon ▶️")
@app_commands.describe(numero="Le Kahoot à jouer (choisis dans la liste)")
@app_commands.autocomplete(numero=kahoot_autocomplete)
async def kahoot_lancer(interaction: discord.Interaction, numero: int):
    k = await kahoot_get(interaction.guild_id, numero)
    if k is None:
        return await interaction.response.send_message("❌ Ce Kahoot n'existe pas.", ephemeral=True)
    await kahoot_open_lobby(interaction, k)


@kahoot_group.command(name="liste", description="Liste les Kahoot du serveur 📋")
@app_commands.describe(mes_kahoots="Ne voir que les miens")
async def kahoot_liste(interaction: discord.Interaction, mes_kahoots: bool = False):
    sql, params = "SELECT id, author_id, title, questions FROM kahoots WHERE guild_id=?", (interaction.guild_id,)
    if mes_kahoots:
        sql += " AND author_id=?"
        params += (interaction.user.id,)
    rows = await db_all(sql + " ORDER BY id DESC LIMIT 25", params)
    if not rows:
        return await interaction.response.send_message("Aucun Kahoot. Crée le premier avec `/kahoot creer` ou `/kahoot generer` 😏", ephemeral=True)
    lines = [f"`#{i}` **{t[:50]}** — {len(json.loads(q))} question(s) · <@{a}>" for i, a, t, q in rows]
    await interaction.response.send_message(
        embed=emb(f"🎯 Kahoot du serveur ({len(rows)})", "\n".join(lines)[:4000], COLOR_PINK),
        ephemeral=True, allowed_mentions=NO_PINGS,
    )


@kahoot_group.command(name="supprimer", description="Supprime un de tes Kahoot (ou n'importe lequel si tu es staff) 🗑️")
@app_commands.describe(numero="Le Kahoot à supprimer")
@app_commands.autocomplete(numero=kahoot_autocomplete)
async def kahoot_supprimer(interaction: discord.Interaction, numero: int):
    k = await kahoot_get(interaction.guild_id, numero)
    if k is None:
        return await interaction.response.send_message("❌ Ce Kahoot n'existe pas.", ephemeral=True)
    if k["author_id"] != interaction.user.id and not interaction.permissions.manage_messages:
        return await interaction.response.send_message("🚫 Ce n'est pas ton Kahoot.", ephemeral=True)
    await db_run("DELETE FROM kahoots WHERE guild_id=? AND id=?", (interaction.guild_id, numero))
    await interaction.response.send_message(f"🗑️ Kahoot **#{numero}** supprimé.", ephemeral=True)


bot.tree.add_command(kahoot_group)


# ---------------------------------------------------------------------
# 🎮 /jeux : panel avec TOUS les jeux (remplace l'ancien)
# ---------------------------------------------------------------------
_jeux_quiz_cd: dict[int, float] = {}


class JeuxPFCSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="✂️ Pierre-feuille-ciseaux contre moi : choisis ton coup…",
            options=[discord.SelectOption(label=n.capitalize(), value=n, emoji=e) for n, e in PFC.items()],
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if await feature_off(interaction, "f_jeux"):
            return
        n = self.values[0]
        spawn(log_cmd(interaction, "jeux › pfc", f"`choix` : {n}"))
        await pfc.callback(interaction, app_commands.Choice(name=n.capitalize(), value=n))


class DuelPickView(_OwnerView):
    def __init__(self, invoker_id: int, mise: int):
        super().__init__(invoker_id)
        self.mise = mise

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="⚔️ Qui veux-tu défier ?", min_values=1, max_values=1)
    async def pick(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        m = select.values[0]
        if not isinstance(m, discord.Member):
            return await interaction.response.send_message("Cette personne n'est pas sur le serveur.", ephemeral=True)
        await pfcduel.callback(interaction, m, self.mise)


class GamesPanel(discord.ui.View):
    """Tout le monde peut cliquer : chaque clic lance la partie pour la personne qui a cliqué."""

    def __init__(self, mise: int = 0):
        super().__init__(timeout=600)
        self.mise = mise
        self.message: Optional[discord.Message] = None
        self.add_item(JeuxPFCSelect())

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def _guard(self, interaction: discord.Interaction, label: str, key: str = "f_jeux") -> bool:
        """True = on peut continuer (fonctionnalité active) ; trace l'action dans les logs."""
        if await feature_off(interaction, key):
            return False
        spawn(log_cmd(interaction, f"jeux › {label}", f"`mise` : {self.mise}" if self.mise else ""))
        return True

    # ligne 0 : jeux de cartes & quiz
    @discord.ui.button(label="Blackjack solo", emoji="🃏", style=discord.ButtonStyle.primary, row=0)
    async def b_bj(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._guard(interaction, "blackjack solo"):
            await blackjack.callback(interaction, app_commands.Choice(name="Solo", value="solo"), self.mise)

    @discord.ui.button(label="Blackjack table", emoji="👥", style=discord.ButtonStyle.primary, row=0)
    async def b_bjt(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._guard(interaction, "blackjack table"):
            await blackjack.callback(interaction, app_commands.Choice(name="Table", value="table"), self.mise)

    @discord.ui.button(label="Poker", emoji="♠️", style=discord.ButtonStyle.primary, row=0)
    async def b_pk(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._guard(interaction, "poker"):
            await poker.callback(interaction, self.mise)

    @discord.ui.button(label="Quiz IA", emoji="🧠", style=discord.ButtonStyle.success, row=0)
    async def b_quiz(self, interaction: discord.Interaction, button: discord.ui.Button):
        wait = 8 - (time.time() - _jeux_quiz_cd.get(interaction.user.id, 0))
        if wait > 0:  # même cooldown que /quiz (protège le quota IA)
            return await interaction.response.send_message(f"⏳ Doucement, réessaie dans {wait:.0f}s.", ephemeral=True)
        if await self._guard(interaction, "quiz"):
            _jeux_quiz_cd[interaction.user.id] = time.time()
            await quiz.callback(interaction, None)

    @discord.ui.button(label="Quiz des membres", emoji="📝", style=discord.ButtonStyle.success, row=0)
    async def b_qp(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._guard(interaction, "quizperso"):
            await quizperso_jouer.callback(interaction, None)

    # ligne 1 : duel, Kahoot, stats
    @discord.ui.button(label="Duel PFC", emoji="⚔️", style=discord.ButtonStyle.danger, row=1)
    async def b_duel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await feature_off(interaction, "f_jeux"):
            return
        await interaction.response.send_message(
            "Choisis ton adversaire :", view=DuelPickView(interaction.user.id, self.mise), ephemeral=True
        )

    @discord.ui.button(label="Kahoot", emoji="🎯", style=discord.ButtonStyle.danger, row=1)
    async def b_kahoot(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await feature_off(interaction, "f_kahoot"):
            return
        rows = await db_all(
            "SELECT id, title, questions FROM kahoots WHERE guild_id=? ORDER BY id DESC LIMIT 25", (interaction.guild_id,)
        )
        txt = "🎯 **Kahoot** : lance une partie, génère un quiz avec l'IA ou crée le tien."
        if not rows:
            txt += "\nAucun Kahoot sur le serveur pour l'instant : crée le premier 😏"
        await interaction.response.send_message(txt, view=KahootHub(interaction.user.id, rows), ephemeral=True)

    @discord.ui.button(label="Classement", emoji="🏆", style=discord.ButtonStyle.secondary, row=1)
    async def b_top(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._guard(interaction, "classement"):
            await classement.callback(interaction, None)

    @discord.ui.button(label="Mes stats", emoji="📊", style=discord.ButtonStyle.secondary, row=1)
    async def b_stat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._guard(interaction, "statu"):
            await statu.callback(interaction, None)

    @discord.ui.button(label="Solde", emoji="🪙", style=discord.ButtonStyle.secondary, row=1)
    async def b_solde(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._guard(interaction, "solde"):
            await solde.callback(interaction, None)

    # ligne 3 : règles & bonus
    @discord.ui.button(label="Règles BJ", emoji="📖", style=discord.ButtonStyle.secondary, row=3)
    async def b_rbj(self, interaction: discord.Interaction, button: discord.ui.Button):
        await regleblackjack.callback(interaction)

    @discord.ui.button(label="Règles poker", emoji="📖", style=discord.ButtonStyle.secondary, row=3)
    async def b_rpk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await reglepoker.callback(interaction)

    @discord.ui.button(label="Mains", emoji="🂡", style=discord.ButtonStyle.secondary, row=3)
    async def b_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        await main_cmd.callback(interaction)

    @discord.ui.button(label="Bonus /daily", emoji="🎁", style=discord.ButtonStyle.secondary, row=3)
    async def b_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._guard(interaction, "daily"):
            await daily.callback(interaction)

    @discord.ui.button(label="Créer un quiz", emoji="✍️", style=discord.ButtonStyle.secondary, row=3)
    async def b_mkquiz(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._guard(interaction, "quizperso creer"):
            await quizperso_creer.callback(interaction)


@bot.tree.command(name="jeux", description="Ouvre le panel avec tous les jeux 🎮")
@app_commands.describe(mise="Mise en pièces pour le blackjack et le poker (0 = sans mise)")
@app_commands.guild_only()
async def jeux(interaction: discord.Interaction, mise: app_commands.Range[int, 0, 1_000_000_000] = 0):
    err = await bet_error(interaction.guild_id, interaction.user.id, mise)
    if err:
        return await interaction.response.send_message(err, ephemeral=True)
    e = emb("🎮 Salle de jeux", f"Clique sur un jeu pour jouer contre {BOT_NAME} (ou entre vous) 😈", COLOR_PURPLE)
    e.add_field(name="🃏 Blackjack", value="Solo contre moi, ou table jusqu'à 5 joueurs.", inline=True)
    e.add_field(name="♠️ Poker", value="Texas Hold'em jusqu'à 6 joueurs, relances si mise.", inline=True)
    e.add_field(name="✂️ Pierre-feuille-ciseaux", value="Contre moi (menu) ou en duel ⚔️.", inline=True)
    e.add_field(name="🧠 Quiz", value="Quiz IA ou quiz créés par les membres.", inline=True)
    e.add_field(name="🎯 Kahoot", value="Quiz live multi-joueurs : crée le tien ou laisse l'IA le faire.", inline=True)
    e.add_field(name="🏆 Stats", value="Classement, profil, solde, règles et classement des mains.", inline=True)
    if mise:
        e.add_field(name="💰 Mise active", value=f"**{mise}** {COIN} sur le blackjack et le poker.", inline=False)
    elif await eco_on(interaction.guild_id):
        e.add_field(name="💰 Mises", value="Relance avec `/jeux mise:100` pour jouer des pièces (`/solde`, `/daily`).", inline=False)
    view = GamesPanel(mise)
    await interaction.response.send_message(embed=e, view=view)
    view.message = await interaction.original_response()


# =====================================================================
# 📜 /regle : règles du serveur à ACCEPTER pour rester (refus ou délai dépassé = expulsion)
#   /regle serveur → admin : texte, salon, rôle donné à l'acceptation, délai, activation.
#   /regle afficher → tout le monde : relire les règles.
#   À l'arrivée, le bot poste les règles avec « J'accepte / Je refuse » (réservé au nouveau membre).
#   Les demandes en attente sont en base : elles survivent à un redémarrage du bot.
# =====================================================================
RULES_DEFAULT_DELAY = 10   # minutes pour accepter avant l'expulsion
RULES_TEXT_MAX = 3500


async def rules_delay(gid: int) -> int:
    d = await get_int(gid, "rules_delay")
    return d if 1 <= d <= 1440 else RULES_DEFAULT_DELAY


def rules_prompt_embed(guild: discord.Guild, text: str, deadline: int) -> discord.Embed:
    e = discord.Embed(title=f"📜 Règles de {guild.name}"[:250], description=text[:RULES_TEXT_MAX], color=COLOR_PURPLE)
    e.add_field(
        name="⚠️ Obligatoire",
        value=(
            "Tu dois **accepter** ces règles pour rester sur le serveur.\n"
            f"Si tu refuses, ou sans réponse avant <t:{deadline}:R>, tu seras expulsé(e)."
        ),
        inline=False,
    )
    e.set_footer(text=f"Seul(e) le nouveau membre peut répondre • {BOT_NAME} 🖤")
    return e


async def rules_claim(gid: int, uid: int) -> Optional[tuple[int, int]]:
    """Retire la demande en attente de façon atomique. Renvoie (salon, message) si on l'a « prise », sinon None
    (déjà traitée par un clic ou par la boucle : impossible de traiter deux fois la même personne)."""
    rows = await db_all(
        "SELECT channel_id, message_id FROM rules_pending WHERE guild_id=? AND user_id=?", (gid, uid)
    )
    if not rows:
        return None
    cur = await bot.db.execute("DELETE FROM rules_pending WHERE guild_id=? AND user_id=?", (gid, uid))
    await bot.db.commit()
    return (rows[0][0], rows[0][1]) if cur.rowcount == 1 else None


async def rules_delete_prompt(channel_id: int, message_id: int):
    if not message_id:
        return
    ch = bot.get_channel(channel_id)
    if ch is None:
        return
    try:
        await ch.get_partial_message(message_id).delete()
    except discord.HTTPException:
        pass


async def delete_later(channel_id: int, message_id: int, delay: float = 8):
    await asyncio.sleep(delay)
    await rules_delete_prompt(channel_id, message_id)


async def rules_drop(gid: int, uid: int):
    """Le membre est parti : on oublie sa demande et on range le message."""
    try:
        claimed = await rules_claim(gid, uid)
        if claimed:
            await rules_delete_prompt(*claimed)
    except Exception:  # noqa: BLE001
        log.exception("rules_drop")


async def rules_log(guild: discord.Guild, member: discord.abc.User, title: str, color: int, cat: str, detail: str = ""):
    e = discord.Embed(title=title, color=color)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Membre", value=f"{member.mention} (`{member.id}`)", inline=True)
    if detail:
        e.add_field(name="Détails", value=detail[:900], inline=False)
    e.timestamp = discord.utils.utcnow()
    await mod_log(guild, e, cat)


async def rules_kick(guild: discord.Guild, member: discord.Member, why: str) -> tuple[bool, str]:
    """Expulse un membre qui n'a pas accepté les règles. Renvoie (réussi, détail). Jamais un admin / le proprio."""
    perms = member.guild_permissions
    if member.id == guild.owner_id or perms.administrator or perms.manage_guild:
        return False, "membre du staff : non expulsé"
    me = guild.me
    if me is None or not me.guild_permissions.kick_members:
        return False, "il me manque la permission « Expulser des membres »"
    if member.top_role >= me.top_role:
        return False, "son rôle est au-dessus du mien (hiérarchie)"
    try:
        await member.send(
            f"📜 Tu n'as pas accepté les règles de **{guild.name}** ({why}), donc tu ne peux pas rester. "
            "Tu peux revenir quand tu veux et les accepter 🖤"
        )
    except discord.HTTPException:
        pass  # MP fermés
    try:
        await member.kick(reason=f"Règles non acceptées ({why})")
    except discord.HTTPException as e:
        log.warning("Expulsion (règles) impossible : %s", e)
        return False, "Discord a refusé l'expulsion"
    return True, "expulsé(e)"


async def rules_on_join(member: discord.Member):
    gid = member.guild.id
    try:
        if member.bot or not await get_flag(gid, "rules_on", False):
            return
        text = (await get_setting(gid, "rules_text", "")).strip()
        ch = member.guild.get_channel(await get_int(gid, "rules_channel"))
        if not text or ch is None:
            log.warning("Règles activées mais texte ou salon manquant sur %s : personne n'est sanctionné", gid)
            return
        p = ch.permissions_for(member.guild.me)
        if not (p.send_messages and p.embed_links):
            log.warning("Règles : je ne peux pas écrire dans #%s (%s)", ch.name, gid)
            return
        deadline = int(time.time()) + await rules_delay(gid) * 60
        await db_run(
            "INSERT OR REPLACE INTO rules_pending(guild_id, user_id, deadline, channel_id, message_id) VALUES (?,?,?,?,0)",
            (gid, member.id, deadline, ch.id),
        )
        view = discord.ui.View(timeout=None)
        view.add_item(RulesButton("ok", gid, member.id))
        view.add_item(RulesButton("no", gid, member.id))
        try:
            msg = await ch.send(
                content=member.mention, embed=rules_prompt_embed(member.guild, text, deadline), view=view,
                allowed_mentions=discord.AllowedMentions(users=[member], roles=False, everyone=False),
            )
        except discord.HTTPException as e:
            # impossible de lui montrer les règles : on ne le punit pas pour ça
            await db_run("DELETE FROM rules_pending WHERE guild_id=? AND user_id=?", (gid, member.id))
            log.warning("Règles : envoi impossible (%s)", e)
            return
        await db_run("UPDATE rules_pending SET message_id=? WHERE guild_id=? AND user_id=?", (msg.id, gid, member.id))
    except Exception:  # noqa: BLE001
        log.exception("rules_on_join")


class RulesButton(discord.ui.DynamicItem[discord.ui.Button], template=r"rl:(?P<act>ok|no):(?P<gid>[0-9]+):(?P<uid>[0-9]+)"):
    def __init__(self, act: str, gid: int, uid: int):
        ok = act == "ok"
        super().__init__(discord.ui.Button(
            label="J'accepte" if ok else "Je refuse", emoji="✅" if ok else "🚪",
            style=discord.ButtonStyle.success if ok else discord.ButtonStyle.danger,
            custom_id=f"rl:{act}:{gid}:{uid}",
        ))
        self.act, self.gid, self.uid = act, gid, uid

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match, /):
        return cls(match["act"], int(match["gid"]), int(match["uid"]))

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid:
            return await interaction.response.send_message("Ces règles ne sont pas pour toi 😏", ephemeral=True)
        guild = interaction.guild
        member = interaction.user if isinstance(interaction.user, discord.Member) else (guild.get_member(self.uid) if guild else None)
        if guild is None or guild.id != self.gid or member is None:
            return await interaction.response.send_message("😅 Je ne te trouve plus sur ce serveur.", ephemeral=True)
        claimed = await rules_claim(self.gid, self.uid)
        if claimed is None:
            return await interaction.response.send_message("⌛ Cette demande n'est plus valable.", ephemeral=True)
        cid = interaction.channel_id or claimed[0]
        mid = interaction.message.id if interaction.message else claimed[1]
        if self.act == "ok":
            role_txt = None
            rid = await get_int(self.gid, "rules_role")
            role = guild.get_role(rid) if rid else None
            if role is not None:
                try:
                    await member.add_roles(role, reason="Règles acceptées")
                    role_txt = role.mention
                except discord.HTTPException as e:
                    log.warning("Règles : rôle non donné (%s)", e)
            await interaction.response.edit_message(
                content=None, embed=emb("✅ Règles acceptées", f"Merci {member.mention}, bienvenue ! 🖤", COLOR_PINK), view=None
            )
            spawn(delete_later(cid, mid))
            spawn(rules_log(guild, member, "✅ Règles acceptées", COLOR_PINK, "arrivees",
                            f"Rôle donné : {role_txt}" if role_txt else ""))
        else:
            await interaction.response.edit_message(
                content=None,
                embed=emb("🚪 Règles refusées", "Tu ne peux pas rester sans les accepter. À bientôt, peut-être 🖤", COLOR_DARK),
                view=None,
            )
            spawn(delete_later(cid, mid))
            ok, detail = await rules_kick(guild, member, "règles refusées")
            await rules_log(guild, member, "👢 Sanction — Règles refusées", 0xFF7A7A, "sanctions", detail)


@tasks.loop(seconds=30)
async def rules_loop():
    """Expulse ceux qui n'ont pas répondu à temps."""
    try:
        rows = await db_all("SELECT guild_id, user_id FROM rules_pending WHERE deadline<=?", (int(time.time()),))
    except Exception:  # noqa: BLE001
        log.exception("rules_loop : lecture impossible")
        return
    for gid, uid in rows:
        try:
            claimed = await rules_claim(gid, uid)
            if claimed is None:
                continue
            await rules_delete_prompt(*claimed)
            guild = bot.get_guild(gid)
            member = guild.get_member(uid) if guild else None
            if member is None or not await get_flag(gid, "rules_on", False):
                continue  # parti entre-temps, ou système coupé : rien à faire
            ok, detail = await rules_kick(guild, member, "délai dépassé")
            await rules_log(guild, member, "👢 Sanction — Règles non acceptées (délai dépassé)", 0xFF7A7A, "sanctions", detail)
        except Exception:  # noqa: BLE001
            log.exception("rules_loop : traitement de %s/%s impossible", gid, uid)


@rules_loop.before_loop
async def _before_rules_loop():
    await bot.wait_until_ready()


async def rules_set_enabled(guild: discord.Guild, on: bool) -> Optional[str]:
    """Active / coupe le système. Renvoie un message d'erreur si les prérequis manquent."""
    gid = guild.id
    if on:
        if not (await get_setting(gid, "rules_text", "")).strip():
            return "Écris d'abord les règles (`/regle serveur texte:True`)."
        if guild.get_channel(await get_int(gid, "rules_channel")) is None:
            return "Choisis d'abord un salon avec `/regle serveur salon:#règles`."
        if not guild.me.guild_permissions.kick_members:
            return "Il me faut la permission « Expulser des membres » pour faire respecter les règles."
    await set_flag(gid, "rules_on", on)
    return None


async def rules_state_embed(guild: discord.Guild) -> discord.Embed:
    gid = guild.id
    on = await get_flag(gid, "rules_on", False)
    cid, rid = await get_int(gid, "rules_channel"), await get_int(gid, "rules_role")
    text = (await get_setting(gid, "rules_text", "")).strip()
    pending = (await db_all("SELECT COUNT(*) FROM rules_pending WHERE guild_id=?", (gid,)))[0][0]
    e = emb("📜 Règles du serveur", None, COLOR_PINK)
    e.add_field(name="État", value="🟢 Obligatoires (expulsion sinon)" if on else "🔴 Désactivées", inline=True)
    e.add_field(name="Salon", value=f"<#{cid}>" if cid else "— (à définir)", inline=True)
    e.add_field(name="Rôle donné", value=f"<@&{rid}>" if rid else "Aucun", inline=True)
    e.add_field(name="Délai pour accepter", value=f"{await rules_delay(gid)} min", inline=True)
    e.add_field(
        name="Permission « Expulser »",
        value="✅ OK" if guild.me.guild_permissions.kick_members else "❌ Manquante", inline=True,
    )
    e.add_field(name="En attente", value=str(pending), inline=True)
    e.add_field(
        name="Aperçu du texte",
        value=(quote_block(text[:700])[:1000] + ("\n…" if len(text) > 700 else "")) if text else "_Pas encore de règles._",
        inline=False,
    )
    return e


class RulesTextModal(SafeModal):
    def __init__(self, enable: Optional[bool], current: str):
        super().__init__(title="📜 Règles du serveur", timeout=900)
        self.enable = enable
        self.texte = discord.ui.TextInput(
            label="Les règles à accepter", style=discord.TextStyle.paragraph, max_length=RULES_TEXT_MAX,
            default=current[:RULES_TEXT_MAX] or None,
            placeholder="1. Respect de tous\n2. Pas de pub\n3. …",
        )
        self.add_item(self.texte)

    async def on_submit(self, interaction: discord.Interaction):
        text = self.texte.value.strip()
        if len(text) < 10:
            return await interaction.response.send_message("📜 Trop court : écris de vraies règles 😏", ephemeral=True)
        await set_setting(interaction.guild_id, "rules_text", text)
        err = None
        if self.enable is not None:
            err = await rules_set_enabled(interaction.guild, self.enable)
        await interaction.response.send_message(
            content="✅ Règles enregistrées." + (f"\n⚠️ {err}" if err else ""),
            embed=await rules_state_embed(interaction.guild), ephemeral=True,
        )


regle_group = app_commands.Group(name="regle", description="Règles du serveur (à accepter pour rester) 📜", guild_only=True)


@regle_group.command(name="serveur", description="(admin) Règles obligatoires : sans acceptation, on ne reste pas 📜")
@app_commands.describe(
    actif="Activer / couper l'obligation d'accepter les règles",
    salon="Salon où les nouveaux voient les règles (visible par les nouveaux membres !)",
    role="Rôle donné quand les règles sont acceptées (optionnel)",
    sans_role="Retirer le rôle donné à l'acceptation",
    delai="Minutes pour accepter avant l'expulsion (défaut 10)",
    texte="Écrire / modifier le texte des règles (s'ouvre automatiquement s'il n'y en a pas)",
)
@admin_only
async def regle_serveur(
    interaction: discord.Interaction, actif: Optional[bool] = None, salon: Optional[discord.TextChannel] = None,
    role: Optional[discord.Role] = None, sans_role: bool = False,
    delai: Optional[app_commands.Range[int, 1, 1440]] = None, texte: bool = False,
):
    guild, gid = interaction.guild, interaction.guild_id
    if salon is not None:
        p = salon.permissions_for(guild.me)
        if not (p.view_channel and p.send_messages and p.embed_links):
            return await interaction.response.send_message(
                f"🚫 Il me manque « Envoyer des messages » et « Intégrer des liens » dans {salon.mention}.", ephemeral=True
            )
    if role is not None:
        problem = role_problem(role, guild)
        if problem:
            return await interaction.response.send_message(f"🚫 {problem}", ephemeral=True)
    if salon is not None:
        await set_setting(gid, "rules_channel", str(salon.id))
    if sans_role:
        await set_setting(gid, "rules_role", "0")
    elif role is not None:
        await set_setting(gid, "rules_role", str(role.id))
    if delai is not None:
        await set_setting(gid, "rules_delay", str(delai))
    current = (await get_setting(gid, "rules_text", "")).strip()
    if texte or (not current and actif is not False):  # pas de règles encore : on ouvre la fenêtre d'écriture
        return await interaction.response.send_modal(RulesTextModal(actif, current))
    err = await rules_set_enabled(guild, actif) if actif is not None else None
    await interaction.response.send_message(
        content=f"⚠️ {err}" if err else None, embed=await rules_state_embed(guild), ephemeral=True
    )


@regle_group.command(name="afficher", description="Relis les règles du serveur 📜")
@app_commands.describe(public="Les afficher pour tout le monde dans le salon")
async def regle_afficher(interaction: discord.Interaction, public: bool = False):
    text = (await get_setting(interaction.guild_id, "rules_text", "")).strip()
    if not text:
        return await interaction.response.send_message("📜 Aucune règle n'a encore été définie sur ce serveur.", ephemeral=True)
    e = discord.Embed(title=f"📜 Règles de {interaction.guild.name}"[:250], description=text[:4000], color=COLOR_PURPLE)
    e.set_footer(text=f"{BOT_NAME} 🖤")
    await interaction.response.send_message(embed=e, ephemeral=not public)


bot.tree.add_command(regle_group)


# =====================================================================
# 🎉 /givawayyy : giveaways à bouton (participation persistante, tirage automatique, relance possible)
#   lancer • terminer • relancer • annuler • liste   (permission « Gérer le serveur »)
#   Le nom de la commande se change avec la constante GW_CMD en haut du fichier.
# =====================================================================
GW_MAX_OPEN = 20       # giveaways ouverts en même temps par serveur
GW_MAX_WINNERS = 20


async def gw_get(gwid: int) -> Optional[dict]:
    rows = await db_all(
        "SELECT id, guild_id, channel_id, message_id, host_id, prize, winners, role_id, ends_at, status, winner_ids "
        "FROM giveaways WHERE id=?", (gwid,),
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "id": r[0], "guild_id": r[1], "channel_id": r[2], "message_id": r[3], "host_id": r[4], "prize": r[5],
        "winners": r[6], "role_id": r[7], "ends_at": r[8], "status": r[9],
        "winner_ids": [int(x) for x in r[10].split(",") if x.strip().isdigit()],
    }


async def gw_count(gwid: int) -> int:
    return (await db_all("SELECT COUNT(*) FROM giveaway_entries WHERE giveaway_id=?", (gwid,)))[0][0]


def gw_embed(g: dict, count: int) -> discord.Embed:
    st = g["status"]
    plural = "s" if g["winners"] > 1 else ""
    if st == "open":
        lines = [
            "Clique sur **🎉 Participer** pour tenter ta chance ! _(re-clique pour te retirer)_",
            f"⏳ Fin : <t:{g['ends_at']}:R> (<t:{g['ends_at']}:f>)",
            f"👑 Organisé par : <@{g['host_id']}>",
            f"🏆 Gagnant{plural} : **{g['winners']}**",
        ]
        if g["role_id"]:
            lines.append(f"🎭 Rôle requis : <@&{g['role_id']}>")
        color = COLOR_PINK
    elif st == "ended":
        won = ", ".join(f"<@{u}>" for u in g["winner_ids"])
        lines = [
            "🔒 **Giveaway terminé**",
            f"🏆 Gagnant{'s' if len(g['winner_ids']) > 1 else ''} : {won}" if won else "😅 Personne n'a pu gagner.",
            f"👑 Organisé par : <@{g['host_id']}>",
        ]
        color = COLOR_DARK
    else:
        lines = ["🚫 **Giveaway annulé**", f"👑 Organisé par : <@{g['host_id']}>"]
        color = COLOR_DARK
    e = discord.Embed(title=f"🎉 {g['prize']}"[:250], description="\n\n".join(lines), color=color)
    e.set_footer(text=f"Giveaway #{g['id']} • {count} participant{'s' if count > 1 else ''} • {BOT_NAME} 🖤")
    return e


class GiveawayJoin(discord.ui.DynamicItem[discord.ui.Button], template=r"gw:join:(?P<gwid>[0-9]+)"):
    def __init__(self, gwid: int):
        super().__init__(discord.ui.Button(
            label="Participer", emoji="🎉", style=discord.ButtonStyle.success, custom_id=f"gw:join:{gwid}",
        ))
        self.gwid = gwid

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match, /):
        return cls(int(match["gwid"]))

    async def callback(self, interaction: discord.Interaction):
        g = await gw_get(self.gwid)
        if g is None or g["status"] != "open" or g["ends_at"] <= time.time():
            return await interaction.response.send_message("🔒 Ce giveaway est terminé.", ephemeral=True)
        user = interaction.user
        if g["role_id"] and not (isinstance(user, discord.Member) and any(r.id == g["role_id"] for r in user.roles)):
            return await interaction.response.send_message(
                f"🎭 Il te faut le rôle <@&{g['role_id']}> pour participer.", ephemeral=True, allowed_mentions=NO_PINGS
            )
        have = await db_all("SELECT 1 FROM giveaway_entries WHERE giveaway_id=? AND user_id=?", (self.gwid, user.id))
        if have:  # re-cliquer retire sa participation
            await bot.db.execute("DELETE FROM giveaway_entries WHERE giveaway_id=? AND user_id=?", (self.gwid, user.id))
        else:
            await bot.db.execute("INSERT OR IGNORE INTO giveaway_entries(giveaway_id, user_id) VALUES (?,?)", (self.gwid, user.id))
        await bot.db.commit()
        await interaction.response.edit_message(embed=gw_embed(g, await gw_count(self.gwid)))
        await interaction.followup.send(
            "➖ Participation retirée." if have else "✅ Tu participes ! Bonne chance 🍀", ephemeral=True
        )


def gw_view(gwid: int) -> discord.ui.View:
    v = discord.ui.View(timeout=None)
    v.add_item(GiveawayJoin(gwid))
    return v


async def gw_channel(cid: int):
    ch = bot.get_channel(cid)
    if ch is None:
        try:
            ch = await bot.fetch_channel(cid)
        except discord.HTTPException:
            return None
    return ch


async def gw_pick(g: dict, n: int, exclude=()) -> list[int]:
    """Tire jusqu'à n gagnants parmi les participants encore présents (et ayant le rôle requis, s'il y en a un)."""
    guild = bot.get_guild(g["guild_id"])
    if guild is None:
        return []
    ids = [r[0] for r in await db_all("SELECT user_id FROM giveaway_entries WHERE giveaway_id=?", (g["id"],))
           if r[0] not in exclude]
    random.shuffle(ids)
    out: list[int] = []
    for uid in ids:
        if len(out) >= n:
            break
        m = guild.get_member(uid)
        if m is None:
            try:
                m = await guild.fetch_member(uid)
            except discord.HTTPException:
                continue  # il a quitté le serveur
        if m.bot or (g["role_id"] and all(r.id != g["role_id"] for r in m.roles)):
            continue
        out.append(uid)
    return out


async def gw_announce(g: dict, ch, winners: list[int], reroll: bool = False):
    if winners:
        who = ", ".join(f"<@{u}>" for u in winners)
        verb = "Tu remportes" if len(winners) == 1 else "Vous remportez"
        text = f"{'🔁 Nouveau tirage : ' if reroll else '🎉 '}Félicitations {who} ! {verb} **{g['prize']}** 🖤"
    else:
        text = f"😅 Personne n'est éligible pour **{g['prize']}**…"
    mentions = discord.AllowedMentions(users=True, roles=False, everyone=False, replied_user=False)
    try:
        await ch.get_partial_message(g["message_id"]).reply(text[:2000], allowed_mentions=mentions, mention_author=False)
    except discord.HTTPException:  # message d'origine supprimé : on poste simplement dans le salon
        try:
            await ch.send(text[:2000], allowed_mentions=mentions)
        except discord.HTTPException:
            pass


async def gw_refresh_message(g: dict, view=None):
    ch = await gw_channel(g["channel_id"])
    if ch is None:
        return None
    try:
        await ch.get_partial_message(g["message_id"]).edit(embed=gw_embed(g, await gw_count(g["id"])), view=view)
    except discord.HTTPException:
        pass
    return ch


async def gw_finish(gwid: int) -> Optional[list[int]]:
    """Termine un giveaway : tirage, mise à jour du message et annonce. None s'il était déjà terminé / introuvable."""
    cur = await bot.db.execute("UPDATE giveaways SET status='ended' WHERE id=? AND status='open'", (gwid,))
    await bot.db.commit()
    if cur.rowcount != 1:  # déjà pris en charge (clic « terminer » + boucle en même temps)
        return None
    g = await gw_get(gwid)
    winners = await gw_pick(g, g["winners"])
    await db_run("UPDATE giveaways SET winner_ids=? WHERE id=?", (",".join(map(str, winners)), gwid))
    g["winner_ids"] = winners
    ch = await gw_refresh_message(g)
    if ch is not None:
        await gw_announce(g, ch, winners)
    guild = bot.get_guild(g["guild_id"])
    if guild is not None:
        le = discord.Embed(title="🎉 Giveaway terminé", color=COLOR_PINK)
        le.add_field(name="Lot", value=g["prize"][:200], inline=True)
        le.add_field(name="Giveaway", value=f"#{gwid}", inline=True)
        le.add_field(name="Gagnants", value=", ".join(f"<@{u}>" for u in winners) or "Personne", inline=False)
        le.timestamp = discord.utils.utcnow()
        await mod_log(guild, le, "admin")
    return winners


@tasks.loop(seconds=20)
async def giveaway_loop():
    try:
        rows = await db_all("SELECT id FROM giveaways WHERE status='open' AND ends_at<=?", (int(time.time()),))
    except Exception:  # noqa: BLE001
        log.exception("giveaway_loop : lecture impossible")
        return
    for (gwid,) in rows:
        try:
            await gw_finish(gwid)
        except Exception:  # noqa: BLE001
            log.exception("giveaway_loop : fin du giveaway %s impossible", gwid)


@giveaway_loop.before_loop
async def _before_giveaway_loop():
    await bot.wait_until_ready()


def gw_autocomplete(status: str):
    async def ac(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[int]]:
        if not interaction.guild_id:
            return []
        rows = await db_all(
            "SELECT id, prize FROM giveaways WHERE guild_id=? AND status=? ORDER BY id DESC LIMIT 50",
            (interaction.guild_id, status),
        )
        cur = current.lower().strip().lstrip("#")
        return [
            app_commands.Choice(name=f"#{i} · {p}"[:100], value=i)
            for i, p in rows if not cur or cur in str(i) or cur in p.lower()
        ][:25]
    return ac


giveaway_group = app_commands.Group(
    name=GW_CMD, description="(staff) Giveaways 🎉", guild_only=True,
    default_permissions=discord.Permissions(manage_guild=True),
)


async def gw_load(interaction: discord.Interaction, gwid: int, want: str) -> Optional[dict]:
    """Charge un giveaway du serveur dans l'état voulu ; sinon répond une erreur et renvoie None."""
    g = await gw_get(gwid)
    if g is None or g["guild_id"] != interaction.guild_id:
        await interaction.response.send_message("🎉 Giveaway introuvable (choisis dans la liste).", ephemeral=True)
        return None
    if g["status"] != want:
        etat = {"open": "ouvert", "ended": "terminé", "cancelled": "annulé"}[g["status"]]
        need = {"open": "encore ouvert", "ended": "terminé"}[want]
        await interaction.response.send_message(f"🎉 Le giveaway #{gwid} est {etat} : il doit être {need}.", ephemeral=True)
        return None
    return g


@giveaway_group.command(name="lancer", description="Lance un giveaway avec un bouton Participer 🎉")
@app_commands.describe(
    lot="Ce qui est à gagner", duree="Durée : 30m, 2h, 1j… (max 28 jours)",
    gagnants=f"Nombre de gagnants (1 à {GW_MAX_WINNERS}, défaut 1)", salon="Salon où publier (ici par défaut)",
    role_requis="Rôle obligatoire pour participer (optionnel)",
)
@staff_only
async def gw_lancer(
    interaction: discord.Interaction, lot: app_commands.Range[str, 1, 200], duree: str,
    gagnants: app_commands.Range[int, 1, GW_MAX_WINNERS] = 1, salon: Optional[discord.TextChannel] = None,
    role_requis: Optional[discord.Role] = None,
):
    minutes = parse_minutes(duree)
    if minutes is None:
        return await interaction.response.send_message("⏱️ Durée invalide : `30m`, `2h`, `1j` (max 28 jours).", ephemeral=True)
    channel = salon or interaction.channel
    if not isinstance(channel, discord.TextChannel):
        return await interaction.response.send_message("🎉 Choisis un salon textuel.", ephemeral=True)
    p = channel.permissions_for(interaction.guild.me)
    if not (p.send_messages and p.embed_links):
        return await interaction.response.send_message(
            f"🚫 Il me manque « Envoyer des messages » et « Intégrer des liens » dans {channel.mention}.", ephemeral=True
        )
    n_open = (await db_all("SELECT COUNT(*) FROM giveaways WHERE guild_id=? AND status='open'", (interaction.guild_id,)))[0][0]
    if n_open >= GW_MAX_OPEN:
        return await interaction.response.send_message(
            f"🎉 Déjà {GW_MAX_OPEN} giveaways en cours : termine ou annule-en un d'abord.", ephemeral=True
        )
    role_id = role_requis.id if role_requis is not None and not role_requis.is_default() else 0
    await interaction.response.defer(ephemeral=True)
    cur = await bot.db.execute(
        "INSERT INTO giveaways(guild_id, channel_id, host_id, prize, winners, role_id, ends_at) VALUES (?,?,?,?,?,?,?)",
        (interaction.guild_id, channel.id, interaction.user.id, lot.strip(), gagnants, role_id,
         int(time.time()) + minutes * 60),
    )
    await bot.db.commit()
    gwid = cur.lastrowid
    g = await gw_get(gwid)
    try:
        msg = await channel.send(embed=gw_embed(g, 0), view=gw_view(gwid), allowed_mentions=NO_PINGS)
    except discord.HTTPException:
        await db_run("DELETE FROM giveaways WHERE id=?", (gwid,))
        return await interaction.followup.send(f"🚫 Je n'ai pas pu publier dans {channel.mention}.", ephemeral=True)
    await db_run("UPDATE giveaways SET message_id=? WHERE id=?", (msg.id, gwid))
    await interaction.followup.send(f"✅ Giveaway **#{gwid}** lancé : {msg.jump_url}", ephemeral=True)


@giveaway_group.command(name="terminer", description="Termine un giveaway maintenant et tire les gagnants 🏁")
@app_commands.describe(giveaway="Le giveaway à terminer")
@app_commands.autocomplete(giveaway=gw_autocomplete("open"))
@staff_only
async def gw_terminer(interaction: discord.Interaction, giveaway: int):
    if await gw_load(interaction, giveaway, "open") is None:
        return
    await interaction.response.defer(ephemeral=True)
    winners = await gw_finish(giveaway)
    if winners is None:
        return await interaction.followup.send("🎉 Il vient d'être terminé.", ephemeral=True)
    await interaction.followup.send(
        f"🏁 Giveaway #{giveaway} terminé : " + (", ".join(f"<@{u}>" for u in winners) or "personne d'éligible."),
        ephemeral=True, allowed_mentions=NO_PINGS,
    )


@giveaway_group.command(name="relancer", description="Retire de nouveaux gagnants d'un giveaway terminé 🔁")
@app_commands.describe(giveaway="Le giveaway terminé", nombre="Combien de nouveaux gagnants (défaut 1)")
@app_commands.autocomplete(giveaway=gw_autocomplete("ended"))
@staff_only
async def gw_relancer(
    interaction: discord.Interaction, giveaway: int, nombre: app_commands.Range[int, 1, GW_MAX_WINNERS] = 1
):
    g = await gw_load(interaction, giveaway, "ended")
    if g is None:
        return
    await interaction.response.defer(ephemeral=True)
    new = await gw_pick(g, nombre, exclude=set(g["winner_ids"]))
    if not new:
        return await interaction.followup.send("😅 Personne d'autre n'est éligible.", ephemeral=True)
    g["winner_ids"] = g["winner_ids"] + new
    await db_run("UPDATE giveaways SET winner_ids=? WHERE id=?", (",".join(map(str, g["winner_ids"])), giveaway))
    ch = await gw_refresh_message(g)
    if ch is not None:
        await gw_announce(g, ch, new, reroll=True)
    await interaction.followup.send(
        "🔁 Nouveaux gagnants : " + ", ".join(f"<@{u}>" for u in new), ephemeral=True, allowed_mentions=NO_PINGS
    )


@giveaway_group.command(name="annuler", description="Annule un giveaway sans tirer de gagnant 🚫")
@app_commands.describe(giveaway="Le giveaway à annuler")
@app_commands.autocomplete(giveaway=gw_autocomplete("open"))
@staff_only
async def gw_annuler(interaction: discord.Interaction, giveaway: int):
    if await gw_load(interaction, giveaway, "open") is None:
        return
    cur = await bot.db.execute("UPDATE giveaways SET status='cancelled' WHERE id=? AND status='open'", (giveaway,))
    await bot.db.commit()
    if cur.rowcount != 1:
        return await interaction.response.send_message("🎉 Il vient d'être terminé.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    await gw_refresh_message(await gw_get(giveaway))
    await interaction.followup.send(f"🚫 Giveaway #{giveaway} annulé.", ephemeral=True)


@giveaway_group.command(name="liste", description="Les giveaways en cours sur le serveur 📋")
@staff_only
async def gw_liste(interaction: discord.Interaction):
    rows = await db_all(
        "SELECT id, channel_id, prize, ends_at, winners, "
        "(SELECT COUNT(*) FROM giveaway_entries e WHERE e.giveaway_id=giveaways.id) "
        "FROM giveaways WHERE guild_id=? AND status='open' ORDER BY ends_at",
        (interaction.guild_id,),
    )
    if not rows:
        return await interaction.response.send_message(f"🎉 Aucun giveaway en cours. Lance-en un avec `/{GW_CMD} lancer`.", ephemeral=True)
    lines = [
        f"`#{i}` **{p[:60]}** — <#{c}> • fin <t:{t}:R> • 🏆 {w} • 👥 {n}"
        for i, c, p, t, w, n in rows
    ]
    await interaction.response.send_message(
        embed=emb(f"🎉 Giveaways en cours ({len(rows)})", "\n".join(lines)[:4000], COLOR_PINK), ephemeral=True
    )


bot.tree.add_command(giveaway_group)

# =====================================================================
# 🔗 /lien  +  🎵 /musique : musique en vocal réservée aux rôles choisis par un admin
#   À COLLER dans bot.py tout en bas, juste AVANT la ligne  if __name__ == "__main__":
#   (il doit venir après tout le reste : il utilise des éléments définis plus haut dans le fichier).
#   Prérequis (pip) : yt-dlp  (en plus de PyNaCl, davey et imageio-ffmpeg déjà utilisés par /vocal)
#   Rien d'autre à modifier : ce bloc s'enregistre tout seul (liste des commandes, interrupteur
#   « Musique » dans /adminpanel, /test).
# =====================================================================

# ---------------------------------------------------------------------
# 🔗 /lien
# ---------------------------------------------------------------------
music_staff = app_commands.checks.has_permissions(manage_guild=True)
BOT_LINK = os.getenv("BOT_LINK", "https://github.com/MrMisteur/Bot-AI-Discord-Mika")


@bot.tree.command(name="lien", description="Le lien du projet du bot 🔗")
async def lien(interaction: discord.Interaction):
    e = emb("🔗 Mon projet", f"Mon code source est ici :\n{BOT_LINK}", COLOR_PINK)
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Ouvrir sur GitHub", emoji="🐙", style=discord.ButtonStyle.link, url=BOT_LINK))
    await interaction.response.send_message(embed=e, view=view)


# ---------------------------------------------------------------------
# 🎵 /musique
# ---------------------------------------------------------------------
MUSIC_MAX_MIN = int(os.getenv("MUSIC_MAX_MIN", "60"))   # durée max d'un titre, en minutes
MUSIC_MAX_QUEUE = 25
MUSIC_MAX_ROLES = 25
MUSIC_HOSTS = ("youtube.com", "youtu.be", "soundcloud.com", "bandcamp.com")  # liens acceptés (sinon : recherche)
FFMPEG_STREAM = {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", "options": "-vn"}


class MusicState:
    def __init__(self):
        self.queue: deque = deque()
        self.current: Optional[dict] = None
        self.volume = 0.5
        self.channel = None                 # salon texte où annoncer les titres
        self.lock = asyncio.Lock()


music_states: dict[int, MusicState] = {}


def music_missing() -> Optional[str]:
    missing = []
    if ffmpeg_path() is None:
        missing.append("ffmpeg (ajoute `imageio-ffmpeg` au requirements.txt)")
    try:
        import nacl  # noqa: F401
    except ImportError:
        missing.append("PyNaCl")
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        missing.append("yt-dlp")
    return ", ".join(missing) or None


def _ytdl_extract(query: str) -> Optional[dict]:
    import yt_dlp
    opts = {
        "format": "bestaudio/best", "quiet": True, "no_warnings": True, "noplaylist": True,
        "default_search": "ytsearch", "source_address": "0.0.0.0", "socket_timeout": 15,
    }
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(query, download=False)
    if info and info.get("entries"):
        entries = [x for x in info["entries"] if x]
        info = entries[0] if entries else None
    return info


def music_query(raw: str) -> Optional[str]:
    """Lien accepté tel quel (hôtes autorisés) ou texte de recherche. None = lien refusé."""
    raw = raw.strip()
    if raw.lower().startswith(("http://", "https://")):
        from urllib.parse import urlparse
        host = (urlparse(raw).hostname or "").lower()
        return raw if any(host == h or host.endswith("." + h) for h in MUSIC_HOSTS) else None
    return f"ytsearch1:{raw}"


def fmt_dur(sec) -> str:
    if not sec:
        return "?"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------- Rôles autorisés ----------
async def music_role_ids(gid: int) -> set[int]:
    raw = await get_setting(gid, "music_roles", "")
    return {int(x) for x in raw.split(",") if x.strip().isdigit()}


async def _save_music_roles(gid: int, ids: set[int]):
    await set_setting(gid, "music_roles", ",".join(str(i) for i in sorted(ids)))


async def music_check(interaction: discord.Interaction) -> bool:
    """Staff (Gérer le serveur) ou membre ayant un des rôles autorisés. Sinon : refus avec explication."""
    m = interaction.user
    roles = await music_role_ids(interaction.guild_id)
    if isinstance(m, discord.Member):
        p = m.guild_permissions
        if p.administrator or p.manage_guild or any(r.id in roles for r in m.roles):
            return True
    if roles:
        txt = "🚫 La musique est réservée aux rôles : " + ", ".join(f"<@&{r}>" for r in sorted(roles)) + "."
    else:
        txt = "🚫 La musique est réservée au staff : aucun rôle n'est autorisé pour l'instant (`/musique autoriser`)."
    await interaction.response.send_message(txt, ephemeral=True, allowed_mentions=NO_PINGS)
    return False


async def music_control(interaction: discord.Interaction):
    """Pour skip / pause / stop / volume : renvoie (vc, état) ou None après avoir répondu l'erreur."""
    if not await music_check(interaction):
        return None
    vc, st = interaction.guild.voice_client, music_states.get(interaction.guild_id)
    if vc is None or not vc.is_connected() or st is None or (st.current is None and not st.queue):
        await interaction.response.send_message("Je ne joue rien pour le moment 😏", ephemeral=True)
        return None
    voice = interaction.user.voice
    if (voice is None or voice.channel is None or voice.channel.id != vc.channel.id) \
            and not interaction.permissions.manage_guild:
        await interaction.response.send_message(f"Viens dans {vc.channel.mention} pour contrôler la musique 😏", ephemeral=True)
        return None
    return vc, st


# ---------- Lecture ----------
async def music_advance(guild: discord.Guild):
    """Lance le titre suivant si rien ne joue. Appelée à la fin de chaque titre."""
    st = music_states.get(guild.id)
    if st is None:
        return
    async with st.lock:
        vc = guild.voice_client
        if vc is None or not vc.is_connected():
            music_states.pop(guild.id, None)
            return
        if vc.is_playing() or vc.is_paused():
            return
        while st.queue:
            track = st.queue.popleft()
            try:
                if time.time() - track["at"] > 600:  # le lien de streaming expire : on le renouvelle
                    info = await asyncio.wait_for(asyncio.to_thread(_ytdl_extract, track["page"]), timeout=40)
                    track["url"], track["at"] = info["url"], time.time()
                src = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(track["url"], executable=ffmpeg_path() or "ffmpeg", **FFMPEG_STREAM),
                    volume=st.volume,
                )
            except Exception as e:  # noqa: BLE001
                log.warning("Musique : lecture impossible (%r)", e)
                await _music_say(st, f"😅 Impossible de lire **{track['title'][:80]}**, je passe au suivant.")
                continue

            def _after(err, g=guild):
                if err:
                    log.warning("Musique : erreur de lecture (%r)", err)
                asyncio.run_coroutine_threadsafe(music_advance(g), bot.loop)

            st.current = track
            vc.play(src, after=_after)
            e = emb("🎶 Je joue", f"**[{track['title'][:150]}]({track['page']})**\n⏱️ {fmt_dur(track['duration'])} • demandé par <@{track['by']}>", COLOR_PURPLE)
            await _music_say(st, embed=e)
            return
        st.current = None


async def _music_say(st: MusicState, text: Optional[str] = None, embed: Optional[discord.Embed] = None):
    if st.channel is None:
        return
    try:
        await st.channel.send(text, embed=embed, allowed_mentions=NO_PINGS)
    except discord.HTTPException:
        pass


# ---------- Commandes ----------
musique_group = app_commands.Group(name="musique", description="Musique en vocal 🎵", guild_only=True)


@musique_group.command(name="jouer", description="Joue un titre (recherche ou lien YouTube / SoundCloud / Bandcamp) 🎶")
@app_commands.describe(titre="Un titre à chercher, ou un lien")
@app_commands.checks.cooldown(1, 3.0, key=lambda i: i.user.id)
async def musique_jouer(interaction: discord.Interaction, titre: app_commands.Range[str, 2, 200]):
    if not await music_check(interaction):
        return
    missing = music_missing()
    if missing:
        return await interaction.response.send_message(
            f"🔧 Je ne peux pas jouer de musique : il manque sur l'hébergement **{missing}**.", ephemeral=True
        )
    guild, voice = interaction.guild, interaction.user.voice
    if voice is None or voice.channel is None:
        return await interaction.response.send_message("Rejoins d'abord un salon vocal, petit chat 😏", ephemeral=True)
    ch = voice.channel
    if await channel_banned(ch, guild.id):
        return await interaction.response.send_message("🚫 Je n'ai pas le droit de venir dans ce vocal.", ephemeral=True)
    query = music_query(titre)
    if query is None:
        return await interaction.response.send_message(
            "🔗 Lien non accepté : YouTube, SoundCloud ou Bandcamp seulement (ou tape juste le titre).", ephemeral=True
        )
    st = music_states.get(guild.id)
    if st is not None and len(st.queue) >= MUSIC_MAX_QUEUE:
        return await interaction.response.send_message(f"🎵 La file est pleine ({MUSIC_MAX_QUEUE} titres max).", ephemeral=True)

    await interaction.response.defer(thinking=True, ephemeral=True)
    vc = guild.voice_client
    if vc is not None and not vc.is_connected():
        music_states.pop(guild.id, None)
        try:
            await vc.disconnect(force=True)
        except Exception:  # noqa: BLE001
            pass
        vc = None
    try:
        if vc is None:
            perms = ch.permissions_for(guild.me)
            if not (perms.connect and perms.speak):
                return await interaction.followup.send(f"🚫 Il me faut « Se connecter » et « Parler » dans {ch.mention}.", ephemeral=True)
            await ch.connect(timeout=20, self_deaf=True)
        elif vc.channel.id != ch.id:
            if vc.is_playing() or vc.is_paused():
                return await interaction.followup.send(f"Je joue déjà dans {vc.channel.mention}, viens m'y rejoindre 😏", ephemeral=True)
            await vc.move_to(ch)
    except (asyncio.TimeoutError, discord.ClientException, discord.HTTPException) as e:
        log.warning("Musique : connexion impossible (%r)", e)
        return await interaction.followup.send("😅 Je n'arrive pas à me connecter au vocal, réessaie dans un instant.", ephemeral=True)

    try:
        info = await asyncio.wait_for(asyncio.to_thread(_ytdl_extract, query), timeout=40)
    except Exception as e:  # noqa: BLE001
        log.warning("Musique : recherche impossible (%r)", e)
        return await interaction.followup.send("😅 Je n'ai pas réussi à récupérer ce titre (introuvable, privé ou bloqué).", ephemeral=True)
    if not info or not info.get("url"):
        return await interaction.followup.send("🤷 Je n'ai rien trouvé.", ephemeral=True)
    if info.get("is_live") or (info.get("duration") or 0) > MUSIC_MAX_MIN * 60:
        return await interaction.followup.send(f"⏱️ Pas de direct ni de titre de plus de {MUSIC_MAX_MIN} min.", ephemeral=True)

    st = music_states.setdefault(guild.id, MusicState())
    st.channel = interaction.channel
    track = {
        "title": info.get("title") or "Titre inconnu", "page": info.get("webpage_url") or titre,
        "duration": info.get("duration"), "url": info["url"], "at": time.time(), "by": interaction.user.id,
    }
    st.queue.append(track)
    busy = st.current is not None
    await interaction.followup.send(
        f"➕ **{track['title'][:100]}** ajouté" + (f" (position {len(st.queue)})." if busy else " : je lance ça."), ephemeral=True
    )
    await music_advance(guild)


@musique_group.command(name="passer", description="Passe au titre suivant ⏭️")
async def musique_passer(interaction: discord.Interaction):
    ctl = await music_control(interaction)
    if ctl is None:
        return
    vc, st = ctl
    title = st.current["title"][:80] if st.current else "le titre"
    vc.stop()  # la fin du titre déclenche automatiquement le suivant
    await interaction.response.send_message(f"⏭️ **{title}** passé.", allowed_mentions=NO_PINGS)


@musique_group.command(name="pause", description="Met la musique en pause ⏸️")
async def musique_pause(interaction: discord.Interaction):
    ctl = await music_control(interaction)
    if ctl is None:
        return
    vc, _ = ctl
    if not vc.is_playing():
        return await interaction.response.send_message("Rien ne joue en ce moment 😏", ephemeral=True)
    vc.pause()
    await interaction.response.send_message("⏸️ Musique en pause. `/musique reprendre` pour continuer.")


@musique_group.command(name="reprendre", description="Reprend la musique ▶️")
async def musique_reprendre(interaction: discord.Interaction):
    ctl = await music_control(interaction)
    if ctl is None:
        return
    vc, _ = ctl
    if not vc.is_paused():
        return await interaction.response.send_message("La musique n'est pas en pause 😏", ephemeral=True)
    vc.resume()
    await interaction.response.send_message("▶️ C'est reparti.")


@musique_group.command(name="stop", description="Arrête la musique et vide la file ⏹️")
async def musique_stop(interaction: discord.Interaction):
    ctl = await music_control(interaction)
    if ctl is None:
        return
    vc, st = ctl
    st.queue.clear()
    vc.stop()
    await interaction.response.send_message("⏹️ Musique arrêtée, file vidée. (`/vocal quitter` pour me renvoyer.)")


@musique_group.command(name="volume", description="Règle le volume (1 à 100) 🔊")
@app_commands.describe(niveau="Volume en pourcentage (50 par défaut)")
async def musique_volume(interaction: discord.Interaction, niveau: app_commands.Range[int, 1, 100]):
    ctl = await music_control(interaction)
    if ctl is None:
        return
    vc, st = ctl
    st.volume = niveau / 100
    if isinstance(vc.source, discord.PCMVolumeTransformer):
        vc.source.volume = st.volume
    await interaction.response.send_message(f"🔊 Volume : **{niveau}%**")


@musique_group.command(name="file", description="Voir le titre en cours et la file d'attente 📜")
async def musique_file(interaction: discord.Interaction):
    st = music_states.get(interaction.guild_id)
    if st is None or (st.current is None and not st.queue):
        return await interaction.response.send_message("La file est vide. `/musique jouer` 😏", ephemeral=True)
    lines = []
    if st.current:
        lines.append(f"🎶 **En cours :** [{st.current['title'][:80]}]({st.current['page']}) • {fmt_dur(st.current['duration'])}")
    for i, t in enumerate(list(st.queue)[:10], 1):
        lines.append(f"`{i}.` {t['title'][:70]} • {fmt_dur(t['duration'])} • <@{t['by']}>")
    if len(st.queue) > 10:
        lines.append(f"_… et {len(st.queue) - 10} autre(s)_")
    await interaction.response.send_message(
        embed=emb("📜 File d'attente", "\n".join(lines)[:4000], COLOR_PURPLE), allowed_mentions=NO_PINGS
    )


# ---------- Gestion des rôles autorisés (staff : Gérer le serveur) ----------
@musique_group.command(name="autoriser", description="(staff) Autorise un rôle à utiliser la musique 🎀")
@app_commands.describe(role="Le rôle autorisé (il peut jouer, passer, mettre en pause…)")
@music_staff
async def musique_autoriser(interaction: discord.Interaction, role: discord.Role):
    gid = interaction.guild_id
    ids = await music_role_ids(gid)
    if role.id in ids:
        return await interaction.response.send_message(f"😏 {role.mention} est déjà autorisé.", ephemeral=True, allowed_mentions=NO_PINGS)
    if len(ids) >= MUSIC_MAX_ROLES:
        return await interaction.response.send_message(f"🚫 {MUSIC_MAX_ROLES} rôles maximum.", ephemeral=True)
    ids.add(role.id)
    await _save_music_roles(gid, ids)
    note = " ⚠️ C'est @everyone : tout le monde pourra mettre de la musique." if role.is_default() else ""
    await interaction.response.send_message(f"🎵 {role.mention} peut maintenant utiliser la musique.{note}", ephemeral=True, allowed_mentions=NO_PINGS)


@musique_group.command(name="interdire", description="(staff) Retire l'accès à la musique à un rôle ✂️")
@app_commands.describe(role="Le rôle à retirer de la liste")
@music_staff
async def musique_interdire(interaction: discord.Interaction, role: discord.Role):
    gid = interaction.guild_id
    ids = await music_role_ids(gid)
    if role.id not in ids:
        return await interaction.response.send_message(f"😏 {role.mention} n'était pas autorisé.", ephemeral=True, allowed_mentions=NO_PINGS)
    ids.discard(role.id)
    await _save_music_roles(gid, ids)
    await interaction.response.send_message(f"✂️ {role.mention} n'a plus accès à la musique.", ephemeral=True, allowed_mentions=NO_PINGS)


@musique_group.command(name="permissions", description="Voir quels rôles peuvent mettre de la musique 🔑")
async def musique_permissions(interaction: discord.Interaction):
    ids = await music_role_ids(interaction.guild_id)
    txt = ("\n".join(f"• <@&{r}>" for r in sorted(ids)) if ids else "Aucun rôle : seul le staff peut mettre de la musique.")
    txt += "\n\n_Le staff (permission « Gérer le serveur ») peut toujours l'utiliser._"
    await interaction.response.send_message(
        embed=emb("🔑 Rôles autorisés pour la musique", txt, COLOR_PINK), ephemeral=True, allowed_mentions=NO_PINGS
    )


bot.tree.add_command(musique_group)


# ---------- Cohabitation avec la voix de /vocal (un seul son à la fois) ----------
_tts_speak_base = tts_speak


async def tts_speak(guild: discord.Guild, text: str) -> bool:  # noqa: F811 : remplace la version de /vocal
    vc = guild.voice_client
    if vc is not None and vc.is_connected() and (vc.is_playing() or vc.is_paused()):
        return False  # la musique joue : je ne parle pas par-dessus
    ok = await _tts_speak_base(guild, text)
    spawn(music_advance(guild))  # reprend la file si des titres attendaient pendant que je parlais
    return ok


# ---------- Enregistrement auprès du reste du bot (aucune autre modification à faire) ----------
EXPECTED_COMMANDS.update({"lien", "musique"})
REMOVED_COMMANDS.difference_update({"musique", "stat"})  # ces deux commandes existent bien (« stat » aussi)
FEATURES.append(("f_musique", "Musique", True, {"musique"}))
_CMD_FEATURE["musique"] = "f_musique"
CFG_TOGGLES["fonctions"].append(("f_musique", "Musique", True))


# =====================================================================
# RÉACTIONS AUX MESSAGES
# =====================================================================
REACT_KEYWORDS = [
    (re.compile(r"\b(gg|bravo|félicitations|bien joué)\b", re.I), ["👏", "🔥", "🖤"]),
    (re.compile(r"\b(mdr|ptdr|lol|xd)\b|\bha(ha)+", re.I), ["😂", "💀"]),
    (re.compile(r"\b(merci|thx)\b", re.I), ["🖤", "😘"]),
    (re.compile(r"\b(gn|bonne nuit)\b", re.I), ["🌙", "🖤"]),
    (re.compile(r"\b(salut|coucou|bonjour|wesh|yo)\b", re.I), ["👋", "😈"]),
]


async def pick_emoji(text: str) -> Optional[str]:
    try:
        out = await ask_ai(
            [{"role": "user", "content": f"Message : {text[:300]}\nRéponds avec UN SEUL emoji, rien d'autre."}],
            system="Tu choisis l'emoji de réaction parfait pour un message Discord. Tu réponds uniquement avec un emoji.",
            max_tokens=300,
            temperature=0.8,
        )
    except Exception as e:
        log.warning("pick_emoji : %s", e)
        return None
    e = out.split()[0] if out.split() else ""
    return e if 0 < len(e) <= 8 and not e.isascii() else None


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.guild and await automod_check(message):
        return
    if message.guild and await channel_banned(message.channel, message.guild.id):
        return  # salon interdit (/interdit) : ni réponse, ni réaction, ni !commande
    if message.guild and await is_silenced(message.guild.id):
        return
    nsfw = is_nsfw(message.channel)
    guild_id = message.guild.id if message.guild else None

    if message.guild and message.content.startswith("!"):
        name = cc_name(message.content[1:].split(maxsplit=1)[0]) if message.content[1:].strip() else None
        response = await cc_get(guild_id, name) if name else None
        if response is not None:
            try:
                await message.channel.send(cc_render(response, message.author, message.guild), allowed_mentions=CC_PINGS)
            except discord.HTTPException:
                pass
            # trace dans les logs : commande perso utilisée via !nom
            le = discord.Embed(title="📋 Commande perso", color=COLOR_PURPLE)
            le.add_field(name="Commande", value=f"`!{name}`", inline=True)
            le.add_field(name="Membre", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
            le.add_field(name="Salon", value=getattr(message.channel, "mention", "—"), inline=True)
            le.timestamp = discord.utils.utcnow()
            spawn(mod_log(message.guild, le))
            return

    named = (
        message.guild is not None
        and name_called(message.content)
        and await get_flag(guild_id, "nom", True)
    )
    addressed = message.guild is None or bot.user in message.mentions or is_reply_to_bot(message) or named

    wx_src = clean_text(message) if addressed else message.content
    if addressed or WX_STANDALONE.match(wx_src):
        wx = weather_request(wx_src)
        if wx is not None:
            now = time.time()
            if now - last_weather[message.author.id] < 5:
                return
            last_weather[message.author.id] = now
            if not wx:
                return await message.reply("Pour quelle ville, petit chat ? Écris par exemple « météo Lyon » 🌤️")
            async with message.channel.typing():
                try:
                    embed = await fetch_weather(wx)
                except CityNotFound:
                    return await message.reply(f"Je ne trouve pas « {wx[:40]} »… tu es sûr(e) de l'orthographe ? 😏")
                except Exception as e:
                    log.warning("Météo : %r", e)
                    return await message.reply("😅 Je n'arrive pas à joindre le service météo, réessaie dans un instant.")
            return await message.reply(embed=embed)

    if addressed:
        now = time.time()
        if now - last_chat[message.author.id] < 3:
            return
        last_chat[message.author.id] = now
        text = clean_text(message)
        if not text:
            return await message.reply("Oui, petit chat ? 😏")

        greet = greeting_reply(text)
        if greet:
            return await message.reply(greet)

        if HUG_HINTS.search(text) and not seems_down(text) and random.random() < PHRASE_CHANCE:
            return await message.reply(mommy_phrase(nsfw))

        async with message.channel.typing():
            try:
                answer = await generate_reply(
                    message.channel.id, message.author.display_name, message.author.id, text,
                    guild_id=guild_id, nsfw=nsfw,
                )
            except Exception as e:
                return await message.reply(fail_msg(e))
        chunks = split_text(answer)
        await message.reply(chunks[0])
        for c in chunks[1:]:
            await message.channel.send(c)
        return

    if message.guild is None:  # hors DM : les réactions / rebonds ne concernent que les serveurs
        return
    content = message.content
    if len(content) < 3:
        return
    now = time.time()
    gid, cid = message.guild.id, message.channel.id

    if (
        await get_flag(gid, "salutations", True)
        and now - last_greet[cid] > 60
        and not message.mentions
        and not message.reference
    ):
        greet = greeting_reply(content)
        if greet:
            last_greet[cid] = now
            try:
                await message.reply(greet, mention_author=False)
            except discord.HTTPException:
                pass
            return

    if await get_flag(gid, "reactions", True) and now - last_react[cid] > 45:
        emoji = None
        for rx, emojis in REACT_KEYWORDS:
            if rx.search(content) and random.random() < 0.35:
                emoji = random.choice(emojis)
                break
        if emoji is None and len(content) > 12 and random.random() < REACT_CHANCE:
            emoji = await pick_emoji(content)
        if emoji:
            last_react[cid] = now
            try:
                await message.add_reaction(emoji)
            except (discord.Forbidden, discord.HTTPException):
                pass

    if (
        await get_flag(gid, "spontane", False)
        and len(content) > 25
        and now - last_spont[cid] > 600
        and random.random() < SPONT_CHANCE
        and not seems_down(content)
    ):
        last_spont[cid] = now
        text = clean_text(message)
        user_msg = f"{message.author.display_name} : {text}"
        system = (
            persona(nsfw, await get_style(gid))
            + "\n\nTu rebondis spontanément sur ce message d'un pote, sans qu'on t'ait parlé. "
            "UNE phrase courte et piquante max. Si tu n'as rien d'intéressant à dire, réponds exactement SKIP."
        )
        try:
            out = await ask_ai([{"role": "user", "content": user_msg}], system=system, max_tokens=500)
        except Exception as e:  # noqa: BLE001
            log.warning("rebond spontané : %s", e)
            return
        if out and not out.strip().upper().startswith("SKIP"):
            await add_history(cid, "user", user_msg)
            await add_history(cid, "assistant", out)
            try:
                await message.reply(out[:1900], mention_author=False)
            except discord.HTTPException:
                pass


@bot.event
async def on_ready():
    log.info("✅ Connecté en tant que %s", bot.user)


if __name__ == "__main__":
    if not DISCORD_TOKEN or not AI_API_KEY:
        raise SystemExit("DISCORD_TOKEN et AI_API_KEY doivent être définis (voir .env.example)")
    bot.run(DISCORD_TOKEN, log_handler=None)

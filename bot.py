"""Bot Discord IA 🖤 — version e-girl dominatrice, "entre potes"

Chat par mention / réponse / prénom (« Mika »), /ask, /recherche, /roast, /blague, /8ball, /choisir,
commandes sociales (/kiss, /hug, /pat, /slap, /bonk, /gift), mariage, mini-jeux (/pfc, /quiz, /blackjack,
/poker) avec stats (/classement, /stat), météo, /ping, commandes personnalisées (/commande, /cc, !nom),
modération (/punition panel|deban, rôles, mute vocal, /silence, /logs), /rolereaction, /envoyer, /statu, /emoji,
/adminpanel + /aideadmin (réservés aux admins), mémoire SQLite.

LOGS : toutes les sanctions (mute, unmute, avertissement, kick, ban, nettoyage, mute vocal, casque, rôles, deban)
ET toutes les commandes du bot (slash, panel admin, commandes perso !nom) sont envoyées dans le salon défini
avec /logs.

Python 3.10+ requis. Voir .env.example pour la config.
"""
import asyncio
import datetime
import hashlib
import json
import logging
import math
import os
import random
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import timedelta
from itertools import combinations
from typing import Optional

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
    t = plain(text)
    if not t or len(t) > 40:
        return None
    hello, how = bool(GREET_HELLO.search(t)), bool(GREET_HOW.search(t))
    doing, night, bye = bool(GREET_DOING.search(t)), bool(GREET_NIGHT.search(t)), bool(GREET_BYE.search(t))
    if not (hello or how or doing or night or bye):
        return None
    # ce qui reste une fois les salutations retirées : si c'est une vraie phrase, ce n'est pas qu'une salutation
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
"""


class MikaBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents, allowed_mentions=NO_PINGS)
        self.tree = app_commands.CommandTree(self)
        self.db: aiosqlite.Connection

    async def setup_hook(self):
        self.db = await aiosqlite.connect(DB_PATH)
        await self.db.executescript(SCHEMA)
        await self.db.commit()
        self.add_dynamic_items(RoleButton)  # boutons de rôles : actifs même après un redémarrage
        if not voice_timer_loop.is_running():
            voice_timer_loop.start()
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


async def ask_json(prompt: str, tries: int = 2, system: str = PERSONA) -> dict:
    """Demande du JSON à l'IA, avec un nouvel essai si le JSON est cassé."""
    last: Optional[Exception] = None
    for _ in range(tries):
        try:
            raw = await ask_ai([{"role": "user", "content": prompt}], system=system, json_mode=True, temperature=0.8)
            return extract_json(raw)
        except ValueError as e:  # json.JSONDecodeError hérite de ValueError
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
async def mod_log(guild: discord.Guild, embed: discord.Embed) -> bool:
    """Envoie un embed dans le salon de logs du serveur (False si pas de salon / envoi impossible)."""
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
LOG_SKIP = {"envoyer", "punition deban"}


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
        super().__init__(label=label[:80], style=discord.ButtonStyle.secondary)
        self.correct = correct

    async def callback(self, interaction: discord.Interaction):
        view: "QuizView" = self.view
        uid = interaction.user.id
        if view.done:
            return await interaction.response.send_message("Trop tard, quelqu'un a déjà gagné 😏", ephemeral=True)
        if uid in view.rates:
            return await interaction.response.send_message("T'as déjà tenté, laisse les autres jouer 😌", ephemeral=True)
        if not self.correct:
            view.rates.add(uid)
            spawn(record_many(interaction.guild_id, "quiz", {uid: "loss"}))
            return await interaction.response.send_message("Raté 😏", ephemeral=True)
        view.done = True
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
    def __init__(self, header: str, bonne: str, choix: list[str], anecdote: str):
        super().__init__(timeout=30)
        self.header, self.bonne, self.anecdote = header, bonne, anecdote
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

    def __init__(self, ids: list[int], names: dict[int, str], guild_id: Optional[int] = None):
        self.ids, self.names, self.guild_id = ids, names, guild_id
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
            if pid in self.afk:
                res += " • 💤 AFK"
            self.results[pid] = res
        if self.guild_id:
            outcomes = {
                pid: ("win" if "🏆" in r else "draw" if "🤝" in r else "loss") for pid, r in self.results.items()
            }
            spawn(record_many(self.guild_id, "blackjack", outcomes))

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
    def __init__(self, host: discord.abc.User):
        super().__init__(timeout=120)
        self.host_id = host.id
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
        e.set_footer(text=f"L'hôte lance la partie • 2 minutes • {BOT_NAME} 🖤")
        return e

    @discord.ui.button(label="Rejoindre", emoji="🎴", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid in self.players:
            return await interaction.response.send_message("T'es déjà à la table 😌", ephemeral=True)
        if len(self.players) >= BJ_MAX_PLAYERS:
            return await interaction.response.send_message("Table complète 😅", ephemeral=True)
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
        table = BJTable(list(self.players), dict(self.players), interaction.guild_id)
        await table.start(interaction, from_lobby=True)

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
@app_commands.describe(mode="Solo contre Mika, ou une table ouverte aux autres")
@app_commands.choices(mode=[
    app_commands.Choice(name="🃏 Solo contre Mika", value="solo"),
    app_commands.Choice(name="👥 À la table (multi, jusqu'à 5)", value="table"),
])
@app_commands.guild_only()
async def blackjack(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    user = interaction.user
    if mode.value == "solo":
        table = BJTable([user.id], {user.id: user.display_name}, interaction.guild_id)
        return await table.start(interaction)
    lobby = BJLobby(user)
    await interaction.response.send_message(embed=lobby.embed(), view=lobby)
    lobby.message = await interaction.original_response()


# =====================================================================
# POKER — Texas Hold'em simplifié (sans mises) : 1 à 6 joueurs contre Mika, qui joue aussi
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


class PokerGame:
    def __init__(self, ids: list, names: dict, guild_id: Optional[int]):
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

    # ---- affichage ----
    def embed(self, view: Optional["PKRoundView"] = None, final: bool = False) -> discord.Embed:
        shown = 5 if final else len(self.visible_board())
        board = " ".join([pk_card(c) for c in self.board[:shown]] + [CARD_BACK] * (5 - shown))
        if final:
            desc = self.final_text
            color = COLOR_PINK
        else:
            desc = f"**{PK_STAGES[self.stage]}** — suis ou couche-toi ({PK_TURN_TIMEOUT}s)."
            if self.mika_note:
                desc += f"\n{self.mika_note}"
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
                val = {"call": "✅ Suit", "fold": "🏳️ Couché(e)"}.get(st, "⏳ Réfléchit…")
            e.add_field(name=name, value=val, inline=True)
        if not final:
            e.set_footer(text=f"« Mes cartes » pour voir ta main (privé) • {BOT_NAME} 🖤")
        return e

    # ---- déroulé ----
    def enter_round(self):
        self.mika_note = ""
        if MIKA_ID not in self.folded and len(self.active_humans()) >= 2 and self._mika_folds():
            self.folded.add(MIKA_ID)
            self.mika_note = f"🏳️ {BOT_NAME} se couche."
        view = PKRoundView(self, self.active_humans())
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
        return self.embed(final=True)


class PKRoundView(discord.ui.View):
    def __init__(self, game: PokerGame, required: list):
        super().__init__(timeout=PK_TURN_TIMEOUT)
        self.game = game
        self.required = list(required)
        self.decided: dict = {}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in self.game.ids:
            await interaction.response.send_message("Tu ne joues pas à cette table, petit chat 😏", ephemeral=True)
            return False
        return True

    async def _decide(self, interaction: discord.Interaction, fold: bool):
        uid = interaction.user.id
        if uid in self.game.folded:
            return await interaction.response.send_message("T'es déjà couché(e) 😌", ephemeral=True)
        if uid in self.decided:
            return await interaction.response.send_message("T'as déjà choisi pour ce tour 😏", ephemeral=True)
        self.decided[uid] = "fold" if fold else "call"
        if fold:
            self.game.folded.add(uid)
        everyone = all(p in self.decided for p in self.required)
        if everyone or len(self.game.active()) <= 1:
            self.stop()
            return await self.game.advance(interaction)
        await interaction.response.edit_message(embed=self.game.embed(self), view=self)

    @discord.ui.button(label="Suivre", emoji="✅", style=discord.ButtonStyle.success)
    async def call(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, fold=False)

    @discord.ui.button(label="Se coucher", emoji="🏳️", style=discord.ButtonStyle.danger)
    async def fold(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, fold=True)

    @discord.ui.button(label="Mes cartes", emoji="🃏", style=discord.ButtonStyle.secondary)  # ← corrigé (🂠 invalide)
    async def mine(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = self.game
        hand = g.hands[interaction.user.id]
        txt = f"Tes cartes : {pk_cards(hand)}"
        best = pk_best(hand + g.visible_board())
        if best:
            txt += f"\nMain actuelle : **{PK_HANDS[best[0]]}**"
        await interaction.response.send_message(txt, ephemeral=True)

    async def on_timeout(self):
        for p in self.required:
            if p not in self.decided:
                self.game.folded.add(p)
                self.game.afk.add(p)
        await self.game.advance(None)


class PKLobby(discord.ui.View):
    def __init__(self, host: discord.abc.User):
        super().__init__(timeout=120)
        self.host_id = host.id
        self.players: dict = {host.id: host.display_name}
        self.started = False
        self.message: Optional[discord.Message] = None

    def embed(self) -> discord.Embed:
        lines = "\n".join(f"{'👑' if p == self.host_id else '🎴'} <@{p}>" for p in self.players)
        e = emb(
            "♠️ Poker — table ouverte",
            f"Hôte : <@{self.host_id}>\n{BOT_NAME} joue aussi contre vous. Clique sur **Rejoindre** "
            f"(max {PK_MAX_PLAYERS}).\n\n**Joueurs ({len(self.players)}/{PK_MAX_PLAYERS})**\n{lines}",
            COLOR_PURPLE,
        )
        e.set_footer(text=f"L'hôte lance la partie • 2 minutes • {BOT_NAME} 🖤")
        return e

    @discord.ui.button(label="Rejoindre", emoji="🎴", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid in self.players:
            return await interaction.response.send_message("T'es déjà à la table 😌", ephemeral=True)
        if len(self.players) >= PK_MAX_PLAYERS:
            return await interaction.response.send_message("Table complète 😅", ephemeral=True)
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
        game = PokerGame(list(self.players), dict(self.players), interaction.guild_id)
        await game.start(interaction)

    async def on_timeout(self):
        if self.started or not self.message:
            return
        try:
            await self.message.edit(
                embed=emb("⌛ Table expirée", "Personne n'a lancé la partie à temps.", COLOR_DARK), view=None
            )
        except discord.HTTPException:
            pass


@bot.tree.command(name="poker", description="Poker Texas Hold'em contre moi, seul ou à plusieurs ♠️")
@app_commands.guild_only()
async def poker(interaction: discord.Interaction):
    lobby = PKLobby(interaction.user)
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
@bot.tree.command(name="config", description="(admin) Réglages du bot sur ce serveur")
@app_commands.describe(
    reactions="Réactions emoji sur les messages",
    spontane="Rebondir de moi-même sur certains messages",
    salutations="Répondre aux « coucou / ça va ? » même sans mention",
    nom="Répondre quand on écrit mon prénom, même sans mention",
)
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
async def config(
    interaction: discord.Interaction,
    reactions: Optional[bool] = None,
    spontane: Optional[bool] = None,
    salutations: Optional[bool] = None,
    nom: Optional[bool] = None,
):
    if reactions is not None:
        await set_flag(interaction.guild_id, "reactions", reactions)
    if spontane is not None:
        await set_flag(interaction.guild_id, "spontane", spontane)
    if salutations is not None:
        await set_flag(interaction.guild_id, "salutations", salutations)
    if nom is not None:
        await set_flag(interaction.guild_id, "nom", nom)
    r = await get_flag(interaction.guild_id, "reactions", True)
    s = await get_flag(interaction.guild_id, "spontane", False)
    g = await get_flag(interaction.guild_id, "salutations", True)
    n = await get_flag(interaction.guild_id, "nom", True)
    style = STYLES[await get_style(interaction.guild_id)][0]
    await interaction.response.send_message(
        f"⚙️ Réactions emoji : **{'on' if r else 'off'}** • Rebonds spontanés : **{'on' if s else 'off'}** "
        f"• Salutations : **{'on' if g else 'off'}** • Réponse au prénom : **{'on' if n else 'off'}** "
        f"• Style : **{style}**",
        ephemeral=True,
    )


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
        super().__init__(discord.ui.Button(label=label[:80], style=discord.ButtonStyle.secondary, custom_id=f"rr:{role_id}"))
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
            "`/classement [jeu]` • `/stat [joueur]` → points, victoires, K/D."
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
        name="🎭 Serveur",
        value=(
            "`/ping` → ma latence.\n"
            "`/statu @membre` → statut, activité, appareils.\n"
            "`/emoji agrandir` → un emoji perso en grand.\n"
            "`/cc nom` ou `!nom` → commandes personnalisées du serveur."
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
            "`/config` → réactions, rebonds spontanés, salutations, réponse au prénom.\n"
            "`/style` → dominatrice, mommy, douce ou sarcastique.\n"
            "`/logs` → salon des logs : **toutes les sanctions** et **toutes les commandes du bot** y sont tracées."
        ),
        inline=False,
    )
    e.add_field(
        name="🎭 Serveur",
        value=(
            "`/rolereaction` → panneau de rôles à boutons.\n"
            "`/envoyer` → message anonyme ou sous un pseudo perso.\n"
            "`/emoji ajouter` → ajouter un emoji au serveur.\n"
            "`/commande ajouter|modifier|supprimer|liste` → commandes perso (utilisables avec `/cc nom` ou `!nom`).\n"
            "`/sync` → (owner du bot) resynchroniser les commandes."
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
    prefix = re.sub(r"[^\w-]", "", current.lower())
    rows = await db_all(
        "SELECT name FROM custom_cmds WHERE guild_id=? AND name LIKE ? ORDER BY name LIMIT 25",
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
WX_TIME_END = re.compile(
    r"(?:\s+(?:aujourd['’]?hui|demain|ce\s+soir|ce\s+matin|maintenant|svp|stp|please|là|actuellement|en\s+ce\s+moment))+\s*$",
    re.I,
)
WX_TIME_START = re.compile(
    r"^(?:aujourd['’]?hui|demain|ce\s+soir|ce\s+matin|maintenant)\s+(?:(?:à|a|de|en|sur|pour|dans)\s+)?", re.I
)
WX_NOT_CITY = {
    "est", "etait", "était", "sera", "c", "ca", "ça", "il", "elle", "me", "nous", "vous", "tu", "je", "qui", "que",
    "fait", "va", "et", "ou", "trop", "tres", "très", "pas", "nulle", "bien", "mauvaise", "belle", "toujours",
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
    for _ in range(3):  # retire « aujourd'hui », « demain »... en début / fin
        city = WX_TIME_START.sub("", city).strip()
        city = WX_TIME_END.sub("", city).strip()
    city = city.strip(" '\"«»-")
    if not city:
        return ""
    first = city.split()[0].lower().strip("',")
    if first in WX_NOT_CITY or len(city.split()) > 5:
        return None  # une phrase sur la météo, pas une demande
    low = city.lower()
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


async def fetch_weather(city: str) -> discord.Embed:
    """Géocode la ville puis récupère la météo actuelle + 3 jours (Open-Meteo, gratuit, sans clé)."""
    async with httpx.AsyncClient(timeout=8) as client:
        g = await client.get(GEO_URL, params={"name": city, "count": 1, "language": "fr", "format": "json"})
        g.raise_for_status()
        results = g.json().get("results") or []
        if not results:
            raise CityNotFound(city)
        place = results[0]
        w = await client.get(FORECAST_URL, params={
            "latitude": place["latitude"], "longitude": place["longitude"], "timezone": "auto", "forecast_days": 3,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        })
        w.raise_for_status()
        data = w.json()

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


@bot.tree.command(name="statu", description="Affiche le statut d'un membre 🟢")
@app_commands.describe(pseudo="Le membre")
@app_commands.guild_only()
async def statu(interaction: discord.Interaction, pseudo: discord.Member):
    m = interaction.guild.get_member(pseudo.id) or pseudo  # le membre en cache a la présence, pas celui de l'interaction
    e = emb(f"Statut — {m.display_name}", None, COLOR_PURPLE)
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


@bot.tree.command(name="envoyer", description="(admin) Envoie un message anonyme ou sous un pseudo perso ✉️")
@app_commands.describe(
    message="Le message (\\n = retour à la ligne)",
    identite="Qui apparaît comme expéditeur",
    pseudo="Le pseudo à afficher (pour « Pseudo perso »)",
    salon="Salon d'envoi (ici par défaut)",
    avatar="URL d'une image d'avatar (optionnel, https)",
)
@app_commands.choices(identite=[
    app_commands.Choice(name="🕶️ Anonyme", value="anon"),
    app_commands.Choice(name="🎭 Pseudo perso", value="perso"),
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
        hook, thread = await get_relay_webhook(channel)
        await hook.send(
            content=text, username=name[:80], avatar_url=avatar or discord.utils.MISSING,
            allowed_mentions=allowed, thread=thread or discord.utils.MISSING,
        )
    except discord.Forbidden:
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
    await interaction.followup.send(f"✅ Envoyé dans {channel.mention} en tant que **{name}**.", ephemeral=True)
    # trace pour le staff : l'anonymat vaut vis-à-vis des membres, pas des admins
    le = discord.Embed(title="✉️ /envoyer utilisé", color=COLOR_DARK)
    le.add_field(name="Admin", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
    le.add_field(name="Identité", value=name, inline=True)
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
            label="Durée (10, 30m, 2h, 1j…) — vide = jusqu'à retrait", required=False, max_length=10,
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
    "config", "style", "reset", "sync", "aide", "aideadmin", "adminpanel", "ping", "punition", "test",
    "commande", "cc", "meteo", "statu", "emoji", "envoyer", "logs", "silence", "rolereaction",
}
REMOVED_COMMANDS = {"musique", "gouts", "favori", "inventaire"}


async def _t_db() -> str:
    await db_run(
        "INSERT INTO settings(guild_id, key, value) VALUES (-1,'test','ok') "
        "ON CONFLICT(guild_id, key) DO UPDATE SET value=excluded.value"
    )
    rows = await db_all("SELECT value FROM settings WHERE guild_id=-1 AND key='test'")
    await db_run("DELETE FROM settings WHERE guild_id=-1 AND key='test'")
    assert rows and rows[0][0] == "ok", "relecture incorrecte"
    for table in ("history", "settings", "marriages", "marriage_members", "custom_cmds", "game_stats", "voice_timers"):
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
    pseudo = discord.ui.TextInput(label="Pseudo (vide = Anonyme)", required=False, max_length=32)
    avatar = discord.ui.TextInput(label="URL d'avatar https (optionnel)", required=False, max_length=300)

    async def on_submit(self, interaction: discord.Interaction):
        pseudo = self.pseudo.value.strip()
        ident = app_commands.Choice(name="", value="perso" if pseudo else "anon")
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


@bot.tree.command(name="adminpanel", description="(admin) Panel regroupant toutes les commandes admin 🛠️")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def adminpanel(interaction: discord.Interaction):
    gid = interaction.guild_id
    states = {k: await get_flag(gid, k, d) for k, _, d in ADMIN_TOGGLES}
    view = AdminPanel(interaction.user.id, states)
    await interaction.response.send_message(embed=await admin_panel_embed(interaction.guild), view=view, ephemeral=True)
    view.origin = interaction


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
import discord
from discord.ext import tasks, commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import asyncio
import os
from dotenv import load_dotenv
import json
import logging
from discord import app_commands

load_dotenv()

TOKEN = os.environ["BOT_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
ROLE_TO_PING = os.environ["ROLE_NAME"]

# Délai de fermeture du sondage en secondes (1h par défaut)
POLL_CLOSE_DELAY_SECONDS = int(os.environ.get("POLL_CLOSE_DELAY_SECONDS", "3600"))

# Mode debug pour tester la fermeture du sondage (10 secondes au lieu du délai normal)
DEBUG_POLL = os.environ.get("DEBUG_POLL", "false").lower() == "true"

CONFIG_FILE = "config.json"
LOG_FILE = "command.log"
BOT_LOG_FILE = "bot.log"

# Configuration du logging pour les commandes
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Configuration du logging pour le bot
bot_logger = logging.getLogger('bot')
bot_logger.setLevel(logging.INFO)
bot_handler = logging.FileHandler(BOT_LOG_FILE, encoding='utf-8')
bot_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
bot_handler.setFormatter(bot_formatter)
bot_logger.addHandler(bot_handler)

def bot_log(message, level="INFO"):
    """Fonction de logging personnalisée pour le bot"""
    if level.upper() == "ERROR":
        bot_logger.error(message)
    elif level.upper() == "WARNING":
        bot_logger.warning(message)
    elif level.upper() == "DEBUG":
        bot_logger.debug(message)
    else:
        bot_logger.info(message)
    # Afficher aussi dans la console pour le debug
    print(f"[{level}] {message}", flush=True)

# Charger ou créer la configuration
def load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "session_time": "21:00",
            "poll_message_id": None,
            "last_posted_date": None,
            "poll_active": False  # Indique si le sondage est activé
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f)
        return default_config
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
        # Ajouter le champ poll_active s'il n'existe pas (pour la compatibilité)
        if "poll_active" not in config:
            config["poll_active"] = False
        return config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def clear_poll_state():
    """Nettoie l'état du sondage dans la configuration et les variables globales"""
    global poll_message_id, last_posted_date
    
    poll_message_id = None
    last_posted_date = None
    
    config["poll_active"] = False
    config["poll_message_id"] = None
    config["last_posted_date"] = None
    config["close_time"] = None
    save_config(config)

config = load_config()

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


# Variables globales pour l'état du bot
poll_message_id = None
last_posted_date = None

# Charger l'état sauvegardé
def load_bot_state():
    global poll_message_id, last_posted_date
    poll_message_id = config.get("poll_message_id")
    last_posted_date_str = config.get("last_posted_date")
    if last_posted_date_str:
        last_posted_date = datetime.strptime(last_posted_date_str, "%Y-%m-%d").date()
    else:
        last_posted_date = None

async def recover_active_poll():
    """Récupère et vérifie l'état du sondage actif au redémarrage du bot"""
    global poll_message_id
    
    # Vérifier si un sondage est marqué comme actif
    if not config.get("poll_active", False) or not config.get("poll_message_id"):
        bot_log("ℹ️ Aucun sondage actif à récupérer")
        return
    
    poll_message_id = config.get("poll_message_id")
    channel = bot.get_channel(CHANNEL_ID)
    
    if not channel:
        bot_log(f"❌ Impossible de récupérer le channel {CHANNEL_ID}", "ERROR")
        # Nettoyer l'état invalide
        clear_poll_state()
        return
    
    try:
        # Vérifier que le message du sondage existe encore
        message = await channel.fetch_message(poll_message_id)
        bot_log(f"✅ Sondage actif récupéré : Message ID {poll_message_id}")
        
        # Vérifier si le sondage n'est pas déjà fermé (pas de réactions)
        if not message.reactions:
            bot_log("⚠️ Le sondage semble fermé, nettoyage de l'état...", "WARNING")
            clear_poll_state()
        else:
            bot_log(f"🔄 Sondage actif maintenu - {len(message.reactions)} réactions détectées")
            
    except discord.NotFound:
        bot_log(f"❌ Message de sondage {poll_message_id} introuvable, nettoyage de l'état...", "ERROR")
        # Nettoyer l'état invalide
        clear_poll_state()
        
    except discord.Forbidden:
        bot_log(f"❌ Pas les permissions pour récupérer le message {poll_message_id}", "ERROR")
        # Nettoyer l'état invalide
        clear_poll_state()
        
    except Exception as e:
        bot_log(f"❌ Erreur lors de la récupération du sondage : {e}", "ERROR")
        # Nettoyer l'état en cas d'erreur
        clear_poll_state()

@bot.event
async def on_ready():
    bot_log(f"✅ Connecté en tant que {bot.user}")
    load_bot_state()  # Charger l'état sauvegardé
    
    # Vérifier et récupérer le sondage actif au redémarrage
    await recover_active_poll()
    
    # Synchroniser les slash commands
    bot_log("🔄 Synchronisation des slash commands...")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    
    tryhard_poll.start()
    daily_reset.start()

def get_scheduled_time():
    """Calcule l'heure de fermeture du sondage"""
    session_str = config.get("session_time", "21:00")
    session_time = datetime.strptime(session_str, "%H:%M").time()
    
    # Utiliser l'heure de fermeture sauvegardée si elle existe
    if config.get("close_time"):
        close_time = datetime.strptime(config["close_time"], "%H:%M:%S").time()
    else:
        # Fallback : calculer l'heure de fermeture
        dt = datetime.combine(datetime.today(), session_time)
        close_time = (dt - timedelta(seconds=POLL_CLOSE_DELAY_SECONDS)).time()

    return session_time, close_time

def generate_info_text():
    """Génère le texte d'information de la configuration (utilisé dans plusieurs commandes)"""
    if not config.get("poll_active", False):
        return "❌ **Aucune session tryhard n'est prévue aujourd'hui**\n\n💡 Pour envoyer le sondage, utilisez `/askForTryhardToday 22:00` par exemple"
    
    session_time, close_time = get_scheduled_time()
    
    # Calculer l'heure de fermeture en créant d'abord un datetime
    session_dt = datetime.combine(datetime.today(), session_time)
    close_time_str = datetime.combine(datetime.today(), close_time).strftime('%H:%M')
    
    # Formater le délai de fermeture de manière lisible
    if POLL_CLOSE_DELAY_SECONDS >= 3600:
        delay_text = f"{POLL_CLOSE_DELAY_SECONDS // 3600}h"
    elif POLL_CLOSE_DELAY_SECONDS >= 60:
        delay_text = f"{POLL_CLOSE_DELAY_SECONDS // 60}min"
    else:
        delay_text = f"{POLL_CLOSE_DELAY_SECONDS}s"

    info_text = f"**Voici la configuration actuelle :**\n"
    info_text += f"🕐 Heure de session : {session_time.strftime('%H:%M')}\n"
    
    if DEBUG_POLL:
        info_text += f"🔒 Fermeture du sondage en mode DEBUG (10 secondes)\n"
        info_text += f"⚠️ **MODE DEBUG ACTIVÉ** - Le sondage se fermera dans 10 secondes"
    else:
        info_text += f"🔒 Fermeture du sondage {delay_text} avant la session ({close_time_str})"
    
    return info_text

@tasks.loop(hours=24)
async def daily_reset():
    """Reset quotidien : désactive le sondage et nettoie l'état"""
    clear_poll_state()
    logging.info("🔄 Reset quotidien effectué : sondage désactivé")

@tasks.loop(seconds=1)
async def tryhard_poll():
    global poll_message_id, last_posted_date
    now = datetime.now(ZoneInfo("Europe/Paris"))
    
    # Vérifier si le sondage est activé
    if not config.get("poll_active", False):
        return
    
    # Utiliser l'ID du message sauvegardé ou celui en mémoire
    current_poll_id = config.get("poll_message_id") or poll_message_id
    if not current_poll_id:
        return
        
    session_time, close_time = get_scheduled_time()

    # Fermer le sondage avant la session (avec une marge de 5 secondes)
    close_datetime = datetime.combine(now.date(), close_time).replace(tzinfo=ZoneInfo("Europe/Paris"))
    time_diff = abs((now - close_datetime).total_seconds())
    if time_diff <= 5 and current_poll_id:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            logging.error(f"Channel {CHANNEL_ID} introuvable")
            return
        
        try:
            message = await channel.fetch_message(current_poll_id)
        except discord.NotFound:
            logging.error(f"Message {current_poll_id} introuvable")
            return
        except discord.Forbidden:
            logging.error(f"Pas les permissions pour récupérer le message {current_poll_id}")
            return

        results = {"✅": [], "❌": [], "🤔": []}

        for reaction in message.reactions:
            if str(reaction.emoji) in results:
                async for user in reaction.users():
                    if user.bot:
                        continue
                    results[str(reaction.emoji)].append(user.display_name)

        logging.info(f"Fermeture du sondage pour la session de {session_time.strftime('%H:%M')}")
        logging.info(f"Résultats : {results}")


        result_text = f"**[🛑 Sondage fermé à {now.strftime('%H:%M')} pour la session de {session_time.strftime('%H:%M')}]**\n\n"

        if(len(results["✅"]) == 0 and len(results["❌"]) == 0 and len(results["🤔"]) == 0):
            result_text += f"**Aucun(e) participant(e)**\n\n"
        else:
            result_text += f"__Résultats :__\n\n"
            result_text += f"{len(results['✅'])} ✅ : " + ", ".join(f"{name}" for name in results["✅"]) + "\n"
            result_text += f"{len(results['❌'])} ❌ : " + ", ".join(f"{name}" for name in results["❌"]) + "\n"
            result_text += f"{len(results['🤔'])} 🤔 : " + ", ".join(f"{name}" for name in results["🤔"]) + "\n"

        await channel.send(f"Sondage du jour terminé ! Voir {message.jump_url}")

        try:
            await message.clear_reactions()
            await message.edit(content=result_text, embed=None)
        except discord.Forbidden:
            pass

        # Nettoyer l'état après fermeture du sondage
        clear_poll_state()



@tree.command(
    name="askfortryhardtoday", 
    description="Lance un sondage tryhard pour aujourd'hui avec une heure optionnelle (21h par défaut)",
    guild=discord.Object(id=GUILD_ID)
)
async def askForTryhardToday(interaction: discord.Interaction, heure: str = "21:00"):
    """Lance un sondage tryhard pour aujourd'hui avec une heure optionnelle"""
    logging.info(f"Commande 'askForTryhardToday' exécutée par {interaction.user.display_name} (ID: {interaction.user.id}) avec heure: {heure}")
    
    # Vérifier si un sondage est déjà en cours
    if config.get("poll_message_id") is not None:
        info_text = generate_info_text()
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Sondage déjà en cours",
                description=f"Un sondage est déjà actif aujourd'hui.\n\n{info_text}",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
        return
    
    try:
        # Parser l'heure demandée
        hour_asked = datetime.strptime(heure, "%H:%M")
        now = datetime.now(ZoneInfo("Europe/Paris"))
        
        # Calculer l'heure de début de session pour aujourd'hui
        session_time = hour_asked.time()
        session_wanted = datetime.combine(
            now.date(),
            session_time, 
            tzinfo=ZoneInfo("Europe/Paris")
        )
        close_time = session_wanted - timedelta(seconds=POLL_CLOSE_DELAY_SECONDS)
        # Vérifier que l'heure est possible (sondage pas encore commencé)
        if session_wanted < now or close_time < now :
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Impossible de lancer le sondage",
                    description=f"L'heure {heure} est déjà passée. L'heure minimum est {(now + timedelta(seconds=POLL_CLOSE_DELAY_SECONDS)).strftime('%H:%M')}",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Mettre à jour la configuration et activer le sondage
        config["session_time"] = heure
        config["poll_active"] = True
        save_config(config)
        
        # Lancer le sondage immédiatement
        channel = interaction.guild.get_channel(int(os.environ["CHANNEL_ID"]))
        if not channel:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Erreur de configuration",
                    description=f"Channel {os.environ['CHANNEL_ID']} introuvable",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
            
        role = discord.utils.get(interaction.guild.roles, name=os.environ["ROLE_NAME"])
        if not role:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Erreur de configuration",
                    description=f"Rôle '{os.environ['ROLE_NAME']}' introuvable",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
        
        formatted_session = session_time.strftime("%Hh%M")
        message = await channel.send(
            f"🗳️ **Qui est chaud pour une session tryhard Valorant à {formatted_session} ? {role.mention} **\n\n"
            "✅ Oui\n❌ Non\n🤔 Plus tard (max 1h)"
        )
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        await message.add_reaction("🤔")
        
        # Calculer et sauvegarder l'heure de fermeture du sondage
        if DEBUG_POLL:
            close_time = (now + timedelta(seconds=10)).time()
        else:
            close_time = (session_wanted - timedelta(seconds=POLL_CLOSE_DELAY_SECONDS)).time()
        
        # Sauvegarder l'état du sondage
        config["poll_message_id"] = message.id
        config["last_posted_date"] = now.strftime("%Y-%m-%d")
        config["close_time"] = close_time.strftime("%H:%M:%S")
        save_config(config)
        
        # Afficher les informations avec le texte d'info
        info_text = generate_info_text()
        
        if DEBUG_POLL:
            title = "🧪 Sondage tryhard lancé en MODE DEBUG !"
            color = discord.Color.orange()
        else:
            title = "✅ Sondage tryhard lancé avec succès !"
            color = discord.Color.green()
            
        await interaction.response.send_message(
            embed=discord.Embed(
                title=title,
                description=f"{info_text}",
                color=color
            ),
            ephemeral=True
        )
        
    except ValueError:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Format invalide",
                description="Utilise le format HH:MM (ex: 21:00)",
                color=discord.Color.red()
            ),
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Erreur lors du lancement du sondage",
                description=f"{e}",
                color=discord.Color.red()
            ),
            ephemeral=True
        )

@tree.command(
    name="tryhardinfo", 
    description="Affiche les informations actuelles de configuration",
    guild=discord.Object(id=GUILD_ID)
)
async def tryhardInfo(interaction: discord.Interaction):
    """Affiche les informations actuelles de configuration"""
    # Log de la commande
    logging.info(f"Commande 'tryhardInfo' exécutée par {interaction.user.display_name} (ID: {interaction.user.id})")
    
    info_text = generate_info_text()
    
    await interaction.response.send_message(
        embed=discord.Embed(
            description=info_text,
            color=discord.Color.blue()
        ),
        ephemeral=True
    )

bot_log("🚀 Lancement de bot.run()")
bot.run(TOKEN)

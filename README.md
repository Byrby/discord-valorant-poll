# Bot Discord Tryhard Valorant

Un bot Discord automatisé pour organiser des sessions tryhard Valorant avec système de sondage intelligent.

## 🎯 Fonctionnalités

### Commandes Slash

- `/askfortryhardtoday [heure]` - Lance un sondage pour une session tryhard à l'heure spécifiée (21:00 par défaut)
- `/tryhardinfo` - Affiche la configuration actuelle et l'état du sondage

### Automatisation

- **Fermeture automatique** : Le sondage se ferme automatiquement avant la session (délai configurable)
- **Récupération d'état** : Le bot récupère l'état des sondages actifs au redémarrage
- **Reset quotidien** : Nettoyage automatique de l'état chaque jour
- **Logging complet** : Suivi des commandes et événements du bot

### Système de sondage

- Réactions automatiques : ✅ (Oui), ❌ (Non), 🤔 (Plus tard)
- Mention automatique du rôle configuré
- Résultats détaillés avec noms des participants
- Protection contre les sondages multiples

## ⚙️ Configuration

### Variables d'environnement requises

```env
BOT_TOKEN=your_discord_bot_token
GUILD_ID=your_server_id
CHANNEL_ID=your_channel_id
ROLE_NAME=your_role_name
POLL_CLOSE_DELAY_SECONDS=3600  # Optionnel (1h par défaut)
DEBUG_POLL=false  # Optionnel (mode debug 10s)
```

### Fichiers générés

- `config.json` - Configuration persistante du bot
- `command.log` - Log des commandes utilisées
- `bot.log` - Log détaillé du bot

## 🚀 Installation

1. **Cloner le projet**

```bash
git clone <repository_url>
cd discord
```

2. **Installer les dépendances**

```bash
pip install -r requirements.txt
```

3. **Configuration**

   - Créer un fichier `.env` avec les variables requises
   - Configurer les permissions du bot Discord (lecture messages, réactions, slash commands)

4. **Lancement**

```bash
python bot.py
```

## 🛠️ Permissions Discord requises

Le bot nécessite les permissions suivantes :

- `Send Messages` - Envoyer des messages
- `Add Reactions` - Ajouter des réactions
- `Manage Messages` - Modifier/supprimer des messages
- `Read Message History` - Lire l'historique
- `Use Slash Commands` - Utiliser les commandes slash
- `Mention Everyone` - Mentionner les rôles

## 📋 Utilisation

### Lancer un sondage

```
/askfortryhardtoday 22:30
```

Lance un sondage pour une session à 22h30. Le sondage se fermera automatiquement 1h avant (21h30 par défaut).

### Vérifier la configuration

```
/tryhardinfo
```

Affiche l'état actuel : heure de session, heure de fermeture, statut du sondage.

## 🔧 Mode Debug

Activez `DEBUG_POLL=true` pour tester rapidement :

- Le sondage se ferme après 10 secondes au lieu du délai normal
- Utile pour les tests et le développement

## 📝 Logs

Le bot génère deux fichiers de log :

- `command.log` : Commandes exécutées par les utilisateurs
- `bot.log` : Événements détaillés du bot (connexion, erreurs, etc.)

## 🏗️ Architecture

- **Gestion d'état persistante** : Configuration sauvegardée en JSON
- **Tâches asynchrones** : Vérification continue et reset quotidien
- **Récupération robuste** : Gestion des redémarrages et erreurs
- **Logging structuré** : Suivi complet des opérations

# Discordeerr

> A Discord bot that sends Seerr notifications as private messages to users instead of just posting to a channel.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg)](https://github.com/Rapptz/discord.py)
[![Docker](https://img.shields.io/badge/docker-ghcr.io/0xsysr3ll/discordeerr-blue.svg)](https://github.com/0xSysR3ll/discordeerr/pkgs/container/discordeerr)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/0xSysR3ll/discordeerr)](https://github.com/0xSysR3ll/discordeerr/releases)
![Release](https://github.com/0xsysr3ll/discordeerr/actions/workflows/release.yml/badge.svg)
![CI](https://github.com/0xsysr3ll/discordeerr/actions/workflows/ci.yml/badge.svg)
[![GitHub issues](https://img.shields.io/github/issues/0xSysR3ll/discordeerr)](https://github.com/0xSysR3ll/discordeerr/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/0xSysR3ll/discordeerr)](https://github.com/0xSysR3ll/discordeerr/pulls)

## Features

- Real-time Discord notifications for Seerr events
- DM notifications for linked users
- Admin commands for user management
- Docker deployment support

## Quick Start

### Prerequisites

- Python 3.13+
- Discord Bot Token
- Jellyseerr/Overseerr instance
- Seerr API Key

> [!NOTE]
> Make sure your Discord bot has the required permissions: Send Messages, Use Slash Commands, Send Messages in Threads, Embed Links, Attach Files, Read Message History

### Installation

```bash
git clone https://github.com/0xSysR3ll/discordeerr.git
cd discordeerr

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your config

# Run the bot
python main.py
```

### Docker

```bash
# Pre-built image
docker run -d \
  --name discordeerr \
  -p 5000:5000 \
  -v ./data:/app/data \
  --env-file .env \
  ghcr.io/0xsysr3ll/discordeerr:latest

# Or build from source
docker build -t discordeerr .
docker run -d --name discordeerr -p 5000:5000 -v ./data:/app/data --env-file .env discordeerr
```

> [!TIP]
> Docker Compose is recommended for easier management and automatic restarts.

### Docker Compose

```yaml
version: "3.8"
services:
  discordeerr:
    image: ghcr.io/0xsysr3ll/discordeerr:latest
    container_name: discordeerr
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    restart: unless-stopped
```

## Configuration

### Environment Variables

| Variable                  | Description                                  | Required | Default                        |
| ------------------------- | -------------------------------------------- | -------- | ------------------------------ |
| `DISCORD_TOKEN`           | Discord bot token                            | Yes      | -                              |
| `SEERR_URL`               | Jellyseerr/Overseerr URL                     | Yes      | -                              |
| `SEERR_API_KEY`           | Seerr API key                                | Yes      | -                              |
| `NOTIFICATION_CHANNEL_ID` | Discord channel for notifications            | Yes      | -                              |
| `WEBHOOK_HOST`            | Webhook server host                          | No       | `0.0.0.0`                      |
| `WEBHOOK_PORT`            | Webhook server port                          | No       | `5000`                         |
| `WEBHOOK_AUTH_HEADER`     | Webhook authentication header                | No       | -                              |
| `DEBUG_MODE`              | Enable debug mode                            | No       | `false`                        |
| `DISCORD_GUILD_ID`        | Discord guild ID for guild-specific commands | No       | -                              |
| `DATABASE_PATH`           | Database file path                           | No       | `data/database/discordeerr.db` |
| `LOG_LEVEL`               | Logging level                                | No       | `INFO`                         |

### Discord Bot Setup

1. Create application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Create bot and get token
3. Grant permissions: Send Messages, Use Slash Commands, Send Messages in Threads, Embed Links
4. Invite bot using OAuth2 URL generator

### Seerr Webhook Configuration

Configure the webhook in your Seerr instance to enable notifications:

1. **Go to Seerr Settings** → **Notifications** → **Webhook**
2. **Webhook URL**: `http://your-bot-ip:5000/webhook`
3. **Authorization Header** (optional): Set to match your `WEBHOOK_AUTH_HEADER` environment variable
4. **JSON Payload**:

```json
{
  "notification_type": "{{notification_type}}",
  "event": "{{event}}",
  "subject": "{{subject}}",
  "message": "{{message}}",
  "image": "{{image}}",
  "notifyuser_username": "{{notifyuser_username}}",
  "notifyuser_avatar": "{{notifyuser_avatar}}",
  "notifyuser_settings_discordId": "{{notifyuser_settings_discordId}}",
  "media_tmdbid": "{{media_tmdbid}}",
  "media_tvdbid": "{{media_tvdbid}}",
  "media_type": "{{media_type}}",
  "media_status": "{{media_status}}",
  "media_status4k": "{{media_status4k}}",
  "request_id": "{{request_id}}",
  "requestedBy_username": "{{requestedBy_username}}",
  "requestedBy_avatar": "{{requestedBy_avatar}}",
  "requestedBy_settings_discordId": "{{requestedBy_settings_discordId}}",
  "issue_id": "{{issue_id}}",
  "issue_type": "{{issue_type}}",
  "issue_status": "{{issue_status}}",
  "reportedBy_username": "{{reportedBy_username}}",
  "reportedBy_avatar": "{{reportedBy_avatar}}",
  "reportedBy_settings_discordId": "{{reportedBy_settings_discordId}}",
  "comment_message": "{{comment_message}}",
  "commentedBy_username": "{{commentedBy_username}}",
  "commentedBy_avatar": "{{commentedBy_avatar}}",
  "commentedBy_settings_discordId": "{{commentedBy_settings_discordId}}",
  "{{extra}}": []
}
```

5. **Enable Notification Types**:
All notification types are supported.


> [!TIP]
> Replace `your-bot-ip` with your actual bot server IP address. If running locally, use `localhost:5000`.

## Commands

### User Commands

| Command         | Description                   |
| --------------- | ----------------------------- |
| `/link-account` | Link Discord account to Seerr |
| `/status`       | Check account link status     |

### Admin Commands

| Command              | Description                                 |
| -------------------- | ------------------------------------------- |
| `/health`            | Check bot health and config                 |
| `/users`             | List all linked users                       |
| `/force-link-member` | Force link Discord member to Seerr          |
| `/unlink-member`     | Unlink Discord member from Seerr            |
| `/force-link`        | Force link by Discord ID and Seerr username |
| `/unlink-user`       | Unlink Discord user by ID                   |
| `/sync`              | Sync commands to Discord                    |
| `/check-discord-id`  | Check Discord ID conflicts                  |
| `/reset-commands`    | Reset all commands                          |

## Account Linking

### User Flow

1. Use `/link-account` command
2. Configure Discord notifications in Seerr settings

> [!IMPORTANT]
> Users must add their Discord ID to their Seerr profile before linking accounts.

### Admin Flow

- Use admin commands for manual linking when auto-linking fails
- Monitor linked accounts with `/users`
- Resolve conflicts with `/check-discord-id`

> [!IMPORTANT]
> Admin commands require:
>
> 1. Your Discord account to be linked to Seerr using `/link-account`
> 2. Admin privileges in Seerr

## Notifications

### Supported Events

- Request Pending
- Request Approved
- Request Declined
- Request Available
- Request Failed
- Issue Reports

### Features

- Rich embeds with media posters
- Action buttons linking to Seerr requests
- DM notifications for linked users
- Channel notifications for public updates

## Development

````

### Development Setup

```bash
pip install -r requirements.txt
pre-commit install
python main.py
````

### Code Quality

- **Ruff**: Linting and import sorting
- **Black**: Code formatting
- **Pre-commit**: Git hooks

## Logging

Logs stored in `data/logs/discordeerr.log` with rotation (10MB max, 5 backups).

### Log Levels

- `DEBUG`: Detailed debugging info
- `INFO`: General information (default)
- `WARNING`: Warning messages
- `ERROR`: Error messages

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- [Issues](https://github.com/0xSysR3ll/discordeerr/issues)
- [Discussions](https://github.com/0xSysR3ll/discordeerr/discussions)

## Acknowledgments

- [Jellyseerr](https://github.com/Fallenbagel/jellyseerr) - Media request management
- [discord.py](https://github.com/Rapptz/discord.py) - Discord API wrapper

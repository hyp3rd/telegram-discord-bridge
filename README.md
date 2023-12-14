# Telegram - Discord Bridge

[![Pylint](https://github.com/hyp3rd/telegram-discord-bridge/actions/workflows/pylint.yml/badge.svg)][pylint_badge]
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A `Python` bridge to forward messages from those pesky Telegram channels to a shiny Discord channel, because why not? It is highly customizable and allows you to configure various settings, such as forwarding messages with specific hashtags, mentioning roles or users in Discord, and more.

## Cunning Features

- Relocate messages from a multitude of Telegram channels
- Shove forwarded messages into a designated Discord channel
- It deals with Media and URL previews on your behalf (photos, videos, documents) from Telegram to Discord
- **The forwarding is configurable based on allowed or excluded hashtags, keeping irrelevant content away**
- **It handles connectivity and APIs outages for you, reconnecting automatically and forwarding the messages that were missed**
- It is customizable mention settings, including mentioning roles or users in Discord when forwarding messages
- It maintains the history, storing a map of the forwarded messages, allowing you to track correspondence between Telegram and Discord, **making possible replies**.
- **It supports OpenAI's API to generate suggestions and sentiment analyses based on the text you're forwarding.**
- It can run as a daemon and handle any shutdown gracefully, including `SIGTERM` and `SIGINT` signals. It will also save the state of the bridge, so you can resume from where you left off
- You can enable logging to the file system, which will handle the rotation for you.

## Installation

First, you need to clone this repository:

```bash
git clone https://github.com/hyp3rd/telegram-discord-bridge.git
cd telegram-discord-bridge
```

Next, follow the instructions here (don't worry, they won't bite):

1. Install **Python 3.10** or higher and set up a virtual environment;
2. Install the dependencies: `pip install -r requirements.txt`
3. Set up a [**Telegram Application**](https://core.telegram.org/api/obtaining_api_id) and obtain the API creds.
4. Set up a Discord bridge with the necessary permissions to read and write the messages, and obtain the bridge token.

Now craft a new `config.yml` file in the root directory, starting from the `config-example.yml` file.
**Keep in mind** that in the example below the angular brackets are indicating a placeholder `<>`, **remove them.**

```yaml
---
# Basic application configuration
application:
  name: "hyp3rbridg3"
  version: "1.1.9"
  description: "A Python bridge to forward messages from those pesky Telegram channels to a shiny Discord channel, because why not?"
  # Whether to enable debug mode, it will increase the verbosity of the logs and the exceptions will be raised instead of being logged
  debug: True
  # healtcheck interval in seconds
  healthcheck_interval: 10
  # The time in seconds to wait before forwarding each missed message
  recoverer_delay: 60

# Management API configuration
api:
  enabled: True
  # Enable the Telegram MFA login via the management API
  telegram_login_enabled: True
  # The file to store the Telegram code and MFA password
  telegram_auth_file: "telegram_auth.json"
  # The Telegram auth request expiration in seconds
  telegram_auth_request_expiration: 300
  # Allow CORS requests from these origins
  cors_origins: ["*"]

# logger setup
logger:
  level: "DEBUG" # NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL
  file_max_bytes: 10485760 # 10MB
  file_backup_count: 5
  # format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  format: "%(asctime)s %(levelprefix)s %(message)s"
  date_format: "%Y-%m-%d %H:%M:%S"
  console: False # set to true to enable console logging and disable file based logging

# Telegram configuration
telegram:
  # Your Telegram phone number | With quotes
  phone: "<your phone number>"
  # Your Telegram password (Two-step verification) | With quotes
  password: "<your password>"
  # This has to be an integer. Read more [here](https://core.telegram.org/api/obtaining_api_id) | No quotes
  api_id: <your api id>
  # Long 32 characters hash identifier. Read more [here](https://core.telegram.org/api/obtaining_api_id) | With quotes
  api_hash: "<your api hash>"
  # Whether to log the conversations that aren't available for forwarding (private chats, etc.)
  log_unhandled_dialogs: False

# Discord configuration
discord:
  # Discord Bot Token. Go create a bridge on discord. | No quotes
  bot_token: "<your bot token>"
  # built-in roles in discord, they need special attention when parsing thee name to mention
  built_in_roles: ["everyone", "here", "@Admin"]
  # Discord Client max tolerable latency
  max_latency: 0.5

# OpenAI configuration
openai:
  enabled: False
  # OpenAI API Key and Organization. Read more [here](https://beta.openai.com/docs/api-reference)
  api_key: "<your openai api key>"
  organization: "<your openai organization>"
  # The prompt to use for OpenAI, the #text_to_parse will be appended to this prompt
  sentiment_analysis_prompt:
    - "Analyze the following text to determine its sentiment: #text_to_parse.\n\n"
    - "<add the rest of your prompt, if any, here>.\n\n"
    - "<add the rest of your prompt, if any, here>.\n\n"

# The channels map to discord channels.
telegram_forwarders:
  - forwarder_name: "<forwarder_name>"
    tg_channel_id: <tg channel id>
    discord_channel_id: <discord channel id>
    strip_off_links: False # whether to strip off links from the message
    mention_everyone: True
    forward_everything: False # whether forwarding everything regardless the hashtag
    forward_hashtags:
      - name: "#example1"
        override_mention_everyone: True
      - name: "#example6"

  - forwarder_name: "<forwarder_name>"
    tg_channel_id: <tg channel id>
    discord_channel_id: <discord channel id>
    strip_off_links: False # whether to strip off links from the message
    mention_everyone: False
    forward_everything: False # whether forwarding everything regardless the hashtag
    mention_override:
      - tag: "#important"
        roles: ["everyone", "here", "@Admin"]
      - tag: "#trading"
        roles: ["Trading", "here"]
    forward_hashtags:
      - name: "#example3"
        override_mention_everyone: True
      - name: "#example4"
    excluded_hashtags:
      - name: "#sponsored"
      - name: "#sponsor"
```

Finally, start the bridge and watch the magic happen:

```bash
python forwarder.py --start  # it will start the bridge in the foreground
```

```bash
python forwarder.py --start --background  # it will start the bridge in background, requires the `Logger` console set to False
```

You can control the process with a stop command:

```bash
python forwarder.py --stop
```

## Usage

Once the script gets going, it will eavesdrop on new messages in the specified Telegram channels. Messages can be filtered based on hashtags, and you can configure the bridge to mention specific roles or users in Discord when forwarding messages. The bridge supports built-in Discord roles like "@everyone" and "@here" and custom role names.

In addition to text messages, the bridge can forward media files such as photos, videos, and documents from Telegram to Discord. The bridge also handles replies to messages and embeds them as Discord replies, maintaining a mapping of forwarded messages for easier correspondence tracking between the two platforms.

## Run it in Docker

You can run the bridge in a Docker container. The Docker image is available on [GitHub Packages](https://github.com/hyp3rd/telegram-discord-bridge/pkgs/container/bridge).

```bash
docker run -p:8000:8000 -v $(pwd)/config.yml:/app/config.yml:ro -it ghcr.io/hyp3rd/bridge:v1.1.10
```

### Limitations

A local `JSON` file is the sole storage supported to maintain the correspondence between Telegram and Discord. It implies that you figure out how to rotate the file, or it will grow out of proportion. **I'm working on a solution to store the history in databases, Redis, and KV storage, but it still needs to be prepared.**

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

This project is a masked vigilante inspired by the base idea of [Telegram-To-Discord-Forward-Bot](https://github.com/kkapuria3/Telegram-To-Discord-Forward-Bot) by [kkapuria3](https://github.com/kkapuria3/).

## Author

I'm a surfer, a crypto trader, and a software architect with 15 years of experience designing highly available distributed production environments and developing cloud-native apps in public and private clouds. Just your average bloke. Feel free to connect with me on LinkedIn, but no funny business, alright?

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/francesco-cosentino/)

[pylint_badge]: https://github.com/hyp3rd/telegram-discord-bridge/actions/workflows/pylint.yml

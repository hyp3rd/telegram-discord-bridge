# Telegram - Discord Bridge

[![Pylint](https://github.com/hyp3rd/telegram-discord-bridge/actions/workflows/pylint.yml/badge.svg)][pylint_badge]

A `Python` bot to forward messages from those pesky Telegram channels to a shiny Discord channel, because why not? It is highly customizable and allows you to configure various settings, such as forwarding messages with specific hashtags, mentioning roles or users in Discord, and more.

## Cunning Features

- Relocate messages from a multitude of Telegram channels
- Shove forwarded messages into a designated Discord channel
- It deals with Media and URL previews on your behalf (photos, videos, documents) from Telegram to Discord
- The forwarding is configurable based on hashtags, keeping irrelevant content away
- It is customizable mention settings, including mentioning roles or users in Discord when forwarding messages
- It maintains the history, storing a map of the forwarded messages, allowing you to track correspondence between Telegram and Discord, **making possible replies**.
- **It supports OpenAI's API to generate suggestions and sentiment analysys based on the text you're forwarding.**

## Installation

First, you need to clone this repository:

```bash

git clone https://github.com/hyp3rd/telegram-discord-bridge.git
cd telegram-discord-bridge
```

Next, follow the instructions here (don't worry, they won't won't bite):

1. Install Python 3.8 or higher and set up a virtual environment;
2. Install the dependencies: `pip install -r requirements.txt`
3. Set up a [**Telegram Application**](https://core.telegram.org/api/obtaining_api_id) and obtain the API creds.
4. Set up a Discord bot with the necessary permissions to read and write the messages,5. and obtain the bot token.

Now craft a new `config.yml` file in the root directory, starting from the `config-example.yml` file:

```yaml
---
app_name: "<your app name>"

# Your Telegram phone number | With quotes
telegram_phone: "<your phone number>"

# Your Telegram password (Two-step verification) | With quotes
telegram_password: "<your password>"

# This has to be an integer. Read more [here](https://core.telegram.org/api/obtaining_api_id) | No quotes
telegram_api_id: <your api id>

# Long 32 characters hash identifier. Read more [here](https://core.telegram.org/api/obtaining_api_id) | With quotes
telegram_api_hash: "<your api hash>"

# Discord Bot Token. Go create a bot on discord. | No quotes
discord_bot_token: <your discord bot token>

# built-in roles in discord, they need special attention when parsing thee name to mention
discord_built_in_roles: ["everyone", "here", "@Admin"]

# OpenAI API Key and Organization. Read more [here](https://beta.openai.com/docs/api-reference)
openai_api_key: "<your openai api key>"
openai_organization: "<your openai organization>"
openai_enabled: False
openai_sentiment_analysis_prompt:
  - "Analyze the following text to determine its sentiment: #text_to_parse.\n\n"
  - "<add the rest of your prompt, if any, here>.\n\n"
  - "<add the rest of your prompt, if any, here>.\n\n"

# The channels map to discord channels.
telegram_forwarders:
  - forwarder_name: "<forwarder_name>"
    tg_channel_id: <tg channel id>
    discord_channel_id: <discord channel id>
    mention_everyone: True
    forward_everything: False # whether forwarding everything regardless the hashtag
    forward_hashtags:
      - name: "#example1"
        override_mention_everyone: True
      - name: "#example6"

  - forwarder_name: "<forwarder_name>"
    tg_channel_id: <tg channel id>
    discord_channel_id: <discord channel id>
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
```

Finally, start the bridge and watch the magic happen:

```bash
python app.py --start
```

You can control the process with a stop command:

```bash
python app.py --stop
```

## Usage

Once the script gets going, it will eavesdrop on new messages in the specified Telegram channels. Messages can be filtered based on hashtags, and you can configure the bot to mention specific roles or users in Discord when forwarding messages. The bot supports built-in Discord roles like "@everyone" and "@here" and custom role names.

In addition to text messages, the bot can forward media files such as photos, videos, and documents from Telegram to Discord. The bot also handles replies to messages and embeds them as Discord replies, maintaining a mapping of forwarded messages for easier correspondence tracking between the two platforms.

### Limitations

Currently, a local' JSON' file is the sole storage supported to maintain the correspondence between Telegram and Discord. It implies that you figure out how to rotate the file, or it will grow out of proportion. **I'm working on a solution to store the history in databases, Redis, and KV storage, but it still needs to be prepared.**

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

This project is a masked vigilante inspired by the base idea of [Telegram-To-Discord-Forward-Bot](https://github.com/kkapuria3/Telegram-To-Discord-Forward-Bot) by [kkapuria3](https://github.com/kkapuria3/).

## Author

I'm a surfer, a crypto trader, and a software architect with 15 years of experience designing highly available distributed production environments and developing cloud-native apps in public and private clouds. Just your average bloke. Feel free to connect with me on LinkedIn, but no funny business, alright?
  
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/francesco-cosentino/)

[pylint_badge]: https://github.com/hyp3rd/telegram-discord-bridge/actions/workflows/pylint.yml

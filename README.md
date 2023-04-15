# Telegram - Discord Bridge

A cheeky `Python` bot to slyly forward messages from those pesky Telegram channels to a shiny Discord channel, because why not?

## Cunning Features

- Relocate messages from a multitude of Telegram channels
- Shove forwarded messages into a designated Discord channel
- Toss in messages with URLs and casually mention '@everyone' in Discord

## Installation

First, mate, you need to clone this repository:

```bash

git clone https://github.com/hyp3rd/telegram-discord-bridge.git
cd telegram-discord-bridge
```

Next, install the required packages (don't worry, it won't bite):

```bash
pip install -r requirements.txt
```

Craft a new `config.yml` file in the root directory, starting from the `config-example.yml` file:

```yaml
---
app_name: '<your app name>'

# Your Telegram phone number | With quotes
telegram_phone: '<your phone number>'

# Your Telegram password (Two-step verification) | With quotes
telegram_password: '<your password>'

# This has to be an integer. Read more [here](https://core.telegram.org/api/obtaining_api_id) | No quotes
telegram_api_id: <your api id>

# Long 32 characters hash identifier. Read more [here](https://core.telegram.org/api/obtaining_api_id) | With quotes
telegram_api_hash: '<your api hash>' 

# Discord Bot Token. Go create a bot on discord. | No quotes
discord_bot_token: <your discord bot token>

# Discord Channel ID, may need to enable discord developer mode in settings. | No quotes
discord_channel: <your discord channel id>

# The channels that you'd like to forward messages from. Input telegram channel names here.
# The user running the client must have these channels present on it's dialogs.
telegram_input_channels:
  - '<your telegram channel name>'
  - <your telegram channel id>
```

Finally, run the script and watch the magic happen, almost, read the **caveats** section:

```bash
python app.py
```

## Usage

Once the script gets going, it will eavesdrop on new messages in the specified Telegram channels. When a message is intercepted, it will be sneakily forwarded to the Discord channel, and '@everyone' will be mentioned. Messages with URLs will include the URLs in the forwarded message because sharing is caring.

### Caveats

When you run the script for the first time, it will ask you to input your Telegram phone number and the verification code that Telegram sends to your phone. After that, rerun the script, which will lurk in the background, forwarding messages from Telegram to Discord. It is required to authenticate the script with Telegram, or it won't work.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

This project is a masked vigilante inspired by the base idea of [Telegram-To-Discord-Forward-Bot](https://github.com/kkapuria3/Telegram-To-Discord-Forward-Bot) by [kkapuria3](https://github.com/kkapuria3/).

## Author

I'm a surfer, a crypto trader, and a software architect with 15 years of experience designing highly available distributed production environments and developing cloud-native apps in public and private clouds. Just your average bloke. Feel free to connect with me on LinkedIn, but no funny business, alright?
  
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/francesco-cosentino/)

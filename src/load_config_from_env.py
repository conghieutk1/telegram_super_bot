import os
import json

class BotConfig:
    def __init__(self):
        self.telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
        self.telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

        self.exchangerate_access_key = os.environ.get("EXCHANGERATE_API_KEY")
        self.openweather_api_key = os.environ.get("OPENWEATHER_API_KEY")
        self.news_api_key = os.environ.get("NEWS_API_KEY")

        # phần config không nhạy cảm có thể để file config.json
        with open("config.json", "r") as f:
            self.config = json.load(f)

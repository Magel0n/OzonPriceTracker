import os

class TelegramWrapper:

    bot_token: str

    def __init__(self):
        self.bot_token = os.environ.get("TG_BOT_TOKEN", "12345")
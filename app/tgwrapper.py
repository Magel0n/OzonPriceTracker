import os
import requests
import time
from api_models import *
from typing import Set


class TelegramWrapper:
    BASE_URL_CORE = "https://api.telegram.org/bot"

    bot_token: str
    base_url: str

    def __init__(self):

        try:
            response = requests.get("https://api.telegram.org", timeout=5)
            print(f"Connection successful (status {response.status_code})")
        except Exception as e:
            print(f"Connection failed: {e}")

        self.bot_token = os.environ.get("TG_BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("TG_BOT_TOKEN environment variable not set")
        self.base_url = f"{self.BASE_URL_CORE}{self.bot_token}/"
        self.authorized_users: Set[int] = set()
        self.last_update_id = None

    def _make_request(self, method: str, params: dict = None) -> dict:
        """Internal method for making API requests"""
        url = f"{self.base_url}{method}"
        response = requests.post(url, json=params) if params else requests.get(url)
        print(response.status_code, response.json())
        return response.json()

    def get_updates(self) -> dict:
        """Get new messages sent to your bot"""
        params = {'timeout': 5}
        if self.last_update_id:
            params['offset'] = self.last_update_id + 1
        return self._make_request('getUpdates', params)

    def send_message(self, chat_id: int, text: str) -> dict:
        """Send a message to a specific chat"""
        if chat_id not in self.authorized_users:
            print("You are not authorized to send messages to that chat", chat_id)
            return {"ok": False, "description": "User not authorized"}
        return self._make_request('sendMessage', {'chat_id': chat_id, 'text': text})

    def authorize_user(self, telegram_id: int) -> None:
        """Add a user to the authorized list"""
        self.authorized_users.add(telegram_id)

    def is_authorized(self, telegram_id: int) -> bool:
        """Check if user is authorized"""
        return telegram_id in self.authorized_users

    def tick(self) -> None:
        """Process one update cycle"""
        print("Got to start tick")
        updates = self.get_updates()
        print("Got to tick")

        if not updates.get('result'):
            print("No updates received")
            return

        for update in updates['result']:
            self.last_update_id = update['update_id']
            message = update.get('message', {})
            chat_id = message.get('chat', {}).get('id')
            text = message.get('text', '').strip().lower()

            if not chat_id:
                continue

            if text == '/start':
                self.send_message(chat_id, "Welcome! Send /auth to get authorized.")

            elif text == '/auth':
                self.authorize_user(chat_id)
                self.send_message(chat_id, "You are now authorized! Send /test to verify.")

            elif text == '/test':
                if self.is_authorized(chat_id):
                    self.send_message(chat_id, "This is a test message for authorized users!")
                else:
                    self.send_message(chat_id, "You need to send /auth first!")

            elif text.startswith('/'):
                self.send_message(chat_id, "Unknown command")

    def start(self, interval: float = 1.0) -> None:
        """Start the bot with specified tick interval (in seconds)"""
        print("Bot started. Press Ctrl+C to stop.")
        try:
            while True:
                self.tick()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nBot stopped.")

#    def push_notifications(users_to_products: dict[str, list[TrackedProductModel]]) -> bool:
#        pass
#
#    def get_user_info(user_tid: str) -> UserModel | None:
#        pass


tgwrapper = TelegramWrapper()
tgwrapper.start()

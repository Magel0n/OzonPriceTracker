import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

from api_models import UserModel, TrackedProductModel
from database import Database

class TelegramWrapper:
    def __init__(self, database: Database):
        self.bot = Bot(
            token=os.getenv('TG_BOT_TOKEN'),
            default=DefaultBotProperties(parse_mode="HTML")
        )
        self.dp = Dispatcher()
        self.db = database
        self.user_sessions: Dict[int, dict] = {}

        # Register handlers
        self.dp.message(Command("start"))(self._handle_start)
        self.dp.message(Command("auth"))(self._handle_auth)
        
        # Run tests if in test mode
        if os.getenv('TEST_MODE') == '1':
            self.run_tests()

    def get_user_info(self, user_tid: str) -> Optional[UserModel]:
        """Synchronously get user info from Telegram"""
        async def async_get_user_info():
            try:
                chat = await self.bot.get_chat(user_tid)
                return UserModel(
                    tid=int(user_tid),
                    name=f"{chat.first_name or ''} {chat.last_name or ''}".strip(),
                    username=chat.username or "",
                    user_pfp=None
                )
            except Exception as e:
                print(f"Error getting user info: {e}")
                return None
        return self._run_async(async_get_user_info())

    def push_notifications(self, users_to_products: dict[str, list[TrackedProductModel]]) -> bool:
        """Push notifications to users about product updates"""
        async def async_push_notifications():
            success = True
            for user_tid, products in users_to_products.items():
                user_id = int(user_tid)
                message = "Product updates:\n\n"
                
                for product in products:
                    price_info = f"Current price: {product.price}"
                    if product.tracking_price:
                        price_info += f" (Tracking: {product.tracking_price})"
                    
                    message += (
                        f"{product.name}\n"
                        f"{price_info}\n"
                        f"Seller: {product.seller}\n"
                        f"{product.url}\n\n"
                    )

                try:
                    await self.bot.send_message(
                        user_id,
                        message,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"Error sending message to {user_id}: {e}")
                    success = False
            return success

        return self._run_async(async_push_notifications())

    def _handle_start(self, message: types.Message):
        """Synchronously handle /start command"""
        welcome_text = (
            "Welcome to Price Tracker Bot!\n\n"
            "I can help you track product prices from Ozon and notify you when prices drop.\n\n"
            "Use /auth to authenticate and link your account\n"
            "You'll receive notifications when prices drop below your specified limits."
        )
        self._run_async(self.bot.send_message(
            chat_id=message.chat.id,
            text=welcome_text
        ))

    def _handle_auth(self, message: types.Message):
        """Synchronously handle /auth command"""
        user_id = str(message.from_user.id)
        user = self.get_user_info(user_id)
        if not user:
            self._run_async(self.bot.send_message(
                chat_id=message.chat.id,
                text="Could not retrieve your Telegram profile information."
            ))
            return
        
        if not self.db.login_user(user):
            self._run_async(self.bot.send_message(
                chat_id=message.chat.id,
                text="Failed to authenticate. Please try again."
            ))
            return
        
        token = f"streamlit_{user_id}_{datetime.now().timestamp()}"
        expires = datetime.now() + timedelta(hours=1)
        self.user_sessions[int(user_id)] = {
            'token': token,
            'expires': expires
        }
        
        streamlit_link = f"https://your-streamlit-app.com/session?token={token}"
        auth_message = (
            "Authentication successful!\n\n"
            f"Your session token: {token}\n"
            f"Expires at: {expires.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Open dashboard: {streamlit_link}"
        )
        self._run_async(self.bot.send_message(
            chat_id=message.chat.id,
            text=auth_message
        ))

    def start(self):
        """Start the bot synchronously"""
        async def async_start():
            await self.dp.start_polling(self.bot)
        self._run_async(async_start())

    def run_tests(self):
        """Run test cases synchronously"""
        test_user_id = os.getenv('TEST_USER_ID')
        if not test_user_id:
            print("TEST_USER_ID environment variable not set")
            return False

        print("\nRunning tests...")

        # Create complete test user object
        test_user = types.User(
            id=int(test_user_id),
            is_bot=False,
            first_name="Test",
            last_name="User",
            username="testuser",
            language_code="en"
        )

        # Test get_user_info
        print("Testing get_user_info...")
        user_info = self.get_user_info(test_user_id)
        print(f"User info: {user_info}")
    
        # Test start command
        print("\nTesting /start command...")
        start_message = types.Message(
            message_id=1,
            date=datetime.now(),
            chat=types.Chat(
                id=int(test_user_id),
                type="private",
                first_name=test_user.first_name,
                last_name=test_user.last_name,
                username=test_user.username
            ),
            from_user=test_user,
            text="/start"
        )
        self._handle_start(start_message)
    
        # Test auth command
        print("\nTesting /auth command...")
        auth_message = types.Message(
            message_id=2,
            date=datetime.now(),
            chat=types.Chat(
                id=int(test_user_id),
                type="private",
                first_name=test_user.first_name,
                last_name=test_user.last_name,
                username=test_user.username
            ),
            from_user=test_user,
            text="/auth"
        )
        self._handle_auth(auth_message)
    
        # Test push_notifications
        print("\nTesting push_notifications...")
        test_products = [
            TrackedProductModel(
                id="test_product_1",  # Required field added
                url="https://example.com/product1",
                sku="TEST123",
                name="Test Product",
                price="100.00",
                seller="Test Seller",
                tracking_price="90.00"
            )
        ]
        success = self.push_notifications({test_user_id: test_products})
        print(f"Notification test {'passed' if success else 'failed'}")
    
        return True

    def _run_async(self, coroutine):
        """Helper method to run async code synchronously"""
        return asyncio.get_event_loop().run_until_complete(coroutine)

if __name__ == '__main__':
    TelegramWrapper().start()
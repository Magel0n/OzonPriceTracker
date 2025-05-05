import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import asyncio
import logging
import jwt

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

from api_models import UserModel, TrackedProductModel
from database import Database

TOKEN_ENCRYPTION_ALGORITHM = os.environ.get("TOKEN_ENCRYPTION_ALGORITHM", "HS256")
TOKEN_EXPIRATION_MINUTES = int(os.environ.get("TOKEN_EXPIRATION_MINUTES", "30"))
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8501")

class TelegramWrapper:
    def __init__(self, database: Database, secret_key: str):
        self.logger = logging.getLogger(__name__)
        token = os.getenv('TG_BOT_TOKEN')
        
        if not token:
            raise ValueError("TG_BOT_TOKEN environment variable not set")
            
        self.bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode="HTML")
        )
        self.dp = Dispatcher()
        self.db = database
        self.secret_key = secret_key
        self.user_sessions: Dict[int, dict] = {}
        self._polling_task = None
        self._test_mode = os.getenv('TEST_MODE') == '1'
        
        # Register handlers
        self.dp.message(Command("start"))(self._handle_start)
        self.dp.message(Command("auth"))(self._handle_auth)

        self._setup_bot_commands()

    def _setup_bot_commands(self):
        """Set up persistent menu buttons"""
        self.commands_menu = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="/start"), types.KeyboardButton(text="/auth")],
            ],
            resize_keyboard=True,
            persistent=True  # Stays visible until removed
        )

    async def verify_connection(self) -> bool:
        """Verify the bot can connect to Telegram"""
        try:
            await self.bot.get_me()
            return True
        except Exception as e:
            self.logger.error(f"Connection verification failed: {e}")
            return False

    async def initialize(self):
        """Async initialization that can be awaited"""
        if self._test_mode:
            await self.run_tests()

    async def get_user_info(self, user_tid: str) -> Optional[UserModel]:
        """Get user info from Telegram"""
        try:
            chat = await self.bot.get_chat(user_tid)
            return UserModel(
                tid=int(user_tid),
                name=f"{chat.first_name or ''} {chat.last_name or ''}".strip(),
                username=chat.username or "",
                user_pfp=None
            )
        except Exception as e:
            self.logger.error(f"Error getting user info: {e}")
            return None

    async def push_notifications(self, users_to_products: dict[str, list[TrackedProductModel]]) -> bool:
        """Push notifications to users about product updates"""
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
                self.logger.error(f"Error sending message to {user_id}: {e}")
                success = False
        
        return success

    async def _handle_start(self, message: types.Message):
        """Handle /start command"""
        welcome_text = (
            "Welcome to Price Tracker Bot!\n\n"
            "Use the buttons below to navigate:\n"
            "/start - Show this welcome message\n"
            "/auth - Authenticate your account"
        )
    
        try:
            await message.answer(
                text=welcome_text,
                reply_markup=self.commands_menu  # Attach persistent menu
            )
        except Exception as e:
            self.logger.error(f"Error sending start message: {e}")

    async def _handle_auth(self, message: types.Message):
        """Handle /auth command"""
        try:
            user_id = str(message.from_user.id)
            user = await self.get_user_info(user_id)
            if not user:
                await self.bot.send_message(
                    chat_id=message.chat.id,
                    text="Could not retrieve your Telegram profile information."
                )
                return
            
            if not self.db.login_user(user):
                await self.bot.send_message(
                    chat_id=message.chat.id,
                    text="Failed to authenticate. Please try again."
                )
                return
                
            expires = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRATION_MINUTES)
            
            token_data = {
                "id": user_id,
                "exp": expires
            }
            
            token = jwt.encode(token_data, self.secret_key, algorithm=TOKEN_ENCRYPTION_ALGORITHM)
            
            streamlit_link = f"{APP_BASE_URL}/?token={token}"
            auth_message = (
                "Authentication successful!\n\n"
                f"Open dashboard: {streamlit_link}"
            )
            await message.answer(
                text=auth_message,
                reply_markup=self.commands_menu  # Keep menu visible after auth
            )
        except Exception as e:
            self.logger.error(f"Error in auth handler: {e}")

    async def start(self):
        """Start the bot asynchronously"""
        if not await self.verify_connection():
            raise RuntimeError("Failed to connect to Telegram")
            
        self.logger.info("Bot starting...")
        self._polling_task = asyncio.create_task(self.dp.start_polling(self.bot))
        self.logger.info("Bot polling started")

        if self._test_mode:
            await self.run_tests()

    async def stop(self):
        """Stop the bot gracefully"""
        if self._polling_task:
            self.logger.info("Stopping bot...")
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                self.logger.info("Bot polling stopped")
            except Exception as e:
                self.logger.error(f"Error stopping bot: {e}")
            finally:
                self._polling_task = None

    async def run_tests(self):
        """Run test cases asynchronously"""
        test_user_id = os.getenv('TEST_USER_ID')
        if not test_user_id:
            self.logger.error("TEST_USER_ID environment variable not set")
            return False

        self.logger.info("Running tests...")

        try:
            # Create test user object
            test_user = types.User(
                id=int(test_user_id),
                is_bot=False,
                first_name="Test",
                last_name="User",
                username="testuser",
                language_code="en"
            )

            # Test get_user_info
            self.logger.info("Testing get_user_info...")
            user_info = await self.get_user_info(test_user_id)
            self.logger.info(f"User info: {user_info}")
        
            # Test start command
            self.logger.info("Testing /start command...")
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
            await self._handle_start(start_message)
        
            # Test auth command
            self.logger.info("Testing /auth command...")
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
            await self._handle_auth(auth_message)
        
            # Test push_notifications
            self.logger.info("Testing push_notifications...")
            test_products = [
                TrackedProductModel(
                    id="test_product_1",
                    url="https://example.com/product1",
                    sku="TEST123",
                    name="Test Product",
                    price="100.00",
                    seller="Test Seller",
                    tracking_price="90.00"
                )
            ]
            success = await self.push_notifications({test_user_id: test_products})
            self.logger.info(f"Notification test {'passed' if success else 'failed'}")
            
            return True
        except Exception as e:
            self.logger.error(f"Test failed: {e}")
            return False

async def create_telegram_wrapper(database: Database, secret_key: str) -> TelegramWrapper:
    """Factory function to create and verify TelegramWrapper"""
    wrapper = TelegramWrapper(database, secret_key)
    if not await wrapper.verify_connection():
        raise RuntimeError("Failed to initialize Telegram bot - invalid token or connection issues")
    return wrapper
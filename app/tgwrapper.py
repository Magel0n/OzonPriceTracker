import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional
import asyncio
import logging
import jwt

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

from api_models import UserModel, TrackedProductModel
from database import Database


PROFILE_PICS_DIR = Path(  # pragma: no mutate
    "./app/static/UserProfilePictures"
)

TOKEN_ENCRYPTION_ALGORITHM = os.environ.get(  # pragma: no mutate
    "TOKEN_ENCRYPTION_ALGORITHM", "HS256"
)
TOKEN_EXPIRATION_MINUTES = os.environ.get(  # pragma: no mutate
    "TOKEN_EXPIRATION_MINUTES", 10
)
APP_BASE_URL = os.environ.get(  # pragma: no mutate
    "APP_BASE_URL", "http://localhost:8501"
)


class TelegramWrapper:
    def __init__(  # pragma: no mutate
        self, database: Database, secret_key: str
    ):
        self.logger = logging.getLogger(__name__)
        token = os.getenv('TG_BOT_TOKEN')

        if not token:  # pragma: no mutate
            raise ValueError("TG_BOT_TOKEN environment variable not set")

        self.bot = Bot(  # pragma: no mutate
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

    def _setup_bot_commands(self):  # pragma: no mutate
        """Set up persistent menu buttons"""  # pragma: no mutate
        self.commands_menu = types.ReplyKeyboardMarkup(
            keyboard=[
                [
                    types.KeyboardButton(text="/start"),
                    types.KeyboardButton(text="/auth")
                ],
            ],
            resize_keyboard=True,
            persistent=True  # Stays visible until removed
        )

    async def verify_connection(self) -> bool:
        """Verify the bot can connect to Telegram"""  # pragma: no mutate
        try:
            await self.bot.get_me()
            return True
        except Exception as e:
            self.logger.error(  # pragma: no mutate
                f"Connection verification failed: {e}"
            )
            return False

    async def initialize(self):  # pragma: no mutate
        """Async initialization that can be awaited"""  # pragma: no mutate

    async def get_user_info(self, user_tid: str) -> Optional[UserModel]:
        try:
            chat = await self.bot.get_chat(user_tid)

            # Initialize with no profile picture
            pfp_file_id = None

            # Try to get profile photos
            try:
                photos = await self.bot.get_user_profile_photos(
                    int(user_tid), limit=1
                )
                if photos.photos:
                    # Get the largest available photo size
                    photo = photos.photos[0][-1]
                    pfp_file_id = photo.file_id

            except Exception as photo_error:
                self.logger.debug(  # pragma: no mutate
                    f"Couldn't get profile photo for user {user_tid}: "
                    f"{photo_error}"
                )

            return UserModel(
                tid=int(user_tid),
                name=f"{chat.first_name or ''} {chat.last_name or ''}".strip(),
                username=chat.username or "",
                user_pfp=pfp_file_id  # Now storing only file_id
            )

        except Exception as e:
            self.logger.error(f"Error getting user info: {e}")
            return None

    async def push_notifications(
        self, users_to_products: dict[str, list[TrackedProductModel]]
    ) -> bool:
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
                    f"XXSeller: {product.seller}\nXX"
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
        """Handle /start command"""  # pragma: no mutate
        welcome_text = (  # pragma: no mutate
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
        try:
            user_id = str(message.from_user.id)

            # Get user info including profile picture file_id
            user = await self.get_user_info(user_id)
            if not user:
                await message.answer(  # pragma: no mutate
                    "Could not retrieve your Telegram profile information."
                )
                return

            # Save profile picture locally if available
            if user.user_pfp:
                try:
                    # Ensure directory exists
                    PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)

                    # Get file path from Telegram
                    file = await self.bot.get_file(user.user_pfp)

                    # Define local path:
                    # ./app/static/UserProfilePictures/{file_id}.jpg
                    local_path = PROFILE_PICS_DIR / f"{user.user_pfp}.jpg"

                    # Download and save the photo
                    await self.bot.download_file(
                        file.file_path, destination=str(local_path)
                    )

                    self.logger.info(
                        "Saved profile picture"
                        f" for user {user_id} to {local_path}"
                    )

                except Exception as download_error:
                    self.logger.error(
                        f"Error saving profile picture: {download_error}"
                    )
                    user.user_pfp = None  # Clear if download fails

            # Store user in database (with or without profile picture file_id)
            if not self.db.login_user(user):
                await message.answer(
                    "Failed to authenticate. Please try again."
                )
                return

            # Generate auth token and prepare response (same as before)
            expires = datetime.now(timezone.utc) + timedelta(
                minutes=TOKEN_EXPIRATION_MINUTES
            )
            token_data = {"id": user_id, "exp": expires}
            token = jwt.encode(
                token_data, self.secret_key,
                algorithm=TOKEN_ENCRYPTION_ALGORITHM
            )

            streamlit_link = f"{APP_BASE_URL}/?token={token}"

            # Prepare response message
            auth_message = "Authentication successful!\n\n"

            auth_message += "Click below to open your dashboard:"

            # Send response (same as before)
            if APP_BASE_URL.startswith((
                'http://localhost', 'http://127.0.0.1'
            )):
                await message.answer(
                    text=f"{auth_message}\n\n{streamlit_link}",
                    reply_markup=self.commands_menu
                )
            else:
                keyboard = types.InlineKeyboardMarkup(
                    inline_keyboard=[[
                        types.InlineKeyboardButton(
                            text="Open Dashboard",
                            url=streamlit_link
                        )
                    ]]
                )
                await message.answer(
                    text=auth_message,
                    reply_markup=keyboard
                )

        except Exception as e:
            self.logger.error(f"Error in auth handler: {e}")
            await message.answer(
                "An error occurred during authentication. "
                "Please try again."
            )

    async def start(self):
        """Start the bot asynchronously"""  # pragma: no mutate
        if not await self.verify_connection():
            raise RuntimeError("Failed to connect to Telegram")

        self.logger.info("Bot starting...")  # pragma: no mutate
        self._polling_task = asyncio.create_task(
            self.dp.start_polling(self.bot)
        )
        self.logger.info("Bot polling started")  # pragma: no mutate

    async def stop(self):
        """Stop the bot gracefully"""  # pragma: no mutate
        if self._polling_task:
            self.logger.info("Stopping bot...")  # pragma: no mutate
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                self.logger.info("Bot polling stopped")  # pragma: no mutate
            except Exception as e:
                self.logger.error(f"Error stopping bot: {e}")
            finally:
                self._polling_task = None


async def create_telegram_wrapper(  # pragma: no mutate
    database: Database, secret_key: str  # pragma: no mutate
) -> TelegramWrapper:  # pragma: no mutate
    wrapper = TelegramWrapper(database, secret_key)  # pragma: no mutate
    if not await wrapper.verify_connection():  # pragma: no mutate
        raise RuntimeError(  # pragma: no mutate
            "Failed to initialize Telegram bot - "  # pragma: no mutate
            "invalid token or connection issues"  # pragma: no mutate
        )  # pragma: no mutate
    return wrapper  # pragma: no mutate

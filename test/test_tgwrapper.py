import unittest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import os
import sys
import jwt
from datetime import datetime, timedelta, timezone
from aiogram import Bot
from aiogram.types import Chat, User as TelegramUser, Message
from contextlib import contextmanager
import shutil
import tempfile
from aiogram import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio

from database import Database
from api_models import UserModel, TrackedProductModel

from pathlib import Path

# Import TelegramWrapper and create_telegram_wrapper after all other dependencies
from tgwrapper import TelegramWrapper, create_telegram_wrapper, PROFILE_PICS_DIR

class TestTelegramWrapper(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        global PROFILE_PICS_DIR
        # Setup test environment with proper token format
        self.patcher = patch.dict('os.environ', {
            'TG_BOT_TOKEN': '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11',
            'APP_BASE_URL': 'http://test.url'
        })
        self.patcher.start()
        
        # Create a temporary directory for profile pictures
        self.temp_dir = tempfile.mkdtemp()
        self.original_profile_pics_dir = PROFILE_PICS_DIR
        # Monkey patch the PROFILE_PICS_DIR to use our temp directory
        PROFILE_PICS_DIR = Path(self.temp_dir)
        
        # Mock database
        self.mock_db = MagicMock(spec=Database)
        self.mock_db.login_user.return_value = True
        self.secret_key = 'test_secret_key_1234567890123456'
        
        # Create wrapper instance with fully mocked bot
        with patch('aiogram.Bot') as mock_bot_class, \
             patch('aiogram.Dispatcher') as mock_dp_class:
            
            # Setup mock bot and dispatcher
            self.mock_bot = AsyncMock()
            self.mock_dp = AsyncMock()
            mock_bot_class.return_value = self.mock_bot
            mock_dp_class.return_value = self.mock_dp
            
            # Create wrapper instance
            self.wrapper = TelegramWrapper(self.mock_db, self.secret_key)

            self.wrapper.APP_BASE_URL = 'http://test.url'
            
            # Ensure the mock bot is used
            self.wrapper.bot = self.mock_bot
            self.wrapper.dp = self.mock_dp

        # Test user data
        self.test_user_id = '123456'
        self.test_user = TelegramUser(
            id=int(self.test_user_id),
            is_bot=False,
            first_name="Test",
            last_name="User",
            username="testuser",
            language_code="en"
        )
        
        # Test chat data
        self.test_chat = Chat(
            id=int(self.test_user_id),
            type="private",
            first_name="Test",
            last_name="User",
            username="testuser"
        )

    def tearDown(self):
        self.patcher.stop()
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)
        # Restore original PROFILE_PICS_DIR
        global PROFILE_PICS_DIR
        PROFILE_PICS_DIR = self.original_profile_pics_dir

    def create_mocked_message(self, text: str, user_id: str = None, chat_id: str = None):
        """Create a properly mocked Message object for testing"""
        if user_id is None:
            user_id = self.test_user_id
        if chat_id is None:
            chat_id = user_id
    
        # Create a MagicMock that will act as our message
        mock_message = MagicMock(
            spec=Message,
            message_id=1,
            date=datetime.now(),
            text=text
        )
    
        # Configure chat attributes
        mock_message.chat = MagicMock(
            spec=Chat,
            id=int(chat_id),
            type="private",
            first_name="Test",
            last_name="User",
            username="testuser"
        )
    
        # Configure user attributes
        mock_message.from_user = MagicMock(
            spec=TelegramUser,
            id=int(user_id),
            is_bot=False,
            first_name="Test",
            last_name="User",
            username="testuser",
            language_code="en"
        )
    
        # Add the answer method as an AsyncMock
        mock_message.answer = AsyncMock()
    
        return mock_message

    async def test_command_menu_setup(self):
        """Test the command menu setup"""
        # Verify the commands_menu is properly configured
        self.assertIsInstance(self.wrapper.commands_menu, types.ReplyKeyboardMarkup)
        self.assertTrue(self.wrapper.commands_menu.persistent)
        self.assertEqual(len(self.wrapper.commands_menu.keyboard), 1)
        self.assertEqual(len(self.wrapper.commands_menu.keyboard[0]), 2)
        self.assertEqual(self.wrapper.commands_menu.keyboard[0][0].text, "/start")
        self.assertEqual(self.wrapper.commands_menu.keyboard[0][1].text, "/auth")

    async def test_verify_connection_success(self):
        """Test successful connection verification"""
        mock_user = MagicMock()
        self.mock_bot.get_me.return_value = mock_user
    
        # Mock the logger
        self.wrapper.logger = MagicMock()
    
        result = await self.wrapper.verify_connection()
    
        self.assertTrue(result)
        self.mock_bot.get_me.assert_called_once()
        self.wrapper.logger.error.assert_not_called()

    async def test_verify_connection_failure(self):
        """Test failed connection verification"""
        test_error = Exception("Connection error")
        self.mock_bot.get_me.side_effect = test_error
    
        with self.assertLogs(self.wrapper.logger, level='ERROR') as cm:
            result = await self.wrapper.verify_connection()
        
        self.assertFalse(result)
        self.assertIn("Connection verification failed", cm.output[0])
        self.assertIn("Connection error", cm.output[0])

    async def test_get_user_info_success(self):
        """Test successful user info retrieval"""
        mock_chat = AsyncMock()
        mock_chat.first_name = "Test"
        mock_chat.last_name = "User"
        mock_chat.username = "testuser"
    
        mock_photo = MagicMock()
        mock_photo.file_id = "test_file_id"
        mock_photos = MagicMock()
        mock_photos.photos = [[mock_photo]]
    
        self.mock_bot.get_chat.return_value = mock_chat
        self.mock_bot.get_user_profile_photos.return_value = mock_photos
    
        result = await self.wrapper.get_user_info(self.test_user_id)
    
        self.assertEqual(result.tid, int(self.test_user_id))
        self.assertEqual(result.name, "Test User")
        self.assertEqual(result.username, "testuser")
        self.assertEqual(result.user_pfp, "test_file_id")
        # Verify None handling for empty fields
        self.assertIsNotNone(result.name)
        self.assertIsNotNone(result.username)

    async def test_get_user_info_with_pfp(self):
        """Test get_user_info with profile picture file_id"""
        mock_chat = AsyncMock()
        mock_chat.first_name = "Test"
        mock_chat.last_name = "User"
        mock_chat.username = "testuser"
    
        mock_photo = MagicMock()
        mock_photo.file_id = "test_file_id_123"
        mock_photos = MagicMock()
        mock_photos.photos = [[mock_photo]]
    
        self.mock_bot.get_chat.return_value = mock_chat
        self.mock_bot.get_user_profile_photos.return_value = mock_photos
    
        result = await self.wrapper.get_user_info(self.test_user_id)
    
        self.assertEqual(result.tid, int(self.test_user_id))
        self.assertEqual(result.name, "Test User")
        self.assertEqual(result.username, "testuser")
        self.assertEqual(result.user_pfp, "test_file_id_123")
        self.mock_bot.get_user_profile_photos.assert_called_once_with(
            int(self.test_user_id), limit=1
        )

    async def test_get_user_info_no_pfp(self):
        """Test get_user_info when user has no profile picture"""
        mock_chat = AsyncMock()
        mock_chat.first_name = "Test"
        mock_chat.last_name = "User"
        mock_chat.username = "testuser"
    
        mock_photos = MagicMock()
        mock_photos.photos = []
    
        self.mock_bot.get_chat.return_value = mock_chat
        self.mock_bot.get_user_profile_photos.return_value = mock_photos
    
        result = await self.wrapper.get_user_info(self.test_user_id)
    
        self.assertEqual(result.tid, int(self.test_user_id))
        self.assertEqual(result.name, "Test User")
        self.assertEqual(result.username, "testuser")
        self.assertIsNone(result.user_pfp)

    async def test_get_user_info_with_empty_names(self):
        """Test get_user_info with empty first or last name"""
        test_cases = [
            {"first": "Test", "last": "", "expected": "Test"},
            {"first": "", "last": "User", "expected": "User"},
            {"first": "", "last": "", "expected": ""}
        ]
    
        for case in test_cases:
            mock_chat = AsyncMock()
            mock_chat.first_name = case["first"]
            mock_chat.last_name = case["last"]
            mock_chat.username = "testuser"
        
            self.mock_bot.get_chat.return_value = mock_chat
            self.mock_bot.get_user_profile_photos.return_value = MagicMock(photos=[])
        
            result = await self.wrapper.get_user_info(self.test_user_id)
        
            self.assertEqual(result.name, case["expected"])

    async def test_get_user_info_failure(self):
        """Test failed user info retrieval"""
        self.mock_bot.get_chat.side_effect = Exception("User not found")
    
        with self.assertLogs(self.wrapper.logger, level='ERROR') as cm:
            result = await self.wrapper.get_user_info(self.test_user_id)
        
        self.assertIsNone(result)
        self.assertIn("Error getting user info", cm.output[0])

    async def test_push_notifications_success(self):
        """Test successful push notifications"""
        test_products = [
            TrackedProductModel(
                id="1",
                url="http://test.com/1",
                sku="TEST1",
                name="Product 1",
                price="100.00",
                seller="Seller 1",
                tracking_price="90.00"
            ),
            TrackedProductModel(
                id="2",
                url="http://test.com/2",
                sku="TEST2",
                name="Product 2",
                price="200.00",
                seller="Seller 2",
                tracking_price=None
            )
        ]

        users_to_products = {self.test_user_id: test_products}

        # Configure the mock to return a successful response
        self.mock_bot.send_message.return_value = MagicMock()

        result = await self.wrapper.push_notifications(users_to_products)

        self.assertTrue(result)
        self.mock_bot.send_message.assert_called_once()

        # Get the call arguments
        call_args = self.mock_bot.send_message.call_args
    
        # Extract the text from the call
        # The message text is the second positional argument
        text = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get('text', '')
    
        # Verify the message contains expected content
        self.assertIn("Product 1", text)
        self.assertIn("100.00 (Tracking: 90.00)", text)
        self.assertIn("Product 2", text)
        self.assertIn("200.00", text)
        self.assertTrue(call_args.kwargs.get('disable_web_page_preview', False))

    async def test_push_notifications_failure(self):
        """Test failed push notifications"""
        test_products = [
            TrackedProductModel(
                id="1",
                url="http://test.com/1",
                sku="TEST1",
                name="Product 1",
                price="100.00",
                seller="Seller 1",
                tracking_price="90.00"
            )
        ]
    
        users_to_products = {self.test_user_id: test_products}
        self.mock_bot.send_message.side_effect = Exception("Send failed")
    
        with self.assertLogs(self.wrapper.logger, level='ERROR') as cm:
            result = await self.wrapper.push_notifications(users_to_products)
        
        self.assertFalse(result)
        self.assertIn("Error sending message", cm.output[0])

    async def test_push_notifications_various_errors(self):
        """Test push_notifications with different error types"""
        test_products = [
            TrackedProductModel(
                id="1",
                url="http://test.com/1",
                sku="TEST1",
                name="Product 1",
                price="100.00",
                seller="Seller 1",
                tracking_price="90.00"
            )
        ]
    
        # Test with different exception types
        for exc in [Exception("Generic error"), 
                    asyncio.TimeoutError("Timeout"),
                    ValueError("Invalid value")]:
            self.mock_bot.send_message.side_effect = exc
        
            with self.assertLogs(self.wrapper.logger, level='ERROR'):
                result = await self.wrapper.push_notifications(
                    {self.test_user_id: test_products}
                )
        
            self.assertFalse(result)

    async def test_handle_start(self):
        """Test /start command handler"""
        message = self.create_mocked_message("/start")
    
        # Mock the logger
        self.wrapper.logger = MagicMock()
    
        await self.wrapper._handle_start(message)
    
        message.answer.assert_called_once()
        args, kwargs = message.answer.call_args
        self.assertIn("Welcome to Price Tracker Bot!", kwargs['text'])
        self.assertIn("/start", kwargs['text'])
        self.assertIn("/auth", kwargs['text'])
        self.assertEqual(kwargs['reply_markup'], self.wrapper.commands_menu)
        self.wrapper.logger.error.assert_not_called()

    async def test_handle_auth_success(self):
        """Test successful /auth command handler with profile picture"""
        # Patch TOKEN_EXPIRATION_MINUTES to avoid None error
        with patch('tgwrapper.TOKEN_EXPIRATION_MINUTES', 30):
            # Rest of your test code remains the same
            test_user_id = "123456"
            test_file_id = "test_file_123"
            test_file_path = "photos/test_path.jpg"

            # Create mock user model
            mock_user = UserModel(
                tid=int(test_user_id),
                name="Test User",
                username="testuser",
                user_pfp=test_file_id
            )

            # Configure mocks
            self.wrapper.get_user_info = AsyncMock(return_value=mock_user)
            self.mock_db.login_user.return_value = True

            # Mock file download
            mock_file = AsyncMock()
            mock_file.file_path = test_file_path
            self.mock_bot.get_file.return_value = mock_file

            # Create test message
            message = self.create_mocked_message("/auth")

            # Patch the module-level constants - use localhost URL to match the condition
            with patch('tgwrapper.APP_BASE_URL', 'http://localhost:8501'), \
                 patch('tgwrapper.PROFILE_PICS_DIR', PROFILE_PICS_DIR):

                await self.wrapper._handle_auth(message)

            # Verify user info retrieval
            self.wrapper.get_user_info.assert_called_once_with(test_user_id)

            # Verify profile picture handling
            self.mock_bot.get_file.assert_called_once_with(test_file_id)
            expected_dest = str(PROFILE_PICS_DIR / f"{test_file_id}.jpg")
            self.mock_bot.download_file.assert_called_once_with(
                test_file_path,
                destination=expected_dest
            )

            # Verify database update
            self.mock_db.login_user.assert_called_once()
            db_call_user = self.mock_db.login_user.call_args[0][0]
            self.assertEqual(db_call_user.tid, int(test_user_id))
            self.assertEqual(db_call_user.user_pfp, test_file_id)

            # Verify response message
            message.answer.assert_called_once()
            call_args = message.answer.call_args
            # Handle both positional and keyword arguments
            if call_args.kwargs:  # If kwargs exist, check there
                response_text = call_args.kwargs.get('text', '')
            else:  # Otherwise check first positional argument
                response_text = call_args.args[0] if call_args.args else ''

            # Check the basic success message
            self.assertIn("Authentication successful", response_text)
            # Verify the URL is included (for localhost case)
            self.assertIn("http://localhost:8501/?token=", response_text)

    async def test_handle_auth_user_info_failure(self):
        """Test /auth command handler when user info retrieval fails"""
        # Mock get_user_info to return None
        self.wrapper.get_user_info = AsyncMock(return_value=None)

        # Mock profile photos to avoid actual calls
        self.mock_bot.get_user_profile_photos.return_value = AsyncMock()
        self.mock_bot.get_user_profile_photos.return_value.photos = []

        message = self.create_mocked_message("/auth")
        await self.wrapper._handle_auth(message)

        # Verify message.answer was called (not bot.send_message)
        message.answer.assert_called_once()
    
        # Get all call arguments (both positional and keyword)
        call_args = message.answer.call_args
        if call_args.kwargs:  # If kwargs exist, check there
            response_text = call_args.kwargs.get('text', '')
        else:  # Otherwise check first positional argument
            response_text = call_args.args[0] if call_args.args else ''
    
        self.assertIn("Could not retrieve", response_text)

    async def test_handle_auth_with_pfp_download(self):
        """Test _handle_auth with successful profile picture download"""
        # Setup test user with profile picture
        mock_user = UserModel(
            tid=int(self.test_user_id),
            name="Test User",
            username="testuser",
            user_pfp="test_file_id_456"
        )
        self.wrapper.get_user_info = AsyncMock(return_value=mock_user)

        # Setup file download
        mock_file = AsyncMock()
        mock_file.file_path = "photos/test_path.jpg"
        self.mock_bot.get_file.return_value = mock_file

        # Create test message
        message = self.create_mocked_message("/auth")

        # Patch PROFILE_PICS_DIR to ensure consistent paths in assertions
        with patch('tgwrapper.PROFILE_PICS_DIR', PROFILE_PICS_DIR):
            await self.wrapper._handle_auth(message)

        # Verify the picture was downloaded
        self.mock_bot.get_file.assert_called_once_with("test_file_id_456")
    
        # Use the same PROFILE_PICS_DIR for assertion
        expected_path = str(PROFILE_PICS_DIR / "test_file_id_456.jpg")
        self.mock_bot.download_file.assert_called_once_with(
            "photos/test_path.jpg",
            destination=expected_path
        )

    async def test_handle_auth_pfp_download_failure(self):
        """Test _handle_auth when profile picture download fails"""
        # Setup test user with profile picture
        mock_user = UserModel(
            tid=int(self.test_user_id),
            name="Test User",
            username="testuser",
            user_pfp="test_file_id_789"
        )
        self.wrapper.get_user_info = AsyncMock(return_value=mock_user)
        
        # Setup file download to fail
        self.mock_bot.get_file.side_effect = Exception("Download failed")
        
        # Create test message
        message = self.create_mocked_message("/auth")
        
        await self.wrapper._handle_auth(message)
        
        # Verify the download was attempted
        self.mock_bot.get_file.assert_called_once_with("test_file_id_789")
        self.mock_bot.download_file.assert_not_called()
        
        # Verify no file was created
        self.assertFalse((PROFILE_PICS_DIR / "test_file_id_789.jpg").exists())
        
        # Verify user was still stored in DB but with None for pfp
        self.mock_db.login_user.assert_called_once()
        call_args = self.mock_db.login_user.call_args[0][0]
        self.assertIsNone(call_args.user_pfp)

    async def test_handle_auth_pfp_directory_creation_failure(self):
        """Test _handle_auth when profile picture directory creation fails"""
        mock_user = UserModel(
            tid=int(self.test_user_id),
            name="Test User",
            username="testuser",
            user_pfp="test_file_id"
        )
        self.wrapper.get_user_info = AsyncMock(return_value=mock_user)
    
        # Mock mkdir to raise an exception
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            mock_mkdir.side_effect = Exception("Directory creation failed")
        
            message = self.create_mocked_message("/auth")
            await self.wrapper._handle_auth(message)
        
            # Verify the error was logged but process continued
            self.mock_db.login_user.assert_called_once()

    async def test_handle_auth_with_existing_pfp(self):
        """Test _handle_auth when profile picture already exists locally"""
        # Setup test user with profile picture
        mock_user = UserModel(
            tid=int(self.test_user_id),
            name="Test User",
            username="testuser",
            user_pfp="existing_file_id"
        )
        self.wrapper.get_user_info = AsyncMock(return_value=mock_user)

        # Create the file in advance
        existing_file = PROFILE_PICS_DIR / "existing_file_id.jpg"
        existing_file.touch()

        # Reset mocks to clear any previous calls
        self.mock_bot.reset_mock()

        # Create test message
        message = self.create_mocked_message("/auth")

        await self.wrapper._handle_auth(message)

        self.mock_bot.get_file.assert_called()
        self.mock_bot.download_file.assert_called()

        # Verify user was stored in DB with original file_id
        self.mock_db.login_user.assert_called_once()
        call_args = self.mock_db.login_user.call_args[0][0]
        self.assertEqual(call_args.user_pfp, "existing_file_id")

    async def test_handle_auth_login_failure(self):
        """Test /auth command handler when login fails"""
        # Create test user with None for profile picture
        mock_user = UserModel(
            tid=int(self.test_user_id),
            name="Test User",
            username="testuser",
            user_pfp=None
        )
    
        # Mock get_user_info to return our test user
        self.wrapper.get_user_info = AsyncMock(return_value=mock_user)
    
        # Mock profile photos to avoid actual calls
        self.mock_bot.get_user_profile_photos.return_value = AsyncMock()
        self.mock_bot.get_user_profile_photos.return_value.photos = []
    
        # Mock database to return failure
        self.mock_db.login_user.return_value = False
    
        message = self.create_mocked_message("/auth")
        await self.wrapper._handle_auth(message)

        # Get all call arguments (both positional and keyword)
        call_args = message.answer.call_args
        if call_args.kwargs:  # If kwargs exist, check there
            response_text = call_args.kwargs.get('text', '')
        else:  # Otherwise check first positional argument
            response_text = call_args.args[0] if call_args.args else ''
    
        self.assertIn("Failed to authenticate", response_text)

    async def test_handle_auth_with_production_url(self):
        """Test /auth command handler with production URL"""
        mock_user = UserModel(
            tid=int(self.test_user_id),
            name="Test User",
            username="testuser",
            user_pfp=None
        )
        self.wrapper.get_user_info = AsyncMock(return_value=mock_user)
        self.mock_db.login_user.return_value = True

        # Patch APP_BASE_URL to a production URL
        with patch('tgwrapper.APP_BASE_URL', 'https://production.url'), \
             patch('tgwrapper.TOKEN_EXPIRATION_MINUTES', 30):
        
            message = self.create_mocked_message("/auth")
            await self.wrapper._handle_auth(message)

            # Verify the response contains an inline keyboard button
            message.answer.assert_called_once()
            call_args = message.answer.call_args
        
            # Get the reply_markup from either kwargs or args
            reply_markup = call_args.kwargs.get('reply_markup') if call_args.kwargs else (
                call_args.args[1] if len(call_args.args) > 1 else None
            )
        
            self.assertIsNotNone(reply_markup, "No reply markup found in response")
            self.assertIsInstance(reply_markup, types.InlineKeyboardMarkup, 
                                "Reply markup is not an InlineKeyboardMarkup")
        
            # Verify the button has the correct URL structure
            inline_keyboard = reply_markup.inline_keyboard
            self.assertEqual(len(inline_keyboard), 1, "Should have one row of buttons")
            self.assertEqual(len(inline_keyboard[0]), 1, "Should have one button in the row")
        
            button = inline_keyboard[0][0]
            self.assertEqual(button.text, "Open Dashboard")
            self.assertTrue(button.url.startswith("https://production.url/?token="))

    async def test_start_stop(self):
        """Test start and stop methods"""
        # Mock verify_connection to return True
        self.wrapper.verify_connection = AsyncMock(return_value=True)
    
        # Create a real task that we can properly cancel
        async def mock_polling():
            while True:
                await asyncio.sleep(0.1)
    
        # Create and immediately cancel the task to simulate behavior
        real_task = asyncio.create_task(mock_polling())
        real_task.cancel()
    
        # Mock the dispatcher's start_polling to return our real task
        self.wrapper.dp.start_polling = AsyncMock(return_value=real_task)
    
        # Test start
        await self.wrapper.start()
    
        # Verify start_polling was called
        self.wrapper.dp.start_polling.assert_called_once_with(self.wrapper.bot)
    
        # Verify the task was stored
        self.assertIsNotNone(self.wrapper._polling_task)
    
        # Test stop
        await self.wrapper.stop()
    
        # Verify the task was cleared
        self.assertIsNone(self.wrapper._polling_task)
    
        # Clean up any pending tasks
        if not real_task.done():
            real_task.cancel()
            try:
                await real_task
            except asyncio.CancelledError:
                pass

    async def test_token_generation_in_auth(self):
        """Test that auth handler generates valid JWT token"""
        # Patch TOKEN_EXPIRATION_MINUTES to avoid None error
        with patch('tgwrapper.TOKEN_EXPIRATION_MINUTES', 30):
            mock_user = UserModel(
                tid=int(self.test_user_id),
                name="Test User",
                username="testuser",
                user_pfp=None
            )

            self.wrapper.get_user_info = AsyncMock(return_value=mock_user)
            self.mock_db.login_user.return_value = True

            message = self.create_mocked_message("/auth")

            # Capture the answer call
            with patch.object(message, 'answer', new_callable=AsyncMock) as mock_answer:
                await self.wrapper._handle_auth(message)
        
                # Verify answer was called once
                mock_answer.assert_called_once()
        
                # Get the call arguments
                call_args = mock_answer.call_args
                # Handle both positional and keyword arguments
                if call_args.kwargs:  # If kwargs exist, check there
                    message_text = call_args.kwargs.get('text', '')
                else:  # Otherwise check first positional argument
                    message_text = call_args.args[0] if call_args.args else ''
        
                # Extract and verify token
                token = message_text.split('token=')[1].split()[0]
                decoded = jwt.decode(token, self.secret_key, algorithms=["HS256"])
                self.assertEqual(decoded['id'], self.test_user_id)
                self.assertIn('exp', decoded)

    async def test_token_generation_with_different_algorithm(self):
        """Test auth handler with different encryption algorithm"""
        with patch('tgwrapper.TOKEN_ENCRYPTION_ALGORITHM', 'HS512'), \
             patch('tgwrapper.TOKEN_EXPIRATION_MINUTES', 30):
        
            mock_user = UserModel(
                tid=int(self.test_user_id),
                name="Test User",
                username="testuser",
                user_pfp=None
            )
            self.wrapper.get_user_info = AsyncMock(return_value=mock_user)
            self.mock_db.login_user.return_value = True

            message = self.create_mocked_message("/auth")
        
            with patch.object(message, 'answer', new_callable=AsyncMock) as mock_answer:
                await self.wrapper._handle_auth(message)
            
                # Verify token was generated with correct algorithm
                call_args = mock_answer.call_args
                message_text = call_args.kwargs.get('text', '') if call_args.kwargs else call_args.args[0]
                token = message_text.split('token=')[1].split()[0]
            
                # This should raise if algorithm doesn't match
                decoded = jwt.decode(token, self.secret_key, algorithms=["HS512"])
                self.assertEqual(decoded['id'], self.test_user_id)

    async def test_create_telegram_wrapper_success(self):
        """Test factory function success case"""
        with patch('tgwrapper.TelegramWrapper') as mock_wrapper_class:
            mock_wrapper = AsyncMock()
            mock_wrapper.verify_connection.return_value = True
            mock_wrapper_class.return_value = mock_wrapper
            
            wrapper = await create_telegram_wrapper(self.mock_db, self.secret_key)
            self.assertIsInstance(wrapper, AsyncMock)

    async def test_create_telegram_wrapper_failure(self):
        """Test factory function failure case"""
        with patch('tgwrapper.TelegramWrapper') as mock_wrapper_class:
            mock_wrapper = AsyncMock()
            mock_wrapper.verify_connection.return_value = False
            mock_wrapper_class.return_value = mock_wrapper
            
            with self.assertRaises(RuntimeError):
                await create_telegram_wrapper(self.mock_db, self.secret_key)


if __name__ == '__main__':
    unittest.main()

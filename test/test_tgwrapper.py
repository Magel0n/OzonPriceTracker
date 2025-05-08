import unittest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import os
import sys
import jwt
from datetime import datetime, timedelta, timezone
from aiogram import Bot
from aiogram.types import Chat, User as TelegramUser, Message
from contextlib import contextmanager

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio

from database import Database
from api_models import UserModel, TrackedProductModel

# Import TelegramWrapper and create_telegram_wrapper after all other dependencies
from tgwrapper import TelegramWrapper, create_telegram_wrapper

class TestTelegramWrapper(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Setup test environment with proper token format
        self.patcher = patch.dict('os.environ', {
            'TG_BOT_TOKEN': '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11',
            'APP_BASE_URL': 'http://test.url'
        })
        self.patcher.start()
        
        # Mock database
        self.mock_db = MagicMock(spec=Database)
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

    async def test_verify_connection_success(self):
        """Test successful connection verification"""
        self.mock_bot.get_me.return_value = True
        result = await self.wrapper.verify_connection()
        self.assertTrue(result)
        self.mock_bot.get_me.assert_called_once()

    async def test_verify_connection_failure(self):
        """Test failed connection verification"""
        self.mock_bot.get_me.side_effect = Exception("Connection error")
        result = await self.wrapper.verify_connection()
        self.assertFalse(result)

    async def test_get_user_info_success(self):
        """Test successful user info retrieval"""
        # Setup mock bot response
        mock_chat = AsyncMock()
        mock_chat.first_name = "Test"
        mock_chat.last_name = "User"
        mock_chat.username = "testuser"
    
        # Mock profile photos response
        mock_photo = MagicMock()
        mock_photo.file_id = "test_file_id"
        mock_photos = MagicMock()
        mock_photos.photos = [[mock_photo]]  # Nested list to match actual structure
    
        self.mock_bot.get_chat.return_value = mock_chat
        self.mock_bot.get_user_profile_photos.return_value = mock_photos
    
        # Call method
        result = await self.wrapper.get_user_info(self.test_user_id)
    
        # Verify results
        self.assertIsInstance(result, UserModel)
        self.assertEqual(result.tid, int(self.test_user_id))
        self.assertEqual(result.name, "Test User")
        self.assertEqual(result.username, "testuser")
        self.assertEqual(result.user_pfp, "test_file_id")
        self.mock_bot.get_chat.assert_called_once_with(self.test_user_id)
        self.mock_bot.get_user_profile_photos.assert_called_once_with(
            int(self.test_user_id), limit=1
        )

    async def test_get_user_info_failure(self):
        """Test failed user info retrieval"""
        self.mock_bot.get_chat.side_effect = Exception("User not found")
        result = await self.wrapper.get_user_info(self.test_user_id)
        self.assertIsNone(result)

    async def test_push_notifications_success(self):
        """Test successful push notifications"""
        # Setup test data
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
        
        # Call method
        result = await self.wrapper.push_notifications(users_to_products)
        
        # Verify results
        self.assertTrue(result)
        self.mock_bot.send_message.assert_called_once()

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
        
        result = await self.wrapper.push_notifications(users_to_products)
        self.assertFalse(result)

    async def test_handle_start(self):
        """Test /start command handler"""
        message = self.create_mocked_message("/start")
        await self.wrapper._handle_start(message)
        message.answer.assert_called_once()
        args, kwargs = message.answer.call_args
        self.assertIn("Welcome to Price Tracker Bot!", kwargs['text'])   

    async def test_handle_auth_success(self):
        """Test successful /auth command handler"""
        mock_user = UserModel(
            tid=int(self.test_user_id),
            name="Test User",
            username="testuser",
            user_pfp=None
        )
    
        self.wrapper.get_user_info = AsyncMock(return_value=mock_user)
        self.mock_db.login_user.return_value = True
    
        message = self.create_mocked_message("/auth")
        await self.wrapper._handle_auth(message)
        self.wrapper.get_user_info.assert_called_once_with(self.test_user_id)
        self.mock_db.login_user.assert_called_once_with(mock_user)
        message.answer.assert_called_once()

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
            call_args = mock_answer.call_args[1]
            message_text = call_args['text']
        
            # Extract and verify token
            token = message_text.split('token=')[1].split()[0]
            decoded = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            self.assertEqual(decoded['id'], self.test_user_id)
            self.assertIn('exp', decoded)

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
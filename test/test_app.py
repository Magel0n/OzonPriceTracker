import pytest # pragma: no mutate
from unittest.mock import patch, MagicMock # pragma: no mutate
from streamlit.testing.v1 import AppTest # pragma: no mutate
import os # pragma: no mutate
import json # pragma: no mutate

# Set test environment variables
os.environ["API_BASE_URL"] = "http://test-api:12345" # pragma: no mutate
os.environ["STATIC_FILES_URL"] = "http://test-static:12345/static" # pragma: no mutate


@pytest.fixture # pragma: no mutate
def mock_auth_success(): # pragma: no mutate
    with patch("app.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"user_tid": "test123"}
        mock_get.return_value = mock_response
        yield


@pytest.fixture # pragma: no mutate
def mock_user_data(): # pragma: no mutate
    with patch("app.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "name": "Test User",
                "username": "testuser",
                "user_pfp": "test_pfp"
            },
            "tracked_products": [
                {
                    "id": "1",
                    "name": "Test Product",
                    "price": "100.00",
                    "seller": "Test Seller",
                    "url": "http://test.com",
                    "tracking_price": "90.00"
                }
            ],
            "history": [
                [1625097600, 100.0],  # [timestamp, price]
                [1625184000, 95.0],
                [1625270400, 90.0]
            ]
        }
        mock_get.return_value = mock_response
        yield


@pytest.fixture # pragma: no mutate
def mock_user_data_several_products(): # pragma: no mutate
    with patch("app.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "name": "Test User",
                "username": "testuser",
                "user_pfp": "test_pfp"
            },
            "tracked_products": [
                {
                    "id": "1",
                    "name": "Product 1",
                    "price": "100.00",
                    "seller": "Test Seller",
                    "url": "http://test.com",
                    "tracking_price": "90.00"
                },
                {
                    "id": "2",
                    "name": "Product 2",
                    "price": "200.00",
                    "seller": "Test Seller",
                    "url": "http://test.com",
                    "tracking_price": "90.00"
                },
                {
                    "id": "3",
                    "name": "Product 3",
                    "price": "300.00",
                    "seller": "Test Seller",
                    "url": "http://test.com",
                    "tracking_price": "270.00"
                }
            ],
            "history": [
                [1625097600, 100.0],  # [timestamp, price]
                [1625184000, 95.0],
                [1625270400, 90.0]
            ]
        }
        mock_get.return_value = mock_response
        yield

@pytest.fixture # pragma: no mutate
def mock_empty_products(): # pragma: no mutate
    with patch("app.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user": {
                "name": "Test User",
                "username": "testuser",
                "user_pfp": "test_pfp"
            },
            "tracked_products": []
        }
        mock_get.return_value = mock_response
        yield


@pytest.fixture # pragma: no mutate
def mock_price_history(): # pragma: no mutate
    with patch("app.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "history": [
                [1625097600, 100.0],
                [1625184000, 95.0]
            ]
        }
        mock_get.return_value = mock_response
        yield


def test_auth_gate(): # pragma: no mutate
    """Test that unauthenticated users see the auth gate"""
    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.run() # pragma: no mutate

    assert at.title[0].value == "🔒 Product Price Tracker"
    assert "Login with Telegram" in at.markdown[1].value
    assert at.session_state["auth_token"] is None


def test_successful_auth(mock_auth_success): # pragma: no mutate
    """Test successful authentication flow"""
    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.query_params = {"token": "test_token"} # pragma: no mutate
    at.run() # pragma: no mutate

    assert at.session_state.auth_token == "test_token"
    assert at.session_state.user_tid == "test123"
    assert "🎨 Menu" in at.sidebar.title[0].value


def test_failed_auth(): # pragma: no mutate
    """Test failed authentication"""
    with patch("app.requests.get") as mock_get: # pragma: no mutate
        mock_response = MagicMock() # pragma: no mutate
        mock_response.status_code = 401 # pragma: no mutate
        mock_get.return_value = mock_response # pragma: no mutate

        at = AppTest.from_file("app/app.py") # pragma: no mutate
        at.query_params = {"token": "invalid_token"} # pragma: no mutate
        at.run() # pragma: no mutate

        assert at.session_state['auth_token'] is None
        assert at.title[0].value == "🔒 Product Price Tracker"


def test_user_profile_display(mock_auth_success, mock_user_data): # pragma: no mutate
    """Test user profile display with mock data"""
    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.query_params = {"token": "test_token"} # pragma: no mutate
    at.run() # pragma: no mutate

    assert "Test User" in at.markdown[1].value
    assert "📊 Your Tracked Products" in at.header[0].value
    assert "Test Product" in at.expander[0].label
    assert "📈 Price History" in at.subheader[0].value


def test_empty_products(mock_auth_success, mock_empty_products): # pragma: no mutate
    """Test display when no products are tracked"""
    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.query_params = {"token": "test_token"} # pragma: no mutate
    at.run() # pragma: no mutate

    assert "You are not tracking any products yet" in at.info[0].value
    assert len(at.expander) == 0  # No expanders for products


def test_add_product_form_by_url(mock_auth_success): # pragma: no mutate
    """Test product form submission by URL"""
    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.query_params = {"token": "test_token"} # pragma: no mutate
    at.run() # pragma: no mutate

    # Navigate to Add Product page
    at.sidebar.radio[0].set_value("➕ Add Product")
    at.run()

    # Fill out the form
    at.radio[0].set_value("Product URL")
    at.text_input[0].set_value("http://test-product.com")
    at.text_input[1].set_value("100.00")

    with patch("app.requests.post") as mock_post, \
            patch("app.requests.put") as mock_put:
        post_response = MagicMock()
        post_response.status_code = 200 # pragma: no mutate
        post_response.json.return_value = {"id": "new123"}
        mock_post.return_value = post_response

        put_response = MagicMock()
        put_response.status_code = 200 # pragma: no mutate
        mock_put.return_value = put_response

        at.button[0].click()
        at.run()

        assert "Product added successfully!" in at.success[0].value


def test_add_product_form_validation(mock_auth_success): # pragma: no mutate
    """Test form validation"""
    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.query_params = {"token": "test_token"} # pragma: no mutate
    at.run() # pragma: no mutate

    at.sidebar.radio[0].set_value("➕ Add Product")
    at.run() # pragma: no mutate

    # Test empty submission
    at.button[0].click()
    at.run() # pragma: no mutate
    assert "Please provide" in at.error[0].value

    # Test invalid price
    at.text_input[0].set_value("https://www.ozon.ru/product/poco-smartfon-c75-8-256-gb-zelenyy-1726508242/?at=28t02plrKTmrm9qRtWN9L4PFgWR99BIR02wDI3qRM6m")
    at.button[0].click()
    at.run() # pragma: no mutate
    assert "price threshold" in at.error[0].value.lower()


def test_product_search(mock_auth_success): # pragma: no mutate
    """Test product search functionality"""
    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.query_params = {"token": "test_token"} # pragma: no mutate
    at.run() # pragma: no mutate

    at.sidebar.radio[0].set_value("🔍 Search Products")
    at.run() # pragma: no mutate

    at.text_input[0].set_value("Headphones")
    at.text_input[1].set_value("AudioTech")
    at.slider[0].set_value((0, 200))

    at.button[0].click()
    at.run() # pragma: no mutate

    assert "Searching for" in at.info[0].value
    assert "Headphones" in at.info[0].value
    assert "AudioTech" in at.info[0].value


def test_product_tracking_actions(mock_auth_success, mock_user_data): # pragma: no mutate
    """Test product tracking actions (update threshold, stop tracking)"""
    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.query_params = {"token": "test_token"} # pragma: no mutate
    at.run() # pragma: no mutate

    # Test threshold update
    with patch("app.requests.put") as mock_put:
        mock_put.return_value.status_code = 200 # pragma: no mutate

        at.text_input[0].set_value("80.00")  # Update threshold input
        at.button[0].click()  # Save button
        at.run() # pragma: no mutate

        assert "Threshold updated" in at.success[0].value
        mock_put.assert_called_once()

    # Test stop tracking
    with patch("app.requests.delete") as mock_delete:
        mock_delete.return_value.status_code = 200 # pragma: no mutate

        at.button[1].click()  # Stop Tracking button
        at.run() # pragma: no mutate

        assert "Product removed" in at.success[0].value
        mock_delete.assert_called_once()

def test_logout(mock_auth_success, mock_user_data): # pragma: no mutate
    """Test logout functionality"""
    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.query_params = {"token": "test_token"} # pragma: no mutate
    at.run() # pragma: no mutate


    with patch("app.requests.get") as mock_get:
        mock_get.return_value.status_code = 200 # pragma: no mutate
        at.sidebar.button[0].click()  # Logout button
        at.query_params = None
        at.run() # pragma: no mutate

        assert at.session_state['auth_token'] is None


def test_api_error_handling(mock_auth_success, mock_user_data): # pragma: no mutate
    """Test API error handling in profile display"""

    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.query_params = {"token": "test_token"} # pragma: no mutate
    at.run() # pragma: no mutate

    with patch("app.requests.get") as mock_get:
        at.sidebar.radio[0].set_value("📦 My Products")
        at.run()
        assert "Failed to load user data" in at.error[0].value


def test_main_page_navigation(mock_auth_success, mock_user_data): # pragma: no mutate
    """Test navigation between pages"""
    at = AppTest.from_file("app/app.py")
    at.query_params = {"token": "test_token"}
    at.run()

    # Verify initial page
    assert "📊 Your Tracked Products" in at.header[0].value

    # Go to Add Product page
    at.sidebar.radio[0].set_value("➕ Add Product")
    at.run()
    assert "Add New Product to Track" in at.subheader[0].value

    # Go to Search page
    at.sidebar.radio[0].set_value("🔍 Search Products")
    at.run()
    assert "Product Search" in at.header[0].value

    # Return to My Products
    at.sidebar.radio[0].set_value("📦 My Products")
    at.run()
    assert "📊 Your Tracked Products" in at.header[0].value


def test_default_profile_picture(mock_auth_success): # pragma: no mutate
    """Test default profile picture when user_pfp is not available"""
    with patch("app.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200 # pragma: no mutate
        mock_response.json.return_value = {
            "user": {
                "name": "Test User",
                "username": "testuser",
                "user_pfp": None  # No profile picture
            },
            "tracked_products": []
        }
        mock_get.return_value = mock_response

        at = AppTest.from_file("app/app.py")
        at.query_params = {"token": "test_token"}
        at.run()

        assert "default.jpg" in at.markdown[1].value

def test_multiple_tracked_products(mock_auth_success, mock_user_data_several_products): # pragma: no mutate
    """Test display of multiple tracked products"""

    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.query_params = {"token": "test_token"} # pragma: no mutate
    at.run() # pragma: no mutate

    assert len(at.expander) == 3  # Should have 3 expanders
    assert "Product 1" in at.expander[0].label
    assert "Product 2" in at.expander[1].label
    assert "Product 3" in at.expander[2].label


def test_environment_variable_fallback(): # pragma: no mutate
    """Test that the app falls back to default URLs when env vars are not set"""
    # Remove environment variables to test fallbacks
    os.environ.pop("API_BASE_URL", None)
    os.environ.pop("STATIC_FILES_URL", None)

    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.run() # pragma: no mutate

    # The app should still run with default values
    assert at.title[0].value == "🔒 Product Price Tracker"


def test_session_state_persistence(mock_auth_success): # pragma: no mutate
    """Test that session state persists across reruns"""
    at = AppTest.from_file("app/app.py") # pragma: no mutate
    at.query_params = {"token": "test_token"} # pragma: no mutate
    at.run() # pragma: no mutate

    # Verify initial state
    assert at.session_state.auth_token == "test_token"

    # Simulate a rerun without query params
    at.query_params = {}
    at.run()

    # Session state should persist
    assert at.session_state.auth_token == "test_token"


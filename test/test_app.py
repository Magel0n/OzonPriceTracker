import pytest
from unittest.mock import patch, MagicMock
import streamlit as st
from app.app import (
    make_api_request,
    check_auth,
    auth_gate,
    display_user_info,
    add_product_form,
    product_search,
    main
)

# Fixtures for common test setups
@pytest.fixture
def mock_requests():
    with patch('app.requests') as mock:
        yield mock

@pytest.fixture
def mock_st():
    with patch('app.st') as mock:
        yield mock

@pytest.fixture
def mock_session_state():
    return {
        "auth_token": "test_token",
        "user_tid": "12345"
    }

@pytest.fixture
def mock_query_params():
    return {"token": "test_token"}

@pytest.fixture
def mock_user_data():
    return {
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
        ]
    }


def test_make_api_request_success(mock_requests):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "value"}
    mock_requests.get.return_value = mock_response

    # Set auth token
    st.session_state.auth_token = "test_token"

    # Test successful GET request
    result, error = make_api_request("/test")
    assert result == {"key": "value"}
    assert error is None
    mock_requests.get.assert_called_once_with(
        "http://localhost:12345/test",
        headers={"Authorization": "Bearer test_token"}
    )


def test_make_api_request_unauthorized(mock_requests):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_requests.get.return_value = mock_response

    # Test unauthorized
    st.session_state.auth_token = "test_token"
    result, error = make_api_request("/test")
    assert result is None
    assert 'Unauthorized' in error


def test_make_api_request_no_auth():
    # Test no authentication
    st.session_state.auth_token = None
    result, error = make_api_request("/test")
    assert result is None
    assert error == "Not authenticated"


def test_check_auth_with_token(mock_requests, mock_query_params):
    # Setup
    st.session_state.auth_token = None
    st.query_params = mock_query_params

    # Mock successful token verification
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"user_tid": "12345"}
    mock_requests.get.return_value = mock_response

    assert check_auth() is True
    assert st.session_state.auth_token == "test_token"
    assert st.session_state.user_tid == "12345"


def test_check_auth_already_authenticated():
    # Setup
    st.session_state.auth_token = "existing_token"
    st.session_state.user_tid = "12345"

    assert check_auth() is True


def test_check_auth_failed_verification(mock_requests, mock_query_params):
    # Setup
    st.session_state.auth_token = None
    st.query_params = mock_query_params

    # Mock failed token verification
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_requests.get.return_value = mock_response

    assert check_auth() is False
    assert st.session_state.auth_token is None


def test_auth_gate(mock_st):
    auth_gate()

    mock_st.title.assert_called_once_with("🔒 Product Price Tracker")
    mock_st.markdown.assert_called_once()
    mock_st.stop.assert_called_once()


def test_display_user_info(mock_requests, mock_st, mock_user_data):
    # Setup
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_user_data
    mock_requests.get.return_value = mock_response

    # Mock history response
    mock_history_response = MagicMock()
    mock_history_response.status_code = 200
    mock_history_response.json.return_value = {
        "history": [
            [1625097600, 100.0],
            [1625184000, 95.0]
        ]
    }
    mock_requests.get.side_effect = [mock_response, mock_history_response]

    display_user_info()

    # Verify profile display
    mock_st.markdown.assert_called()
    assert "Test User" in mock_st.markdown.call_args_list[0][0][0]

    # Verify product display
    mock_st.header.assert_called_with("📊 Your Tracked Products")
    mock_st.expander.assert_called()

    # Verify price history
    mock_st.subheader.assert_called_with("📈 Price History")
    mock_st.plotly_chart.assert_called_once()


def test_add_product_form_by_url(mock_requests, mock_st):
    # Setup form submission
    mock_st.radio.return_value = "Product URL"
    mock_st.text_input.side_effect = ["http://test.com", "90.00"]
    mock_st.form_submit_button.return_value = True

    # Mock API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "1"}
    mock_requests.post.return_value = mock_response
    mock_requests.put.return_value = mock_response

    add_product_form("12345")

    # Verify API calls
    mock_requests.post.assert_called_once_with(
        "http://localhost:12345/tracking",
        json={
            "user_tid": "12345",
            "product_url": "http://test.com",
            "product_sku": None
        },
        headers={"Authorization": "Bearer None"}
    )

    mock_st.success.assert_called_with("Product added successfully!")


def test_product_search(mock_st):
    # Setup search inputs
    mock_st.text_input.side_effect = ["Headphones", "AudioTech"]
    mock_st.slider.return_value = (0.0, 200.0)
    mock_st.button.return_value = True

    product_search("12345")

    # Verify search results display
    mock_st.header.assert_called_with("🔍 Product Search")
    mock_st.container.assert_called()
    mock_st.button.assert_called_with(
        "🔎 Search Products",
        use_container_width=True,
        type="primary"
    )


def test_main_authenticated(mock_st, mock_requests):
    # Setup authentication
    mock_st.query_params.to_dict.return_value = {"token": "test_token"}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"user_tid": "12345"}
    mock_requests.get.return_value = mock_response

    # Setup page navigation
    mock_st.sidebar.radio.return_value = "📦 My Products"

    with patch('app.display_user_info') as mock_display:
        main()

        # Verify authentication
        mock_st.set_page_config.assert_called_once()

        # Verify page navigation
        mock_st.sidebar.title.assert_called_with("🎨 Menu")
        mock_display.assert_called_once()
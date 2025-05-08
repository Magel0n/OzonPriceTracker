import pytest
from unittest.mock import patch, MagicMock

from datetime import datetime, timedelta, timezone

import jwt
import requests

from fastapi.testclient import TestClient
from fastapi import HTTPException

from api_models import (
    StatusResponse,
    CreateTrackingModel,
    TrackedProductModel,
    UserModel,
    TrackingModel,
    UserResponse,
    VerifyTokenResponse,
    ProductHistoryResponse,
    SearchProductsRequest,
    SearchProductsResponse
)

from api import app

USER_ID = 12
SECRET_KEY = "its23ZCpqZjtNg6g3duzlFqwWiWMMUuk"
TOKEN_ENCRYPTION_ALGORITHM = "HS256"

client = TestClient(app)

def make_api_request(endpoint: str, token: str, method: str = "GET",
                     data: dict | None = None):
    if not st.session_state.auth_token:
        return None, "Not authenticated"

    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}
    
    if method.upper() == "GET":
        response = client.get(url, headers=headers)
    elif method.upper() == "POST":
        response = client.post(url, json=data, headers=headers)
    elif method.upper() == "PUT":
        response = client.put(url, json=data, headers=headers)
    elif method.upper() == "DELETE":
        response = client.delete(url, json=data, headers=headers)
    else:
        return None, "Invalid HTTP method"

    return response
    
def make_token(key, user_id=USER_ID):
    expires = datetime.now(timezone.utc) + timedelta(minutes=1)
    token_data = {"id": user_id, "exp": expires}
    token = jwt.encode(token_data, SECRET_KEY, algorithm=TOKEN_ENCRYPTION_ALGORITHM)
    return token

@pytest.fixture
def mock_app():
    mockd = MagicMock()
    mocks = MagicMock()
    mockt = MagicMock()
    app.state.database = mockd
    app.state.tgwrapper = mockt
    app.state.scraper = mocks
    app.state.secret_key = SECRET_KEY
    return mockd, mocks, mockt

@pytest.fixture
def mock_user():
    return UserModel(
        tid = 12,
        name = "test_namw",
        username = "test_username",
        user_pfp = "test_pfp"
    )

@pytest.fixture
def mock_product():
    return TrackedProductModel(
        id = 11,
        url = "test_url",
        sku = "test_sku",
        name = "test_name",
        price = "100.0",
        seller = "test_seller",
        tracking_price = "test_tracking_price"
    )

@pytest.fixture
def mock_product_2():
    return TrackedProductModel(
        id = 21,
        url = "test_url_2",
        sku = "test_sku_2",
        name = "test_name_2",
        price = "test_price_2",
        seller = "test_seller_2",
        tracking_price = "test_tracking_price_2"
    )

@pytest.fixture
def mock_many_products():
    return [TrackedProductModel(
        id = 11,
        url = "test_url",
        sku = "test_sku",
        name = "test_name",
        price = "200",
        seller = "test_seller",
        tracking_price = "test_tracking_price"
    ), TrackedProductModel(
        id = 13,
        url = "test_url",
        sku = "test_sku",
        name = "test_name",
        price = "90",
        seller = "test_seller",
        tracking_price = "test_tracking_price"
    ), TrackedProductModel(
        id = 14,
        url = "test_url",
        sku = "test_sku",
        name = "test_name",
        price = "1010",
        seller = "test_seller",
        tracking_price = "test_tracking_price"
    ), TrackedProductModel(
        id = 15,
        url = "test_url",
        sku = "test_sku",
        name = "invalid_name",
        price = "200",
        seller = "test_seller",
        tracking_price = "test_tracking_price"
    ),  TrackedProductModel(
        id = 16,
        url = "test_url",
        sku = "test_sku",
        name = "test_name",
        price = "200.10",
        seller = "invalid_seller",
        tracking_price = "test_tracking_price"
    ), TrackedProductModel(
        id = 17,
        url = "correct_url",
        sku = "test_sku",
        name = "test_name",
        price = "200.11",
        seller = "test_seller",
        tracking_price = "test_tracking_price"
    )]

@pytest.fixture
def mock_tracking():
    return TrackingModel(
        user_tid = 12,
        product_id = 11,
        new_price = "1234"
    )

@pytest.fixture
def mock_create_tracking():
    return CreateTrackingModel(
        user_tid = 12,
        product_url = "test_url",
        product_sku = "test_sku"
    )

def test_verify_token(mock_app):
    # Given
    token = make_token(app.state.secret_key)
    
    # When
    response = client.get("/verify-token", headers={"Authorization": f"Bearer {token}"})
    
    # Then
    assert response.json()["user_tid"] == USER_ID

def test_verify_token_invalid_scheme(mock_app):
    # Given
    token = make_token(app.state.secret_key)
    
    # Then
    response = client.get("/verify-token", headers={"Authorization": f"Basic dGVzdDoxMjPCow=="})
    assert response.status_code == 403 and response.json()["detail"] == "Invalid authentication credentials"


def test_verify_token_no_id(mock_app):
    # Given
    expires = datetime.now(timezone.utc) + timedelta(minutes=1)
    token_data = {"exp": expires}
    token = jwt.encode(token_data, SECRET_KEY, algorithm=TOKEN_ENCRYPTION_ALGORITHM)
    
    # Then
    response = client.get("/verify-token", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401 and response.json()["detail"] == "Could not validate credentials"

def test_verify_token_gibberish(mock_app):
    # Given
    token = "Gibberish"
    
    # Then
    response = client.get("/verify-token", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401 and response.json()["detail"] == "Could not validate credentials"

def test_logout(mock_app):
    # Given
    token = make_token(app.state.secret_key)
    token2 = make_token(app.state.secret_key, user_id="432")
    tokengibberish = "Gibberish"
    
    expires = datetime.now(timezone.utc) + timedelta(minutes=1)
    token_data = {"exp": expires}
    tokennouser = jwt.encode(token_data, SECRET_KEY, algorithm=TOKEN_ENCRYPTION_ALGORITHM)
    
    # Then
    response = client.get("/logout", headers={"Authorization": f"Bearer {tokengibberish}"})
    assert response.status_code == 401 and response.json()["detail"] == "Could not validate credentials"
    response = client.get("/logout", headers={"Authorization": f"Bearer {tokennouser}"})
    assert response.status_code == 401 and response.json()["detail"] == "Could not validate credentials"
    response = client.get("/logout", headers={"Authorization": f"Basic dGVzdDoxMjPCow=="})
    assert response.status_code == 403 and response.json()["detail"] == "Invalid authentication credentials"
    
    response = client.get("/verify-token", headers={"Authorization": f"Bearer {token2}"})
    assert response.status_code == 200
    response = client.get("/logout", headers={"Authorization": f"Bearer {token2}"})
    assert response.status_code == 200
    
    
    response = client.get("/verify-token", headers={"Authorization": f"Bearer {token2}"})
    assert response.status_code == 401 and response.json()["detail"] == "Could not validate credentials"
    response = client.get("/logout", headers={"Authorization": f"Bearer {token2}"})
    assert response.status_code == 401 and response.json()["detail"] == "Could not validate credentials"
    
    response = client.get("/verify-token", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_get_user(mock_app, mock_user, mock_product):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_user.return_value = mock_user
    mock_app[0].get_tracked_products.return_value = [mock_product]
    
    # When
    response = client.get("/profile", headers={"Authorization": f"Bearer {token}"})
    
    # Then
    mock_app[0].get_user.assert_called_once_with(mock_user.tid)
    mock_app[0].get_tracked_products.assert_called_once_with(mock_user.tid)
    assert response.json() == {
        "user": mock_user.__dict__,
        "tracked_products": [mock_product.__dict__] 
    }

def test_get_user_error(mock_app, mock_user, mock_product):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_user.return_value = None
    
    # When
    response = client.get("/profile", headers={"Authorization": f"Bearer {token}"})
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "Could not find user data"

@patch("time.time", return_value="12345")
def test_add_tracking(
    mock_time,
    mock_app,
    mock_product,
    mock_product_2,
    mock_create_tracking,
    mock_tracking
):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_tracked_products.return_value = [mock_product_2]
    mock_app[0].add_product.return_value = 54321
    mock_app[0].add_tracking.return_value = True
    mock_app[1].scrape_product.return_value = mock_product
    
    # When
    response = client.post(
        "/tracking",
        json=mock_create_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then

    assert response.json() == \
        (lambda d: d.update({"id": 54321}) or d)(mock_product.__dict__)

    mock_app[0].get_tracked_products.assert_called_once_with(USER_ID)
    mock_app[0].add_product.assert_called_once_with(mock_product)
    mock_app[0].add_tracking.assert_called_once_with(TrackingModel(
        user_tid=USER_ID,
        product_id=54321,
        new_price=str(float(mock_product.price) * 0.9)
    ))
    mock_app[0].add_to_price_history.assert_called_once_with(
        [54321],
        12345
    )
    mock_app[1].scrape_product.assert_called_once_with(
        mock_create_tracking.product_sku,
        mock_create_tracking.product_url,
    )

@patch("time.time", return_value="12345")
def test_add_tracking_incorrect_user(
    mock_time,
    mock_app,
    mock_product,
    mock_product_2,
    mock_create_tracking,
    mock_tracking
):
    # Given
    token = make_token(app.state.secret_key, "213")
    mock_app[0].get_tracked_products.return_value = [mock_product_2]
    mock_app[0].add_product.return_value = 54321
    mock_app[0].add_tracking.return_value = True
    mock_app[1].scrape_product.return_value = mock_product
    
    # When
    response = client.post(
        "/tracking",
        json=mock_create_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 403 and response.json()["detail"] == "Cannot modify other user data"

@patch("time.time", return_value="12345")
def test_add_tracking_incorrect_product(
    mock_time,
    mock_app,
    mock_product,
    mock_product_2,
    mock_create_tracking,
    mock_tracking
):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_tracked_products.return_value = [mock_product]
    mock_app[0].add_product.return_value = 54321
    mock_app[0].add_tracking.return_value = True
    mock_app[1].scrape_product.return_value = mock_product
    
    # When
    response = client.post(
        "/tracking",
        json=mock_create_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "You are already tracking this product!"


@patch("time.time", return_value="12345")
def test_add_tracking_incorrect_scraper(
    mock_time,
    mock_app,
    mock_product,
    mock_product_2,
    mock_create_tracking,
    mock_tracking
):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_tracked_products.return_value = [mock_product_2]
    mock_app[0].add_product.return_value = 54321
    mock_app[0].add_tracking.return_value = True
    mock_app[1].scrape_product.return_value = None
    
    # When
    response = client.post(
        "/tracking",
        json=mock_create_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "Product could not be scraped"

@patch("time.time", return_value="12345")
def test_add_tracking_incorrect_adding(
    mock_time,
    mock_app,
    mock_product,
    mock_product_2,
    mock_create_tracking,
    mock_tracking
):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_tracked_products.return_value = [mock_product_2]
    mock_app[0].add_product.return_value = None
    mock_app[0].add_tracking.return_value = True
    mock_app[1].scrape_product.return_value = mock_product
    
    # When
    response = client.post(
        "/tracking",
        json=mock_create_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "Database could not be inserted into"

@patch("time.time", return_value="12345")
def test_add_tracking_incorrect_tracking(
    mock_time,
    mock_app,
    mock_product,
    mock_product_2,
    mock_create_tracking,
    mock_tracking
):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_tracked_products.return_value = [mock_product_2]
    mock_app[0].add_product.return_value = 54321
    mock_app[0].add_tracking.return_value = False
    mock_app[1].scrape_product.return_value = mock_product
    
    # When
    response = client.post(
        "/tracking",
        json=mock_create_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "Error while adding tracking to database"

def test_update_threshold(mock_app, mock_tracking):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].add_tracking.return_value = True
    
    # When
    response = client.put(
        "/tracking",
        json=mock_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    mock_app[0].add_tracking.assert_called_once_with(mock_tracking)
    assert response.json() == {"success":True, "message":""}

def test_update_threshold_incorrect_user(mock_app, mock_tracking):
    # Given
    token = make_token(app.state.secret_key, "321")
    mock_app[0].add_tracking.return_value = True
    
    # When
    response = client.put(
        "/tracking",
        json=mock_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "Unauthorized to perform actions on other users"


def test_update_threshold_incorrect_adding(mock_app, mock_tracking):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].add_tracking.return_value = False
    
    # When
    response = client.put(
        "/tracking",
        json=mock_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "Error while adding tracking to database"


def test_delete_tracking(mock_app, mock_tracking):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].delete_tracking.return_value = True
    
    # When
    response = client.request(
        "DELETE",
        "/tracking",
        json=mock_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    mock_app[0].delete_tracking.assert_called_once_with(mock_tracking)
    assert response.json() == {"success":True, "message":""}

def test_delete_tracking_invalid_user(mock_app, mock_tracking):
    # Given
    token = make_token(app.state.secret_key, "321")
    mock_app[0].delete_tracking.return_value = True
    
    # When
    response = client.request(
        "DELETE",
        "/tracking",
        json=mock_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "Unauthorized to perform actions on other users"

def test_delete_tracking_invalid_deletion(mock_app, mock_tracking):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].delete_tracking.return_value = False
    
    # When
    response = client.request(
        "DELETE",
        "/tracking",
        json=mock_tracking.__dict__,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "Error while deleting tracking from database"

def test_get_product_history(mock_app, mock_product):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_price_history.return_value = [(mock_product.id, mock_product.price)]
    
    # When
    response = client.get(
        f"/product/{mock_product.id}/history",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    mock_app[0].get_price_history.assert_called_once_with(mock_product.id)
    assert response.json() == {"history": [[mock_product.id, mock_product.price]]}

def test_get_product_history_error(mock_app, mock_product):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_price_history.return_value = None
    
    # When
    response = client.get(
        f"/product/{mock_product.id}/history",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "Could not get price history from database"

def test_search(mock_app, mock_product, mock_many_products):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_tracked_products.return_value = [mock_product]
    mock_app[0].get_products.return_value = mock_many_products
    
    # When
    response = client.post(
        f"/search",
        json={
            "min_price": 100.20,
            "max_price": 1000.20,
            "query": "Test",
            "seller": "Test",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    mock_app[0].get_tracked_products.assert_called_once_with(USER_ID)
    mock_app[0].get_products.assert_called_once_with()
    assert len(response.json()["products"]) == 1
    assert response.json()["products"][0]["url"] == "correct_url"
    
def test_search_error_get_tracked(mock_app, mock_product, mock_many_products):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_tracked_products.return_value = None
    mock_app[0].get_products.return_value = mock_many_products
    
    # When
    response = client.post(
        f"/search",
        json={
            "min_price": 100.20,
            "max_price": 1000.20,
            "query": "Test",
            "seller": "Test",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "Could not get my products from database"

    
def test_search_error_get_all(mock_app, mock_product, mock_many_products):
    # Given
    token = make_token(app.state.secret_key)
    mock_app[0].get_tracked_products.return_value = [mock_product]
    mock_app[0].get_products.return_value = None
    
    # When
    response = client.post(
        f"/search",
        json={
            "min_price": 100.20,
            "max_price": 1000.20,
            "query": "Test",
            "seller": "Test",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Then
    assert response.status_code == 500 and response.json()["detail"] == "Could not get products from database"

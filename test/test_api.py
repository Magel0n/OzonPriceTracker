import pytest
from unittest.mock import patch, MagicMock

from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api_models import *
from api import app

SECRET_KEY = "its23ZCpqZjtNg6g3duzlFqwWiWMMUuk"
TOKEN_ENCRYPTION_ALGORITHM = "HS256"
USER_ID = 12

client = TestClient(app)

def make_api_request(endpoint: str, method: str = "GET",
                     data: Optional[dict] = None):
    if not st.session_state.auth_token:
        return None, "Not authenticated"

    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {st.session_state.auth_token}"}
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method.upper() == "DELETE":
            response = requests.delete(url, json=data, headers=headers)
        else:
            return None, "Invalid HTTP method"

        if response.status_code == 200:
            return response.json(), None
        elif response.status_code == 401:  # Unauthorized
            return (None,
                    'Unauthorized - please login'
                    + ' via Telegram bot {TG_BOT_LINK}')
        else:
            error_data = response.json()
            return None, error_data.get("message", "Unknown error occurred")
    except requests.exceptions.RequestException as e:
        return None, f"Connection error: {str(e)}"

def test_validate_token_success(mock_blacklist):
    # Given
    expires = datetime.now(timezone.utc) + timedelta(minutes=1)
    token_data = {"id": USER_ID, "exp": expires}
    credentials = jwt.encode(token_data, SECRET_KEY, algorithm=TOKEN_ENCRYPTION_ALGORITHM)
    token = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=credentials
    )
    
    # When
    response = validate_token(token)
    
    # Then
    assert response == USER_ID
    
def test_verify_token_blacklisted(mock_blacklist):
    global blacklist
    # Given
    expires = datetime.now(timezone.utc) + timedelta(minutes=1)
    token_data = {"id": USER_ID, "exp": expires}
    credentials = jwt.encode(token_data, SECRET_KEY, algorithm=TOKEN_ENCRYPTION_ALGORITHM)
    blacklist.add(credentials)
    token = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=credentials
    )
    
    # When
    response = await validate_token(token)
    
    # Then
    assert response == USER_ID

def test_validate_token_success(mock_blacklist):
    # Given
    expires = datetime.now(timezone.utc) + timedelta(minutes=1)
    token_data = {"id": USER_ID, "exp": expires}
    credentials = jwt.encode(token_data, SECRET_KEY, algorithm=TOKEN_ENCRYPTION_ALGORITHM)
    token = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=credentials
    )
    
    # When
    response = await validate_token(token)
    
    # Then
    assert response == USER_ID
    

def test_validate_token_no_user_id(mock_blacklist):
    # Given
    expires = datetime.now(timezone.utc) + timedelta(minutes=1)
    token_data = {"exp": expires}
    credentials = jwt.encode(token_data, SECRET_KEY, algorithm=TOKEN_ENCRYPTION_ALGORITHM)
    token = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=credentials
    )
    
    # When
    with pytest.raises(HTTPException):
        await validate_token(token)
    

def test_validate_token_gibberish(mock_blacklist):
    # Given
    credentials = "todysgofjdsxuof832y 9r"
    token = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=credentials
    )
    
    # When
    with pytest.raises(HTTPException):
        await validate_token(token)
    

def test_validate_token_not_bearer(mock_blacklist):
    # Given
    expires = datetime.now(timezone.utc) + timedelta(minutes=1)
    token_data = {"exp": expires}
    credentials = jwt.encode(token_data, SECRET_KEY, algorithm=TOKEN_ENCRYPTION_ALGORITHM)
    token = HTTPAuthorizationCredentials(
        scheme="something else",
        credentials=credentials
    )
    
    # When
    with pytest.raises(HTTPException):
        await validate_token(token)
    

def test_validate_token_expired(mock_blacklist):
    # Given
    expires = datetime.now(timezone.utc) - timedelta(minutes=1)
    token_data = {"exp": expires}
    credentials = jwt.encode(token_data, SECRET_KEY, algorithm=TOKEN_ENCRYPTION_ALGORITHM)
    token = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=credentials
    )
    
    # When
    with pytest.raises(HTTPException):
        await validate_token(token)
    

def test_validate_token_token_success(mock_blacklist):
    # Given
    expires = datetime.now(timezone.utc) + timedelta(minutes=1)
    token_data = {"id": USER_ID, "exp": expires}
    credentials = jwt.encode(token_data, SECRET_KEY, algorithm=TOKEN_ENCRYPTION_ALGORITHM)
    token = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=credentials
    )
    
    # When
    response = await validate_token(token)
    
    # Then
    assert response == credentials
    

def test_verify_token():
    # When
    response = await verify_token(USER_ID)
    
    # Then
    assert response == VerifyTokenResponse(user_tid=USER_ID)
    

def test_logout():
    global blacklist
    
    # When
    response = await logout(USER_ID)
    
    # Then
    assert USER_ID in blacklist
    assert response == StatusResponse(success=True, message="")
    

"""def test_get_user():
    # Given
    
    
    # When
    response = get_user(USER_ID)
    
    # Then
    assert USER_ID in blacklist
    assert response == StatusResponse(success=True, message="")
    """

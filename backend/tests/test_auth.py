import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    random_str = str(uuid.uuid4())[:8]
    payload = {
        "email": f"alice_{random_str}@example.com",
        "password": "Password123!",
        "full_name": "Alice Tester",
        "organization_name": "Acme Corp",
    }
    response = await client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == payload["email"]
    assert data["organization"]["name"] == "Acme Corp"
    assert data["organization"]["role"] == "admin"


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient):
    random_str = str(uuid.uuid4())[:8]
    payload = {
        "email": f"dup_{random_str}@example.com",
        "password": "Password123!",
        "full_name": "Duplicate User",
    }
    # First signup
    res1 = await client.post("/api/v1/auth/signup", json=payload)
    assert res1.status_code == 201

    # Second signup with same email
    res2 = await client.post("/api/v1/auth/signup", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    random_str = str(uuid.uuid4())[:8]
    email = f"bob_{random_str}@example.com"
    password = "SecurePassword123!"

    # Signup
    await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "full_name": "Bob Builder"},
    )

    # Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == email


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    random_str = str(uuid.uuid4())[:8]
    email = f"charlie_{random_str}@example.com"

    await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "CorrectPassword123!"},
    )

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword!"},
    )
    assert login_res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    random_str = str(uuid.uuid4())[:8]
    email = f"dave_{random_str}@example.com"
    signup_res = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "Password123!", "full_name": "Dave"},
    )
    refresh_token = signup_res.json()["refresh_token"]

    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    random_str = str(uuid.uuid4())[:8]
    email = f"eve_{random_str}@example.com"
    signup_res = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "Password123!", "full_name": "Eve"},
    )
    token = signup_res.json()["access_token"]

    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == email
    assert me_data["active_organization"]["role"] == "admin"

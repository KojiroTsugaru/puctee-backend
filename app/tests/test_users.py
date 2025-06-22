import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_password_hash
from app.models import User
from typing import AsyncGenerator

@pytest.mark.asyncio
async def test_create_user(client: AsyncGenerator[AsyncClient, None]):
    async for c in client:
        response = await c.post(
            "/api/v1/users/",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "testpassword"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"
        assert "id" in data

@pytest.mark.asyncio
async def test_create_user_duplicate_username(client: AsyncGenerator[AsyncClient, None]):
    async for c in client:
        # 最初のユーザーを作成
        await c.post(
            "/api/v1/users/",
            json={
                "email": "test1@example.com",
                "username": "testuser",
                "password": "testpassword"
            }
        )
        
        # 同じユーザー名で再度作成を試みる
        response = await c.post(
            "/api/v1/users/",
            json={
                "email": "test2@example.com",
                "username": "testuser",
                "password": "testpassword"
            }
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login(client: AsyncGenerator[AsyncClient, None]):
    async for c in client:
        # ユーザーを作成
        await c.post(
            "/api/v1/users/",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "testpassword"
            }
        )
        
        # ログイン
        response = await c.post(
            "/api/v1/token",
            data={
                "username": "testuser",
                "password": "testpassword"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncGenerator[AsyncClient, None]):
    async for c in client:
        # ユーザーを作成
        await c.post(
            "/api/v1/users/",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "testpassword"
            }
        )
        
        # 間違ったパスワードでログイン
        response = await c.post(
            "/api/v1/token",
            data={
                "username": "testuser",
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

@pytest.mark.asyncio
async def test_read_users_me(client: AsyncGenerator[AsyncClient, None]):
    async for c in client:
        # ユーザーを作成
        await c.post(
            "/api/v1/users/",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "testpassword"
            }
        )
        
        # ログインしてトークンを取得
        login_response = await c.post(
            "/api/v1/token",
            data={
                "username": "testuser",
                "password": "testpassword"
            }
        )
        token = login_response.json()["access_token"]
        
        # ユーザー情報を取得
        response = await c.get(
            "/api/v1/users/me/",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser" 
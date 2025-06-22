import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_create_item(client: AsyncClient):
    # ユーザーを作成してログイン
    await client.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword"
        }
    )
    login_response = await client.post(
        "/api/v1/token",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # アイテムを作成
    response = await client.post(
        "/api/v1/items/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Item",
            "description": "This is a test item",
            "price": 1000
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Item"
    assert data["description"] == "This is a test item"
    assert data["price"] == 1000
    assert "id" in data
    assert "owner_id" in data

@pytest.mark.asyncio
async def test_read_items(client: AsyncClient):
    # ユーザーを作成してログイン
    await client.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword"
        }
    )
    login_response = await client.post(
        "/api/v1/token",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # アイテムを作成
    await client.post(
        "/api/v1/items/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Item 1",
            "description": "This is test item 1",
            "price": 1000
        }
    )
    await client.post(
        "/api/v1/items/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Item 2",
            "description": "This is test item 2",
            "price": 2000
        }
    )
    
    # アイテム一覧を取得
    response = await client.get(
        "/api/v1/items/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Test Item 1"
    assert data[1]["title"] == "Test Item 2"

@pytest.mark.asyncio
async def test_read_item(client: AsyncClient):
    # ユーザーを作成してログイン
    await client.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword"
        }
    )
    login_response = await client.post(
        "/api/v1/token",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # アイテムを作成
    create_response = await client.post(
        "/api/v1/items/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Item",
            "description": "This is a test item",
            "price": 1000
        }
    )
    item_id = create_response.json()["id"]
    
    # アイテムを取得
    response = await client.get(
        f"/api/v1/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Item"
    assert data["description"] == "This is a test item"
    assert data["price"] == 1000

@pytest.mark.asyncio
async def test_update_item(client: AsyncClient):
    # ユーザーを作成してログイン
    await client.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword"
        }
    )
    login_response = await client.post(
        "/api/v1/token",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # アイテムを作成
    create_response = await client.post(
        "/api/v1/items/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Item",
            "description": "This is a test item",
            "price": 1000
        }
    )
    item_id = create_response.json()["id"]
    
    # アイテムを更新
    response = await client.put(
        f"/api/v1/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Updated Item",
            "description": "This is an updated item",
            "price": 2000
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Item"
    assert data["description"] == "This is an updated item"
    assert data["price"] == 2000

@pytest.mark.asyncio
async def test_delete_item(client: AsyncClient):
    # ユーザーを作成してログイン
    await client.post(
        "/api/v1/users/",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword"
        }
    )
    login_response = await client.post(
        "/api/v1/token",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    token = login_response.json()["access_token"]
    
    # アイテムを作成
    create_response = await client.post(
        "/api/v1/items/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Item",
            "description": "This is a test item",
            "price": 1000
        }
    )
    item_id = create_response.json()["id"]
    
    # アイテムを削除
    response = await client.delete(
        f"/api/v1/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    
    # 削除されたアイテムを取得しようとする
    get_response = await client.get(
        f"/api/v1/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 404 
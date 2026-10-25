"""Comprehensive tests for items CRUD operations."""
from fastapi import status


def test_list_all_items(client):
    """Test retrieving list of items."""
    response = client.get("/items")
    assert response.status_code == status.HTTP_200_OK
    items = response.json()
    assert isinstance(items, list)
    assert len(items) == 3


def test_list_items_pagination(client):
    """Test pagination parameters skip and limit."""
    response = client.get("/items?skip=1&limit=1")
    assert response.status_code == status.HTTP_200_OK
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == 2


def test_list_items_search(client):
    """Test filtering items by search query."""
    response = client.get("/items?search=keyboard")
    assert response.status_code == status.HTTP_200_OK
    items = response.json()
    assert len(items) == 1
    assert items[0]["title"] == "Mechanical Keyboard"


def test_get_item_by_id_success(client):
    """Test fetching an existing item by its ID."""
    response = client.get("/items/1")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == 1
    assert data["title"] == "Laptop"
    assert data["price"] == 1299.99
    assert data["in_stock"] is True


def test_get_item_by_id_not_found(client):
    """Test getting an item that does not exist returns 404."""
    response = client.get("/items/999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "detail" in data
    assert "Item with ID 999 not found" in data["detail"]


def test_create_item_success(client):
    """Test successfully creating a new item."""
    new_item = {
        "title": "USB-C Hub",
        "description": "Multiport adapter with 4K HDMI",
        "price": 45.50,
        "in_stock": True,
    }
    response = client.post("/items", json=new_item)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id"] == 4
    assert data["title"] == "USB-C Hub"
    assert data["price"] == 45.50
    assert data["in_stock"] is True

    # Verify it can be retrieved
    get_res = client.get("/items/4")
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["title"] == "USB-C Hub"


def test_create_item_validation_error(client):
    """Test creating an item with invalid data fails validation (422)."""
    invalid_item = {
        "title": "",  # Min length is 1
        "price": -10.0,  # Must be > 0
    }
    response = client.post("/items", json=invalid_item)
    assert response.status_code == 422


def test_update_item_success(client):
    """Test updating existing item fields."""
    update_data = {
        "price": 1199.99,
        "in_stock": False,
    }
    response = client.put("/items/1", json=update_data)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == 1
    assert data["title"] == "Laptop"  # preserved
    assert data["price"] == 1199.99  # updated
    assert data["in_stock"] is False  # updated


def test_update_item_not_found(client):
    """Test updating a non-existent item returns 404."""
    response = client.put("/items/999", json={"title": "Ghost Item"})
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_item_success(client):
    """Test deleting an item removes it."""
    delete_res = client.delete("/items/2")
    assert delete_res.status_code == status.HTTP_200_OK

    # Verify item is gone
    get_res = client.get("/items/2")
    assert get_res.status_code == status.HTTP_404_NOT_FOUND


def test_delete_item_not_found(client):
    """Test deleting a non-existent item returns 404."""
    response = client.delete("/items/999")
    assert response.status_code == status.HTTP_404_NOT_FOUND

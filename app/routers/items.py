"""Endpoints for Item resources."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.crud import repo
from app.schemas import ItemCreate, ItemResponse, ItemUpdate

router = APIRouter(prefix="/items", tags=["Items"])


@router.get("", response_model=List[ItemResponse], summary="List items with pagination and search")
def list_items(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=1, le=100, description="Max number of items to return"),
    search: Optional[str] = Query(None, description="Search keyword in title or description"),
):
    """Retrieve all items, optionally filtered by keyword search and paginated."""
    return repo.get_all(skip=skip, limit=limit, search=search)


@router.get("/{item_id}", response_model=ItemResponse, summary="Get item by ID")
def get_item(item_id: int):
    """Fetch details of a specific item by its identifier."""
    item = repo.get_by_id(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {item_id} not found"
        )
    return item


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED, summary="Create a new item")
def create_item(payload: ItemCreate):
    """Create a new item with title, description, price, and stock status."""
    return repo.create(payload)


@router.put("/{item_id}", response_model=ItemResponse, summary="Update an existing item")
def update_item(item_id: int, payload: ItemUpdate):
    """Update existing item fields."""
    updated = repo.update(item_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {item_id} not found"
        )
    return updated


@router.delete("/{item_id}", status_code=status.HTTP_200_OK, summary="Delete an item")
def delete_item(item_id: int):
    """Delete an item by its identifier."""
    success = repo.delete(item_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {item_id} not found"
        )
    return {"status": "success", "message": f"Item {item_id} successfully deleted"}

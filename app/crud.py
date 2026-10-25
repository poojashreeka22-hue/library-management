"""In-memory repository and business operations."""
from typing import Dict, List, Optional
from app.schemas import ItemCreate, ItemResponse, ItemUpdate


class ItemRepository:
    def __init__(self):
        self._items: Dict[int, ItemResponse] = {}
        self._counter: int = 1
        self._seed_initial_data()

    def _seed_initial_data(self) -> None:
        self.create(ItemCreate(title="Laptop", description="High-performance developer laptop", price=1299.99, in_stock=True))
        self.create(ItemCreate(title="Wireless Mouse", description="Ergonomic Bluetooth mouse", price=29.99, in_stock=True))
        self.create(ItemCreate(title="Mechanical Keyboard", description="RGB mechanical keyboard", price=89.99, in_stock=False))

    def reset(self) -> None:
        """Reset repository to clean initial state for test isolation."""
        self._items.clear()
        self._counter = 1
        self._seed_initial_data()

    def get_all(self, skip: int = 0, limit: int = 10, search: Optional[str] = None) -> List[ItemResponse]:
        items = list(self._items.values())
        if search:
            search_lower = search.lower()
            items = [item for item in items if search_lower in item.title.lower() or (item.description and search_lower in item.description.lower())]
        return items[skip : skip + limit]

    def get_by_id(self, item_id: int) -> Optional[ItemResponse]:
        return self._items.get(item_id)

    def create(self, item_in: ItemCreate) -> ItemResponse:
        item = ItemResponse(id=self._counter, **item_in.model_dump())
        self._items[self._counter] = item
        self._counter += 1
        return item

    def update(self, item_id: int, item_in: ItemUpdate) -> Optional[ItemResponse]:
        existing = self._items.get(item_id)
        if not existing:
            return None
        
        update_data = item_in.model_dump(exclude_unset=True)
        updated_dict = existing.model_dump()
        updated_dict.update(update_data)
        updated_item = ItemResponse(**updated_dict)
        self._items[item_id] = updated_item
        return updated_item

    def delete(self, item_id: int) -> bool:
        if item_id in self._items:
            del self._items[item_id]
            return True
        return False


repo = ItemRepository()

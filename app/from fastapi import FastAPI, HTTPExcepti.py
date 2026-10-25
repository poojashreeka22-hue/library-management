from fastapi import FastAPI, HTTPException

app = FastAPI(title="FastAPI Bulk Test Project", version="1.0.0")

@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI project!"}

@app.get("/process/{item_id}")
def process_item(item_id: int):
    if item_id < 0:
        raise HTTPException(status_code=400, detail="Negative IDs not allowed")
    return {
        "item_id": item_id,
        "status": "success",
        "computed_value": item_id * 3
    }
from fastapi.testclient import TestClient
import pytest
from main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the FastAPI project!"}

# Dynamically generate 3,000 passing test cases
@pytest.mark.parametrize("val", range(3000))
def test_bulk_processing_cases(val):
    response = client.get(f"/process/{val}")
    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == val
    assert data["status"] == "success"
    assert data["computed_value"] == val * 3
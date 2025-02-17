import os
import sys
import pytest
from datetime import datetime

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from models.set import FlashcardSet
from models.flashcard import Flashcard
from models.enums import EditContext, FeedbackType, FeedbackCategory

def test_create_flashcard_set(client):
    response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": [
                {"front": "Front 1", "back": "Back 1"},
                {"front": "Front 2", "back": "Back 2"}
            ]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Set"
    assert data["description"] == "Test Description"
    assert data["card_count"] == 2

def test_get_flashcard_sets(client):
    # Create a test set first
    client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": [{"front": "Front 1", "back": "Back 1"}]
        }
    )

    response = client.get("/api/flashcard-sets/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["title"] == "Test Set"
    assert data[0]["card_count"] == 1

def test_get_flashcard_set(client):
    # Create a test set first
    create_response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": [{"front": "Front 1", "back": "Back 1"}]
        }
    )
    set_id = create_response.json()["id"]

    response = client.get(f"/api/flashcard-sets/{set_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Set"
    assert len(data["flashcards"]) == 1
    assert data["flashcards"][0]["front"] == "Front 1"

def test_update_flashcard_set(client):
    # Create a test set first
    create_response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": []
        }
    )
    set_id = create_response.json()["id"]

    # Update the set
    response = client.patch(
        f"/api/flashcard-sets/{set_id}",
        json={
            "title": "Updated Title",
            "description": "Updated Description"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["description"] == "Updated Description"

def test_add_card_to_set(client):
    # Create a test set first
    create_response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": []
        }
    )
    set_id = create_response.json()["id"]

    # Add a card
    response = client.post(
        f"/api/flashcard-sets/{set_id}/cards",
        json={
            "front": "New Front",
            "back": "New Back"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["front"] == "New Front"
    assert data["back"] == "New Back"

    # Verify card was added to set
    set_response = client.get(f"/api/flashcard-sets/{set_id}")
    assert set_response.json()["card_count"] == 1

def test_update_card(client):
    # Create a test set with a card
    create_response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": [{"front": "Front 1", "back": "Back 1"}]
        }
    )
    set_id = create_response.json()["id"]
    
    # Get the card ID
    set_response = client.get(f"/api/flashcard-sets/{set_id}")
    card_id = set_response.json()["flashcards"][0]["id"]

    # Update the card
    response = client.patch(
        f"/api/flashcard-sets/cards/{card_id}",
        json={
            "front": "Updated Front",
            "back": "Updated Back"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["front"] == "Updated Front"
    assert data["back"] == "Updated Back"

def test_delete_card(client):
    # Create a test set with a card
    create_response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": [{"front": "Front 1", "back": "Back 1"}]
        }
    )
    set_id = create_response.json()["id"]
    
    # Get the card ID
    set_response = client.get(f"/api/flashcard-sets/{set_id}")
    card_id = set_response.json()["flashcards"][0]["id"]

    # Delete the card
    response = client.delete(f"/api/flashcard-sets/cards/{card_id}")
    assert response.status_code == 200

    # Verify card was deleted
    set_response = client.get(f"/api/flashcard-sets/{set_id}")
    assert set_response.json()["card_count"] == 0

def test_get_nonexistent_set(client):
    response = client.get("/api/flashcard-sets/99999")
    assert response.status_code == 404

def test_update_nonexistent_set(client):
    response = client.patch(
        "/api/flashcard-sets/99999",
        json={"title": "New Title"}
    )
    assert response.status_code == 404

def test_add_card_to_nonexistent_set(client):
    response = client.post(
        "/api/flashcard-sets/99999/cards",
        json={"front": "Front", "back": "Back"}
    )
    assert response.status_code == 404

def test_update_nonexistent_card(client):
    response = client.patch(
        "/api/flashcard-sets/cards/99999",
        json={"front": "Front", "back": "Back"}
    )
    assert response.status_code == 404

def test_delete_nonexistent_card(client):
    response = client.delete("/api/flashcard-sets/cards/99999")
    assert response.status_code == 404

def test_update_card_creates_version(client):
    # Create a test set with a card
    create_response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": [{"front": "Front 1", "back": "Back 1"}]
        }
    )
    set_id = create_response.json()["id"]
    
    # Get the card ID
    set_response = client.get(f"/api/flashcard-sets/{set_id}")
    card_id = set_response.json()["flashcards"][0]["id"]

    # Update the card with edit context
    response = client.patch(
        f"/api/flashcard-sets/cards/{card_id}",
        json={
            "front": "Updated Front",
            "back": "Updated Back"
        },
        params={
            "edit_context": "quick_review",
            "edit_summary": "Quick review update",
            "user_id": "test_user"
        }
    )
    assert response.status_code == 200

    # Get versions
    versions_response = client.get(f"/api/flashcard-sets/cards/{card_id}/versions")
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert len(versions) > 0
    latest_version = versions[0]
    assert latest_version["front"] == "Updated Front"
    assert latest_version["back"] == "Updated Back"
    assert latest_version["edit_context"] == "quick_review"
    assert latest_version["edit_summary"] == "Quick review update"
    assert latest_version["user_id"] == "test_user"

def test_get_specific_card_version(client):
    # Create and update a card to generate versions
    create_response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": [{"front": "Original Front", "back": "Original Back"}]
        }
    )
    set_id = create_response.json()["id"]
    set_response = client.get(f"/api/flashcard-sets/{set_id}")
    card_id = set_response.json()["flashcards"][0]["id"]

    # Update the card
    client.patch(
        f"/api/flashcard-sets/cards/{card_id}",
        json={"front": "Updated Front", "back": "Updated Back"}
    )

    # Get version 1 (original)
    version_response = client.get(f"/api/flashcard-sets/cards/{card_id}/versions/1")
    assert version_response.status_code == 200
    version = version_response.json()
    assert version["version_number"] == 1
    assert version["front"] == "Original Front"
    assert version["back"] == "Original Back"

def test_get_card_edit_history(client):
    # Create and update a card to generate history
    create_response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": [{"front": "Original Front", "back": "Original Back"}]
        }
    )
    set_id = create_response.json()["id"]
    set_response = client.get(f"/api/flashcard-sets/{set_id}")
    card_id = set_response.json()["flashcards"][0]["id"]

    # Update the card
    client.patch(
        f"/api/flashcard-sets/cards/{card_id}",
        json={"front": "Updated Front", "back": "Updated Back"}
    )

    # Get edit history
    history_response = client.get(f"/api/flashcard-sets/cards/{card_id}/history")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) > 0
    latest_edit = history[0]
    assert latest_edit["previous_front"] == "Original Front"
    assert latest_edit["previous_back"] == "Original Back"
    assert isinstance(latest_edit["created_at"], str)  # Should be ISO format datetime

def test_submit_and_get_card_feedback(client):
    # Create a card
    create_response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": [{"front": "Front 1", "back": "Back 1"}]
        }
    )
    set_id = create_response.json()["id"]
    set_response = client.get(f"/api/flashcard-sets/{set_id}")
    card_id = set_response.json()["flashcards"][0]["id"]

    # Submit feedback
    feedback_response = client.post(
        f"/api/flashcard-sets/cards/{card_id}/feedback",
        json={
            "feedback_type": "thumbs_up",
            "feedback_category": "too_specific",
            "feedback_text": "Good card but too detailed"
        },
        params={"user_id": "test_user"}
    )
    assert feedback_response.status_code == 200

    # Get feedback
    get_feedback_response = client.get(f"/api/flashcard-sets/cards/{card_id}/feedback")
    assert get_feedback_response.status_code == 200
    feedback = get_feedback_response.json()
    assert len(feedback) > 0
    latest_feedback = feedback[0]
    assert latest_feedback["feedback_type"] == "thumbs_up"
    assert latest_feedback["feedback_category"] == "too_specific"
    assert latest_feedback["feedback_text"] == "Good card but too detailed"

def test_nonexistent_card_version(client):
    response = client.get("/api/flashcard-sets/cards/99999/versions/1")
    assert response.status_code == 404

def test_nonexistent_card_history(client):
    response = client.get("/api/flashcard-sets/cards/99999/history")
    assert response.status_code == 404

def test_nonexistent_card_feedback(client):
    response = client.get("/api/flashcard-sets/cards/99999/feedback")
    assert response.status_code == 404

def test_submit_feedback_invalid_type(client):
    # Create a card
    create_response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": [{"front": "Front 1", "back": "Back 1"}]
        }
    )
    set_id = create_response.json()["id"]
    set_response = client.get(f"/api/flashcard-sets/{set_id}")
    card_id = set_response.json()["flashcards"][0]["id"]

    # Submit invalid feedback
    response = client.post(
        f"/api/flashcard-sets/cards/{card_id}/feedback",
        json={
            "feedback_type": "invalid_type",  # Invalid type
            "feedback_category": "too_specific",
            "feedback_text": "Test feedback"
        }
    )
    assert response.status_code == 422  # Validation error 
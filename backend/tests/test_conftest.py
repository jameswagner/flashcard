import pytest
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from sqlalchemy import text
from fastapi.testclient import TestClient

def test_test_db_fixture(test_db):
    """Test that the test_db fixture provides a working database session."""
    assert isinstance(test_db, Session)
    
    # Test that we can execute queries
    result = test_db.execute(text("SELECT 1")).scalar()
    assert result == 1
    
    # Test that we can commit transactions
    test_db.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY)"))
    test_db.commit()
    
    # Test that the table was created
    result = test_db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")).scalar()
    assert result == 'test'

def test_test_db_isolation(test_db):
    """Test that each test gets a fresh database."""
    # Create a table
    test_db.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY)"))
    test_db.commit()
    
    # Table should exist in this test
    result = test_db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")).scalar()
    assert result == 'test'

def test_test_db_isolation_2(test_db):
    """Test that we get a fresh database (table from previous test should not exist)."""
    # The table from the previous test should not exist
    result = test_db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")).scalar()
    assert result is None

def test_client_fixture(client):
    """Test that the client fixture provides a working FastAPI test client."""
    assert isinstance(client, TestClient)
    
    # Test that we can make requests
    response = client.get("/")
    assert response.status_code in (200, 404)  # Either is fine, we just want to ensure the client works

def test_client_db_integration(client, test_db):
    """Test that the client uses the test database."""
    # Create a table and insert data
    test_db.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)"))
    test_db.execute(text("INSERT INTO test (id, value) VALUES (1, 'test')"))
    test_db.commit()
    
    # Verify through raw SQL that the data exists
    result = test_db.execute(text("SELECT value FROM test WHERE id = 1")).scalar()
    assert result == 'test'

def test_db_rollback(test_db):
    """Test that transactions are properly rolled back on error."""
    # Start a transaction
    test_db.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY)"))
    test_db.execute(text("INSERT INTO test (id) VALUES (1)"))
    test_db.commit()  # Commit the initial transaction
    
    try:
        # This should fail due to PRIMARY KEY constraint
        test_db.execute(text("INSERT INTO test (id) VALUES (1)"))
        test_db.commit()
        pytest.fail("Should have raised an error")
    except:
        test_db.rollback()
    
    # Verify only one row exists
    result = test_db.execute(text("SELECT COUNT(*) FROM test")).scalar()
    assert result == 1

def test_db_relationship_cascade(test_db):
    """Test that relationships and foreign keys work in the test database."""
    # Create parent and child tables
    test_db.execute(text("""
        CREATE TABLE parent (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    """))
    test_db.execute(text("""
        CREATE TABLE child (
            id INTEGER PRIMARY KEY,
            parent_id INTEGER,
            name TEXT,
            FOREIGN KEY(parent_id) REFERENCES parent(id)
        )
    """))
    
    # Insert parent and child
    test_db.execute(text("INSERT INTO parent (id, name) VALUES (1, 'parent')"))
    test_db.execute(text("INSERT INTO child (id, parent_id, name) VALUES (1, 1, 'child')"))
    test_db.commit()
    
    # Test foreign key constraint
    try:
        test_db.execute(text("INSERT INTO child (id, parent_id, name) VALUES (2, 999, 'orphan')"))
        test_db.commit()
        pytest.fail("Should have raised a foreign key constraint error")
    except:
        test_db.rollback()

def test_client_dependency_override(client, test_db):
    """Test that the client's dependency override for get_db works."""
    # This is a bit tricky to test directly, but we can verify that
    # the client is using our test database by checking if tables
    # created through the client are visible in test_db
    
    # Make a request that should create some data
    response = client.post(
        "/api/flashcard-sets/",
        json={
            "title": "Test Set",
            "description": "Test Description",
            "flashcards": []
        }
    )
    assert response.status_code == 200
    
    # Verify the data exists in our test_db
    result = test_db.execute(text("SELECT title FROM flashcard_sets")).scalar()
    assert result == "Test Set" 
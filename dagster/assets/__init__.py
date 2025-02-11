from dagster import asset

@asset
def flashcard_data():
    """
    Example asset that could later process flashcard data
    """
    return {"status": "placeholder"}

@asset
def processed_flashcards(flashcard_data):
    """
    Example downstream asset that depends on flashcard_data
    """
    return {"processed": flashcard_data} 
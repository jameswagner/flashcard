from dagster import Definitions
from ..assets import flashcard_data, processed_flashcards
from ..jobs import flashcard_job

defs = Definitions(
    assets=[flashcard_data, processed_flashcards],
    jobs=[flashcard_job]
) 
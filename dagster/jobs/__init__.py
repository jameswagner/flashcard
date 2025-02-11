from dagster import define_asset_job
from ..assets import flashcard_data, processed_flashcards

# Define jobs in terms of assets
flashcard_job = define_asset_job(
    name="flashcard_job",
    selection=[flashcard_data, processed_flashcards]
) 
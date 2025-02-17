from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from dotenv import load_dotenv
import os
import time

# Import our models
from models.base import Base
from models.flashcard import Flashcard, CardVersion, CardEditHistory
from models.feedback import CardFeedback
from models.source import SourceFile, Citation
from models.prompt import PromptTemplate
from models.set import FlashcardSet
from models.study import StudySession, CardReview, ReviewScore
from models.scoring_config import DBScoringConfig

# Load local env if it exists, otherwise use system env vars
if os.path.exists(".env.local"):
    load_dotenv(".env.local")
else:
    load_dotenv()

config = context.config

# Set config options for URL interpolation
section = config.config_ini_section
config.set_section_option(section, "POSTGRES_USER", os.getenv("POSTGRES_USER"))
config.set_section_option(section, "POSTGRES_PASSWORD", os.getenv("POSTGRES_PASSWORD"))
config.set_section_option(section, "POSTGRES_HOST", os.getenv("POSTGRES_HOST"))
config.set_section_option(section, "POSTGRES_PORT", os.getenv("POSTGRES_PORT"))
config.set_section_option(section, "POSTGRES_DB", os.getenv("POSTGRES_DB"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# After loading env vars
print(f"DB Connection: {os.getenv('POSTGRES_USER')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}")

def get_next_revision_id():
    """Generate a sequential revision ID based on timestamp."""
    # Use millisecond timestamp for uniqueness
    return str(int(time.time() * 1000))

def process_revision_directives(context, revision, directives):
    """Override revision ID generation."""
    
    # Generate new timestamp-based revision ID
    new_rev_id = get_next_revision_id()
    print(f"Generated revision ID: {new_rev_id}")
    
    # Update the revision ID in the script
    script = directives[0]
    script.rev_id = new_rev_id
    
    # Also update the path to match the new ID
    if hasattr(script, 'path'):
        old_path = script.path
        new_path = old_path.replace(script.path.split('_')[0].split('/')[-1], new_rev_id)
        script.path = new_path

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

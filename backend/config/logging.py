import logging
import logging.handlers
import os
from datetime import datetime
import sys
import codecs
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(logs_dir, exist_ok=True)

def configure_logging():
    """Configure logging with proper Unicode handling for all platforms."""
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if sys.platform == 'win32':
        # Ensure stdout can handle UTF-8
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        
        # Create handler with UTF-8 encoding for Windows
        handler = logging.StreamHandler(
            codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
        )
    else:
        # Standard handler for other platforms
        handler = logging.StreamHandler()
    
    # Configure handler
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    
    # Configure specific loggers
    loggers_to_configure = [
        'uvicorn',
        'uvicorn.error',
        'uvicorn.access',
        'fastapi',
        'sqlalchemy.engine',
        'alembic',
        'openai',
        'anthropic',
        'google.generativeai',
    ]
    
    for logger_name in loggers_to_configure:
        logger = logging.getLogger(logger_name)
        # Remove any existing handlers to prevent duplicates
        logger.handlers = []
        logger.addHandler(handler)
        
        # Set appropriate levels
        if logger_name in ['uvicorn.access', 'sqlalchemy.engine']:
            logger.setLevel(logging.WARNING)  # Less verbose
        else:
            logger.setLevel(logging.INFO)
    
    # Optionally set up file logging
    logs_dir = Path(__file__).parent.parent / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    file_handler = logging.FileHandler(
        logs_dir / 'app.log',
        encoding='utf-8',
        errors='replace'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

# Configure logging
def setup_logging():
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )

    # Create handlers
    # File handler for all logs
    all_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, 'flashcards.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    all_handler.setFormatter(file_formatter)
    all_handler.setLevel(logging.DEBUG)

    # File handler for errors only
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(logs_dir, 'error.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    error_handler.setFormatter(file_formatter)
    error_handler.setLevel(logging.ERROR)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove any existing handlers
    root_logger.handlers = []

    # Add handlers
    root_logger.addHandler(all_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)

    # Create logger for this module
    logger = logging.getLogger(__name__)
    logger.info('Logging setup completed') 
"""HTML processing utilities for flashcard generation."""

from .scraper import scrape_url, clean_html
from .processor import process_html, HTMLContent, HTMLSection, HTMLProcessor

__all__ = ['scrape_url', 'clean_html', 'process_html', 'HTMLContent', 'HTMLSection', 'HTMLProcessor'] 
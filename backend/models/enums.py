import enum

class FileType(enum.Enum):
    """Supported file types for content processing."""
    TXT = "txt"
    HTML = "html"
    PDF = "pdf"
    YOUTUBE_TRANSCRIPT = "youtube_transcript"
    IMAGE = "image"  # New type for image files

    @property
    def structure_description(self) -> str:
        """Get the content structure description for this file type."""
        return _FILE_TYPE_STRUCTURES[self]

class AIModel(enum.Enum):
    GPT_4 = "gpt-4"
    GPT_35_TURBO = "gpt-3.5-turbo"
    CLAUDE_3_OPUS = "claude-3-opus"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    GEMINI_PRO = "gemini-pro"
    GPT4O_MINI = "gpt-4o-mini"  # New affordable model with 128k context

class FlashcardCreationType(enum.Enum):
    """Types of flashcard creation methods."""
    AI_GENERATED = "ai_generated"
    MANUAL = "manual"
    IMPORTED = "imported"
    SELECTED_CONTENT = "selected_content"

class CitationType(enum.Enum):
    character_range = "character_range"
    line_numbers = "line_numbers"
    pdf_bbox = "pdf_bbox"
    semantic_chunk = "semantic_chunk"
    sentence_range = "sentence_range"  # Used for unstructured content fallback
    paragraph = "paragraph"  # For citing paragraphs in any content type
    section = "section"  # For citing entire sections with headings
    table = "table"  # For citing tables
    list = "list"  # For citing lists (ordered or unordered)
    video_timestamp = "video_timestamp"  # For citing specific video timestamps
    video_chapter = "video_chapter"  # For citing entire video chapters
    image_region = "image_region"  # For citing specific regions in an image
    image_block = "image_block"  # For citing text blocks in an image

class FeedbackType(enum.Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"

class FeedbackCategory(enum.Enum):
    INCORRECT_ANSWER = "incorrect_answer"
    UNCLEAR_QUESTION = "unclear_question"
    TOO_SPECIFIC = "too_specific"
    TOO_GENERAL = "too_general"
    NOT_RELEVANT = "not_relevant"
    OTHER = "other"

class CardStatus(enum.Enum):
    ACTIVE = "active"
    DELETED = "deleted"
    ARCHIVED = "archived"

class EditType(enum.Enum):
    MANUAL = "manual"
    AI_ASSISTED = "ai_assisted"
    AI_GENERATED = "ai_generated"
    DELETION = "deletion"
    UNDELETION = "undeletion"
    ARCHIVE = "archive"
    UNARCHIVE = "unarchive"

class EditContext(enum.Enum):
    QUICK_REVIEW = "quick_review"
    DETAILED_EDIT = "detailed_edit"
    BULK_EDIT = "bulk_edit"
    STUDY_SESSION = "study_session"
    AI_ASSISTED = "ai_assisted"

# New enums for study sessions
class StudySessionType(enum.Enum):
    LEARN = "learn"  # First time learning cards
    REVIEW = "review"  # Regular review of known cards
    TEST = "test"  # Test mode with scoring
    AI_ASSISTED = "ai_assisted"  # Review with AI validation

class ReviewGrade(enum.Enum):
    CORRECT = "correct"  # User got it completely right
    PARTIALLY_CORRECT = "partially_correct"  # Some elements correct but missing details
    INCORRECT = "incorrect"  # Wrong answer
    SKIPPED = "skipped"  # User skipped the card
    TOO_EASY = "too_easy"  # User marks card as too easy
    TOO_HARD = "too_hard"  # User marks card as too difficult

class ReviewConfidence(enum.Enum):
    VERY_LOW = "very_low"  # Complete guess
    LOW = "low"  # Uncertain
    MEDIUM = "medium"  # Somewhat confident
    HIGH = "high"  # Very confident
    PERFECT = "perfect"  # Absolutely certain

class AnswerMethod(enum.Enum):
    TEXT = "text"  # Typed answer
    SPEECH = "speech"  # Speech-to-text answer
    MULTIPLE_CHOICE = "multiple_choice"  # Multiple choice selection
    TRUE_FALSE = "true_false"  # True/False selection

class ScoreType(enum.Enum):
    SELF_ASSESSED = "self_assessed"  # User's self-assessment
    NLI_ENTAILMENT = "nli_entailment"  # NLI entailment score
    NLI_CONTRADICTION = "nli_contradiction"  # NLI contradiction score
    SEMANTIC_SIMILARITY = "semantic_similarity"  # Semantic similarity score
    SEMANTIC_ROLE = "semantic_role"  # Semantic role labeling score
    FINAL_AI = "final_ai"  # Final weighted AI score combining all components

# Content structure descriptions
_FILE_TYPE_STRUCTURES = {
    FileType.HTML: (
        "The text is structured HTML content with sections, paragraphs, tables, and lists. "
        "Each section begins with [Section: heading]. "
        "Content is organized hierarchically with sections containing paragraphs and other elements. "
        "Valid citation types:\n"
        "- section: For citing entire sections with their headings\n"
        "- paragraph: For citing specific paragraphs\n"
        "- table: For citing tables\n"
        "- list: For citing ordered or unordered lists\n"
    ),
    FileType.YOUTUBE_TRANSCRIPT: (
        "The text is a YouTube video transcript with timestamps in seconds. "
        "Valid citation types:\n"
        "- video_timestamp: For citing specific moments (use range for time spans)\n"
        "- video_chapter: For citing entire chapters or sections\n"
        "Each citation should include relevant context like chapter names or topics."
    ),
    FileType.TXT: (
        "The text has been pre-processed to identify paragraph sentence boundaries. "
        "Each sentence and paragraph is numbered starting from 1."
        "Valid citation types:\n"
        "- sentence_range: For citing one or more sentences by their numbers. Use this if a concept does not span 1 or more paragraphs."
        "- paragraph: For citing one or more paragraphs by their numbers. Use this if a concept spans 1 or more paragraphs."
    ),
    FileType.PDF: (
        "The text is extracted from a PDF document with special processing to maintain structure. "
        "IMPORTANT: Only use citation types that match the document's structure. The available types depend on what was successfully extracted:\n"
        "- If sections were found: Sections are marked with [Section X] headers\n"
        "- If paragraphs were found: Paragraphs are marked with [Paragraph X]\n"
        "- All documents have sentence markers: [SENTENCE X]\n\n"
        "Valid citation types (use ONLY if corresponding markers exist in the text):\n"
        "- section: For citing sections (only if [Section X] markers exist)\n"
        "- paragraph: For citing paragraphs (only if [Paragraph X] markers exist)\n"
        "- list: For citing lists (only if [List X] markers exist)\n"
        "- sentence_range: For citing specific sentences \n"
        "- pdf_bbox: For citing specific regions by their bounding box coordinates (advanced use)\n\n"
        "CRITICAL: Check the processed text first and only use citation types that match existing markers. "
        "Using non-existent markers will result in failed citations."
    ),
    FileType.IMAGE: (
        "The text is extracted from an image using OCR with preserved layout information. "
        "Text is organized into blocks and regions based on their position in the image. "
        "Valid citation types:\n"
        "- image_region: For citing specific regions by their coordinates\n"
        "- image_block: For citing specific text blocks\n"
        "- paragraph: For citing logical paragraphs of text\n"
        "Each citation includes position information for highlighting in the UI."
    ),
} 
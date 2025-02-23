import enum

class FileType(enum.Enum):
    TXT = "txt"
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    YOUTUBE_TRANSCRIPT = "youtube_transcript"

class AIModel(enum.Enum):
    GPT_4 = "gpt-4"
    GPT_35_TURBO = "gpt-3.5-turbo"
    CLAUDE_3_OPUS = "claude-3-opus"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    GEMINI_PRO = "gemini-pro"
    GPT4O_MINI = "gpt-4o-mini"  # New affordable model with 128k context

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
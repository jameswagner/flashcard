export interface FlashcardSet {
  id: number;
  title: string;
  description: string | null;
  card_count: number;
}

export interface AnswerKeyTerm {
  terms: string[];
  weight: number;
  exact_match: boolean;
  explanation: string;
}

export interface Flashcard {
  id: number;
  front: string;
  back: string;
  set_id: number;
  citations?: Citation[];
  feedback?: string;
  answer_key_terms?: AnswerKeyTerm[];
  key_concepts?: string[];
  abbreviations?: [string, string][];
  created_at: string;
  updated_at: string;
  is_ai_generated?: boolean;
  card_index?: number;
  isNew?: boolean;  // Used for tracking new cards in the UI
}

export interface FlashcardSetDetail extends FlashcardSet {
  flashcards: Flashcard[];
}

// API Request Types
export interface FlashcardSetCreateRequest {
  title: string;
  description?: string;
  flashcards?: FlashcardCreateRequest[];
}

export interface FlashcardSetUpdateRequest {
  title?: string;
  description?: string;
}

export interface FlashcardCreateRequest {
  front: string;
  back: string;
}

export interface FlashcardUpdateRequest {
  front?: string;
  back?: string;
  card_index?: number;
}

export interface FlashcardFeedbackRequest {
  feedback_type: 'thumbs_up' | 'thumbs_down';
  feedback_category?: string;
  feedback_text?: string;
}

export interface URLUploadRequest {
  url: string;
  user_id?: string;
  title?: string;
  description?: string;
}

export interface YouTubeUploadRequest {
  video_id: string;
  title: string;
  description?: string;
  user_id?: string;
}

export interface ContentSelection {
  citation_type: 'paragraph' | 'sentence_range';
  range: [number, number]; // [start, end] inclusive
}

export interface AIGenerateRequest {
  model?: string;
  user_id?: string;
  model_params?: Record<string, any>;  // For JSON stringified parameters
  title?: string;
  description?: string;
  use_sentences?: boolean;  // Default: true
  selected_content?: ContentSelection[];  // Optional content selection for partial generation
}

// Citation Types
export interface CitationData {
  start_line?: number;
  end_line?: number;
  start_char?: number;
  end_char?: number;
  page_number?: number;
  bbox?: [number, number, number, number];  // [x1, y1, x2, y2] for PDF bounding boxes
  text?: string;
  start_time?: number;  // For video timestamps (in seconds)
  end_time?: number;    // For video timestamps (in seconds)
  section_id?: number;  // For PDF sections
  paragraph_id?: number;  // For PDF paragraphs
  is_header?: boolean;  // For PDF headers/titles
}

export interface Citation {
  id: number;
  source_file_id: number;
  citation_type: 'character_range' | 'line_numbers' | 'pdf_bbox' | 'semantic_chunk' | 
                 'sentence_range' | 'paragraph' | 'section' | 'table' | 
                 'list' | 'video_timestamp' | 'video_chapter' | 'block';
  citation_data: [number, number][];  // Array of [start, end] tuples
  preview_text: string | null;
}

export interface SourceTextWithCitations {
  source_file_id: number;
  filename: string;
  text_content: string;
  citations: {
    citation_id: number;
    citation_type: string;
    citation_data: [number, number][];
    preview_text: string | null;
    card_id: number;
    card_front: string;
    card_back: string;
    card_index: number;
  }[];
  file_type: string;
  processed_text_type: string | null;
}

export interface FlashcardSetSourceResponse {
  set_id: number;
  title: string;
  sources: SourceTextWithCitations[];
}

// API Response Types
export type FlashcardSetResponse = FlashcardSet;
export type FlashcardSetDetailResponse = FlashcardSetDetail;

export interface FlashcardResponse extends Flashcard {
  is_ai_generated?: boolean;
  citations?: Citation[];
}

export interface UploadResponse {
  id: number;
  filename: string;
}

export interface GenerateResponse {
  set_id: number;
  num_cards: number;
}

export interface FlashcardFeedbackResponse {
  status: string;
  id: number;
}

export interface FlashcardVersionResponse {
  id: number;
  version_number: number;
  front: string;
  back: string;
  status: string;
  edit_type: string;
  edit_context?: string;
  user_id?: string;
  created_at: string;
  edit_summary?: string;
}

export interface FlashcardHistoryResponse {
  id: number;
  previous_front: string;
  previous_back: string;
  edit_type: string;
  created_at: string;
}

export interface FlashcardFeedbackDetailResponse {
  id: number;
  feedback_type: string;
  feedback_category?: string;
  feedback_text?: string;
  feedback_context?: string;
  created_at: string;
}

// Study Session Types
export enum StudySessionType {
  LEARN = "learn",
  REVIEW = "review",
  TEST = "test",
  AI_ASSISTED = "ai_assisted"
}

export enum ReviewGrade {
  CORRECT = "correct",
  PARTIALLY_CORRECT = "partially_correct",
  INCORRECT = "incorrect",
  SKIPPED = "skipped",
  TOO_EASY = "too_easy",
  TOO_HARD = "too_hard"
}

export enum ReviewConfidence {
  VERY_LOW = "very_low",
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
  PERFECT = "perfect"
}

export enum AnswerMethod {
  TEXT = "text",
  SPEECH = "speech",
  MULTIPLE_CHOICE = "multiple_choice",
  TRUE_FALSE = "true_false"
}

export enum ScoreType {
  SELF_ASSESSED = 'self_assessed',
  NLI_ENTAILMENT = 'nli_entailment',
  NLI_CONTRADICTION = 'nli_contradiction',
  SEMANTIC_SIMILARITY = 'semantic_similarity',
  SEMANTIC_ROLE = 'semantic_role',
  FINAL_AI = 'final_ai'
}

// Study Session Request/Response Types
export interface StudySessionSettings {
  mode?: 'self_assessed' | 'timed' | 'spaced';
  timer_duration?: number;
  card_order?: 'sequential' | 'random';
  review_threshold?: number;
}

export interface ScoreMetadata {
  status?: 'pending' | 'completed' | 'error';
  error?: string;
  nli?: {
    neutral: number;
    was_contradiction: boolean;
  };
  similarity?: {
    model_scores: Record<string, number>;
  };
  srl?: {
    role_scores: Record<string, number>;
    missing_concepts: string[];
    correct_roles: Record<string, string>;
    student_roles: Record<string, string>;
  };
}

export interface StudySessionCreateRequest {
  set_id: number;
  session_type: StudySessionType;
  settings?: StudySessionSettings;
}

export interface CardReviewCreateRequest {
  flashcard_id: number;
  answer_method: AnswerMethod;
  user_answer?: string;
  time_to_answer?: number;
}

export interface ReviewScoreCreateRequest {
  score_type: ScoreType;
  score: number;
  grade?: ReviewGrade;
  confidence?: ReviewConfidence;
  score_metadata?: ScoreMetadata;
}

export interface ReviewScore {
  id: number;
  score_type: string;
  score: number;
  grade?: string;
  confidence?: string;
  score_metadata?: Record<string, string | number | boolean>;
  created_at: string;
}

export interface CardReview {
  id: number;
  flashcard_id: number;
  answer_method: string;
  user_answer?: string;
  time_to_answer?: number;
  reviewed_at: string;
  scores: ReviewScore[];
}

export interface StudySession {
  id: number;
  user_id: string;
  set_id: number;
  session_type: string;
  started_at: string;
  completed_at: string | null;
  cards_reviewed: number;
  correct_count: number;
  incorrect_count: number;
  average_confidence: number;
  average_nli_score: number;
  average_self_assessed_score: number;
  ai_scores: Record<string, number>;
  settings: StudySessionSettings | null;
  reviews: CardReview[];
}

export interface StudySessionStatistics {
  cards_reviewed: number;
  correct_count: number;
  incorrect_count: number;
  accuracy: number;
  average_confidence: number;
  average_self_assessed_score: number;
  ai_scores: {
    [key in ScoreType]?: number;
  };
}

export interface CompleteStudySessionResponse {
  status: string;
  message: string;
  statistics: StudySessionStatistics;
}

export interface SourceFileUploadResponse {
  id: number;
  filename: string;
  source_type: "file" | "url" | "youtube";
} 
import config from '../config';
import {
  FlashcardSet,
  FlashcardSetResponse,
  FlashcardSetDetailResponse,
  FlashcardSetCreateRequest,
  FlashcardSetUpdateRequest,
  FlashcardResponse,
  FlashcardCreateRequest,
  FlashcardUpdateRequest,
  FlashcardFeedbackRequest,
  FlashcardFeedbackResponse,
  FlashcardFeedbackDetailResponse,
  FlashcardVersionResponse,
  FlashcardHistoryResponse,
  UploadResponse,
  GenerateResponse,
  AIGenerateRequest,
  Citation,
  URLUploadRequest,
  YouTubeUploadRequest,
  FlashcardSetSourceResponse,
  SourceFileUploadResponse
} from '@/types';

// Get all flashcard sets
export const getFlashcardSets = async (): Promise<FlashcardSetResponse[]> => {
  const response = await fetch(`${config.apiUrl}/api/flashcard-sets/`);
  if (!response.ok) {
    throw new Error('Failed to fetch flashcard sets');
  }
  return response.json();
};

// Get a single flashcard set with its cards
export const getFlashcardSet = async (id: number): Promise<FlashcardSetDetailResponse> => {
  const response = await fetch(`${config.apiUrl}/api/flashcard-sets/${id}`);
  if (!response.ok) {
    throw new Error('Failed to fetch flashcard set');
  }
  return response.json();
};

// Get source text with citations for a flashcard set
export const getSetSourceText = async (id: number): Promise<FlashcardSetSourceResponse> => {
  const response = await fetch(`${config.apiUrl}/api/flashcard-sets/${id}/source-text`);
  if (!response.ok) {
    throw new Error('Failed to fetch source text');
  }
  return response.json();
};

// Create a new flashcard set
export const createFlashcardSet = async (data: FlashcardSetCreateRequest): Promise<FlashcardSetResponse> => {
  const response = await fetch(`${config.apiUrl}/api/flashcard-sets/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error('Failed to create flashcard set');
  }
  return response.json();
};

// Update a flashcard set's details
export const updateFlashcardSet = async (
  id: number,
  data: FlashcardSetUpdateRequest
): Promise<FlashcardSetResponse> => {
  const response = await fetch(`${config.apiUrl}/api/flashcard-sets/${id}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error('Failed to update flashcard set');
  }
  return response.json();
};

// Add a new card to a set
export const addCardToSet = async (
  setId: number,
  card: FlashcardCreateRequest
): Promise<FlashcardResponse> => {
  const response = await fetch(`${config.apiUrl}/api/flashcards/set/${setId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(card),
  });
  if (!response.ok) {
    throw new Error('Failed to add card to set');
  }
  return response.json();
};

// Update an existing card
export const updateCard = async (cardId: number, data: FlashcardUpdateRequest): Promise<FlashcardResponse> => {
  const response = await fetch(`${config.apiUrl}/api/flashcards/${cardId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    throw new Error('Failed to update card');
  }

  return response.json();
};

// Delete a card
export const deleteCard = async (cardId: number): Promise<void> => {
  const response = await fetch(`${config.apiUrl}/api/flashcards/${cardId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to delete card');
  }
};

export interface UnifiedUploadRequest {
  sources: Array<{
    source_type: "file" | "url" | "youtube";
    url?: string;
    video_id?: string;
    title?: string;
    description?: string;
    user_id?: string;
  }>;
  user_id?: string;
}

// Replace the three separate upload functions with one unified function
export const uploadSource = async (
  request: UnifiedUploadRequest,
  files?: File[]
): Promise<SourceFileUploadResponse[]> => {
  const formData = new FormData();
  
  // Add request data as a JSON string
  formData.append('request', JSON.stringify(request));
  
  // Add files if present
  if (files) {
    files.forEach(file => {
      formData.append('files', file);
    });
  }
  
  const response = await fetch(`${config.apiUrl}/api/ai/upload`, {
    method: 'POST',
    body: formData,
  });
  
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to upload source: ${error}`);
  }
  
  return response.json();
};

// Keep these as convenience wrappers for backward compatibility
export const uploadSourceFile = async (file: File, title?: string, description?: string): Promise<SourceFileUploadResponse> => {
  const response = await uploadSource({
    sources: [{
      source_type: "file",
      title,
      description
    }]
  }, [file]);
  return response[0];
};

export const uploadSourceUrl = async (data: URLUploadRequest): Promise<SourceFileUploadResponse> => {
  const response = await uploadSource({
    sources: [{
      source_type: "url",
      url: data.url,
      user_id: data.user_id
    }]
  });
  return response[0];
};

export const uploadYouTubeVideo = async (data: YouTubeUploadRequest): Promise<SourceFileUploadResponse> => {
  const response = await uploadSource({
    sources: [{
      source_type: "youtube",
      video_id: data.video_id,
      title: data.title,
      description: data.description,
      user_id: data.user_id
    }]
  });
  return response[0];
};

// Generate flashcards from a source file using AI
export const generateFlashcards = async (
  sourceFileId: number,
  options: AIGenerateRequest = {}
): Promise<GenerateResponse> => {
  const params = new URLSearchParams({
    model: options.model || 'gpt-4o-mini',
  });
  
  if (options.user_id) {
    params.append('user_id', options.user_id);
  }
  if (options.model_params) {
    params.append('model_params', JSON.stringify(options.model_params));
  }
  if (options.title) {
    params.append('title', options.title);
  }
  if (options.description) {
    params.append('description', options.description);
  }
  if (options.use_sentences !== undefined) {
    params.append('use_sentences', options.use_sentences.toString());
  }
  
  const response = await fetch(`${config.apiUrl}/api/ai/generate/${sourceFileId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: params,
  });
  
  if (!response.ok) {
    throw new Error('Failed to generate flashcards');
  }
  
  return response.json();
};

// Submit feedback for a card
export const submitCardFeedback = async (
  cardId: number,
  data: FlashcardFeedbackRequest
): Promise<FlashcardFeedbackResponse> => {
  const response = await fetch(`${config.apiUrl}/api/flashcards/${cardId}/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to submit feedback');
  }
  
  return response.json();
};

// Get card versions and citations
export const getCardVersions = async (cardId: number): Promise<FlashcardVersionResponse[]> => {
  const response = await fetch(`${config.apiUrl}/api/flashcards/${cardId}/versions`);
  if (!response.ok) {
    throw new Error('Failed to fetch card versions');
  }
  return response.json();
};

// Get card edit history
export const getCardHistory = async (cardId: number): Promise<FlashcardHistoryResponse[]> => {
  const response = await fetch(`${config.apiUrl}/api/flashcards/${cardId}/history`);
  if (!response.ok) {
    throw new Error('Failed to fetch card history');
  }
  return response.json();
};

// Get card feedback
export const getCardFeedback = async (cardId: number): Promise<FlashcardFeedbackDetailResponse[]> => {
  const response = await fetch(`${config.apiUrl}/api/flashcards/${cardId}/feedback`);
  if (!response.ok) {
    throw new Error('Failed to fetch card feedback');
  }
  return response.json();
};
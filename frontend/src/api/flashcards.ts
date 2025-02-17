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
  YouTubeUploadRequest
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

// Upload a source file for AI generation
export const uploadSourceFile = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch(`${config.apiUrl}/api/ai/upload`, {
    method: 'POST',
    body: formData,
  });
  
  if (!response.ok) {
    throw new Error('Failed to upload file');
  }
  
  return response.json();
};

// Upload a URL for AI generation
export const uploadSourceUrl = async (data: URLUploadRequest): Promise<UploadResponse> => {
  const response = await fetch(`${config.apiUrl}/api/ai/upload/url`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to upload URL');
  }
  
  return response.json();
};

// Upload a YouTube video for AI generation
export const uploadYouTubeVideo = async (data: YouTubeUploadRequest): Promise<UploadResponse> => {
  const response = await fetch(`${config.apiUrl}/api/ai/upload/youtube`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to upload YouTube video');
  }
  
  return response.json();
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
import config from '../config';
import {
  StudySession,
  StudySessionCreateRequest,
  CardReview,
  CardReviewCreateRequest,
  ReviewScore,
  ReviewScoreCreateRequest,
  ScoreType,
  CompleteStudySessionResponse
} from '@/types';

// Create a new study session
export const createStudySession = async (
  data: StudySessionCreateRequest,
  userId: string
): Promise<StudySession> => {
  const requestData = { 
    ...data,
    session_type: data.session_type.toString()  // Convert enum to string
  };
  
  const response = await fetch(`${config.apiUrl}/api/study-sessions/?user_id=${encodeURIComponent(userId)}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(requestData),
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to create study session: ${errorText}`);
  }
  
  return response.json();
};

// Get a study session by ID
export const getStudySession = async (sessionId: number): Promise<StudySession> => {
  const response = await fetch(`${config.apiUrl}/api/study-sessions/${sessionId}`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch study session');
  }
  
  return response.json();
};

// Create a new card review in a session
export const createCardReview = async (
  sessionId: number,
  data: CardReviewCreateRequest
): Promise<CardReview> => {
  const response = await fetch(`${config.apiUrl}/api/study-sessions/${sessionId}/reviews`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error('Failed to create card review');
  }
  
  return response.json();
};

// Add a score to a card review
export const createReviewScore = async (
  reviewId: number,
  data: ReviewScoreCreateRequest
): Promise<ReviewScore> => {
  const requestData = {
    ...data,
    score_type: data.score_type.toString(),  // Convert enum to string
    grade: data.grade?.toString(),  // Convert enum to string
    confidence: data.confidence?.toString()  // Convert enum to string
  };

  const response = await fetch(`${config.apiUrl}/api/study-sessions/reviews/${reviewId}/scores`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(requestData),
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to create review score: ${errorText}`);
  }
  
  return response.json();
};

// Complete a study session
export const completeStudySession = async (sessionId: number): Promise<CompleteStudySessionResponse> => {
  const response = await fetch(`${config.apiUrl}/api/study-sessions/${sessionId}/complete`, {
    method: 'PATCH',
  });
  
  if (!response.ok) {
    throw new Error('Failed to complete study session');
  }
  
  return response.json();
};

// Get scores for a review
export const getReviewScores = async (reviewId: number): Promise<ReviewScore[]> => {
  const response = await fetch(`${config.apiUrl}/api/study-sessions/reviews/${reviewId}/scores`);
  
  if (!response.ok) {
    throw new Error('Failed to fetch review scores');
  }
  
  return response.json();
};

// Poll for AI scores until they're ready or max attempts reached
export const waitForAIScore = async (
  reviewId: number,
  maxAttempts: number = 10,
  interval: number = 500
): Promise<ReviewScore[]> => {
  console.log(`Starting to poll for AI scores for review ${reviewId}`);
  
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    console.log(`Polling attempt ${attempt + 1}/${maxAttempts}`);
    
    const scores = await getReviewScores(reviewId);
    console.log('Received scores:', scores);
    
    const finalScore = scores.find(s => s.score_type === ScoreType.FINAL_AI);
    console.log('Final AI score:', finalScore);
    
    if (!finalScore) {
      console.log('No final AI score found, waiting...');
      await new Promise(resolve => setTimeout(resolve, interval));
      continue;
    }
    
    const status = finalScore.score_metadata?.status;
    console.log('Score status:', status);
    
    if (status === 'completed') {
      console.log('Scoring completed, returning all non-self-assessed scores');
      return scores.filter(s => s.score_type !== ScoreType.SELF_ASSESSED);
    }
    
    if (status === 'error') {
      console.warn('Scoring error detected');
      return [];
    }
    
    console.log(`Status is ${status}, waiting for next attempt...`);
    await new Promise(resolve => setTimeout(resolve, interval));
  }
  
  console.warn(`Max polling attempts (${maxAttempts}) reached without completion`);
  return [];
};

// Submit an answer and wait for AI scoring
export const submitAnswerAndWaitForScore = async (
  sessionId: number,
  data: CardReviewCreateRequest
): Promise<{ review: CardReview; scores: ReviewScore[] }> => {
  const review = await createCardReview(sessionId, data);
  const scores = await waitForAIScore(review.id);
  return { review, scores };
}; 
'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { AnswerMethod, CardReview, ReviewScore } from '@/types';
import { submitAnswerAndWaitForScore } from '@/api/study-sessions';

interface AnswerSubmissionProps {
  sessionId: number;
  flashcardId: number;
  onSubmit?: (answer: string) => void;
  onScoreComplete?: (review: CardReview, scores: ReviewScore[]) => void;
  isSubmitting: boolean;
  showAnswer: boolean;
}

export function AnswerSubmission({ 
  sessionId, 
  flashcardId, 
  onSubmit, 
  onScoreComplete,
  isSubmitting,
  showAnswer 
}: AnswerSubmissionProps) {
  const [answer, setAnswer] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!answer.trim() || isSubmitting) return;

    try {
      if (onSubmit) {
        onSubmit(answer.trim());
      } else {
        console.log('Submitting answer and waiting for score...');
        const { review, scores } = await submitAnswerAndWaitForScore(sessionId, {
          flashcard_id: flashcardId,
          answer_method: AnswerMethod.TEXT,
          user_answer: answer.trim()
        });
        
        console.log('Received response:', { review, scores });
        onScoreComplete?.(review, scores);
      }
      
      setAnswer('');
      
    } catch (err) {
      console.error('Error submitting answer:', err);
      setError(err instanceof Error ? err.message : 'Failed to submit answer');
    }
  };

  if (showAnswer) return null;

  return (
    <form onSubmit={handleSubmit} className="mt-6">
      <Card>
        <CardContent className="p-6">
          <div className="mb-4">
            <h3 className="text-sm font-medium text-slate-500 mb-2">Your Answer</h3>
            <Textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Type your answer here..."
              className="min-h-[100px]"
              disabled={isSubmitting}
            />
          </div>
          
          {error && (
            <div className="mb-4 text-sm text-red-600">
              {error}
            </div>
          )}
          
          <div className="flex justify-end">
            <Button 
              type="submit" 
              disabled={!answer.trim() || isSubmitting}
              className="flex items-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Submitting...
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                  </svg>
                  Submit Answer
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </form>
  );
} 
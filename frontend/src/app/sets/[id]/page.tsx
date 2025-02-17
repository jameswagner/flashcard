'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { use } from 'react';
import { 
  FlashcardSetDetail,
  StudySession,
  StudySessionType,
  AnswerMethod,
  ReviewGrade,
  ReviewConfidence,
  ScoreType,
  CardReview,
  ReviewScore
} from '@/types';
import { getFlashcardSet } from '@/api/flashcards';
import { 
  createStudySession,
  submitAnswerAndWaitForScore,
  createReviewScore,
  completeStudySession,
  createCardReview,
  getStudySession
} from '@/api/study-sessions';
import { Card, CardContent } from '@/components/ui/card';
import { CardDisplay } from './components/CardDisplay';
import { AnswerSubmission } from './components/AnswerSubmission';
import { ScoreDisplay } from './components/ScoreDisplay';
import { SelfAssessment } from './components/SelfAssessment';
import { SessionComplete } from './components/SessionComplete';

export default function StudyPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const [set, setSet] = useState<FlashcardSetDetail | null>(null);
  const [session, setSession] = useState<StudySession | null>(null);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [scores, setScores] = useState<ReviewScore[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [currentReviewId, setCurrentReviewId] = useState<number | null>(null);
  const [submittedAnswer, setSubmittedAnswer] = useState<string>('');

  useEffect(() => {
    const fetchSet = async () => {
      try {
        const data = await getFlashcardSet(parseInt(resolvedParams.id));
        setSet(data);
        
        // Create a new study session
        const newSession = await createStudySession({
          set_id: data.id,
          session_type: StudySessionType.REVIEW
        }, 'user123'); // TODO: Get real user ID
        
        setSession(newSession);
      } catch (err) {
        setError('Failed to load flashcard set');
        console.error('Error:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSet();
  }, [resolvedParams.id]);

  const handleShowAnswer = async () => {
    if (!session || !set) {
      return;
    }
    
    try {
      const currentCard = set.flashcards[currentCardIndex];
      const review = await createCardReview(session.id, {
        flashcard_id: currentCard.id,
        answer_method: AnswerMethod.TEXT
      });
      
      setCurrentReviewId(review.id);
      setShowAnswer(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to show answer');
    }
  };

  const handleSubmitAnswer = async (answer: string) => {
    if (!session || !set) return;
    
    setIsSubmitting(true);
    setError(null);
    
    try {
      const currentCard = set.flashcards[currentCardIndex];
      const { review, scores: newScores } = await submitAnswerAndWaitForScore(session.id, {
        flashcard_id: currentCard.id,
        answer_method: AnswerMethod.TEXT,
        user_answer: answer
      });
      
      setCurrentReviewId(review.id);
      setScores(newScores);
      setShowAnswer(true);
      setSubmittedAnswer(answer);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit answer');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGradeAnswer = async (grade: ReviewGrade, confidence: ReviewConfidence) => {
    if (!session || !set || !currentReviewId) {
      return;
    }
    
    try {
      await createReviewScore(currentReviewId, {
        score_type: ScoreType.SELF_ASSESSED,
        score: (() => {
          switch (grade) {
            case ReviewGrade.CORRECT:
              return 1.0;
            case ReviewGrade.PARTIALLY_CORRECT:
              return 0.5;
            case ReviewGrade.TOO_EASY:
              return 1.0;
            case ReviewGrade.INCORRECT:
              return 0.0;
            default:
              return 0.0;
          }
        })(),
        grade,
        confidence
      });
      
      // Move to next card or complete session
      if (currentCardIndex < set.flashcards.length - 1) {
        setCurrentCardIndex(prev => prev + 1);
        setShowAnswer(false);
        setScores([]);
        setCurrentReviewId(null);
        setSubmittedAnswer('');
      } else {
        const completionResult = await completeStudySession(session.id);
        const updatedSession = {
          ...session,
          completed_at: new Date().toISOString(),
          ...completionResult.statistics
        };
        setSession(updatedSession);
        setIsComplete(true);
      }
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit grade');
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="w-96">
          <CardContent className="pt-6 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading flashcard set...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error || !set || !session) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="w-96">
          <CardContent className="pt-6 text-center">
            <div className="inline-flex items-center justify-center flex-shrink-0 w-12 h-12 rounded-full bg-red-100 mb-4">
              <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <p className="text-gray-900 font-semibold">{error || 'Failed to load set'}</p>
            <div className="mt-4">
              <button
                onClick={() => router.push('/sets')}
                className="text-blue-600 hover:text-blue-700 font-medium"
              >
                Back to Sets
              </button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (isComplete) {
    return (
      <SessionComplete
        session={session}
        onRestart={() => router.refresh()}
        onBack={() => router.push(`/sets/${set.id}`)}
      />
    );
  }

  const currentCard = set.flashcards[currentCardIndex];

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">{set.title}</h1>
          <div className="mt-2 flex items-center gap-4">
            <span className="text-sm text-gray-600">
              Card {currentCardIndex + 1} of {set.flashcards.length}
            </span>
            <div className="h-1.5 flex-1 bg-gray-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-blue-500 rounded-full transition-all duration-300"
                style={{ width: `${((currentCardIndex + 1) / set.flashcards.length) * 100}%` }}
              />
            </div>
          </div>
        </div>

        {/* Cards */}
        <CardDisplay
          card={currentCard}
          showAnswer={showAnswer}
          onShowAnswer={handleShowAnswer}
        />

        {/* Answer Submission */}
        <AnswerSubmission
          sessionId={session.id}
          flashcardId={currentCard.id}
          onSubmit={handleSubmitAnswer}
          isSubmitting={isSubmitting}
          showAnswer={showAnswer}
          onScoreComplete={(review, scores) => {
            console.log('Score complete callback received:', { review, scores });
            setCurrentReviewId(review.id);
            setScores(scores);
            setShowAnswer(true);
          }}
        />

        {/* Score Display */}
        <ScoreDisplay
          scores={scores}
          isLoading={isSubmitting}
          submittedAnswer={submittedAnswer}
        />

        {/* Self Assessment */}
        {showAnswer && (
          <SelfAssessment
            onSubmit={(grade, confidence) => {
              handleGradeAnswer(grade, confidence);
            }}
            isSubmitting={isSubmitting}
          />
        )}
      </div>
    </div>
  );
} 
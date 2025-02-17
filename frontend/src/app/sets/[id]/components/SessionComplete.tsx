import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { StudySession, ScoreType } from '@/types';

interface SessionCompleteProps {
  session: StudySession;
  onRestart: () => void;
  onBack: () => void;
}

export function SessionComplete({ session, onRestart, onBack }: SessionCompleteProps) {
  const formatScore = (score: number) => `${(score * 100).toFixed(1)}%`;
  
  // Calculate accuracy from available data
  const accuracy = session.cards_reviewed > 0 ? (session.correct_count / session.cards_reviewed) : 0;

  // Get AI score averages
  const aiScores = session.ai_scores || {};

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <Card>
          <CardContent className="pt-6">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-gray-900 mb-6">Session Complete!</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                {/* Basic Stats */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h3 className="text-lg font-semibold text-gray-700 mb-2">Basic Stats</h3>
                  <div className="space-y-2">
                    <p className="text-gray-600">
                      Cards Reviewed: <span className="font-medium">{session.cards_reviewed}</span>
                    </p>
                    <p className="text-gray-600">
                      Correct: <span className="font-medium text-green-600">{session.correct_count}</span>
                    </p>
                    <p className="text-gray-600">
                      Incorrect: <span className="font-medium text-red-600">{session.incorrect_count}</span>
                    </p>
                    <p className="text-gray-600">
                      Accuracy: <span className="font-medium">{formatScore(accuracy)}</span>
                    </p>
                  </div>
                </div>
                
                {/* Self Assessment Scores */}
                <div className="bg-white p-4 rounded-lg shadow">
                  <h3 className="text-lg font-semibold text-gray-700 mb-2">Self Assessment</h3>
                  <div className="space-y-2">
                    <p className="text-gray-600">
                      Average Score: <span className="font-medium">{formatScore(session.average_self_assessed_score || 0)}</span>
                    </p>
                    <p className="text-gray-600">
                      Average Confidence: <span className="font-medium">{formatScore(session.average_confidence || 0)}</span>
                    </p>
                  </div>
                </div>

                {/* AI Scores */}
                <div className="bg-white p-4 rounded-lg shadow md:col-span-2">
                  <h3 className="text-lg font-semibold text-gray-700 mb-2">AI Assessment Averages</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Final AI Score */}
                    {aiScores[ScoreType.FINAL_AI] !== undefined && (
                      <div className="space-y-2">
                        <p className="text-gray-600">
                          Overall AI Score: <span className="font-medium">{formatScore(aiScores[ScoreType.FINAL_AI])}</span>
                        </p>
                      </div>
                    )}
                    
                    {/* NLI Scores */}
                    <div className="space-y-2">
                      {aiScores[ScoreType.NLI_ENTAILMENT] !== undefined && (
                        <p className="text-gray-600">
                          NLI Entailment: <span className="font-medium">{formatScore(aiScores[ScoreType.NLI_ENTAILMENT])}</span>
                        </p>
                      )}
                      {aiScores[ScoreType.NLI_CONTRADICTION] !== undefined && (
                        <p className="text-gray-600">
                          NLI Contradiction: <span className="font-medium">{formatScore(aiScores[ScoreType.NLI_CONTRADICTION])}</span>
                        </p>
                      )}
                    </div>
                    
                    {/* Semantic Scores */}
                    <div className="space-y-2">
                      {aiScores[ScoreType.SEMANTIC_SIMILARITY] !== undefined && (
                        <p className="text-gray-600">
                          Semantic Similarity: <span className="font-medium">{formatScore(aiScores[ScoreType.SEMANTIC_SIMILARITY])}</span>
                        </p>
                      )}
                      {aiScores[ScoreType.SEMANTIC_ROLE] !== undefined && (
                        <p className="text-gray-600">
                          Semantic Role: <span className="font-medium">{formatScore(aiScores[ScoreType.SEMANTIC_ROLE])}</span>
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="flex justify-center space-x-4">
                <Button onClick={onRestart} variant="default">
                  Start New Session
                </Button>
                <Button onClick={onBack} variant="outline">
                  Back to Set
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 
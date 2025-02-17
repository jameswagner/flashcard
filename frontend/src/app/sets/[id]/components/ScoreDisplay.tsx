import { Card, CardContent } from '@/components/ui/card';
import { ReviewScore, ScoreType, ScoreMetadata } from '@/types';

interface ScoreDisplayProps {
  scores: ReviewScore[];
  isLoading?: boolean;
  submittedAnswer?: string;
}

export function ScoreDisplay({ scores, isLoading, submittedAnswer }: ScoreDisplayProps) {
  console.log('ScoreDisplay render:', { scores, isLoading });
  
  if ((!scores || scores.length === 0) && !isLoading) {
    console.log('No scores to display and not loading, returning null');
    return null;
  }

  const formatScore = (score: number) => `${(score * 100).toFixed(1)}%`;

  const renderModelScores = (scores: Record<string, number>) => (
    <div className="space-y-2">
      {Object.entries(scores).map(([model, score]) => (
        <div key={model} className="flex justify-between text-sm">
          <span>{model}:</span>
          <span>{formatScore(score)}</span>
        </div>
      ))}
    </div>
  );

  const renderRoleScores = (scores: Record<string, number>) => (
    <div className="space-y-2">
      {Object.entries(scores).map(([role, score]) => (
        <div key={role} className="flex justify-between text-sm">
          <span>{role}:</span>
          <span>{formatScore(score)}</span>
        </div>
      ))}
    </div>
  );

  // Get the final AI score
  const finalScore = scores?.find(s => s.score_type === ScoreType.FINAL_AI);
  console.log('Final AI score:', finalScore);
  
  // Get component scores
  const nliEntailment = scores?.find(s => s.score_type === ScoreType.NLI_ENTAILMENT);
  const nliContradiction = scores?.find(s => s.score_type === ScoreType.NLI_CONTRADICTION);
  const semanticSimilarity = scores?.find(s => s.score_type === ScoreType.SEMANTIC_SIMILARITY);
  const semanticRole = scores?.find(s => s.score_type === ScoreType.SEMANTIC_ROLE);
  
  console.log('Component scores:', {
    nliEntailment,
    nliContradiction,
    semanticSimilarity,
    semanticRole
  });

  // Cast score_metadata to ScoreMetadata type for proper typing
  const metadata = finalScore?.score_metadata as ScoreMetadata | undefined;
  console.log('Score metadata:', metadata);

  return (
    <Card className="mt-6">
      <CardContent className="p-6">
        <h3 className="text-sm font-medium text-slate-500 mb-4">AI Assessment</h3>
        
        {isLoading ? (
          <div className="flex items-center justify-center py-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          </div>
        ) : scores && scores.length > 0 ? (
          <div className="space-y-6">
            {/* User's Answer */}
            {submittedAnswer && (
              <div>
                <div className="text-sm font-medium text-slate-700 mb-2">Your Answer</div>
                <div className="text-sm text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-200">
                  {submittedAnswer}
                </div>
              </div>
            )}

            {/* Overall Score */}
            {finalScore && (
              <div>
                <div className="text-sm font-medium text-slate-700 mb-1">Overall Score</div>
                <div className="text-2xl font-bold text-blue-600">
                  {formatScore(finalScore.score)}
                </div>
              </div>
            )}

            {/* NLI Scores */}
            {(nliEntailment || nliContradiction) && (
              <div>
                <div className="text-sm font-medium text-slate-700 mb-2">Natural Language Understanding</div>
                <div className="space-y-2">
                  {nliEntailment && (
                    <div className="flex justify-between text-sm">
                      <span>Entailment:</span>
                      <span>{formatScore(nliEntailment.score)}</span>
                    </div>
                  )}
                  {nliContradiction && (
                    <div className="flex justify-between text-sm">
                      <span>Contradiction:</span>
                      <span>{formatScore(nliContradiction.score)}</span>
                    </div>
                  )}
                  {metadata?.nli?.was_contradiction && (
                    <div className="text-sm text-red-500 mt-1">
                      Warning: Answer contradicts the correct answer
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Semantic Similarity */}
            {semanticSimilarity && (
              <div>
                <div className="text-sm font-medium text-slate-700 mb-2">Semantic Similarity</div>
                {(semanticSimilarity.score_metadata as ScoreMetadata)?.similarity?.model_scores ? (
                  renderModelScores((semanticSimilarity.score_metadata as ScoreMetadata).similarity!.model_scores)
                ) : (
                  <div className="flex justify-between text-sm">
                    <span>Overall:</span>
                    <span>{formatScore(semanticSimilarity.score)}</span>
                  </div>
                )}
              </div>
            )}

            {/* Semantic Role Analysis */}
            {semanticRole && (
              <div>
                <div className="text-sm font-medium text-slate-700 mb-2">Semantic Role Analysis</div>
                {(semanticRole.score_metadata as ScoreMetadata)?.srl?.role_scores ? (
                  renderRoleScores((semanticRole.score_metadata as ScoreMetadata).srl!.role_scores)
                ) : (
                  <div className="flex justify-between text-sm">
                    <span>Overall:</span>
                    <span>{formatScore(semanticRole.score)}</span>
                  </div>
                )}
                
                {(semanticRole.score_metadata as ScoreMetadata)?.srl?.missing_concepts?.length > 0 && (
                  <div className="mt-2">
                    <div className="text-sm font-medium text-slate-700">Missing Concepts:</div>
                    <ul className="list-disc list-inside text-sm text-slate-600 mt-1">
                      {((semanticRole.score_metadata as ScoreMetadata)?.srl?.missing_concepts || []).map((concept: string, idx: number) => (
                        <li key={idx}>{concept}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-slate-500">
            No score data available
          </div>
        )}
      </CardContent>
    </Card>
  );
} 
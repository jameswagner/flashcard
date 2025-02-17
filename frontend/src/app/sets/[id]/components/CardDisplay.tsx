import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Flashcard } from '@/types';

interface CardDisplayProps {
  card: Flashcard;
  showAnswer: boolean;
  onShowAnswer: () => void;
}

export function CardDisplay({ card, showAnswer, onShowAnswer }: CardDisplayProps) {
  return (
    <div className="grid grid-cols-2 gap-6">
      {/* Question Card */}
      <Card>
        <CardContent className="p-6">
          <div className="mb-4">
            <h3 className="text-sm font-medium text-slate-500 mb-2">Question</h3>
            <p className="text-lg text-slate-900">{card.front}</p>
          </div>
        </CardContent>
      </Card>

      {/* Answer Card */}
      <Card>
        <CardContent className="p-6">
          <div className="mb-4 relative">
            <h3 className="text-sm font-medium text-slate-500 mb-2">Answer</h3>
            <div className={`transition-opacity duration-200 ${showAnswer ? 'opacity-100' : 'opacity-0'}`}>
              <p className="text-lg text-slate-900">{card.back}</p>
            </div>
            
            {!showAnswer && (
              <div className="absolute inset-0 flex items-center justify-center">
                <Button
                  onClick={onShowAnswer}
                  variant="outline"
                  className="flex items-center gap-2"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                  Show Answer
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 
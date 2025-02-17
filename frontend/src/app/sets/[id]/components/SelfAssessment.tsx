import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ReviewGrade, ReviewConfidence } from '@/types';

interface SelfAssessmentProps {
  onSubmit: (grade: ReviewGrade, confidence: ReviewConfidence) => void;
  isSubmitting?: boolean;
}

export function SelfAssessment({ onSubmit, isSubmitting }: SelfAssessmentProps) {
  return (
    <Card className="mt-6">
      <CardContent className="p-6">
        <h3 className="text-sm font-medium text-slate-500 mb-4">Self Assessment</h3>
        
        <div className="space-y-6">
          {/* Grade Selection */}
          <div>
            <div className="text-sm font-medium text-slate-700 mb-3">How well did you do?</div>
            <div className="grid grid-cols-2 gap-3">
              <Button
                variant="outline"
                onClick={() => onSubmit(ReviewGrade.CORRECT, ReviewConfidence.HIGH)}
                disabled={isSubmitting}
                className="flex items-center justify-center gap-2 py-6 hover:bg-green-50 hover:text-green-700 hover:border-green-200"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
                Got it right
              </Button>
              
              <Button
                variant="outline"
                onClick={() => onSubmit(ReviewGrade.PARTIALLY_CORRECT, ReviewConfidence.MEDIUM)}
                disabled={isSubmitting}
                className="flex items-center justify-center gap-2 py-6 hover:bg-yellow-50 hover:text-yellow-700 hover:border-yellow-200"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                Partially correct
              </Button>
              
              <Button
                variant="outline"
                onClick={() => onSubmit(ReviewGrade.INCORRECT, ReviewConfidence.LOW)}
                disabled={isSubmitting}
                className="flex items-center justify-center gap-2 py-6 hover:bg-red-50 hover:text-red-700 hover:border-red-200"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
                Got it wrong
              </Button>
              
              <Button
                variant="outline"
                onClick={() => onSubmit(ReviewGrade.TOO_EASY, ReviewConfidence.PERFECT)}
                disabled={isSubmitting}
                className="flex items-center justify-center gap-2 py-6 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-200"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Too easy
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
} 
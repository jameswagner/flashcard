'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { use } from 'react';
import { FlashcardSetDetail } from '@/types';
import { getFlashcardSet } from '@/api/flashcards';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { EditSetForm } from './components/EditSetForm';

export default function EditSetPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [set, setSet] = useState<FlashcardSetDetail | null>(null);

  useEffect(() => {
    const fetchSet = async () => {
      try {
        const data = await getFlashcardSet(parseInt(resolvedParams.id));
        setSet(data);
      } catch (err) {
        setError('Failed to load flashcard set');
        console.error('Error fetching set:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSet();
  }, [resolvedParams.id]);

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

  if (error || !set) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="w-96">
          <CardContent className="pt-6 text-center">
            <div className="inline-flex items-center justify-center flex-shrink-0 w-12 h-12 rounded-full bg-red-100 mb-4">
              <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <p className="text-gray-900 font-semibold">{error}</p>
            <div className="mt-4 space-x-4">
              <Button
                variant="link"
                onClick={() => window.location.reload()}
              >
                Try again
              </Button>
              <Button
                variant="link"
                onClick={() => router.push('/sets')}
              >
                Back to sets
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Edit Set</h1>
          <p className="mt-2 text-sm text-gray-600">Modify your flashcard set details and cards.</p>
        </div>

        <EditSetForm initialSet={set} />
      </div>
    </div>
  );
} 
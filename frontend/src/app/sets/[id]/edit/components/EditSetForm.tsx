'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  FlashcardSetDetail,
  Flashcard,
  FlashcardSetSourceResponse
} from '@/types';
import { updateFlashcardSet, addCardToSet, updateCard, deleteCard, submitCardFeedback, getSetSourceText } from '@/api/flashcards';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { SourceTextDisplay } from './SourceTextDisplay';

interface FlashcardFeedbackState {
  type?: 'thumbs_up' | 'thumbs_down';
  category?: string;
  text?: string;
}

interface EditSetFormProps {
  initialSet: FlashcardSetDetail;
  onSaveComplete?: () => void;
}

export function EditSetForm({ initialSet, onSaveComplete }: EditSetFormProps) {
  const router = useRouter();
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState(initialSet.title);
  const [description, setDescription] = useState(initialSet.description || '');
  const [flashcards, setFlashcards] = useState<Flashcard[]>(
    initialSet.flashcards.map(card => ({ ...card, isNew: false }))
  );
  const [deletedFlashcardIds, setDeletedFlashcardIds] = useState<number[]>([]);
  const [flashcardFeedback, setFlashcardFeedback] = useState<Record<number, FlashcardFeedbackState>>({});
  const [sourceText, setSourceText] = useState<FlashcardSetSourceResponse | null>(null);
  const [isSourceTextVisible, setIsSourceTextVisible] = useState(false);

  const handleAddFlashcard = () => {
    setFlashcards([
      ...flashcards,
      {
        id: -1 * (flashcards.length + 1), // Temporary negative ID for new cards
        front: '',
        back: '',
        isNew: true,
        card_index: flashcards.length // Set card_index to current length
      },
    ]);
  };

  const handleRemoveFlashcard = (flashcardId: number) => {
    if (flashcardId > 0) {  // Only track deletion of existing flashcards
      setDeletedFlashcardIds([...deletedFlashcardIds, flashcardId]);
    }
    setFlashcards(flashcards.filter(card => card.id !== flashcardId));
  };

  const handleFlashcardChange = (index: number, field: keyof Flashcard, value: string) => {
    const newFlashcards = [...flashcards];
    newFlashcards[index] = {
      ...newFlashcards[index],
      [field]: value,
      card_index: index // Ensure card_index is always set correctly
    };
    setFlashcards(newFlashcards);
  };

  const handleFeedback = (flashcardId: number, type: 'thumbs_up' | 'thumbs_down') => {
    setFlashcardFeedback(prev => ({
      ...prev,
      [flashcardId]: { ...prev[flashcardId], type }
    }));
  };

  const handleFeedbackCategory = (flashcardId: number, category: string) => {
    setFlashcardFeedback(prev => ({
      ...prev,
      [flashcardId]: { ...prev[flashcardId], category }
    }));
  };

  const handleFeedbackText = (flashcardId: number, text: string) => {
    setFlashcardFeedback(prev => ({
      ...prev,
      [flashcardId]: { ...prev[flashcardId], text }
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSaving(true);

    try {
      // Update the set
      await updateFlashcardSet(initialSet.id, {
        title,
        description,
      });

      // Process each flashcard
      for (let i = 0; i < flashcards.length; i++) {
        const card = flashcards[i];
        
        if (card.isNew) {
          // For new cards, only send front and back
          await addCardToSet(initialSet.id, {
            front: card.front,
            back: card.back
          });
        } else {
          // For existing cards, only send the fields that changed
          const updateData: { front?: string; back?: string } = {};
          if (card.front !== initialSet.flashcards.find(c => c.id === card.id)?.front) {
            updateData.front = card.front;
          }
          if (card.back !== initialSet.flashcards.find(c => c.id === card.id)?.back) {
            updateData.back = card.back;
          }
          
          // Only update if there are changes
          if (Object.keys(updateData).length > 0) {
            await updateCard(card.id, updateData);
          }
          
          // Submit feedback if provided
          const feedback = flashcardFeedback[card.id];
          if (feedback?.type) {
            await submitCardFeedback(card.id, {
              feedback_type: feedback.type,
              feedback_category: feedback.category,
              feedback_text: feedback.text
            });
          }
        }
      }

      // Handle flashcard deletions
      for (const flashcardId of deletedFlashcardIds) {
        await deleteCard(flashcardId);
      }

      onSaveComplete?.();
      router.push(`/sets/${initialSet.id}`);
    } catch (err) {
      setError('Failed to update flashcard set');
      console.error('Error updating flashcard set:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const fetchSourceText = async () => {
    try {
      const response = await getSetSourceText(initialSet.id);
      setSourceText(response);
    } catch (err) {
      console.error('Error fetching source text:', err);
      setError('Failed to fetch source text');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="min-h-screen bg-gradient-to-b from-slate-50 to-white pb-24">
      <div className="container max-w-[1600px] mx-auto px-4 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50/50 backdrop-blur-sm border border-red-100 rounded-xl">
            <div className="flex">
              <svg className="h-5 w-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="ml-3 text-sm text-red-600">{error}</p>
            </div>
          </div>
        )}

        {/* Smart Collapsing Header */}
        <div className="sticky top-0 z-20 bg-white/80 backdrop-blur-sm border-b border-slate-200 -mx-4 px-4 py-4 transition-all duration-200">
          <div className="flex items-center justify-between mb-3">
            <div className="flex-1 min-w-0 mr-4">
              <Input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                className="text-2xl font-semibold bg-transparent border-0 p-0 focus:ring-0 placeholder-slate-400"
                placeholder="Set Title"
              />
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-600">Total Cards: {flashcards.length}</span>
              <Button
                type="button"
                onClick={handleAddFlashcard}
                size="sm"
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                </svg>
                Add Card
              </Button>
            </div>
          </div>
          
          <div className="relative">
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add a description (optional)"
              rows={1}
              className="text-sm bg-transparent border-0 p-0 focus:ring-0 placeholder-slate-400 resize-none overflow-hidden"
            />
            {description && description.length > 100 && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="absolute right-0 top-0 text-xs text-blue-600 hover:text-blue-700"
                onClick={() => {
                  const textarea = document.querySelector('textarea');
                  if (textarea) {
                    textarea.rows = textarea.rows === 1 ? 4 : 1;
                  }
                }}
              >
                {document.querySelector('textarea')?.rows === 1 ? 'Show More' : 'Show Less'}
              </Button>
            )}
          </div>

          {/* Source Text Toggle Button */}
          <div className="mt-4 border-t border-slate-200 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                if (!sourceText) {
                  fetchSourceText();
                }
                setIsSourceTextVisible(!isSourceTextVisible);
              }}
              className="flex items-center gap-2"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {isSourceTextVisible ? 'Hide Source Text' : 'Show Source Text'}
            </Button>
          </div>

          {/* Source Text Panel */}
          {isSourceTextVisible && (
            <div className="mt-4 space-y-4 max-h-[500px] overflow-y-auto">
              {sourceText ? (
                sourceText.sources.map((source) => (
                  <SourceTextDisplay key={source.source_file_id} source={source} />
                ))
              ) : (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                  <p className="mt-4 text-slate-600">Loading source text...</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Flashcards Grid */}
        <div className="mt-6 space-y-8">
          {flashcards.sort((a, b) => (a.card_index || 0) - (b.card_index || 0)).map((flashcard, index) => (
            <div key={flashcard.id} className="relative">
              {/* Card Header with Number */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-50 text-blue-700 font-semibold text-sm border border-blue-100">
                    {index + 1}
                  </span>
                  {flashcard.is_ai_generated && (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-700/10">
                      <svg className="h-3 w-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      AI Generated
                    </span>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleRemoveFlashcard(flashcard.id)}
                  className="hover:bg-red-50 hover:text-red-600"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </Button>
              </div>

              {/* Card Content */}
              <div className="grid md:grid-cols-2 gap-6">
                {/* Front of Card */}
                <Card className="backdrop-blur-sm bg-white/50 shadow-sm border-0 ring-1 ring-slate-100 hover:ring-blue-100 transition-all duration-300">
                  <CardContent className="p-6">
                    <Label className="text-sm font-medium text-slate-700 flex items-center gap-2">
                      <span className="inline-block w-2 h-2 rounded-full bg-emerald-400"></span>
                      Front
                    </Label>
                    <Textarea
                      value={flashcard.front}
                      onChange={(e) => handleFlashcardChange(index, 'front', e.target.value)}
                      rows={4}
                      required
                      className="mt-2 border-slate-200 focus:border-blue-500 focus:ring-blue-500/20 resize-none text-base"
                    />
                  </CardContent>
                </Card>

                {/* Back of Card */}
                <Card className="backdrop-blur-sm bg-white/50 shadow-sm border-0 ring-1 ring-slate-100 hover:ring-blue-100 transition-all duration-300">
                  <CardContent className="p-6">
                    <Label className="text-sm font-medium text-slate-700 flex items-center gap-2">
                      <span className="inline-block w-2 h-2 rounded-full bg-amber-400"></span>
                      Back
                    </Label>
                    <Textarea
                      value={flashcard.back}
                      onChange={(e) => handleFlashcardChange(index, 'back', e.target.value)}
                      rows={4}
                      required
                      className="mt-2 border-slate-200 focus:border-blue-500 focus:ring-blue-500/20 resize-none text-base"
                    />
                  </CardContent>
                </Card>
              </div>

              {/* Expandable Citations & Feedback */}
              {((flashcard.citations && flashcard.citations.length > 0) || flashcard.is_ai_generated) && (
                <div className="mt-4">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-sm text-slate-600 hover:text-slate-900"
                    onClick={() => {
                      const element = document.getElementById(`card-${flashcard.id}-details`);
                      if (element) {
                        element.style.display = element.style.display === 'none' ? 'block' : 'none';
                      }
                    }}
                  >
                    <svg className="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Show Details
                  </Button>

                  <div id={`card-${flashcard.id}-details`} className="mt-4 space-y-6" style={{ display: 'none' }}>
                    {/* Citations Section */}
                    {flashcard.citations && flashcard.citations.length > 0 ? (
                      <div>
                        <Label className="text-xs font-medium uppercase tracking-wide text-slate-500">Source Citations</Label>
                        <div className="mt-2 space-y-2">
                          {flashcard.citations.map((citation, index) => (
                            <div key={index} className="bg-slate-50/50 p-4 rounded-lg text-sm text-slate-600 ring-1 ring-inset ring-slate-100">
                              {citation.preview_text || `[No preview text available - ${citation.citation_type}]`}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div>
                        <Label className="text-xs font-medium uppercase tracking-wide text-slate-500">Source Citations</Label>
                        <div className="mt-2 p-4 rounded-lg text-sm text-slate-500 bg-slate-50/50 ring-1 ring-inset ring-slate-100">
                          No citations available for this flashcard.
                        </div>
                      </div>
                    )}

                    {/* Key Terms Section */}
                    <div className="mt-6">
                      <Label className="text-xs font-medium uppercase tracking-wide text-slate-500">Key Terms</Label>
                      {flashcard.answer_key_terms && flashcard.answer_key_terms.length > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {flashcard.answer_key_terms.map((term, index) => (
                            <span key={index} className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-700/10">
                              {term.terms[0]}
                              {term.terms.length > 1 && (
                                <span className="ml-1 text-emerald-500/70">
                                  (+{term.terms.length - 1})
                                </span>
                              )}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <div className="mt-2 p-4 rounded-lg text-sm text-slate-500 bg-slate-50/50 ring-1 ring-inset ring-slate-100">
                          No key terms identified for this flashcard.
                        </div>
                      )}
                    </div>

                    {/* Key Concepts Section */}
                    <div className="mt-6">
                      <Label className="text-xs font-medium uppercase tracking-wide text-slate-500">Key Concepts</Label>
                      {flashcard.key_concepts && flashcard.key_concepts.length > 0 ? (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {flashcard.key_concepts.map((concept, index) => (
                            <span key={index} className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-700/10">
                              {concept}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <div className="mt-2 p-4 rounded-lg text-sm text-slate-500 bg-slate-50/50 ring-1 ring-inset ring-slate-100">
                          No key concepts identified for this flashcard.
                        </div>
                      )}
                    </div>

                    {/* Feedback Section */}
                    {flashcard.is_ai_generated && (
                      <div className="pt-4 border-t border-slate-200">
                        <Label className="text-xs font-medium uppercase tracking-wide text-slate-500">Feedback</Label>
                        <div className="mt-3 flex items-center gap-3">
                          <Button
                            type="button"
                            variant={flashcardFeedback[flashcard.id]?.type === 'thumbs_up' ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => handleFeedback(flashcard.id, 'thumbs_up')}
                            className={`flex items-center gap-2 ${
                              flashcardFeedback[flashcard.id]?.type === 'thumbs_up'
                                ? 'bg-green-50 text-green-700 hover:bg-green-100 border-green-200'
                                : 'border-slate-200 hover:bg-slate-50'
                            }`}
                          >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                            </svg>
                            Helpful
                          </Button>
                          <Button
                            type="button"
                            variant={flashcardFeedback[flashcard.id]?.type === 'thumbs_down' ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => handleFeedback(flashcard.id, 'thumbs_down')}
                            className={`flex items-center gap-2 ${
                              flashcardFeedback[flashcard.id]?.type === 'thumbs_down'
                                ? 'bg-red-50 text-red-700 hover:bg-red-100 border-red-200'
                                : 'border-slate-200 hover:bg-slate-50'
                            }`}
                          >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018c.163 0 .326.02.485.06L17 4m-7 10v2a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2" />
                            </svg>
                            Not Helpful
                          </Button>
                        </div>

                        {flashcardFeedback[flashcard.id]?.type === 'thumbs_down' && (
                          <div className="mt-4 space-y-4">
                            <div>
                              <Label className="text-xs font-medium uppercase tracking-wide text-slate-500">What&apos;s wrong with this flashcard?</Label>
                              <select
                                className="mt-2 block w-full rounded-lg border-slate-200 text-sm focus:border-blue-500 focus:ring-blue-500/20"
                                value={flashcardFeedback[flashcard.id]?.category || ''}
                                onChange={(e) => handleFeedbackCategory(flashcard.id, e.target.value)}
                              >
                                <option value="">Select a reason...</option>
                                <option value="incorrect_answer">Incorrect Answer</option>
                                <option value="unclear_question">Unclear Question</option>
                                <option value="too_specific">Too Specific</option>
                                <option value="too_general">Too General</option>
                                <option value="not_relevant">Not Relevant</option>
                                <option value="other">Other</option>
                              </select>
                            </div>

                            <div>
                              <Label className="text-xs font-medium uppercase tracking-wide text-slate-500">Additional Comments</Label>
                              <Textarea
                                value={flashcardFeedback[flashcard.id]?.text || ''}
                                onChange={(e) => handleFeedbackText(flashcard.id, e.target.value)}
                                placeholder="Please provide more details about the issue..."
                                rows={3}
                                className="mt-2 text-sm border-slate-200 focus:border-blue-500 focus:ring-blue-500/20 resize-none"
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {flashcards.length === 0 && (
          <Card className="backdrop-blur-sm bg-white/50 shadow-sm border-0 ring-1 ring-slate-100 mt-8">
            <CardContent className="p-16 text-center">
              <div className="mx-auto w-20 h-20 rounded-full bg-slate-50 flex items-center justify-center mb-6">
                <svg className="h-10 w-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </div>
              <h3 className="text-xl font-medium text-slate-900">No flashcards yet</h3>
              <p className="mt-2 text-base text-slate-600">Get started by adding your first flashcard.</p>
              <Button
                type="button"
                onClick={handleAddFlashcard}
                size="lg"
                className="mt-8 bg-blue-600 hover:bg-blue-700 text-white"
              >
                Add Your First Card
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Action Buttons */}
      <div className="fixed bottom-0 left-0 right-0 bg-white/80 backdrop-blur-sm border-t border-slate-200 py-4 px-6 z-10">
        <div className="container max-w-[1600px] mx-auto flex justify-end space-x-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => router.push(`/sets/${initialSet.id}`)}
            className="border-slate-200 hover:bg-slate-50"
            size="lg"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={isSaving}
            className="bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
            size="lg"
          >
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </div>
    </form>
  );
} 
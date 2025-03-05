import React from 'react';
import { SourceTextWithCitations } from '@/types';
import { CitationTooltip } from '../../CitationTooltipFixed';

export function withCitations(
  element: React.ReactNode,
  cardIds: number[],
  citations: SourceTextWithCitations['citations']
): React.ReactNode {
  return cardIds.length > 0 ? (
    <CitationTooltip citations={citations} cardIds={cardIds}>
      {element}
    </CitationTooltip>
  ) : element;
} 
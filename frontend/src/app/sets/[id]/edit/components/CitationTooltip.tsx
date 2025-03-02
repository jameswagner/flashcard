'use client';

import React, { useState, useRef, useEffect, useMemo } from 'react';
import { SourceTextWithCitations } from '@/types';
import { getCitationColor } from '../utils/citations';

// Helper function to find citations based on element type and number
export function findCitations(elementType: string, elementNum: number, citations: SourceTextWithCitations['citations']): number[] {
  console.log('Finding citations for:', elementType, elementNum, citations);
  const cardIds: number[] = [];
  for (const citation of citations) {
    // Check if citation type matches any of our expected types
    if (citation.citation_type === elementType) {
      for (const [start, end] of citation.citation_data) {
        if (elementNum >= start && elementNum <= end) {
          console.log('Found matching citation:', citation.card_id);
          cardIds.push(citation.card_id);
          break; // Only add each card once
        }
      }
    }
  }
  return [...new Set(cardIds)]; // Deduplicate card IDs
}

// CitationTooltip interface
interface CitationTooltipProps {
  citations: Array<{
    citation_id: number;
    citation_type: string;
    citation_data: [number, number][];
    preview_text: string | null;
    card_id: number;
    card_front: string;
    card_back: string;
    card_index?: number;
  }>;
  cardIds: number[];
  children: React.ReactNode;
  variant?: 'default' | 'block' | 'inline';
}

// CitationTooltip component
export function CitationTooltip({ citations, cardIds, children, variant = 'default' }: CitationTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  
  // Create deterministic IDs based on the cardIds
  const tooltipBaseId = useMemo(() => {
    return `citation-${cardIds.sort().join('-')}`;
  }, [cardIds]);
  
  const buttonId = useRef(tooltipBaseId + '-button');
  const tooltipId = useRef(tooltipBaseId + '-tooltip');
  
  // Filter citations to only include those that match our cardIds and deduplicate by card_id
  const relevantCitations = useMemo(() => {
    return new Set(citations.filter(c => cardIds.includes(c.card_id)));
  }, [cardIds, citations]);
  
  // Sort citations by card_index, with null check
  const sortedCitations = useMemo(() => {
    return [...relevantCitations].sort((a, b) => a.citation_id - b.citation_id);
  }, [relevantCitations]);

  // Add global click handler to close tooltip when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (tooltipRef.current && !tooltipRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener('click', handleClickOutside);
    }

    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  }, [isOpen]);

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    setIsOpen(!isOpen);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setIsOpen(!isOpen);
    } else if (e.key === 'Escape' && isOpen) {
      setIsOpen(false);
    }
  };

  // Get the citation color for styling
  const citationColor = useMemo(() => {
    if (cardIds.length === 0) return '';
    const firstCardIndex = sortedCitations.values().next().value?.card_index ?? 0;
    return getCitationColor(firstCardIndex - 1);
  }, [cardIds, sortedCitations]);

  // Wrap children with citation styling based on variant
  const styledChildren = useMemo(() => {
    if (!citationColor) return children;

    switch (variant) {
      case 'block':
        return (
          <div className={`${citationColor} p-3 rounded-lg`}>
            {children}
          </div>
        );
      case 'inline':
        return (
          <span className={`${citationColor} px-1 rounded border cursor-help`}>
            {children}
          </span>
        );
      default:
        // For 'default', we assume the parent will handle the layout
        return (
          <div className={citationColor}>
            {children}
          </div>
        );
    }
  }, [children, citationColor, variant]);

  // Pre-calculate citation colors for the tooltip
  const citationColors = useMemo(() => {
    return new Map(
      [...sortedCitations].map(citation => [
        citation.citation_id,
        getCitationColor((citation.card_index ?? 0) - 1)
      ])
    );
  }, [sortedCitations]);

  return (
    <div className="relative inline-block" ref={tooltipRef}>
      <button
        id={buttonId.current}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        type="button"
        className="inline-block text-left focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 rounded"
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        aria-controls={tooltipId.current}
        aria-label={`View ${sortedCitations.length} card reference${sortedCitations.length > 1 ? 's' : ''}`}
      >
        {styledChildren}
      </button>
      {isOpen && sortedCitations.length > 0 && (
        <div 
          id={tooltipId.current}
          role="dialog"
          aria-labelledby={`${tooltipId.current}-title`}
          className="absolute z-50 mt-2 w-96 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5"
        >
          <div className="p-4">
            <h3 
              id={`${tooltipId.current}-title`}
              className="text-sm font-medium text-gray-900 mb-2"
            >
              Referenced in {sortedCitations.length} card{sortedCitations.length > 1 ? 's' : ''}:
            </h3>
            <div className="space-y-3">
              {sortedCitations.map((citation) => (
                <div
                  key={citation.citation_id}
                  className={`p-2 rounded border ${citationColors.get(citation.citation_id)}`}
                >
                  <p className="text-sm font-medium text-gray-900">
                    Card {citation.card_index}
                  </p>
                  <p className="text-sm text-gray-600 mt-1">
                    Front: {citation.card_front}
                  </p>
                  <p className="text-sm text-gray-600 mt-1">
                    Back: {citation.card_back}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 
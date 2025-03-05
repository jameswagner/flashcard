'use client';

import React, { useState, useRef, useEffect, useMemo } from 'react';
import { SourceTextWithCitations, Citation } from '@/types';
import { getCitationColor } from '../utils/citations';

interface CitationMap {
  sentences: Map<number, number[]>;
  paragraphs: Map<number, number[]>;
  sections: Map<number, number[]>;
  lists: Map<number, number[]>;
  tables: Map<number, number[]>;
  segments: Map<number, number[]>;  // For YouTube transcript segments
}

// Function to create citation map from raw citations
export function createCitationMap(
  citations: SourceTextWithCitations['citations'],
  documentJson: any  // The raw PDF document JSON
): CitationMap {
  const map: CitationMap = {
    sentences: new Map(),
    paragraphs: new Map(),
    sections: new Map(),
    lists: new Map(),
    tables: new Map(),
    segments: new Map()  // Initialize segments map
  };
  console.log("Building citation map from raw citations: ");
  console.log(citations);
  console.log(documentJson);

  // First pass: Build initial maps
  for (const citation of citations) {
    const targetMap = (() => {
      switch (citation.citation_type) {
        case 'sentence_range':
          return map.sentences;
        case 'paragraph':
          return map.paragraphs;
        case 'section':
          return map.sections;
        case 'list':
          return map.lists;
        case 'table':
          return map.tables;
        case 'video_timestamp':
          return map.segments;
        default:
          return null;
      }
    })();

    if (!targetMap) continue;

    // Special handling for video timestamps
    if (citation.citation_type === 'video_timestamp') {
      console.log('Processing video timestamp citation:', {
        citation_id: citation.citation_id,
        card_id: citation.card_id,
        time_ranges: citation.citation_data
      });

      // For each segment in the document
      let globalSegmentIndex = 0;
      documentJson.sections?.forEach((section: any, sectionIndex: number) => {
        console.log(`Processing section ${sectionIndex}:`, {
          header: section.header,
          content_length: section.content?.length
        });

        section.content?.forEach((segment: any, segmentIndex: number) => {
          console.log(`Checking segment ${globalSegmentIndex}:`, {
            start_time: segment.start_time,
            end_time: segment.end_time,
            text_preview: segment.text.substring(0, 50)
          });

          // For each citation time range
          for (const [start, end] of citation.citation_data) {
            console.log('Checking time range overlap:', {
              citation_start: start,
              citation_end: end,
              segment_start: segment.start_time,
              segment_end: segment.end_time,
              overlaps: !(end < segment.start_time || start > segment.end_time)
            });

            // If citation range overlaps with segment range
            if (!(end < segment.start_time || start > segment.end_time)) {
              const existing = targetMap.get(globalSegmentIndex) || [];
              console.log('Found overlap! Adding citation:', {
                segment_index: globalSegmentIndex,
                existing_cards: existing,
                adding_card: citation.card_id
              });
              targetMap.set(globalSegmentIndex, [...new Set([...existing, citation.card_id])]);
              break;
            }
          }
          globalSegmentIndex++;
        });
      });
      console.log('Final segments map:', map.segments);
    } else {
      // Process citation data ranges for non-video citations
      for (const [start, end] of citation.citation_data) {
        // For each number in the range
        for (let num = start; num <= end; num++) {
          const existing = targetMap.get(num) || [];
          targetMap.set(num, [...new Set([...existing, citation.card_id])]);
        }
      }
    }
  }

  // Second pass: For each paragraph that has citations, collect any sentence-level citations
  // within that paragraph and move them up to paragraph level
  let currentSentenceNum = 1;
  let currentParagraphNum = 1;
  
  documentJson.sections?.forEach((section: any) => {
    section.content?.forEach((item: any) => {
      if (item.sentences) { // This is a paragraph
        const paragraphCitations = map.paragraphs.get(currentParagraphNum) || [];
        
        // If this paragraph has citations, check its sentences
        if (paragraphCitations.length > 0) {
          // Collect all sentence citations in this paragraph
          const sentenceCitations: number[] = [];
          const sentenceRange = Array.from(
            { length: item.sentences.length }, 
            (_, i) => currentSentenceNum + i
          );
          
          // Gather all sentence citations
          sentenceRange.forEach(sentNum => {
            const sentCits = map.sentences.get(sentNum) || [];
            if (sentCits.length > 0) {
              sentenceCitations.push(...sentCits);
              // Clear the sentence-level citation since we're moving it up
              console.log("Clearing sentence-level citation: ", sentNum, currentParagraphNum);
              map.sentences.delete(sentNum);
            }
          });
          
          // Add any sentence citations to the paragraph level
          if (sentenceCitations.length > 0) {
            map.paragraphs.set(
              currentParagraphNum,
              [...new Set([...paragraphCitations, ...sentenceCitations])]
            );
          }
        }
        
        currentSentenceNum += item.sentences.length;
        currentParagraphNum++;
      }
    });
  });
  console.log(map);
  return map;
}

// Function to get citations for an element
export function getCombinedCitations(
  citationMap: CitationMap,
  elementType: keyof CitationMap,
  elementNum: number
): number[] {
  return citationMap[elementType].get(elementNum) || [];
}

// Helper to find all cards that cite a specific time range - optimized version
interface TimeRangeInfo {
  start: number;
  end: number;
  cardId: number;
}

function findOverlappingRanges(
  sortedRanges: TimeRangeInfo[],
  segmentStart: number,
  segmentEnd: number
): number[] {
  const cardIds = new Set<number>();
  
  // Binary search for the first potential overlapping range
  let left = 0;
  let right = sortedRanges.length - 1;
  
  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const range = sortedRanges[mid];
    
    if (range.end < segmentStart) {
      // Range ends before segment, look in right half
      left = mid + 1;
    } else if (range.start > segmentEnd) {
      // Range starts after segment, look in left half
      right = mid - 1;
    } else {
      // Found an overlapping range, expand outwards
      // Check ranges before mid
      for (let i = mid; i >= 0; i--) {
        const r = sortedRanges[i];
        if (r.end < segmentStart) break;
        if (r.start <= segmentEnd) {
          cardIds.add(r.cardId);
        }
      }
      // Check ranges after mid
      for (let i = mid + 1; i < sortedRanges.length; i++) {
        const r = sortedRanges[i];
        if (r.start > segmentEnd) break;
        if (r.end >= segmentStart) {
          cardIds.add(r.cardId);
        }
      }
      break;
    }
  }
  
  return Array.from(cardIds);
}

export function findCitationsForTimeRange(
  citations: SourceTextWithCitations['citations'],
  segmentStart: number,
  segmentEnd: number
): number[] {
  // Create and sort time ranges (this should be memoized by the formatter)
  const ranges: TimeRangeInfo[] = [];
  
  for (const citation of citations) {
    if (citation.citation_type !== 'video_timestamp') continue;
    
    for (const [start, end] of citation.citation_data) {
      ranges.push({
        start,
        end,
        cardId: citation.card_id
      });
    }
  }
  
  // Sort by start time, then end time for ranges with same start
  ranges.sort((a, b) => a.start - b.start || a.end - b.end);
  
  return findOverlappingRanges(ranges, segmentStart, segmentEnd);
}

interface CitationTooltipProps {
  cardIds: number[];
  citations: SourceTextWithCitations['citations'];
  children: React.ReactNode;
}

export function CitationTooltip({
  cardIds,
  citations,
  children,
}: CitationTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const tooltipRef = useRef<HTMLSpanElement>(null);

  // Create deterministic IDs based on the cardIds
  const tooltipBaseId = useMemo(() => {
    return `citation-${cardIds.sort().join('-')}`;
  }, [cardIds]);

  const buttonId = useRef(tooltipBaseId + '-button');
  const tooltipId = useRef(tooltipBaseId + '-tooltip');

  // Filter citations to only include those that match our cardIds
  const relevantCitations = useMemo(() => {
    return new Set(citations.filter(c => cardIds.includes(c.card_id)));
  }, [cardIds, citations]);

  // Sort citations by card_index
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

  const handleClick = (e: React.MouseEvent<HTMLElement>) => {
    e.stopPropagation();
    setIsOpen(!isOpen);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLElement>) => {
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

  // Wrap children with citation styling
  const styledChildren = useMemo(() => {
    if (!citationColor) return children;

    return (
      <div className={`${citationColor} p-3 rounded-lg`}>
        {children}
      </div>
    );
  }, [children, citationColor]);

  // Pre-calculate citation colors for the tooltip
  const citationColors = useMemo(() => {
    return new Map(
      [...sortedCitations].map(citation => [
        citation.citation_id,
        getCitationColor((citation.card_index ?? 0) - 1)
      ])
    );
  }, [sortedCitations]);

  // If there are no citations, just render children
  if (cardIds.length === 0) {
    return <>{children}</>;
  }

  return (
    <span className="relative inline" ref={tooltipRef}>
      <button
        id={buttonId.current}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        type="button"
        className="inline-block text-left focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
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
    </span>
  );
} 
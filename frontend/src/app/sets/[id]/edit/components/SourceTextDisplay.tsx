'use client';

import { Card, CardContent } from '@/components/ui/card';
import { SourceTextWithCitations } from '@/types';
import React, { useState, useRef, useEffect, useMemo } from 'react';

interface SourceTextDisplayProps {
  source: SourceTextWithCitations;
}

function formatTimestamp(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  
  const parts = [];
  if (hours > 0) {
    parts.push(hours.toString().padStart(2, '0'));
  }
  parts.push(minutes.toString().padStart(2, '0'));
  parts.push(remainingSeconds.toString().padStart(2, '0'));
  
  return parts.join(':');
}

// Helper to get citation color based on card index
function getCitationColor(cardIndex: number): string {
  const colors = [
    'bg-blue-100/50 border-blue-200',
    'bg-green-100/50 border-green-200',
    'bg-purple-100/50 border-purple-200',
    'bg-amber-100/50 border-amber-200',
    'bg-pink-100/50 border-pink-200',
  ];
  return colors[cardIndex % colors.length];
}

// Add CitationTooltip component at the top
interface CitationTooltipProps {
  citations: Array<{
    citation_id: number;
    citation_type: string;
    citation_data: [number, number][];
    preview_text: string | null;
    card_id: number;
    card_front: string;
    card_back: string;
    card_index?: number;  // Make optional again
  }>;
  cardIds: number[];
  children: React.ReactNode;
}

function CitationTooltip({ citations, cardIds, children }: CitationTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const buttonId = useRef(`citation-button-${Math.random().toString(36).substr(2, 9)}`);
  const tooltipId = useRef(`citation-tooltip-${Math.random().toString(36).substr(2, 9)}`);
  
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
        {children}
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
              {sortedCitations.map((citation) => {
                return (
                  <div
                    key={citation.citation_id}
                    className={`p-2 rounded border ${getCitationColor((citation.card_index ?? 0) - 1)}`}
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
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Update helper functions to return all matching card IDs
function isSentenceCited(sentenceNum: number, citations: SourceTextWithCitations['citations']): number[] {
  const cardIds: number[] = [];
  for (const citation of citations) {
    if (citation.citation_type === 'sentence_range') {
      for (const [start, end] of citation.citation_data) {
        if (sentenceNum >= start && sentenceNum <= end) {
          cardIds.push(citation.card_id);
          break; // Only add each card once
        }
      }
    }
  }
  return [...new Set(cardIds)]; // Deduplicate card IDs
}

function isTimestampCited(timestamp: number, citations: SourceTextWithCitations['citations']): number[] {
  const cardIds: number[] = [];
  for (const citation of citations) {
    if (citation.citation_type === 'video_timestamp') {
      for (const [start, end] of citation.citation_data) {
        if (timestamp >= start && timestamp <= end) {
          cardIds.push(citation.card_id);
          break; // Only add each card once
        }
      }
    }
  }
  return [...new Set(cardIds)]; // Deduplicate card IDs
}

// Update formatPlainText to use CitationTooltip
function formatPlainText(text: string, citations: SourceTextWithCitations['citations']): React.ReactElement {
  const sentences = text.split(/(\[SENTENCE \d+\])/);
  const elements: React.ReactElement[] = [];
  let currentSentence = 0;

  for (let i = 0; i < sentences.length; i++) {
    const part = sentences[i];
    if (part.match(/\[SENTENCE (\d+)\]/)) {
      currentSentence = parseInt(part.match(/\[SENTENCE (\d+)\]/)?.[1] || '0');
      continue;
    }
    if (!part.trim()) continue;

    const cardIds = isSentenceCited(currentSentence, citations);
    const element = (
      <span key={i}>
        {cardIds.length > 0 ? (
          <CitationTooltip citations={citations} cardIds={cardIds}>
            <span className={`${getCitationColor(cardIds[0])} px-1 rounded border cursor-help`}>
              {part.trim()}
            </span>
          </CitationTooltip>
        ) : (
          <span>{part.trim()}</span>
        )}
      </span>
    );
    elements.push(element);
  }

  return <div className="space-y-1">{elements}</div>;
}

// Update formatYouTubeTranscript to use CitationTooltip
function formatYouTubeTranscript(
  text: string,
  title: string,
  description: string,
  citations: SourceTextWithCitations['citations']
): React.ReactElement {
  const segments = text.split('\n').filter(Boolean);

  return (
    <div className="space-y-4">
      <div className="border-b border-slate-200 pb-4">
        <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
        <p className="mt-2 text-sm text-slate-600">{description}</p>
      </div>
      <div className="space-y-2">
        {segments.map((segment, index) => {
          const match = segment.match(/\[(\d+\.\d+)s-(\d+\.\d+)s\](.*)/);
          if (!match) return null;
          
          const [_, startTime, endTime, content] = match;
          const startSeconds = parseFloat(startTime);
          const cardIds = isTimestampCited(startSeconds, citations);

          return (
            <div key={index}>
              {cardIds.length > 0 ? (
                <CitationTooltip citations={citations} cardIds={cardIds}>
                  <div className={`flex gap-3 text-sm rounded cursor-help ${getCitationColor(cardIds[0])} p-1`}>
                    <span className="flex-none font-mono text-slate-500">
                      {formatTimestamp(startSeconds)} - {formatTimestamp(parseFloat(endTime))}
                    </span>
                    <span className="flex-1 text-slate-700">{content.trim()}</span>
                  </div>
                </CitationTooltip>
              ) : (
                <div className="flex gap-3 text-sm">
                  <span className="flex-none font-mono text-slate-500">
                    {formatTimestamp(startSeconds)} - {formatTimestamp(parseFloat(endTime))}
                  </span>
                  <span className="flex-1 text-slate-700">{content.trim()}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Update isElementCited in formatHTMLContent to return all matching card IDs
function isElementCited(elementType: string, elementNum: number, citations: SourceTextWithCitations['citations']): number[] {
  const cardIds: number[] = [];
  for (const citation of citations) {
    if (citation.citation_type === `html_${elementType}`) {
      for (const [start, end] of citation.citation_data) {
        if (elementNum >= start && elementNum <= end) {
          cardIds.push(citation.card_id);
          break; // Only add each card once
        }
      }
    }
  }
  return [...new Set(cardIds)]; // Deduplicate card IDs
}

// Add CollapsibleMarker component after CitationTooltip
interface CollapsibleMarkerProps {
  type: 'REF' | 'REFS' | 'IMG';
  number?: string;
  range?: { start: string; end: string; };
  content: string;
  context?: 'list' | 'table' | 'normal';
}

function CollapsibleMarker({ type, number, range, content, context = 'normal' }: CollapsibleMarkerProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Adjust styles based on context
  const containerStyles = {
    normal: 'inline-block mx-1 align-baseline',
    list: 'inline-block mx-1 align-middle',
    table: 'inline-block mx-1 align-middle whitespace-normal'
  }[context];
  
  const contentStyles = {
    normal: 'mt-1',
    list: 'mt-0 inline-block',
    table: 'mt-0 inline-block max-w-md'
  }[context];

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();  // Stop event from bubbling up to parent CitationTooltip
    setIsExpanded(!isExpanded);
  };

  return (
    <span className={containerStyles}>
      <button
        onClick={handleClick}
        type="button"
        className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 focus:outline-none"
      >
        <span className="font-mono">
          {type}
          {number ? ` ${number}` : ''}
          {range ? ` ${range.start}-${range.end}` : ''}
          {isExpanded ? ' ▼' : ' ▶'}
        </span>
      </button>
      {isExpanded && (
        <div className={contentStyles} onClick={(e) => e.stopPropagation()}>
          <span className="text-sm text-gray-600">{content}</span>
        </div>
      )}
    </span>
  );
}

// Update the HTML element rendering to use CitationTooltip
// Example for paragraphs (do similar updates for sections, lists, and tables):
function formatHTMLContent(content: string, citations: SourceTextWithCitations['citations']): React.ReactElement {
  try {
    const data = JSON.parse(content);
    
    const renderCollapsibleMarker = (match: string, context: 'list' | 'table' | 'normal' = 'normal') => {
      try {
        const [type, numbers] = match.match(/\[(?:REF|REFS|IMG)\s*:\s*([^\]]+)\]/)?.slice(1) || [];
        const [start, end] = numbers?.split('-') || [];
        const number = !end ? start : undefined;
        const range = end ? { start, end } : undefined;
        
        return (
          <CollapsibleMarker
            type={type as 'REF' | 'REFS' | 'IMG'}
            number={number}
            range={range}
            content={match.replace(/\[(?:REF|REFS|IMG)\s*:\s*([^\]]+)\]/g, '$1')}
            context={context}
          />
        );
      } catch (e) {
        return null;
      }
    };

    const renderSection = (section: any, index: number | string) => {
      try {
        if (!section?.heading || !section?.paragraphs) {
          return null;
        }

        const headingText = section.heading.replace(/\[Section \d+(\.\d+)*\]\s*/, '');
        const headingLevel = Math.min(section.level + 1, 6);
        const sectionNum = parseInt(section.heading.match(/\[Section (\d+)/)?.[1] || '0');
        const cardIds = isElementCited('section', sectionNum, citations);
        
        const sectionContent = (
          <div key={index} className={`mb-8 ${cardIds.length > 0 ? getCitationColor(cardIds[0]) + ' p-4 rounded-lg' : ''}`}>
            {React.createElement(
              `h${headingLevel}`,
              {
                className: `font-semibold text-slate-900 mb-4 ${
                  section.level === 1 ? 'text-2xl' :
                  section.level === 2 ? 'text-xl' :
                  'text-lg'
                }`
              },
              headingText
            )}
            
            <div className="space-y-4">
              {(section.paragraphs || []).map((item: string, pIndex: number) => {
                try {
                  // Handle lists
                  if (item?.startsWith('[List')) {
                    const listNum = parseInt(item.match(/\[List (\d+)\]/)?.[1] || '0');
                    const listCardIds = isElementCited('list', listNum, citations);
                    const listItems = (section.paragraphs || [])
                      .slice(pIndex + 1)
                      .filter((p: string) => p?.startsWith('•'));
                    
                    if (!listItems.length) {
                      return null;
                    }

                    const listContent = (
                      <ul 
                        key={`list-${pIndex}`} 
                        className={`list-disc pl-6 space-y-2 text-slate-700 ${
                          listCardIds.length > 0 ? getCitationColor(listCardIds[0]) + ' p-3 rounded-lg' : ''
                        }`}
                      >
                        {listItems.map((li: string, liIndex: number) => (
                          <li key={liIndex}>{li.replace('• ', '')}</li>
                        ))}
                      </ul>
                    );

                    return listCardIds.length > 0 ? (
                      <CitationTooltip key={`list-${pIndex}`} citations={citations} cardIds={listCardIds}>
                        {listContent}
                      </CitationTooltip>
                    ) : listContent;
                  }
                  
                  // Handle tables
                  if (item?.startsWith('[Table')) {
                    const tableNum = parseInt(item.match(/\[Table (\d+)\]/)?.[1] || '0');
                    const tableCardIds = isElementCited('table', tableNum, citations);
                    const tableRows = (section.paragraphs || [])
                      .slice(pIndex + 1)
                      .filter((p: string) => p?.includes('|'))
                      .map((row: string) => row.split('|').map((cell: string) => cell.trim()));
                    
                    if (!tableRows.length) {
                      return null;
                    }

                    const tableContent = (
                      <div key={`table-${pIndex}`} className={`overflow-x-auto ${
                        tableCardIds.length > 0 ? getCitationColor(tableCardIds[0]) + ' p-3 rounded-lg' : ''
                      }`}>
                        <table className="min-w-full divide-y divide-slate-200">
                          <thead>
                            <tr>
                              {tableRows[0].map((header: string, hIndex: number) => (
                                <th key={hIndex} className="px-4 py-2 text-left text-sm font-semibold text-slate-900 bg-slate-50">
                                  {header.trim()}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-200">
                            {tableRows.slice(1).map((row: string[], rIndex: number) => (
                              <tr key={rIndex}>
                                {row.map((cell: string, cIndex: number) => (
                                  <td key={cIndex} className="px-4 py-2 text-sm text-slate-700 whitespace-nowrap">
                                    {cell.trim()}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    );

                    return tableCardIds.length > 0 ? (
                      <CitationTooltip key={`table-${pIndex}`} citations={citations} cardIds={tableCardIds}>
                        {tableContent}
                      </CitationTooltip>
                    ) : tableContent;
                  }
                  
                  // Handle regular paragraphs
                  if (item?.startsWith('[Paragraph')) {
                    const paragraphNum = parseInt(item.match(/\[Paragraph (\d+)\]/)?.[1] || '0');
                    const paragraphCardIds = isElementCited('paragraph', paragraphNum, citations);
                    
                    // Process the paragraph text to handle REF and IMG markers
                    const text = item.replace(/\[Paragraph \d+\]\s*/, '').trim();
                    const parts: React.ReactNode[] = [];
                    let currentIndex = 0;
                    
                    // Updated regex to handle both single/range refs and simpler IMG format
                    const markerRegex = /\[((?:REF|REFS)\s+\d+(?:-\d+)?|IMG)\s*:\s*([^\]]+)\]/g;
                    let match;
                    
                    while ((match = markerRegex.exec(text)) !== null) {
                      // Add text before the marker
                      if (match.index > currentIndex) {
                        parts.push(text.slice(currentIndex, match.index));
                      }
                      
                      // Parse the marker type and content
                      const [_, marker, content] = match;
                      
                      if (marker === 'IMG') {
                        parts.push(
                          <CollapsibleMarker
                            key={match.index}
                            type="IMG"
                            content={content.trim()}
                          />
                        );
                      } else {
                        // Handle REF/REFS
                        const [type, numbers] = marker.split(/\s+/);
                        const [start, end] = numbers.split('-');
                        
                        parts.push(
                          <CollapsibleMarker
                            key={match.index}
                            type={type as 'REF' | 'REFS'}
                            number={!end ? start : undefined}
                            range={end ? { start, end } : undefined}
                            content={content.trim()}
                          />
                        );
                      }
                      
                      currentIndex = match.index + match[0].length;
                    }
                    
                    // Add any remaining text
                    if (currentIndex < text.length) {
                      parts.push(text.slice(currentIndex));
                    }
                    
                    const paragraphContent = (
                      <p 
                        key={`p-${pIndex}`} 
                        className={`text-slate-700 ${
                          paragraphCardIds.length > 0 ? getCitationColor(paragraphCardIds[0]) + ' p-3 rounded-lg' : ''
                        }`}
                      >
                        {parts.map((part, i) => (
                          <React.Fragment key={i}>{part}</React.Fragment>
                        ))}
                      </p>
                    );

                    return paragraphCardIds.length > 0 ? (
                      <CitationTooltip key={`p-${pIndex}`} citations={citations} cardIds={paragraphCardIds}>
                        {paragraphContent}
                      </CitationTooltip>
                    ) : paragraphContent;
                  }
                  
                  return null;
                } catch (e) {
                  return null;
                }
              })}
            </div>
            
            {section.sections?.map((subsection: any, sIndex: number) => 
              renderSection(subsection, `${index}.${sIndex}`)
            )}
          </div>
        );

        return cardIds.length > 0 ? (
          <CitationTooltip key={index} citations={citations} cardIds={cardIds}>
            {sectionContent}
          </CitationTooltip>
        ) : sectionContent;
      } catch (e: unknown) {
        const error = e instanceof Error ? e : new Error('Unknown error in renderSection');
        return null;
      }
    };
    
    if (!data?.sections) {
      return <p className="text-red-600">Error: Invalid HTML content structure (missing sections)</p>;
    }

    return (
      <div className="prose prose-slate max-w-none">
        <h1 className="text-3xl font-bold text-slate-900 mb-6">{data.title || 'Untitled'}</h1>
        {data.sections.map((section: any, index: number) => renderSection(section, index))}
      </div>
    );
  } catch (e: unknown) {
    const error = e instanceof Error ? e : new Error('Unknown error parsing HTML content');
    return (
      <div className="text-red-600">
        <p>Error parsing HTML content</p>
        <pre className="mt-2 text-sm bg-red-50 p-2 rounded">
          {error.toString()}
        </pre>
      </div>
    );
  }
}

// Add PDF content formatting function
function formatPDFContent(content: string, citations: SourceTextWithCitations['citations']): React.ReactElement {
  try {
    const data = JSON.parse(content);
    
    // Function to process text with sentence markers
    const processTextWithSentences = (text: string, startSentence: number) => {
      const elements: React.ReactNode[] = [];
      let currentSentence = startSentence;

      if (Array.isArray(text)) {
        text.forEach((sentence) => {
          const sentenceCardIds = isSentenceCited(currentSentence, citations);
          
          if (sentenceCardIds.length > 0) {
            elements.push(
              <CitationTooltip key={`sentence-${currentSentence}`} citations={citations} cardIds={sentenceCardIds}>
                <span className={`${getCitationColor(sentenceCardIds[0])} px-1 rounded border cursor-help`}>
                  {sentence.trim()}
                </span>
              </CitationTooltip>
            );
          } else {
            elements.push(<span key={`sentence-${currentSentence}`}>{sentence.trim()} </span>);
          }
          currentSentence++;
        });
      }
      return { elements, nextSentence: currentSentence };
    };
    
    const renderParagraph = (item: any, sentenceOffset: number) => {
      const paragraphNum = sentenceOffset;
      const paragraphCardIds = isElementCited('pdf_paragraph', paragraphNum, citations);
      
      const { elements } = processTextWithSentences(item.sentences, sentenceOffset);
      
      const paragraphContent = (
        <p className={`text-slate-700 ${
          paragraphCardIds.length > 0 ? getCitationColor(paragraphCardIds[0]) + ' p-3 rounded-lg' : ''
        }`}>
          {elements}
        </p>
      );
      
      return paragraphCardIds.length > 0 ? (
        <CitationTooltip key={`para-${paragraphNum}`} citations={citations} cardIds={paragraphCardIds}>
          {paragraphContent}
        </CitationTooltip>
      ) : paragraphContent;
    };

    const renderListItem = (item: any, sentenceOffset: number) => {
      const text = item.text;
      const continuations = item.continuation_texts || [];
      
      return (
        <li key={`list-${sentenceOffset}`} className="text-slate-700">
          {text}
          {continuations.map((cont: string, idx: number) => (
            <div key={`cont-${idx}`} className="ml-8">{cont}</div>
          ))}
        </li>
      );
    };
    
    const renderSection = (section: any, sectionIndex: number, sentenceOffset: number) => {
      if (!section) {
        return { element: null, nextSentence: sentenceOffset };
      }

      const sectionCardIds = isElementCited('pdf_section', sectionIndex + 1, citations);
      let currentSentence = sentenceOffset;
      const contentElements: React.ReactNode[] = [];

      // Process each content item (paragraph or list)
      section.content?.forEach((item: any) => {
        if (item.sentences) {  // It's a paragraph
          contentElements.push(renderParagraph(item, currentSentence));
          currentSentence += item.sentences.length;
        } else if (item.text) {  // It's a list item
          contentElements.push(renderListItem(item, currentSentence));
          currentSentence++;  // Each list item counts as one sentence
        }
      });

      const sectionContent = (
        <div key={sectionIndex} className="pdf-section mb-8">
          {section.header && <h2 className="text-2xl font-bold text-slate-900 mb-4">{section.header}</h2>}
          {contentElements}
        </div>
      );

      return {
        element: sectionCardIds.length > 0 ? (
          <CitationTooltip key={`section-${sectionIndex}`} citations={citations} cardIds={sectionCardIds}>
            {sectionContent}
          </CitationTooltip>
        ) : sectionContent,
        nextSentence: currentSentence
      };
    };
    
    let currentSentence = 1;
    const sectionElements: React.ReactNode[] = [];

    data.sections?.forEach((section: any, index: number) => {
      const { element, nextSentence } = renderSection(section, index, currentSentence);
      if (element) {
        sectionElements.push(element);
      }
      currentSentence = nextSentence;
    });
    
    return (
      <div className="prose prose-slate max-w-none">
        {data.title && <h1 className="text-3xl font-bold text-slate-900 mb-6">{data.title}</h1>}
        {sectionElements}
      </div>
    );
  } catch (e) {
    console.error('Error parsing PDF content:', e);
    return <p className="text-red-600">Error parsing PDF content</p>;
  }
}

export function SourceTextDisplay({ source }: SourceTextDisplayProps) {
  const content = (() => {
    if (source.file_type.toLocaleUpperCase() === 'YOUTUBE_TRANSCRIPT') {
      try {
        const data = JSON.parse(source.text_content);
        return formatYouTubeTranscript(
          data.transcript_text,
          data.title,
          data.description,
          source.citations
        );
      } catch (e) {
        return <p className="text-red-600">Error parsing YouTube transcript</p>;
      }
    }
    
    if (source.file_type.toLocaleUpperCase() === 'TXT') {
      return (
        <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700">
          {formatPlainText(source.text_content, source.citations)}
        </pre>
      );
    }
    
    if (source.file_type.toLocaleUpperCase() === 'HTML') {
      return formatHTMLContent(source.text_content, source.citations);
    }
    
    if (source.file_type.toLocaleUpperCase() === 'PDF') {
      return formatPDFContent(source.text_content, source.citations);
    }
    
    // Default case (other formats)
    return (
      <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700">
        {source.text_content}
      </pre>
    );
  })();

  return (
    <Card className="backdrop-blur-sm bg-white/50 shadow-sm border-0 ring-1 ring-slate-100">
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-slate-900">{source.filename}</h3>
          <span className="text-sm text-slate-500">{source.file_type}</span>
        </div>
        <div className="prose prose-slate max-w-none">
          {content}
        </div>
      </CardContent>
    </Card>
  );
} 
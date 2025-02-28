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
function findCitations(elementType: string, elementNum: number, citations: SourceTextWithCitations['citations']): number[] {
  console.log('Finding citations for:', elementType, elementNum, citations);
  const cardIds: number[] = [];
  for (const citation of citations) {
    console.log('Checking citation:', citation);
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

// Update formatPlainText to use CitationTooltip
function formatPlainText(text: string, citations: SourceTextWithCitations['citations']): React.ReactElement {
  const sentences = text.split(/(\[(?:SENTENCE|PARAGRAPH) \d+\])/);
  const elements: React.ReactElement[] = [];
  let currentSentence = 0;
  let currentParagraph = 0;

  for (let i = 0; i < sentences.length; i++) {
    const part = sentences[i];
    
    // Check for sentence or paragraph markers
    const sentenceMatch = part.match(/\[SENTENCE (\d+)\]/);
    const paragraphMatch = part.match(/\[PARAGRAPH (\d+)\]/);
    
    if (sentenceMatch) {
      currentSentence = parseInt(sentenceMatch[1]);
      continue;
    }
    
    if (paragraphMatch) {
      currentParagraph = parseInt(paragraphMatch[1]);
      continue;
    }
    
    if (!part.trim()) continue;

    // Check for both sentence and paragraph citations
    const sentenceCardIds = findCitations('sentence_range', currentSentence, citations);
    const paragraphCardIds = findCitations('paragraph', currentParagraph, citations);
    const cardIds = [...new Set([...sentenceCardIds, ...paragraphCardIds])];

    console.log('Processing text part:', {
      text: part,
      currentSentence,
      currentParagraph,
      sentenceCardIds,
      paragraphCardIds,
      combinedCardIds: cardIds
    });

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

// Add these interfaces at the top of the file
interface YouTubeTranscriptContent {
  title: string;
  sections: Array<{
    header: string;
    content: Array<{
      start_time: number;
      end_time: number;
      text: string;
    }>;
  }>;
  metadata?: {
    video_id: string;
    description: string;
    channel: string;
    [key: string]: any;
  };
}

interface YouTubeSection {
  header: string;
  content?: Array<{
    type: string;
    text: string;
    start_time: number;
    end_time: number;
  }>;
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
          const cardIds = findCitations('video_timestamp', startSeconds, citations);

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
    console.log('formatHTMLContent - parsed data:', data);
    
    // If we have a simple HTML structure without proper sections, use a simpler renderer
    if (!data.sections || data.sections.length === 0 || 
        (data.sections.length > 0 && (!data.sections[0].heading || !data.sections[0].paragraphs))) {
      console.log('Using simple HTML renderer due to missing expected structure');
      return renderSimpleHTML(data, citations);
    }
    
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
        console.log('Rendering section:', section);
        
        if (!section?.heading || !section?.paragraphs) {
          console.log('Section missing heading or paragraphs:', section);
          return null;
        }

        const headingText = section.heading.replace(/\[Section \d+(\.\d+)*\]\s*/, '');
        const headingLevel = Math.min(section.level + 1, 6);
        const sectionNum = parseInt(section.heading.match(/\[Section (\d+)/)?.[1] || '0');
        const cardIds = findCitations('section', sectionNum, citations);
        
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
                    const listCardIds = findCitations('list', listNum, citations);
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
                    const tableCardIds = findCitations('table', tableNum, citations);
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
                    const paragraphCardIds = findCitations('paragraph', paragraphNum, citations);
                    
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
        console.error('Error rendering section:', error);
        return null;
      }
    };
    
    if (!data?.sections) {
      console.error('HTML data missing sections array:', data);
      return <p className="text-red-600">Error: Invalid HTML content structure (missing sections)</p>;
    }

    console.log('About to render sections, count:', data.sections.length);
    
    return (
      <div className="prose prose-slate max-w-none">
        <h1 className="text-3xl font-bold text-slate-900 mb-6">{data.title || 'Untitled'}</h1>
        {data.sections.map((section: any, index: number) => {
          const renderedSection = renderSection(section, index);
          console.log('Section', index, 'rendered as:', renderedSection ? 'content' : 'null');
          return renderedSection;
        })}
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

// Add a simpler HTML renderer for when the structure is not as expected
function renderSimpleHTML(data: any, citations: SourceTextWithCitations['citations']): React.ReactElement {
  console.log('Rendering simple HTML with data:', data);
  
  // Extract content from the data object
  const title = data.title || 'Untitled';
  
  // Process sections
  const renderContent = (contentItem: any, index: number) => {
    // Handle different content types
    if (contentItem.type === 'paragraph') {
      const paragraphNum = contentItem.paragraph_number || index + 1;
      const paragraphCardIds = findCitations('paragraph', paragraphNum, citations);
      const paragraphText = contentItem.text || '';
      
      // Process references in the text
      const parts: React.ReactNode[] = [];
      let currentIndex = 0;
      const refRegex = /\[REF (\d+):\s+([^\]]+)\]/g;
      let match;
      
      while ((match = refRegex.exec(paragraphText)) !== null) {
        // Add text before the reference
        if (match.index > currentIndex) {
          parts.push(paragraphText.slice(currentIndex, match.index));
        }
        
        // Add the reference as a collapsible marker
        const refNumber = match[1];
        const refContent = match[2];
        parts.push(
          <span key={`ref-${match.index}`} className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 cursor-pointer group">
            <sup>[{refNumber}]</sup>
            <span className="hidden group-hover:block absolute bg-white p-2 border rounded shadow-lg max-w-md z-10 text-xs">
              {refContent}
            </span>
          </span>
        );
        
        currentIndex = match.index + match[0].length;
      }
      
      // Add any remaining text
      if (currentIndex < paragraphText.length) {
        parts.push(paragraphText.slice(currentIndex));
      }
      
      return (
        <div key={`p-${index}`} className={`mb-4 ${paragraphCardIds.length > 0 ? getCitationColor(paragraphCardIds[0]) + ' p-3 rounded-lg' : ''}`}>
          {paragraphCardIds.length > 0 ? (
            <CitationTooltip citations={citations} cardIds={paragraphCardIds}>
              <div className="text-slate-700">
                {parts.length > 0 ? parts.map((part, i) => <React.Fragment key={i}>{part}</React.Fragment>) : paragraphText}
              </div>
            </CitationTooltip>
          ) : (
            <div className="text-slate-700">
              {parts.length > 0 ? parts.map((part, i) => <React.Fragment key={i}>{part}</React.Fragment>) : paragraphText}
            </div>
          )}
        </div>
      );
    }
    
    // Handle tables
    else if (contentItem.type === 'table') {
      const tableId = contentItem.table_id || index;
      const tableCardIds = findCitations('table', tableId, citations);
      const tableContent = contentItem.content || [];
      
      // Check if the first row contains an image description
      let imageDescription = null;
      if (tableContent.length > 0 && typeof tableContent[0] === 'string' && tableContent[0].includes('[IMG:')) {
        const imgMatch = tableContent[0].match(/\[IMG: desc: ([^\]]+)\]/);
        if (imgMatch) {
          imageDescription = imgMatch[1];
          // Remove the image description from the first row
          tableContent[0] = tableContent[0].replace(/\[IMG: desc: ([^\]]+)\]/, '');
        }
      }
      
      // Process the table rows
      const tableRows = tableContent.map((row: string) => {
        if (typeof row === 'string') {
          // Split by | for simple tables
          return row.split('|').map(cell => cell.trim());
        }
        return [row];
      });
      
      const tableElement = (
        <div key={`table-${index}`} className="mb-6">
          {imageDescription && (
            <div className="mb-2 italic text-sm text-gray-600">
              Image description: {imageDescription}
            </div>
          )}
          <table className="min-w-full divide-y divide-slate-200 border">
            <tbody className="divide-y divide-slate-200">
              {tableRows.map((row: string[], rowIndex: number) => (
                <tr key={rowIndex}>
                  {row.map((cell: string, cellIndex: number) => (
                    <td key={cellIndex} className="px-4 py-2 text-sm text-slate-700 border-r last:border-r-0">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      
      return tableCardIds.length > 0 ? (
        <CitationTooltip key={`table-${index}`} citations={citations} cardIds={tableCardIds}>
          <div className={getCitationColor(tableCardIds[0]) + ' p-3 rounded-lg'}>
            {tableElement}
          </div>
        </CitationTooltip>
      ) : tableElement;
    }
    
    // Handle lists
    else if (contentItem.type === 'list') {
      const listId = contentItem.list_id || index;
      const listCardIds = findCitations('list', listId, citations);
      const listItems = contentItem.items || [];
      const listType = contentItem.list_type === 'ordered' ? 'ol' : 'ul';
      
      const listElement = React.createElement(
        listType,
        { 
          className: `${listType === 'ul' ? 'list-disc' : 'list-decimal'} pl-6 space-y-2 text-slate-700 mb-4`
        },
        listItems.map((item: string, itemIndex: number) => (
          <li key={itemIndex}>{item.replace(/^\u2022\s*/, '')}</li>
        ))
      );
      
      return listCardIds.length > 0 ? (
        <CitationTooltip key={`list-${index}`} citations={citations} cardIds={listCardIds}>
          <div className={getCitationColor(listCardIds[0]) + ' p-3 rounded-lg'}>
            {listElement}
          </div>
        </CitationTooltip>
      ) : listElement;
    }
    
    // Default case for unknown content types
    return (
      <div key={`content-${index}`} className="mb-4 text-slate-700">
        {JSON.stringify(contentItem)}
      </div>
    );
  };
  
  return (
    <div className="prose prose-slate max-w-none">
      <h1 className="text-3xl font-bold text-slate-900 mb-6">{title}</h1>
      
      {data.sections && data.sections.map((section: any, sectionIndex: number) => {
        const sectionNumber = section.section_number?.[0] || sectionIndex + 1;
        const sectionCardIds = findCitations('section', sectionNumber, citations);
        
        const sectionContent = (
          <div key={`section-${sectionIndex}`} className="mb-8">
            {section.header && (
              <h2 className="text-2xl font-semibold text-slate-900 mb-4">
                {section.header}
              </h2>
            )}
            
            <div className="space-y-2">
              {section.content && section.content.map(renderContent)}
            </div>
          </div>
        );
        
        return sectionCardIds.length > 0 ? (
          <CitationTooltip key={`section-${sectionIndex}`} citations={citations} cardIds={sectionCardIds}>
            <div className={getCitationColor(sectionCardIds[0]) + ' p-3 rounded-lg'}>
              {sectionContent}
            </div>
          </CitationTooltip>
        ) : sectionContent;
      })}
    </div>
  );
}

// Add PDF content formatting function
function formatPDFContent(content: string, citations: SourceTextWithCitations['citations']): React.ReactElement {
  try {
    console.log('Starting PDF content formatting with citations:', citations);
    const data = JSON.parse(content);
    console.log('Parsed PDF content:', data);
    
    let currentParagraphNum = 1;
    let currentSentenceNum = 1;
    
    // Function to process text with sentences
    const processTextWithSentences = (text: string[], paragraphNum: number, startSentence: number) => {
      console.log('Processing sentences for paragraph', paragraphNum, 'starting at sentence', startSentence, 'Text:', text);
      const elements: React.ReactNode[] = [];
      let currentSentence = startSentence;

      text.forEach((sentence) => {
        const sentenceCardIds = findCitations('sentence_range', currentSentence, citations);
        console.log('Sentence', currentSentence, ':', sentence, 'Card IDs:', sentenceCardIds);
        
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
      return { elements, nextSentence: currentSentence };
    };
    
    const renderParagraph = (item: any) => {
      console.log('Rendering paragraph', currentParagraphNum, 'Item:', item);
      const paragraphCardIds = findCitations('paragraph', currentParagraphNum, citations);
      console.log('Paragraph card IDs:', paragraphCardIds);
      
      const { elements } = processTextWithSentences(item.sentences, currentParagraphNum, currentSentenceNum);
      currentSentenceNum += item.sentences.length;
      
      const paragraphContent = (
        <p className={`text-slate-700 ${
          paragraphCardIds.length > 0 ? getCitationColor(paragraphCardIds[0]) + ' p-3 rounded-lg' : ''
        }`}>
          {elements}
        </p>
      );
      
      const result = paragraphCardIds.length > 0 ? (
        <CitationTooltip key={`para-${currentParagraphNum}`} citations={citations} cardIds={paragraphCardIds}>
          {paragraphContent}
        </CitationTooltip>
      ) : paragraphContent;
      
      currentParagraphNum++;
      return result;
    };

    const renderList = (items: any[]) => {
      console.log('Rendering list at paragraph', currentParagraphNum, 'Items:', items);
      const listCardIds = findCitations('list', currentParagraphNum, citations);
      console.log('List card IDs:', listCardIds);
      
      const listContent = (
        <ul className={`list-disc pl-6 space-y-2 text-slate-700 ${
          listCardIds.length > 0 ? getCitationColor(listCardIds[0]) + ' p-3 rounded-lg' : ''
        }`}>
          {items.map((item, idx) => {
            console.log('Rendering list item:', idx, 'Item:', item);
            const itemCardIds = findCitations('list', currentParagraphNum + idx, citations);
            console.log('List item card IDs:', itemCardIds);
            
            const itemContent = (
              <li key={`list-${currentParagraphNum}-${idx}`} className="text-slate-700">
                {item.text}
                {item.continuation_texts?.map((cont: string, contIdx: number) => {
                  console.log('Rendering continuation:', contIdx, 'Text:', cont);
                  return (
                    <div key={`cont-${contIdx}`} className="ml-8 mt-1">{cont}</div>
                  );
                })}
              </li>
            );
            
            return itemCardIds.length > 0 ? (
              <CitationTooltip key={`list-item-${idx}`} citations={citations} cardIds={itemCardIds}>
                <span className={`${getCitationColor(itemCardIds[0])} px-1 rounded border cursor-help`}>
                  {itemContent}
                </span>
              </CitationTooltip>
            ) : itemContent;
          })}
        </ul>
      );
      
      const result = listCardIds.length > 0 ? (
        <CitationTooltip key={`list-${currentParagraphNum}`} citations={citations} cardIds={listCardIds}>
          {listContent}
        </CitationTooltip>
      ) : listContent;
      
      currentParagraphNum += items.length;
      return result;
    };
    
    const renderSection = (section: any) => {
      console.log('Rendering section, current paragraph:', currentParagraphNum, 'Section:', section);
      if (!section) {
        console.log('Section is null, returning');
        return null;
      }

      const sectionCardIds = findCitations('section', currentParagraphNum, citations);
      console.log('Section card IDs:', sectionCardIds);
      const contentElements: React.ReactNode[] = [];

      // Group list items together
      let currentListItems: any[] = [];
      
      section.content?.forEach((item: any, idx: number) => {
        console.log('Processing content item:', idx, 'Type:', item.sentences ? 'paragraph' : 'list item', 'Item:', item);
        
        if (item.sentences) {  // It's a paragraph
          if (currentListItems.length > 0) {
            console.log('Flushing accumulated list items:', currentListItems.length);
            // Render accumulated list items
            contentElements.push(renderList(currentListItems));
            currentListItems = [];
          }
          contentElements.push(renderParagraph(item));
        } else if (item.text) {  // It's a list item
          console.log('Accumulating list item:', item);
          currentListItems.push(item);
          // If this is the last item or next item is not a list item, render the list
          if (idx === section.content.length - 1 || !section.content[idx + 1]?.text) {
            console.log('End of list reached, rendering accumulated items:', currentListItems.length);
            contentElements.push(renderList(currentListItems));
            currentListItems = [];
          }
        }
      });

      const sectionContent = (
        <div className="pdf-section mb-8">
          {section.header && <h2 className="text-2xl font-bold text-slate-900 mb-4">{section.header}</h2>}
          {contentElements}
        </div>
      );

      return sectionCardIds.length > 0 ? (
        <CitationTooltip citations={citations} cardIds={sectionCardIds}>
          <div className={getCitationColor(sectionCardIds[0]) + ' p-3 rounded-lg'}>
            {sectionContent}
          </div>
        </CitationTooltip>
      ) : sectionContent;
    };
    
    console.log('Starting to process sections');
    const sectionElements = data.sections?.map((section: any) => renderSection(section));
    console.log('Finished processing sections, total elements:', sectionElements?.length);
    
    return (
      <div className="prose prose-slate max-w-none">
        {data.title && <h1 className="text-3xl font-bold text-slate-900 mb-6">{data.title}</h1>}
        {sectionElements}
      </div>
    );
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : 'Unknown error parsing PDF content';
    console.error('Error parsing PDF content:', errorMessage);
    return <p className="text-red-600">Error parsing PDF content: {errorMessage}</p>;
  }
}

// Add this function before the SourceTextDisplay component
function formatImageContent(jsonContent: string, citations: SourceTextWithCitations['citations']): React.ReactElement {
  try {
    // Parse the JSON content
    const data = JSON.parse(jsonContent);
    
    // Validate that this is image data
    if (data.type !== 'image' || !Array.isArray(data.blocks)) {
      throw new Error('Invalid image data format');
    }
    
    // Extract all paragraphs and sentences from the blocks
    const paragraphs: React.ReactElement[] = [];
    let globalParagraphNumber = 1;
    
    data.blocks.forEach((block: any) => {
      const blockId = block.id;
      // Find citations that reference this block
      const blockCardIds = findCitations('block', blockId, citations);
      
      if (!block.paragraphs || block.paragraphs.length === 0) {
        // If no paragraphs, use the original text as a fallback
        if (block.metadata?.original_text) {
          const text = block.metadata.original_text;
          // Use both block citations and paragraph citations
          const paragraphCardIds = findCitations('paragraph', globalParagraphNumber, citations);
          const cardIds = [...new Set([...blockCardIds, ...paragraphCardIds])];
          
          paragraphs.push(
            <p key={`p-${globalParagraphNumber}`} className="mb-2">
              {cardIds.length > 0 ? (
                <CitationTooltip citations={citations} cardIds={cardIds}>
                  <span className={`${getCitationColor(cardIds[0])} px-1 rounded border cursor-help`}>
                    {text}
                  </span>
                </CitationTooltip>
              ) : (
                <span>{text}</span>
              )}
            </p>
          );
          globalParagraphNumber++;
        }
      } else {
        // Process each paragraph in the block
        block.paragraphs.forEach((paragraph: any) => {
          if (paragraph.sentences && paragraph.sentences.length > 0) {
            const sentences: React.ReactElement[] = [];
            let sentenceNumber = 1;
            
            // Find paragraph citations
            const paragraphCardIds = findCitations('paragraph', globalParagraphNumber, citations);
            
            // Process each sentence in the paragraph
            paragraph.sentences.forEach((sentence: string, sentenceIndex: number) => {
              // For image content, we need to check both paragraph and sentence citations
              const sentenceCardIds = findCitations('sentence_range', sentenceNumber, citations);
              // Combine all citation types
              const cardIds = [...new Set([...blockCardIds, ...paragraphCardIds, ...sentenceCardIds])];
              
              sentences.push(
                <span key={`s-${sentenceIndex}`} className="mr-1">
                  {cardIds.length > 0 ? (
                    <CitationTooltip citations={citations} cardIds={cardIds}>
                      <span className={`${getCitationColor(cardIds[0])} px-1 rounded border cursor-help`}>
                        {sentence}
                      </span>
                    </CitationTooltip>
                  ) : (
                    <span>{sentence}</span>
                  )}
                  {" "}
                </span>
              );
              
              sentenceNumber++;
            });
            
            // Add the paragraph with all its sentences
            paragraphs.push(
              <p key={`p-${globalParagraphNumber}`} className="mb-2">
                {sentences}
              </p>
            );
            
            globalParagraphNumber++;
          }
        });
      }
    });
    
    return <div className="space-y-2">{paragraphs}</div>;
  } catch (e) {
    console.error('Error formatting image content:', e);
    return <p className="text-red-600">Error parsing image content: {e instanceof Error ? e.message : 'Unknown error'}</p>;
  }
}

// Add this function before the SourceTextDisplay component
function formatStructuredPlainText(content: string, citations: SourceTextWithCitations['citations']): React.ReactElement {
  try {
    // Parse the JSON content
    const data = JSON.parse(content);
    console.log('Structured plain text data:', data);
    
    // Validate that this is structured plain text data
    if (!data.paragraphs || !Array.isArray(data.paragraphs)) {
      throw new Error('Invalid structured plain text format');
    }
    
    // Process each paragraph
    const paragraphElements = data.paragraphs.map((paragraph: any, paragraphIndex: number) => {
      const paragraphNum = paragraph.number || paragraphIndex + 1;
      const paragraphCardIds = findCitations('paragraph', paragraphNum, citations);
      
      // Process sentences within the paragraph
      const sentenceElements = paragraph.sentences.map((sentence: string, sentenceIndex: number) => {
        // Use sentence_numbers array if available, otherwise use index + 1
        const sentenceNum = paragraph.sentence_numbers && paragraph.sentence_numbers[sentenceIndex] 
          ? paragraph.sentence_numbers[sentenceIndex] 
          : sentenceIndex + 1;
          
        console.log(`Processing sentence ${sentenceNum}: "${sentence}"`);
        
        const sentenceCardIds = findCitations('sentence_range', sentenceNum, citations);
        
        // Combine paragraph and sentence citations
        const cardIds = [...new Set([...paragraphCardIds, ...sentenceCardIds])];
        
        return (
          <span key={`s-${sentenceIndex}`} className="mr-1">
            {cardIds.length > 0 ? (
              <CitationTooltip citations={citations} cardIds={cardIds}>
                <span className={`${getCitationColor(cardIds[0])} px-1 rounded border cursor-help`}>
                  {sentence.trim()}
                </span>
              </CitationTooltip>
            ) : (
              <span>{sentence.trim()}</span>
            )}
            {" "}
          </span>
        );
      });
      
      // Use div instead of p to avoid nested p tags
      return (
        <div key={`p-${paragraphIndex}`} className="mb-4">
          {sentenceElements}
        </div>
      );
    });
    
    // Add metadata if available
    const metadata = data.metadata || {};
    const metadataElement = Object.keys(metadata).length > 0 ? (
      <div className="text-xs text-gray-500 mt-4 border-t pt-2">
        <p>Document metadata:</p>
        <ul className="list-disc pl-5 mt-1">
          {Object.entries(metadata).map(([key, value]) => (
            <li key={key}>{key}: {String(value)}</li>
          ))}
        </ul>
      </div>
    ) : null;
    
    return (
      <div className="space-y-2">
        {paragraphElements}
        {metadataElement}
      </div>
    );
  } catch (e) {
    console.error('Error formatting structured plain text:', e);
    // Fallback to the original formatPlainText function
    console.log('Falling back to original plain text formatter');
    return formatPlainText(content, citations);
  }
}

export function SourceTextDisplay({ source }: SourceTextDisplayProps) {
  // Add debugging logs right at the start
  console.log('SourceTextDisplay received source:', {
    fileType: source.file_type,
    filename: source.filename,
    citationsCount: source.citations?.length,
    textContentPreview: source.text_content?.substring(0, 100) + '...',
    hasFullSource: !!source.text_content
  });

  const renderContent = () => {
    console.log('renderContent called with file_type:', source.file_type);
    console.log('Full source.text_content:', source.text_content);

    if (source.file_type.toLowerCase() === 'youtube_transcript') {
      console.log('=== YOUTUBE TRANSCRIPT PROCESSING START ===');
      console.log('Raw content type:', typeof source.text_content);
      console.log('Full raw content:', source.text_content);
      console.log('Citations:', source.citations);

      try {
        console.log('Attempting to parse content as JSON...');
        const parsedContent = JSON.parse(source.text_content);
        console.log('Successfully parsed JSON:', {
          hasTitle: !!parsedContent.title,
          hasSections: !!parsedContent.sections,
          sectionsLength: parsedContent.sections?.length
        });

        const segments: React.ReactNode[] = [];
        
        console.log('Processing sections...');
        parsedContent.sections?.forEach((section: YouTubeSection, sectionIndex: number) => {
          console.log(`Processing section ${sectionIndex}:`, {
            header: section.header,
            contentLength: section.content?.length
          });

          section.content?.forEach((item, index: number) => {
            console.log(`Processing segment ${index}:`, {
              startTime: item.start_time,
              endTime: item.end_time,
              textPreview: item.text.substring(0, 50)
            });

            // Find all citations that overlap with this segment's time range
            const overlappingCardIds = source.citations.reduce((acc: number[], citation) => {
              if (citation.citation_type === 'video_timestamp') {
                for (const [start, end] of citation.citation_data) {
                  console.log('Checking citation overlap:', {
                    citationStart: start,
                    citationEnd: end,
                    segmentStart: item.start_time,
                    segmentEnd: item.end_time
                  });
                  
                  // If citation range overlaps with segment range
                  if (!(end < item.start_time || start > item.end_time)) {
                    console.log('Found overlapping citation:', citation.card_id);
                    acc.push(citation.card_id);
                    break;
                  }
                }
              }
              return acc;
            }, []);

            console.log('Overlapping card IDs for segment:', overlappingCardIds);

            const formattedStartTime = formatTimestamp(item.start_time);
            const formattedEndTime = formatTimestamp(item.end_time);
            const timeRange = `[${formattedStartTime}-${formattedEndTime}]`;

            console.log('Formatted time range:', timeRange);

            if (overlappingCardIds.length > 0) {
              console.log('Adding cited segment with card IDs:', overlappingCardIds);
              segments.push(
                <CitationTooltip key={index} citations={source.citations} cardIds={overlappingCardIds}>
                  <div className={`${getCitationColor(overlappingCardIds[0])} px-2 py-1 rounded my-1`}>
                    <span className="font-mono text-slate-500">{timeRange}</span>
                    {" "}
                    <span className="text-slate-700">{item.text}</span>
                  </div>
                </CitationTooltip>
              );
            } else {
              console.log('Adding uncited segment');
              segments.push(
                <div key={index} className="my-1">
                  <span className="font-mono text-slate-500">{timeRange}</span>
                  {" "}
                  <span className="text-slate-700">{item.text}</span>
                </div>
              );
            }
          });
        });

        console.log('Finished processing segments, total count:', segments.length);
        console.log('=== YOUTUBE TRANSCRIPT PROCESSING COMPLETE ===');

        return (
          <div className="space-y-1 font-sans text-sm">
            <h3 className="text-lg font-medium text-slate-900 mb-4">{parsedContent.title}</h3>
            {segments}
          </div>
        );
      } catch (error) {
        console.error('=== YOUTUBE TRANSCRIPT PROCESSING ERROR ===');
        console.error('Error details:', error);
        console.error('Raw content that failed:', source.text_content);
        return (
          <div className="text-red-600">
            <p>Error parsing transcript data</p>
            <pre className="mt-2 text-sm bg-red-50 p-2 rounded">
              {error instanceof Error ? error.message : 'Unknown error'}
            </pre>
          </div>
        );
      }
    }
    
    if (source.file_type.toLocaleUpperCase() === 'TXT') {
      try {
        // Check if the content is in the new structured JSON format
        if (source.text_content.trim().startsWith('{')) {
          return (
            <div className="font-sans text-sm text-slate-700">
              {formatStructuredPlainText(source.text_content, source.citations)}
            </div>
          );
        } else {
          // If it's in the old format with markers, use the original formatter
          return (
            <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700">
              {formatPlainText(source.text_content, source.citations)}
            </pre>
          );
        }
      } catch (e) {
        console.error('Error handling plain text content:', e);
        return (
          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700">
            {formatPlainText(source.text_content, source.citations)}
          </pre>
        );
      }
    }
    
    if (source.file_type.toLocaleUpperCase() === 'HTML') {
      try {
        // Add debugging to understand the structure
        console.log('HTML content received:', source.text_content);
        
        // Check if the content is valid JSON
        if (source.text_content.trim().startsWith('{')) {
          // Log the parsed structure
          try {
            const parsedData = JSON.parse(source.text_content);
            console.log('Parsed HTML structure:', parsedData);
            console.log('Has sections?', !!parsedData.sections);
            if (parsedData.sections) {
              console.log('Number of sections:', parsedData.sections.length);
              console.log('First section:', parsedData.sections[0]);
            }
          } catch (parseError) {
            console.error('Error parsing HTML JSON:', parseError);
          }
          
          return formatHTMLContent(source.text_content, source.citations);
        } else {
          // If it's not valid JSON, display an error
          console.error('HTML content is not in valid JSON format');
          return <p className="text-red-600">Error: HTML content is not in valid JSON format</p>;
        }
      } catch (e) {
        console.error('Error handling HTML content:', e);
        return <p className="text-red-600">Error parsing HTML content: {e instanceof Error ? e.message : 'Unknown error'}</p>;
      }
    }
    
    if (source.file_type.toLocaleUpperCase() === 'PDF') {
      return formatPDFContent(source.text_content, source.citations);
    }
    
    if (source.file_type.toLocaleUpperCase() === 'IMAGE') {
      try {
        // Check if the content is already in JSON format
        if (source.text_content.trim().startsWith('{')) {
          return formatImageContent(source.text_content, source.citations);
        } else {
          // If it's in the old format (with markers), use the plain text formatter
          console.log('Image content is not in JSON format, using plain text formatter');
          return (
            <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700">
              {formatPlainText(source.text_content, source.citations)}
            </pre>
          );
        }
      } catch (e) {
        console.error('Error handling image content:', e);
        return <p className="text-red-600">Error parsing image content: {e instanceof Error ? e.message : 'Unknown error'}</p>;
      }
    }
    
    // Default case (other formats)
    return (
      <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700">
        {source.text_content}
      </pre>
    );
  };

  return (
    <Card className="backdrop-blur-sm bg-white/50 shadow-sm border-0 ring-1 ring-slate-100">
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-slate-900">{source.filename}</h3>
          <span className="text-sm text-slate-500">{source.file_type}</span>
        </div>
        <div className="prose prose-slate max-w-none">
          {renderContent()}
        </div>
      </CardContent>
    </Card>
  );
} 
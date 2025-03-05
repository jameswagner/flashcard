'use client';

import React, { useMemo } from 'react';
import { SourceTextWithCitations } from '@/types';
import { CitationTooltip, createCitationMap, getCombinedCitations } from '../CitationTooltipFixed';
import { handleFormatterError } from './shared/errorHandler';
import { ContentCard } from './shared/ContentCard';
import { styles } from './shared/styles';
import { withCitations } from './shared/withCitations';

// Types
interface HTMLContent {
  title: string;
  sections: Array<{
    header: string;
    content: Array<{
      type: 'paragraph' | 'list' | 'table';
      text?: string;
      paragraph_number?: number;
      table_id?: number;
      content?: string[];
      items?: string[];
      list_id?: number;
      list_type?: 'ordered' | 'unordered';
    }>;
    section_number: number[];
  }>;
  metadata?: {
    total_sections: number;
    total_paragraphs: number;
    has_tables: boolean;
    has_lists: boolean;
  };
}

// Content renderers
function renderParagraph(
  contentItem: any, 
  index: number, 
  citations: SourceTextWithCitations['citations'],
  citationMap: ReturnType<typeof createCitationMap>
) {
  const paragraphNum = contentItem.paragraph_number || index + 1;
  const paragraphCardIds = getCombinedCitations(citationMap, 'paragraphs', paragraphNum);
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
  
  const paragraphContent = (
    <p key={`p-${index}`} className="text-slate-700">
      {parts.map((part, i) => (
        <React.Fragment key={i}>{part}</React.Fragment>
      ))}
    </p>
  );

  return paragraphCardIds.length > 0 ? (
    <CitationTooltip 
      key={`p-${index}`} 
      citations={citations} 
      cardIds={paragraphCardIds}
    >
      {paragraphContent}
    </CitationTooltip>
  ) : paragraphContent;
}

function renderList(
  contentItem: any, 
  index: number, 
  citations: SourceTextWithCitations['citations'],
  citationMap: ReturnType<typeof createCitationMap>
) {
  const listId = contentItem.list_id || index;
  const listCardIds = getCombinedCitations(citationMap, 'lists', listId);
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
    <CitationTooltip 
      key={`list-${index}`} 
      citations={citations} 
      cardIds={listCardIds}
    >
      {listElement}
    </CitationTooltip>
  ) : listElement;
}

function renderTable(
  contentItem: any, 
  index: number, 
  citations: SourceTextWithCitations['citations'],
  citationMap: ReturnType<typeof createCitationMap>
) {
  const tableId = contentItem.table_id || index;
  const tableCardIds = getCombinedCitations(citationMap, 'tables', tableId);
  const tableContent = contentItem.content || [];

  if (!tableContent.length) return null;

  const tableElement = (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200">
        <tbody className="divide-y divide-slate-200">
          {tableContent.map((row: string, rIndex: number) => (
            <tr key={rIndex}>
              {row.split('|').map((cell: string, cIndex: number) => (
                <td key={cIndex} className="px-4 py-2 text-sm text-slate-700">
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
    <CitationTooltip 
      key={`table-${index}`} 
      citations={citations} 
      cardIds={tableCardIds}
    >
      {tableElement}
    </CitationTooltip>
  ) : tableElement;
}

function renderContent(
  contentItem: any, 
  index: number, 
  citations: SourceTextWithCitations['citations'],
  citationMap: ReturnType<typeof createCitationMap>
) {
  switch (contentItem.type) {
    case 'paragraph':
      return renderParagraph(contentItem, index, citations, citationMap);
    case 'list':
      return renderList(contentItem, index, citations, citationMap);
    case 'table':
      return renderTable(contentItem, index, citations, citationMap);
    default:
      return (
        <div key={`content-${index}`} className="mb-4 text-slate-700">
          {JSON.stringify(contentItem)}
        </div>
      );
  }
}

// Main formatter function
export function formatHTMLContent(
  content: string,
  citations: SourceTextWithCitations['citations']
): React.ReactElement {
  try {
    const data = JSON.parse(content) as HTMLContent;
    const citationMap = useMemo(() => createCitationMap(citations, data), [citations, data]);

    return (
      <ContentCard title={data.title || 'Untitled'} type="HTML">
        <div className={styles.section.spacing}>
          {data.sections.map((section, sectionIndex) => {
            const sectionCardIds = getCombinedCitations(citationMap, 'sections', section.section_number[0]);
            const sectionContent = (
              <div key={`section-${sectionIndex}`} className={styles.section.container}>
                {section.header && (
                  <h2 className={styles.headers.h2}>
                    {section.header}
                  </h2>
                )}
                <div className={styles.section.contentSpacing}>
                  {section.content?.map((item, index) => 
                    renderContent(item, index, citations, citationMap)
                  )}
                </div>
              </div>
            );

            return withCitations(sectionContent, sectionCardIds, citations);
          })}
        </div>
      </ContentCard>
    );
  } catch (e: unknown) {
    return handleFormatterError(e, 'HTML');
  }
} 
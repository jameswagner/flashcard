import React, { useMemo } from 'react';
import { SourceTextWithCitations } from '@/types';
import { createCitationMap, getCombinedCitations } from '../CitationTooltipFixed';
import { handleFormatterError } from './shared/errorHandler';
import { ContentCard } from './shared/ContentCard';
import { styles } from './shared/styles';
import { withCitations } from './shared/withCitations';

interface PlainTextContent {
  paragraphs: {
    number: number;
    sentences: string[];
    sentence_numbers: number[];
  }[];
  metadata: {
    total_paragraphs: number;
    total_sentences: number;
    [key: string]: any;  // Allow for additional metadata fields
  };
}

function renderParagraph(
  paragraph: PlainTextContent['paragraphs'][0],
  citations: SourceTextWithCitations['citations'],
  citationMap: ReturnType<typeof createCitationMap>
): React.ReactNode {
  // Get citations for the entire paragraph
  const paragraphCardIds = getCombinedCitations(
    citationMap,
    'paragraphs',
    paragraph.number
  );

  // Process each sentence with its own citations
  const sentenceElements = paragraph.sentences.map((sentence, idx) => {
    const sentenceNum = paragraph.sentence_numbers[idx];
    const sentenceCardIds = getCombinedCitations(
      citationMap,
      'sentences',
      sentenceNum
    );

    // If the paragraph has citations, use those instead of sentence-level citations
    const cardIds = paragraphCardIds.length > 0 ? paragraphCardIds : sentenceCardIds;

    return (
      <span key={`sentence-${sentenceNum}`} className="mr-1">
        {withCitations(
          sentence.trim(),
          cardIds,
          citations
        )}
        {" "}
      </span>
    );
  });

  // If the paragraph has citations, wrap the entire paragraph
  return (
    <div key={`paragraph-${paragraph.number}`} className="mb-4">
      {paragraphCardIds.length > 0 ? (
        withCitations(
          <div>{sentenceElements}</div>,
          paragraphCardIds,
          citations
        )
      ) : (
        sentenceElements
      )}
    </div>
  );
}

function renderMetadata(metadata: PlainTextContent['metadata']): React.ReactNode {
  if (!metadata || Object.keys(metadata).length === 0) {
    return null;
  }

  return (
    <div className="text-xs text-gray-500 mt-4 border-t pt-2">
      <p>Document metadata:</p>
      <ul className="list-disc pl-5 mt-1">
        {Object.entries(metadata).map(([key, value]) => (
          <li key={key}>{key}: {String(value)}</li>
        ))}
      </ul>
    </div>
  );
}

export function formatPlainTextContent(
  content: string,
  citations: SourceTextWithCitations['citations']
): React.ReactElement {
  try {
    const data = JSON.parse(content) as PlainTextContent;
    
    // Validate structure
    if (!data.paragraphs || !Array.isArray(data.paragraphs)) {
      throw new Error('Invalid structured plain text format');
    }
    
    const citationMap = useMemo(() => createCitationMap(citations, data), [citations, data]);

    return (
      <ContentCard title="Plain Text" type="TXT">
        <div className={styles.section.spacing}>
          {data.paragraphs.map((paragraph) => 
            renderParagraph(paragraph, citations, citationMap)
          )}
          {renderMetadata(data.metadata)}
        </div>
      </ContentCard>
    );
  } catch (e: unknown) {
    return handleFormatterError(e, 'Plain Text');
  }
} 
import React from 'react';
import { SourceTextWithCitations } from '@/types';
import { CitationTooltip } from '../CitationTooltipFixed';
import { findCitations } from '../../utils/citations';
import { ContentCard } from './shared/ContentCard';

interface ImageBlock {
  id: number;
  metadata?: {
    original_text?: string;
  };
  paragraphs?: {
    sentences: string[];
    sentence_numbers: number[];
  }[];
}

interface ImageContent {
  type: 'image';
  blocks: ImageBlock[];
  metadata?: {
    total_blocks: number;
    total_paragraphs: number;
    total_sentences: number;
  };
}

function renderParagraph(
  paragraph: NonNullable<ImageBlock['paragraphs']>[0],
  blockId: number,
  globalParagraphNumber: number,
  globalSentenceNumber: number,
  citations: SourceTextWithCitations['citations']
): [React.ReactNode, number] {
  // Find citations for the block and paragraph
  const blockCardIds = findCitations('block', blockId, citations);
  const paragraphCardIds = findCitations('paragraph', globalParagraphNumber, citations);

  let currentSentenceNumber = globalSentenceNumber;

  // Process each sentence with its own citations
  const sentenceElements = paragraph.sentences.map((sentence: string, idx: number) => {
    const sentenceNum = currentSentenceNumber++;
    
    const sentenceCardIds = findCitations('sentence_range', sentenceNum, citations);
    
    // Combine all citation types, prioritizing block and paragraph citations
    const cardIds = blockCardIds.length > 0 ? blockCardIds :
                   paragraphCardIds.length > 0 ? paragraphCardIds :
                   sentenceCardIds;

    return (
      <span key={`sentence-${sentenceNum}`} className="mr-1">
        {cardIds.length > 0 ? (
          <CitationTooltip citations={citations} cardIds={cardIds}>
            {sentence.trim()}
          </CitationTooltip>
        ) : (
          <span>{sentence.trim()}</span>
        )}
        {" "}
      </span>
    );
  });

  const element = (
    <div key={`p-${globalParagraphNumber}`} className="mb-2">
      {blockCardIds.length > 0 || paragraphCardIds.length > 0 ? (
        <CitationTooltip 
          citations={citations} 
          cardIds={[...new Set([...blockCardIds, ...paragraphCardIds])]}
        >
          <div>{sentenceElements}</div>
        </CitationTooltip>
      ) : (
        sentenceElements
      )}
    </div>
  );

  return [element, currentSentenceNumber];
}

function renderBlock(
  block: ImageBlock,
  globalParagraphNumber: number,
  globalSentenceNumber: number,
  citations: SourceTextWithCitations['citations']
): [React.ReactNode[], number, number] {
  const elements: React.ReactNode[] = [];
  let currentParagraphNumber = globalParagraphNumber;
  let currentSentenceNumber = globalSentenceNumber;

  if (!block.paragraphs || block.paragraphs.length === 0) {
    // If no paragraphs, use the original text as a fallback
    if (block.metadata?.original_text) {
      const blockCardIds = findCitations('block', block.id, citations);
      const paragraphCardIds = findCitations('paragraph', currentParagraphNumber, citations);
      const cardIds = [...new Set([...blockCardIds, ...paragraphCardIds])];

      elements.push(
        <div key={`p-${currentParagraphNumber}`} className="mb-2">
          {cardIds.length > 0 ? (
            <CitationTooltip citations={citations} cardIds={cardIds}>
              {block.metadata.original_text}
            </CitationTooltip>
          ) : (
            <span>{block.metadata.original_text}</span>
          )}
        </div>
      );
      currentParagraphNumber++;
      currentSentenceNumber++;
    }
  } else {
    // Process each paragraph in the block
    block.paragraphs.forEach((paragraph, pIdx) => {
      if (paragraph.sentences && paragraph.sentences.length > 0) {
        const [paragraphElement, nextSentenceNumber] = renderParagraph(
          paragraph,
          block.id,
          currentParagraphNumber,
          currentSentenceNumber,
          citations
        );
        elements.push(paragraphElement);
        currentParagraphNumber++;
        currentSentenceNumber = nextSentenceNumber;
      }
    });
  }

  return [elements, currentParagraphNumber, currentSentenceNumber];
}

export function formatImageContent(content: string, citations: SourceTextWithCitations['citations']): React.ReactNode {
  try {
    const data = JSON.parse(content) as ImageContent;
    
    // Validate structure
    if (data.type !== 'image' || !Array.isArray(data.blocks)) {
      throw new Error('Invalid image data format');
    }
    
    // Process all blocks
    let globalParagraphNumber = 1;
    let globalSentenceNumber = 1;
    const elements: React.ReactNode[] = [];
    
    data.blocks.forEach((block, idx) => {
      const [blockElements, nextParagraphNumber, nextSentenceNumber] = renderBlock(
        block,
        globalParagraphNumber,
        globalSentenceNumber,
        citations
      );
      elements.push(...blockElements);
      globalParagraphNumber = nextParagraphNumber;
      globalSentenceNumber = nextSentenceNumber;
    });

    return (
      <ContentCard title="Image Text" type="IMAGE">
        <div className="space-y-2">
          {elements}
          {data.metadata && Object.keys(data.metadata).length > 0 && (
            <div className="text-xs text-gray-500 mt-4 border-t pt-2">
              <p>Image metadata:</p>
              <ul className="list-disc pl-5 mt-1">
                {Object.entries(data.metadata).map(([key, value]) => (
                  <li key={key}>{key}: {String(value)}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </ContentCard>
    );
  } catch (e) {
    console.error('Error formatting image content:', e);
    return <p className="text-red-600">Error parsing image content: {e instanceof Error ? e.message : 'Unknown error'}</p>;
  }
} 
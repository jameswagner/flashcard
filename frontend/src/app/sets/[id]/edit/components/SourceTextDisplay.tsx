'use client';

import { Card, CardContent } from '@/components/ui/card';
import { SourceTextWithCitations } from '@/types';
import React, { useState } from 'react';
import { formatHTMLContent as formatHTMLContentFromFormatter } from './formatters/HTMLFormatter';
import { formatPDFContent } from './formatters/PDFFormatter';
import { formatYouTubeContent } from './formatters/YouTubeFormatter';
import { formatImageContent } from './formatters/ImageFormatter';
import { CitationTooltip } from './CitationTooltipFixed';
import { findCitations } from '../utils/citations';
import { formatPlainTextContent } from './formatters/PlaintextFormatter';

interface SourceTextDisplayProps {
  source: SourceTextWithCitations;
}

// Legacy plain text formatter for backward compatibility with marker format
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

    const element = (
      <span key={i}>
        {cardIds.length > 0 ? (
          <CitationTooltip citations={citations} cardIds={cardIds}>
              {part.trim()}
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
                  {sentence.trim()}
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
      try {
        console.log('YouTube content received:', source.text_content);
        if (source.text_content.trim().startsWith('{')) {
          return formatYouTubeContent(source.text_content, source.citations);
        } else {
          console.error('YouTube content is not in valid JSON format');
          return <p className="text-red-600">Error: YouTube content is not in valid JSON format</p>;
        }
      } catch (e) {
        console.error('Error handling YouTube content:', e);
        return <p className="text-red-600">Error parsing YouTube content: {e instanceof Error ? e.message : 'Unknown error'}</p>;
      }
    }
    
    if (source.file_type.toLocaleUpperCase() === 'TXT') {
      try {
        // Check if the content is in the structured JSON format
        if (source.text_content.trim().startsWith('{')) {
          return (
            <div className="font-sans text-sm text-slate-700">
              {formatPlainTextContent(source.text_content, source.citations)}
            </div>
          );
        } else {
          // If it's in the old format with markers, use the legacy formatter
          return (
            <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700">
              {formatPlainText(source.text_content, source.citations)}
            </pre>
          );
        }
      } catch (e) {
        console.error('Error handling plain text content:', e);
        // Fallback to legacy formatter
        return (
          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700">
            {formatPlainText(source.text_content, source.citations)}
          </pre>
        );
      }
    }
    
    if (source.file_type.toLocaleUpperCase() === 'HTML') {
      try {
        console.log('HTML content received:', source.text_content);
        if (source.text_content.trim().startsWith('{')) {
          return formatHTMLContentFromFormatter(source.text_content, source.citations);
        } else {
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
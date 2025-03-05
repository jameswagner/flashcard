import React, { useMemo } from 'react';
import { SourceTextWithCitations } from '@/types';
import { CitationTooltip, createCitationMap, getCombinedCitations } from '../CitationTooltipFixed';
import { handleFormatterError } from './shared/errorHandler';
import { ContentCard } from './shared/ContentCard';
import { styles } from './shared/styles';
import { withCitations } from './shared/withCitations';

interface ProcessedSentences {
  elements: React.ReactNode[];
  nextSentence: number;
}

function processTextWithSentences(
  text: string[], 
  paragraphNum: number, 
  startSentence: number,
  citationMap: ReturnType<typeof createCitationMap>,
  citations: SourceTextWithCitations['citations']
): ProcessedSentences {
  const elements: React.ReactNode[] = [];
  let currentSentence = startSentence;

  text.forEach((sentence) => {
    const cardIds = getCombinedCitations(
      citationMap,
      'sentences',
      currentSentence
    );

    elements.push(
      cardIds.length > 0 ? (
        <CitationTooltip 
          key={`sentence-${currentSentence}`}
          citations={citations}
          cardIds={cardIds}
        >
          <span>{sentence.trim()} </span>
        </CitationTooltip>
      ) : (
        <span key={`sentence-${currentSentence}`}>{sentence.trim()} </span>
      )
    );
    currentSentence++;
  });
  return { elements, nextSentence: currentSentence };
}

interface RenderParagraphResult {
  element: React.ReactNode;
  nextParagraph: number;
  nextSentence: number;
}

function renderParagraph(
  item: { sentences: string[] },
  currentParagraphNum: number,
  currentSentenceNum: number,
  citations: SourceTextWithCitations['citations'],
  citationMap: ReturnType<typeof createCitationMap>
): RenderParagraphResult {
  const { elements, nextSentence } = processTextWithSentences(
    item.sentences, 
    currentParagraphNum, 
    currentSentenceNum,
    citationMap,
    citations
  );
  
  const cardIds = getCombinedCitations(
    citationMap,
    'paragraphs',
    currentParagraphNum
  );
  
  const element = cardIds.length > 0 ? (
    <CitationTooltip 
      key={`para-${currentParagraphNum}`}
      citations={citations}
      cardIds={cardIds}
    >
      <p className="text-slate-700">
        {elements}
      </p>
    </CitationTooltip>
  ) : (
    <p key={`para-${currentParagraphNum}`} className="text-slate-700">
      {elements}
    </p>
  );
  
  return {
    element,
    nextParagraph: currentParagraphNum + 1,
    nextSentence
  };
}

interface RenderListResult {
  element: React.ReactNode;
  nextParagraph: number;
}

function renderList(
  items: Array<{ text: string; continuation_texts?: string[] }>,
  currentParagraphNum: number,
  citations: SourceTextWithCitations['citations'],
  citationMap: ReturnType<typeof createCitationMap>
): RenderListResult {
  const listContent = (
    <ul className="list-disc pl-6 space-y-2 text-slate-700">
      {items.map((item, idx) => {
        const itemCardIds = getCombinedCitations(
          citationMap,
          'lists',
          currentParagraphNum + idx
        );
        
        const itemContent = (
          <li key={`list-${currentParagraphNum}-${idx}`} className="text-slate-700">
            {item.text}
            {item.continuation_texts?.map((cont, contIdx) => (
              <div key={`cont-${contIdx}`} className="ml-8 mt-1">{cont}</div>
            ))}
          </li>
        );
        
        return itemCardIds.length > 0 ? (
          <CitationTooltip 
            key={`list-item-${idx}`}
            citations={citations}
            cardIds={itemCardIds}
          >
            {itemContent}
          </CitationTooltip>
        ) : itemContent;
      })}
    </ul>
  );
  
  const listCardIds = getCombinedCitations(
    citationMap,
    'lists',
    currentParagraphNum
  );
  
  return {
    element: listCardIds.length > 0 ? (
      <CitationTooltip 
        key={`list-${currentParagraphNum}`}
        citations={citations}
        cardIds={listCardIds}
      >
        {listContent}
      </CitationTooltip>
    ) : listContent,
    nextParagraph: currentParagraphNum + items.length
  };
}

interface PDFParagraphItem {
  sentences: string[];
}

interface PDFListItem {
  text: string;
  continuation_texts?: string[];
}

interface PDFSection {
  header?: string;
  content?: Array<PDFParagraphItem | PDFListItem>;
}

function isParagraphItem(item: PDFParagraphItem | PDFListItem): item is PDFParagraphItem {
  return 'sentences' in item && Array.isArray(item.sentences);
}

function isListItem(item: PDFParagraphItem | PDFListItem): item is PDFListItem {
  return 'text' in item && typeof item.text === 'string';
}

function renderSection(
  section: PDFSection,
  currentParagraphNum: number,
  currentSentenceNum: number,
  citations: SourceTextWithCitations['citations'],
  citationMap: ReturnType<typeof createCitationMap>
): { element: React.ReactNode; nextParagraph: number; nextSentence: number } {
  if (!section || !section.content) {
    return { element: null, nextParagraph: currentParagraphNum, nextSentence: currentSentenceNum };
  }

  const contentElements: React.ReactNode[] = [];
  let currentListItems: PDFListItem[] = [];
  let nextParagraph = currentParagraphNum;
  let nextSentence = currentSentenceNum;
  
  const content = section.content;
  content.forEach((item, idx) => {
    if (isParagraphItem(item)) {
      if (currentListItems.length > 0) {
        const { element, nextParagraph: newNextParagraph } = renderList(currentListItems, nextParagraph, citations, citationMap);
        contentElements.push(element);
        nextParagraph = newNextParagraph;
        currentListItems = [];
      }
      const { element, nextParagraph: newNextParagraph, nextSentence: newNextSentence } = 
        renderParagraph(item, nextParagraph, nextSentence, citations, citationMap);
      contentElements.push(element);
      nextParagraph = newNextParagraph;
      nextSentence = newNextSentence;
    } else if (isListItem(item)) {
      currentListItems.push(item);
      const nextItem = content[idx + 1];
      if (idx === content.length - 1 || (nextItem && !isListItem(nextItem))) {
        const { element, nextParagraph: newNextParagraph } = renderList(currentListItems, nextParagraph, citations, citationMap);
        contentElements.push(element);
        nextParagraph = newNextParagraph;
        currentListItems = [];
      }
    }
  });

  const sectionCardIds = getCombinedCitations(
    citationMap,
    'sections',
    currentParagraphNum
  );

  const sectionContent = (
    <div className="pdf-section mb-8">
      {section.header && (
        sectionCardIds.length > 0 ? (
          <CitationTooltip
            citations={citations}
            cardIds={sectionCardIds}
          >
            <h2 className="text-2xl font-bold text-slate-900 mb-4">{section.header}</h2>
          </CitationTooltip>
        ) : (
          <h2 className="text-2xl font-bold text-slate-900 mb-4">{section.header}</h2>
        )
      )}
      {contentElements}
    </div>
  );

  return { 
    element: sectionContent,
    nextParagraph, 
    nextSentence 
  };
}

export function formatPDFContent(content: string, citations: SourceTextWithCitations['citations']): React.ReactElement {
  try {
    const data = JSON.parse(content);
    const citationMap = useMemo(() => createCitationMap(citations, data), [citations, data]);
    
    let currentParagraphNum = 1;
    let currentSentenceNum = 1;
    const sectionElements: React.ReactNode[] = [];
    
    data.sections?.forEach((section: PDFSection) => {
      const { element, nextParagraph, nextSentence } = renderSection(
        section,
        currentParagraphNum,
        currentSentenceNum,
        citations,
        citationMap
      );
      if (element) {
        sectionElements.push(element);
      }
      currentParagraphNum = nextParagraph;
      currentSentenceNum = nextSentence;
    });
    
    const titleCardIds = getCombinedCitations(citationMap, 'sections', 0);
    const title = data.title && withCitations(
      <h1 className={styles.headers.h1}>{data.title}</h1>,
      titleCardIds,
      citations
    );
    
    return (
      <ContentCard title={data.title || 'Untitled'} type="PDF">
        <div className={styles.section.spacing}>
          {title}
          {sectionElements}
        </div>
      </ContentCard>
    );
  } catch (e: unknown) {
    return handleFormatterError(e, 'PDF');
  }
}
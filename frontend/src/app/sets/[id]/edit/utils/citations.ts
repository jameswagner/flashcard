import { SourceTextWithCitations, Citation } from '@/types';

// Helper to get citation color based on card index
export function getCitationColor(cardIndex: number): string {
  const colors = [
    'bg-blue-100/50 border-blue-200',
    'bg-green-100/50 border-green-200',
    'bg-purple-100/50 border-purple-200',
    'bg-amber-100/50 border-amber-200',
    'bg-pink-100/50 border-pink-200',
  ];
  return colors[cardIndex % colors.length];
}

type CitationType = Citation['citation_type'];

// Helper to create a map of citations by type for efficient lookup
function createCitationMap(citations: SourceTextWithCitations['citations']) {
  const map = new Map<CitationType, Map<number, number[]>>();
  
  for (const citation of citations) {
    const type = citation.citation_type as CitationType;
    if (!map.has(type)) {
      map.set(type, new Map());
    }
    
    const typeMap = map.get(type)!;
    for (const [start, end] of citation.citation_data) {
      // For each position in range, add the card_id
      for (let pos = start; pos <= end; pos++) {
        const existing = typeMap.get(pos) || [];
        typeMap.set(pos, [...existing, citation.card_id]);
      }
    }
  }
  
  return map;
}

// Cache for citation maps to avoid rebuilding on every call
const citationMapCache = new WeakMap<SourceTextWithCitations['citations'], Map<CitationType, Map<number, number[]>>>();

// Helper to check if a paragraph contains any sentence-level citations
function hasSentenceLevelCitations(
  paragraphNum: number,
  citations: SourceTextWithCitations['citations']
): boolean {
  const citationMap = citationMapCache.get(citations);
  if (!citationMap) return false;

  const sentenceMap = citationMap.get('sentence_range');
  if (!sentenceMap) return false;

  // Check if any sentences in this paragraph have citations
  // We assume sentences are numbered sequentially within paragraphs
  // This might need adjustment based on your actual sentence numbering scheme
  for (let i = 0; i < 100; i++) { // Reasonable upper limit for sentences in a paragraph
    if (sentenceMap.has(paragraphNum * 100 + i)) {
      return true;
    }
  }
  return false;
}

// Helper to find citations for a given element, with collapsing logic
export function findCitations(
  elementType: CitationType,
  elementNum: number,
  citations: SourceTextWithCitations['citations']
): number[] {
  // Get or create citation map
  let citationMap = citationMapCache.get(citations);
  if (!citationMap) {
    citationMap = createCitationMap(citations);
    citationMapCache.set(citations, citationMap);
    console.log('Citation map created for citations:', citations);
  }
  
  // Special handling for sentence-level citations
  if (elementType === 'sentence_range') {
    const paragraphNum = Math.floor(elementNum / 100); // Assuming paragraph numbering scheme
    const paragraphCitations = findParagraphCitations(paragraphNum, citations);
    if (paragraphCitations.length > 0) {
      // If paragraph has citations, collapse sentence-level citations into it
      return paragraphCitations;
    }
  }
  
  // Get citations for this type and position
  const typeMap = citationMap.get(elementType);
  if (!typeMap) return [];
  
  const cardIds = typeMap.get(elementNum) || [];
  return [...new Set(cardIds)]; // Deduplicate just in case
}

// Helper to find paragraph-level citations
function findParagraphCitations(
  paragraphNum: number,
  citations: SourceTextWithCitations['citations']
): number[] {
  const citationMap = citationMapCache.get(citations);
  if (!citationMap) return [];

  const paragraphMap = citationMap.get('paragraph');
  if (!paragraphMap) return [];

  return paragraphMap.get(paragraphNum) || [];
}

// Helper to determine if an element should be highlighted
export function shouldHighlight(
  elementType: CitationType,
  elementNum: number,
  citations: SourceTextWithCitations['citations']
): boolean {
  // Only highlight sections at the header level
  if (elementType === 'section') {
    return false; // The section header component will handle its own highlighting
  }

  // For paragraphs, only highlight if there are paragraph-level citations
  // and no sentence-level citations within
  if (elementType === 'paragraph') {
    const paragraphCitations = findParagraphCitations(elementNum, citations);
    return paragraphCitations.length > 0 && !hasSentenceLevelCitations(elementNum, citations);
  }

  // For sentences, only highlight if there are no paragraph-level citations
  if (elementType === 'sentence_range') {
    const paragraphNum = Math.floor(elementNum / 100); // Assuming paragraph numbering scheme
    const paragraphCitations = findParagraphCitations(paragraphNum, citations);
    return paragraphCitations.length === 0;
  }

  // For other types (like lists), always highlight if they have citations
  const citations_ = findCitations(elementType, elementNum, citations);
  return citations_.length > 0;
}

interface CitationWrapperResult {
  element: React.ReactNode;
  shouldWrap: boolean;
  cardIds: number[];
}

// Helper to determine if and how content should be wrapped with citations
export function getCitationWrapper(
  elementType: CitationType,
  elementNum: number,
  citations: SourceTextWithCitations['citations'],
  children: React.ReactNode
): CitationWrapperResult {
  // Get all relevant citations
  const directCitations = findCitations(elementType, elementNum, citations);
  
  // For paragraphs, also get sentence citations
  let allCitations = directCitations;
  if (elementType === 'paragraph') {
    const sentenceCitations = getAllSentenceCitations(elementNum, citations);
    allCitations = [...new Set([...directCitations, ...sentenceCitations])];
  }
  
  // For lists, combine list and list item citations
  if (elementType === 'list') {
    const itemCitations = getListItemCitations(elementNum, citations);
    allCitations = [...new Set([...directCitations, ...itemCitations])];
  }
  
  const shouldWrap = shouldHighlight(elementType, elementNum, citations) && allCitations.length > 0;
  
  return {
    element: children,
    shouldWrap,
    cardIds: allCitations
  };
}

// Helper to get all sentence citations for a paragraph
function getAllSentenceCitations(
  paragraphNum: number,
  citations: SourceTextWithCitations['citations']
): number[] {
  const citationMap = citationMapCache.get(citations);
  if (!citationMap) return [];

  const sentenceMap = citationMap.get('sentence_range');
  if (!sentenceMap) return [];

  const allCitations: number[] = [];
  // Check sentences in this paragraph
  for (let i = 0; i < 100; i++) {
    const sentenceNum = paragraphNum * 100 + i;
    const sentenceCitations = sentenceMap.get(sentenceNum) || [];
    allCitations.push(...sentenceCitations);
  }
  
  return [...new Set(allCitations)];
}

// Helper to get all list item citations for a list
function getListItemCitations(
  listNum: number,
  citations: SourceTextWithCitations['citations']
): number[] {
  const citationMap = citationMapCache.get(citations);
  if (!citationMap) return [];

  const listMap = citationMap.get('list');
  if (!listMap) return [];

  const allCitations: number[] = [];
  // Check items in this list (assuming they're numbered sequentially after the list)
  for (let i = 0; i < 50; i++) { // Reasonable upper limit for list items
    const itemCitations = listMap.get(listNum + i) || [];
    allCitations.push(...itemCitations);
  }
  
  return [...new Set(allCitations)];
} 
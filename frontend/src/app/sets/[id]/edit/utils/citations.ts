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

// Helper to find citations for a given element
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
  }
  
  // Get citations for this type and position
  const typeMap = citationMap.get(elementType);
  if (!typeMap) return [];
  
  const cardIds = typeMap.get(elementNum) || [];
  return [...new Set(cardIds)]; // Deduplicate just in case
} 
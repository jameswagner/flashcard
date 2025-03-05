export interface TimeRangeInfo {
  start: number;
  end: number;
  cardId: number;
}

export function findOverlappingRanges(
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

export function formatTimestamp(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toFixed(2).padStart(5, '0')}`;
  }
  return `${minutes}:${secs.toFixed(2).padStart(5, '0')}`;
} 
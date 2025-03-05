'use client';

import React, { useMemo } from 'react';
import { SourceTextWithCitations } from '@/types';
import { CitationTooltip, findCitationsForTimeRange } from '../CitationTooltipFixed';
import { handleFormatterError } from './shared/errorHandler';
import { ContentCard } from './shared/ContentCard';
import { styles } from './shared/styles';
import { withCitations } from './shared/withCitations';

// Types
interface YouTubeContent {
  title: string;
  sections: Array<{
    header: string;
    content: Array<{
      type: 'transcript_segment';
      text: string;
      start_time: number;
      end_time: number;
    }>;
  }>;
  metadata: {
    video_id: string;
    title: string;
    description: string;
    channel: string;
    published_at: string;
    duration: {
      raw: string;
      formatted: string;
    };
    statistics: {
      views: number;
      likes: number;
      comments: number;
    };
    thumbnail_url: string;
    total_sections: number;
    has_chapters: boolean;
  };
}

interface TimeRangeInfo {
  start: number;
  end: number;
  cardId: number;
}

function formatTimestamp(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toFixed(2).padStart(5, '0')}`;
  }
  return `${minutes}:${secs.toFixed(2).padStart(5, '0')}`;
}

function findOverlappingRanges(
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

function renderTranscriptSegment(
  segment: YouTubeContent['sections'][0]['content'][0],
  citations: SourceTextWithCitations['citations'],
  sortedRanges: TimeRangeInfo[]
): React.ReactNode {
  const timestamp = `[${formatTimestamp(segment.start_time)}-${formatTimestamp(segment.end_time)}]`;
  
  const content = (
    <div className="mb-2 text-slate-700">
      <span className="text-slate-500 font-mono text-sm mr-2">{timestamp}</span>
      {segment.text}
    </div>
  );

  const cardIds = findOverlappingRanges(sortedRanges, segment.start_time, segment.end_time);
  
  return withCitations(content, cardIds, citations);
}

// Main formatter function
export function formatYouTubeContent(
  content: string,
  citations: SourceTextWithCitations['citations']
): React.ReactElement {
  try {
    const data = JSON.parse(content) as YouTubeContent;

    // Memoize the sorted time ranges
    const sortedRanges = useMemo(() => {
      const ranges: TimeRangeInfo[] = [];
      
      for (const citation of citations) {
        if (citation.citation_type !== 'video_timestamp') continue;
        
        for (const [start, end] of citation.citation_data) {
          ranges.push({
            start,
            end,
            cardId: citation.card_id
          });
        }
      }
      
      // Sort by start time, then end time for ranges with same start
      return ranges.sort((a, b) => a.start - b.start || a.end - b.end);
    }, [citations]);

    const metadata = (
      <p className="text-sm text-slate-500">
        {data.metadata.channel} • {data.metadata.duration.formatted}
      </p>
    );

    return (
      <ContentCard 
        title={data.metadata.title || 'Untitled Video'} 
        type="YouTube"
        metadata={metadata}
      >
        {data.metadata.thumbnail_url && (
          <div className="mb-4 relative aspect-video">
            <img 
              src={data.metadata.thumbnail_url} 
              alt={data.metadata.title}
              className="rounded-lg object-cover w-full"
            />
          </div>
        )}
        <div className={styles.section.spacing}>
          {data.sections.map((section, sectionIndex) => (
            <div key={`section-${sectionIndex}`} className={styles.section.container}>
              {section.header && (
                <h2 className={styles.headers.h2}>
                  {section.header}
                </h2>
              )}
              <div className={styles.section.contentSpacingTight}>
                {section.content?.map((segment, index) => (
                  <React.Fragment key={`segment-${sectionIndex}-${index}`}>
                    {renderTranscriptSegment(segment, citations, sortedRanges)}
                  </React.Fragment>
                ))}
              </div>
            </div>
          ))}
        </div>
      </ContentCard>
    );
  } catch (e: unknown) {
    return handleFormatterError(e, 'YouTube');
  }
} 
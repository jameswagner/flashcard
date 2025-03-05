import React from 'react';

type ContentType = 'HTML' | 'PDF' | 'YouTube' | 'Plain Text';

export function handleFormatterError(error: unknown, contentType: ContentType): React.ReactElement {
  console.error(`Error formatting ${contentType} content:`, error);
  return (
    <p className="text-red-600">
      Error parsing {contentType} content: {error instanceof Error ? error.message : 'Unknown error'}
    </p>
  );
} 
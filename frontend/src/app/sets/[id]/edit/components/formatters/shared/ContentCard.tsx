import React from 'react';
import { Card, CardContent } from '@/components/ui/card';

interface ContentCardProps {
  title: string;
  type: string;
  metadata?: React.ReactNode;
  children: React.ReactNode;
}

export function ContentCard({ title, type, metadata, children }: ContentCardProps) {
  return (
    <Card className="backdrop-blur-sm bg-white/50 shadow-sm border-0 ring-1 ring-slate-100">
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex-1">
            <h3 className="text-lg font-medium text-slate-900">{title}</h3>
            {metadata}
          </div>
          <span className="text-sm text-slate-500">{type}</span>
        </div>
        <div className="prose prose-slate max-w-none">
          {children}
        </div>
      </CardContent>
    </Card>
  );
} 
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  createFlashcardSet, 
  uploadSourceFile, 
  uploadSourceUrl, 
  uploadYouTubeVideo,
  generateFlashcards 
} from '@/api/flashcards';

// YouTube URL patterns
const YOUTUBE_PATTERNS = [
  /(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&]+)/,  // Standard watch URL
  /(?:https?:\/\/)?(?:www\.)?youtu\.be\/([^?]+)/,             // Shortened URL
  /(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^?]+)/    // Embed URL
];

function extractYouTubeId(url: string): string | null {
  for (const pattern of YOUTUBE_PATTERNS) {
    const match = url.match(pattern);
    if (match && match[1]) {
      return match[1];
    }
  }
  return null;
}

export default function CreateSet() {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [directText, setDirectText] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    try {
      let sourceFileId: number;
      setIsGenerating(true);

      if (file) {
        // Handle file upload
        const uploadResponse = await uploadSourceFile(file);
        sourceFileId = uploadResponse.id;
      } else if (url) {
        // Check if it's a YouTube URL
        const youtubeId = extractYouTubeId(url);
        if (youtubeId) {
          // Handle YouTube video upload
          const uploadResponse = await uploadYouTubeVideo({
            video_id: youtubeId,
            title: title || `YouTube Video ${youtubeId}`,
            description: description
          });
          sourceFileId = uploadResponse.id;
        } else {
          // Handle regular URL upload
          const uploadResponse = await uploadSourceUrl({ url });
          sourceFileId = uploadResponse.id;
        }
      } else if (directText.trim()) {
        // Handle direct text input by creating a Blob/File
        const textFile = new File([directText], 'input.txt', { type: 'text/plain' });
        const uploadResponse = await uploadSourceFile(textFile);
        sourceFileId = uploadResponse.id;
      } else {
        // Handle manual creation
        const data = await createFlashcardSet({
          title,
          description,
        });
        router.push(`/sets/${data.id}/edit`);
        return;
      }
      
      // Generate flashcards from either file, URL, or YouTube video
      const { set_id } = await generateFlashcards(sourceFileId, {
        title,
        description
      });
      router.push(`/sets/${set_id}/edit`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setIsGenerating(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.type !== 'text/plain') {
        setError('Please upload a .txt file');
        return;
      }
      setFile(selectedFile);
      setUrl(''); // Clear URL when file is selected
      setDirectText(''); // Clear direct text input
      setError(null);
    }
  };

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newUrl = e.target.value;
    setUrl(newUrl);
    setFile(null); // Clear file when URL is entered
    setDirectText(''); // Clear direct text input
    setError(null);

    // If it's a YouTube URL, update the title if not already set
    if (!title) {
      const youtubeId = extractYouTubeId(newUrl);
      if (youtubeId) {
        setTitle(`YouTube Flashcards: ${youtubeId}`);
      }
    }
  };

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newText = e.target.value;
    setDirectText(newText);
    setFile(null); // Clear file when text is entered
    setUrl(''); // Clear URL when text is entered
    setError(null);

    // Auto-populate title if not already set by user
    if (!title) {
      // Find first line break or take entire text if no line break
      const firstLine = newText.split('\n')[0];
      // Take up to 50 characters, stopping at the last complete word
      const words = firstLine.split(' ');
      let titleText = '';
      for (const word of words) {
        if ((titleText + word).length > 50) break;
        titleText += (titleText ? ' ' : '') + word;
      }
      setTitle(titleText.trim());
    }
  };

  return (
    <div className="container mx-auto p-4">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Create New Flashcard Set</h1>
        <Button
          variant="outline"
          onClick={() => router.push('/sets')}
        >
          Cancel
        </Button>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        <Card className="p-4">
          <div className="space-y-4">
            <div>
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>
            
            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="space-y-4">
            <h2 className="text-xl font-semibold">AI Generation</h2>
            <p className="text-sm text-gray-600">
              Upload a text file or provide a URL (including YouTube videos) to automatically generate flashcards using AI.
            </p>
            
            <Tabs defaultValue="file" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="file">Text File</TabsTrigger>
                <TabsTrigger value="text">Direct Text</TabsTrigger>
                <TabsTrigger value="url">URL</TabsTrigger>
              </TabsList>
              
              <TabsContent value="file" className="space-y-4">
                <div>
                  <Label htmlFor="file">Text File</Label>
                  <Input
                    id="file"
                    type="file"
                    accept=".txt"
                    onChange={handleFileChange}
                    className="mt-1"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Only .txt files are supported
                  </p>
                </div>
              </TabsContent>

              <TabsContent value="text" className="space-y-4">
                <div>
                  <Label htmlFor="directText">Enter Text</Label>
                  <Textarea
                    id="directText"
                    value={directText}
                    onChange={handleTextChange}
                    placeholder="Enter or paste your text here..."
                    className="mt-1 min-h-[200px]"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Enter or paste your text directly
                  </p>
                </div>
              </TabsContent>
              
              <TabsContent value="url" className="space-y-4">
                <div>
                  <Label htmlFor="url">Web Page or YouTube URL</Label>
                  <Input
                    id="url"
                    type="url"
                    value={url}
                    onChange={handleUrlChange}
                    placeholder="https://example.com/article or https://youtube.com/watch?v=..."
                    className="mt-1"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Enter a web page URL or YouTube video URL to generate flashcards from its content
                  </p>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </Card>

        {error && (
          <div className="text-red-500 text-sm">{error}</div>
        )}

        <div className="flex gap-4">
          <Button 
            type="submit" 
            className="flex-1"
            disabled={isGenerating}
          >
            {isGenerating ? 'Generating Flashcards...' : 'Create Set'}
          </Button>
        </div>
      </form>
    </div>
  );
} 
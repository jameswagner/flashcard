'use client';

import React from 'react';
import { SelectionProvider } from '../sets/[id]/edit/components/formatters/SelectionContext';

export default function MockupPage() {
  return (
    <div className="container mx-auto py-8 bg-white">
      <h1 className="text-2xl font-bold mb-6">Improved Selection UI Mockup</h1>
      
      <SelectionProvider onCreateFlashcards={(items) => console.log('Create flashcards:', items)}>
        <div className="pl-10">
          {/* Example content with hierarchical selection */}
          <div className="mb-8">
            <h2 className="text-xl font-semibold mb-4">Hierarchical Selection</h2>
            
            <div className="border p-4 mb-8 rounded shadow-sm">
              <p className="text-sm text-gray-600 mb-4">
                This mockup demonstrates the improved hierarchical selection UI. 
                Sentences are only selectable after you select a paragraph, providing a cleaner interface.
                Citation highlighting is more subtle, using underlines instead of full highlighting.
              </p>
              
              {/* Unselected paragraph */}
              <div className="relative group mb-6">
                <div className="absolute left-[-1.5rem] top-2 opacity-25 group-hover:opacity-100 transition-opacity">
                  <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                </div>
                <div className="absolute right-2 top-2 text-gray-400 hover:text-gray-600 cursor-pointer">
                  ►
                </div>
                <p className="my-2">
                  Paragraph with no citations. When a paragraph is not selected, you don't see sentence checkboxes.
                  This creates a cleaner interface that focuses the user on the hierarchical selection process.
                </p>
              </div>
              
              {/* Selected paragraph with citations */}
              <div className="relative group mb-6 bg-blue-50/40 border-l-2 border-blue-200 pl-1 rounded-md">
                <div className="absolute left-[-1.5rem] top-2 opacity-100 transition-opacity">
                  <input type="checkbox" checked readOnly className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                </div>
                <div className="absolute right-2 top-2 text-gray-400 hover:text-gray-600 cursor-pointer">
                  ▼
                </div>
                <p className="my-2">
                  <span className="relative inline-block group bg-blue-100/60 px-0.5 py-0.5 rounded">
                    This sentence is selected.
                    <span className="absolute -top-1 -right-1 opacity-100">
                      <input type="checkbox" checked readOnly className="h-3 w-3 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                    </span>
                  </span>
                  {" "}
                  <span className="relative inline-block group hover:bg-blue-50/40 px-0.5 py-0.5 rounded">
                    This sentence is not selected.
                    <span className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <input type="checkbox" readOnly className="h-3 w-3 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                    </span>
                  </span>
                  {" "}
                  <span className="relative inline-block group border-b border-yellow-200 hover:bg-blue-50/40 px-0.5 py-0.5 rounded">
                    This sentence has a citation but is not selected.
                    <span className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <input type="checkbox" readOnly className="h-3 w-3 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                    </span>
                  </span>
                  {" "}
                  <span className="relative inline-block group border-b border-yellow-200 bg-blue-50/60 px-0.5 py-0.5 rounded">
                    This sentence has a citation and is selected.
                    <span className="absolute -top-1 -right-1 opacity-100">
                      <input type="checkbox" checked readOnly className="h-3 w-3 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                    </span>
                  </span>
                </p>
              </div>
              
              {/* Paragraph that remains expanded after unselection */}
              <div className="relative group mb-6">
                <div className="absolute left-[-1.5rem] top-2 opacity-25 group-hover:opacity-100 transition-opacity">
                  <input type="checkbox" readOnly className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                </div>
                <div className="absolute right-2 top-2 text-gray-400 hover:text-gray-600 cursor-pointer">
                  ▼
                </div>
                <p className="my-2">
                  <span className="relative inline-block group hover:bg-blue-50/40 px-0.5 py-0.5 rounded">
                    This paragraph was previously selected and expanded, but then unselected.
                    The sentence checkboxes remain visible, letting users select individual sentences without selecting the whole paragraph.
                    <span className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <input type="checkbox" readOnly className="h-3 w-3 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                    </span>
                  </span>
                </p>
              </div>
            </div>
          </div>
          
          {/* Legend */}
          <div className="p-4 bg-gray-50 rounded-lg">
            <h3 className="text-lg font-semibold mb-2">UI Legend</h3>
            <ul className="space-y-2 text-sm">
              <li className="flex items-center">
                <span className="inline-block w-6 h-6 bg-blue-50/40 border-l-2 border-blue-200 mr-2"></span>
                <span>Selected paragraph/block</span>
              </li>
              <li className="flex items-center">
                <span className="inline-block w-6 h-6 bg-blue-100/60 mr-2"></span>
                <span>Selected sentence/inline element</span>
              </li>
              <li className="flex items-center">
                <span className="inline-block w-6 h-6 border-b border-yellow-200 mr-2"></span>
                <span>Element with citation (subtle underline)</span>
              </li>
              <li className="flex items-center">
                <span className="inline-block w-6 h-6 border-b border-yellow-200 bg-blue-50/60 mr-2"></span>
                <span>Selected element with citation</span>
              </li>
              <li className="flex items-center">
                <span className="inline-block mr-2">►</span>
                <span>Expandable content (not expanded)</span>
              </li>
              <li className="flex items-center">
                <span className="inline-block mr-2">▼</span>
                <span>Expandable content (expanded)</span>
              </li>
            </ul>
            
            <div className="mt-4 p-3 bg-blue-50 rounded border border-blue-100 text-sm">
              <p><strong>Key improvements:</strong></p>
              <ol className="list-decimal pl-5 mt-2 space-y-1">
                <li>Hierarchical selection reduces visual clutter</li>
                <li>Citations use subtle underlines rather than intense highlighting</li>
                <li>Checkboxes only appear when relevant, reducing noise</li>
                <li>Paragraphs can stay expanded even when unselected</li>
                <li>Improved event handling prevents tooltip conflicts</li>
                <li>Keyboard accessibility is maintained throughout</li>
              </ol>
            </div>
          </div>
          
          {/* Example of selection preview */}
          <div className="fixed bottom-4 right-4 bg-white shadow-lg rounded-lg border border-blue-100 p-4 w-96 max-h-[50vh] overflow-auto z-50">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-lg font-medium text-gray-900">Selected Content</h3>
              <div className="flex space-x-1">
                <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs font-medium">
                  3 sentences
                </span>
                <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs font-medium">
                  1 paragraph
                </span>
              </div>
            </div>
            
            <div className="max-h-40 overflow-y-auto mb-4 text-sm text-gray-600 border-t border-b border-gray-100 py-2">
              <div className="mb-2 pb-2 border-b border-gray-100">
                <span className="text-xs font-medium text-gray-500 block">paragraph:</span>
                <span className="block truncate">Paragraph with citations...</span>
              </div>
              <div className="mb-2 pb-2 border-b border-gray-100">
                <span className="text-xs font-medium text-gray-500 block">sentence:</span>
                <span className="block truncate">This sentence is selected.</span>
              </div>
              <div className="mb-2 pb-2 border-b border-gray-100">
                <span className="text-xs font-medium text-gray-500 block">sentence:</span>
                <span className="block truncate">This sentence has a citation and is selected.</span>
              </div>
            </div>
            
            <div className="flex space-x-2">
              <button className="flex-1 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                Clear
              </button>
              <button className="flex-1 px-3 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                Create Flashcards
              </button>
            </div>
          </div>
        </div>
      </SelectionProvider>
    </div>
  );
} 
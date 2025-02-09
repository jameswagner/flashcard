import Image from "next/image";

export default function Home() {
  return (
    <div className="min-h-screen p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold">Flashcards</h1>
      </header>
      
      <main>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {/* Placeholder for flashcard sets */}
          <div className="p-6 rounded-lg border hover:border-blue-500 cursor-pointer transition-colors">
            <h2 className="text-xl font-semibold mb-2">Example Set</h2>
            <p className="text-gray-600">10 cards</p>
          </div>
          
          <div className="p-6 rounded-lg border border-dashed hover:border-blue-500 cursor-pointer transition-colors flex items-center justify-center">
            <span className="text-lg text-gray-600">+ Create New Set</span>
          </div>
        </div>
      </main>
    </div>
  );
}

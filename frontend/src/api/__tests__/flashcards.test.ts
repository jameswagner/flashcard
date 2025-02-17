import {
  getFlashcardSets,
  getFlashcardSet,
  createFlashcardSet,
  updateFlashcardSet,
  addCardToSet,
  updateCard,
  deleteCard,
} from '../flashcards';
import config from '@/config';

describe('Flashcards API', () => {
  const apiUrl = config.apiUrl;

  beforeEach(() => {
    // Clear all mocks before each test
    global.fetch = jest.fn();
  });

  describe('getFlashcardSets', () => {
    it('should fetch all flashcard sets', async () => {
      const mockSets = [
        { id: 1, title: 'Set 1', description: 'Desc 1', card_count: 2 },
        { id: 2, title: 'Set 2', description: 'Desc 2', card_count: 3 },
      ];

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockSets,
      });

      const result = await getFlashcardSets();
      expect(result).toEqual(mockSets);
      expect(fetch).toHaveBeenCalledWith(`${apiUrl}/api/flashcard-sets/`);
    });

    it('should handle errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
      });

      await expect(getFlashcardSets()).rejects.toThrow('Failed to fetch flashcard sets');
    });
  });

  describe('getFlashcardSet', () => {
    it('should fetch a single flashcard set with cards', async () => {
      const mockSet = {
        id: 1,
        title: 'Set 1',
        description: 'Desc 1',
        card_count: 2,
        flashcards: [
          { id: 1, front: 'Front 1', back: 'Back 1' },
          { id: 2, front: 'Front 2', back: 'Back 2' },
        ],
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockSet,
      });

      const result = await getFlashcardSet(1);
      expect(result).toEqual(mockSet);
      expect(fetch).toHaveBeenCalledWith(`${apiUrl}/api/flashcard-sets/1`);
    });
  });

  describe('createFlashcardSet', () => {
    it('should create a new flashcard set', async () => {
      const newSet = {
        title: 'New Set',
        description: 'New Desc',
        flashcards: [{ front: 'Front 1', back: 'Back 1' }],
      };

      const mockResponse = {
        id: 1,
        ...newSet,
        card_count: 1,
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await createFlashcardSet(newSet);
      expect(result).toEqual(mockResponse);
      expect(fetch).toHaveBeenCalledWith(`${apiUrl}/api/flashcard-sets/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newSet),
      });
    });
  });

  describe('updateFlashcardSet', () => {
    it('should update a flashcard set', async () => {
      const updates = {
        title: 'Updated Title',
        description: 'Updated Desc',
      };

      const mockResponse = {
        id: 1,
        ...updates,
        card_count: 2,
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await updateFlashcardSet(1, updates);
      expect(result).toEqual(mockResponse);
      expect(fetch).toHaveBeenCalledWith(`${apiUrl}/api/flashcard-sets/1`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });
    });
  });

  describe('addCardToSet', () => {
    it('should add a card to a set', async () => {
      const newCard = {
        front: 'New Front',
        back: 'New Back',
      };

      const mockResponse = {
        id: 1,
        ...newCard,
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await addCardToSet(1, newCard);
      expect(result).toEqual(mockResponse);
      expect(fetch).toHaveBeenCalledWith(`${apiUrl}/api/flashcard-sets/1/cards`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newCard),
      });
    });
  });

  describe('updateCard', () => {
    it('should update a card', async () => {
      const updates = {
        front: 'Updated Front',
        back: 'Updated Back',
      };

      const mockResponse = {
        id: 1,
        ...updates,
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await updateCard(1, updates);
      expect(result).toEqual(mockResponse);
      expect(fetch).toHaveBeenCalledWith(`${apiUrl}/api/flashcard-sets/cards/1`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });
    });
  });

  describe('deleteCard', () => {
    it('should delete a card', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
      });

      await expect(deleteCard(1)).resolves.not.toThrow();
      expect(fetch).toHaveBeenCalledWith(`${apiUrl}/api/flashcard-sets/cards/1`, {
        method: 'DELETE',
      });
    });

    it('should handle deletion errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
      });

      await expect(deleteCard(1)).rejects.toThrow('Failed to delete card');
    });
  });
}); 
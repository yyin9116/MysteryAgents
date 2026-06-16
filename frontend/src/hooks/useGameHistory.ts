import { useState, useEffect } from 'react';

export interface GameHistoryItem {
  id: string;
  type: 'undercover' | 'discussion';
  timestamp: number;
  config: any;
  status: 'active' | 'completed';
}

const STORAGE_KEY = 'killer_game_history';
const MAX_HISTORY = 5;

export const useGameHistory = () => {
  const [history, setHistory] = useState<GameHistoryItem[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        setHistory(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to parse game history', e);
      }
    }
  }, []);

  const saveGame = (game: Omit<GameHistoryItem, 'id' | 'timestamp'>) => {
    const newItem: GameHistoryItem = {
      ...game,
      id: Math.random().toString(36).substr(2, 9),
      timestamp: Date.now(),
    };

    setHistory(prev => {
      const updated = [newItem, ...prev].slice(0, MAX_HISTORY);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    });
  };

  const removeGame = (id: string) => {
    setHistory(prev => {
      const updated = prev.filter(item => item.id !== id);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    });
  };

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem(STORAGE_KEY);
  };

  return {
    history,
    saveGame,
    removeGame,
    clearHistory
  };
};

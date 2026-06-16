import { create } from 'zustand';
import type { GameState } from '../types/game';
import { gameService } from '../services/gameService';

interface GameStore {
    currentGame: GameState | null;
    loading: boolean;
    error: string | null;

    setGame: (game: GameState) => void;
    fetchGameState: (gameId: string) => Promise<void>;
    resetGame: () => void;
}

export const useGameStore = create<GameStore>((set) => ({
    currentGame: null,
    loading: false,
    error: null,

    setGame: (game) => set({ currentGame: game }),

    fetchGameState: async (gameId) => {
        set({ loading: true, error: null });
        try {
            const state = await gameService.getGameState(gameId);
            set({ currentGame: state, loading: false });
        } catch (err: any) {
            set({ error: err.message, loading: false });
        }
    },

    resetGame: () => set({ currentGame: null, error: null }),
}));

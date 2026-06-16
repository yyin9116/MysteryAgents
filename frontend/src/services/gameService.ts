import api from './api';
import type { GameState, GameConfig } from '../types/game';

export const gameService = {
    createGame: async (config: Partial<GameConfig>): Promise<{ game_id: string; agents: any[] }> => {
        const response = await api.post('/api/game/create', config);
        return response.data;
    },

    startGame: async (gameId: string): Promise<any> => {
        const response = await api.post('/api/game/start', { game_id: gameId });
        return response.data;
    },

    nextRound: async (gameId: string): Promise<any> => {
        const response = await api.post('/api/game/next-round', { game_id: gameId });
        return response.data;
    },

    getGameState: async (gameId: string): Promise<GameState> => {
        const response = await api.get(`/api/game/state/${gameId}`);
        return response.data;
    },

    possessAgent: async (gameId: string, agentId: string): Promise<any> => {
        const response = await api.post('/api/game/possess', { game_id: gameId, agent_id: agentId });
        return response.data;
    },

    releaseAgent: async (gameId: string, agentId: string): Promise<any> => {
        const response = await api.post('/api/game/release', { game_id: gameId, agent_id: agentId });
        return response.data;
    },

    submitUserInput: async (gameId: string, agentId: string, speech: string, suspicion: Record<string, number>): Promise<any> => {
        const response = await api.post('/api/game/user-input', { game_id: gameId, agent_id: agentId, speech, suspicion });
        return response.data;
    },

    submitUserVote: async (gameId: string, agentId: string, vote: string, confidence: number): Promise<any> => {
        const response = await api.post('/api/game/user-vote', { game_id: gameId, agent_id: agentId, vote, confidence });
        return response.data;
    },

    saveGame: async (gameId: string, snapshotName?: string): Promise<any> => {
        const response = await api.post('/api/game/save', { game_id: gameId, snapshot_name: snapshotName });
        return response.data;
    },

    loadGame: async (snapshotId: string): Promise<any> => {
        const response = await api.post('/api/game/load', { snapshot_id: snapshotId });
        return response.data;
    },

    listSnapshots: async (gameId?: string): Promise<any> => {
        const url = gameId ? `/api/game/snapshots?game_id=${gameId}` : '/api/game/snapshots';
        const response = await api.get(url);
        return response.data;
    },

    deleteSnapshot: async (snapshotId: string): Promise<any> => {
        const response = await api.delete(`/api/game/snapshot/${snapshotId}`);
        return response.data;
    },
};

export default gameService;

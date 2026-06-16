import api from './api';

export interface ReplayEvent {
    event_type: string;
    round_num: number;
    timestamp: string;
    data: any;
}

export interface ReplayProgress {
    active: boolean;
    current_index?: number;
    total_events?: number;
    progress_percentage?: number;
    current_round?: number;
    total_rounds?: number;
    at_start?: boolean;
    at_end?: boolean;
}

export const replayService = {
    /**
     * Start replay from snapshot
     */
    startReplay: async (snapshotId: string): Promise<{
        status: string;
        snapshot_id: string;
        total_events: number;
        total_rounds: number;
        current_index: number;
    }> => {
        const response = await api.post('/api/replay/start', {
            snapshot_id: snapshotId
        });
        return response.data;
    },

    /**
     * Step forward to next event
     */
    stepForward: async (): Promise<{
        status: string;
        event?: ReplayEvent;
        progress?: ReplayProgress;
        message?: string;
    }> => {
        const response = await api.post('/api/replay/step/forward');
        return response.data;
    },

    /**
     * Step backward to previous event
     */
    stepBackward: async (): Promise<{
        status: string;
        event?: ReplayEvent;
        progress?: ReplayProgress;
        message?: string;
    }> => {
        const response = await api.post('/api/replay/step/backward');
        return response.data;
    },

    /**
     * Jump to specific round
     */
    jumpToRound: async (roundNum: number): Promise<{
        status: string;
        round: number;
        events: ReplayEvent[];
        progress: ReplayProgress;
    }> => {
        const response = await api.post('/api/replay/jump/round', {
            round_num: roundNum
        });
        return response.data;
    },

    /**
     * Jump to specific event index
     */
    jumpToIndex: async (index: number): Promise<{
        status: string;
        event: ReplayEvent;
        progress: ReplayProgress;
    }> => {
        const response = await api.post('/api/replay/jump/index', {
            index
        });
        return response.data;
    },

    /**
     * Get current replay progress
     */
    getProgress: async (): Promise<ReplayProgress> => {
        const response = await api.get('/api/replay/progress');
        return response.data;
    },

    /**
     * Get round summary
     */
    getRoundSummary: async (roundNum: number): Promise<{
        round: number;
        total_events: number;
        descriptions: number;
        eliminations: number;
        events: ReplayEvent[];
    }> => {
        const response = await api.get(`/api/replay/round/${roundNum}`);
        return response.data;
    },

    /**
     * Get agent timeline
     */
    getAgentTimeline: async (agentId: string): Promise<{
        agent_id: string;
        total_events: number;
        events: ReplayEvent[];
    }> => {
        const response = await api.get(`/api/replay/agent/${agentId}`);
        return response.data;
    },

    /**
     * Stop replay
     */
    stopReplay: async (): Promise<{
        status: string;
        snapshot_id?: string;
        total_events?: number;
        events_viewed?: number;
        completion_percentage?: number;
    }> => {
        const response = await api.post('/api/replay/stop');
        return response.data;
    },

    /**
     * Export replay data
     */
    exportReplay: async (): Promise<{
        snapshot_id: string;
        total_events: number;
        total_rounds: number;
        events: ReplayEvent[];
        progress: ReplayProgress;
    }> => {
        const response = await api.get('/api/replay/export');
        return response.data;
    }
};

export default replayService;

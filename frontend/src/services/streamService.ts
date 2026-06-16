/**
 * Game Stream Service
 * 处理 Server-Sent Events (SSE) 实时游戏流
 */

import { buildApiUrl } from './api';

export interface StreamEvent {
    type: 'round_start' | 'agent_thinking' | 'agent_speaking' | 'voting_start' | 'agent_voting' | 'elimination' | 'game_over' | 'round_complete' | 'agent_error' | 'error' | 'duplicate_violation';
    [key: string]: any;
}

export interface AgentThinkingEvent extends StreamEvent {
    type: 'agent_thinking';
    agent_id: string;
    agent_name: string;
    index: number;
    total: number;
}

export interface AgentSpeakingEvent extends StreamEvent {
    type: 'agent_speaking';
    agent_id: string;
    agent_name: string;
    speech: string;
    thought: string;
    suspicion: Record<string, number>;
    index: number;
    total: number;
}

export interface RoundCompleteEvent extends StreamEvent {
    type: 'round_complete';
    round: number;
    conversation_history: any[];
}

export type GameStreamCallback = (event: StreamEvent) => void;

class StreamService {
    private eventSource: EventSource | null = null;
    private abortController: AbortController | null = null;

    constructor() {
    }

    startGameStream(gameId: string, onEvent: GameStreamCallback, onError?: (error: Error) => void): () => void {
        this.stopGameStream();
        this.abortController = new AbortController();
        const url = buildApiUrl('/api/game/stream/start');
        this.connectStream(url, gameId, onEvent, onError);
        return () => this.stopGameStream();
    }

    private async connectStream(
        url: string,
        gameId: string,
        onEvent: GameStreamCallback,
        onError?: (error: Error) => void
    ) {
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ game_id: gameId }),
                signal: this.abortController?.signal,
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) {
                throw new Error('No response body');
            }

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    break;
                }

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            onEvent(data);
                        } catch (e) {
                            console.error('Failed to parse SSE data:', e);
                        }
                    }
                }
            }
        } catch (error) {
            if (error instanceof Error && error.name === 'AbortError') {
                return;
            }

            console.error('Stream connection error:', error);
            if (onError) {
                onError(error as Error);
            }
        }
    }

    stopGameStream() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
        this.closeStream();
    }

    closeStream() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}

export const streamService = new StreamService();

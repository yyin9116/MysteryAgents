/**
 * Werewolf game service for API communication and SSE streaming.
 * 狼人杀游戏服务 - API 通信和 SSE 流式推送
 */

import { buildApiUrl } from './api';

export interface GameConfig {
  playerCount: number;
  provider?: string;
  model: string;
  apiKey?: string;
  baseUrl?: string;
  fastMode?: boolean;
  discussionTurnLimit?: number;
}

export interface Agent {
  agent_id: string;
  name: string;
  mbti_type: string;
  iq_level: string;
  is_alive: boolean;
  is_possessed?: boolean;
  role?: string;
  role_cn?: string;
  faction?: string;
}

export interface CreateGameResponse {
  game_id: string;
  player_count: number;
  agents: Agent[];
  message: string;
}

export interface GameStateResponse {
  game_id: string;
  phase: string;
  current_round: number;
  agents: Record<string, Agent>;
  alive_count: number;
}

export interface AgentRoleResponse {
  agent_id: string;
  name: string;
  role: string;
  role_cn: string;
  faction: string;
  is_alive: boolean;
  witch_potions?: {
    antidote: boolean;
    poison: boolean;
  };
  seer_check_results?: Record<string, string>;
  guard_last_protected?: string;
}

export type WerewolfEventType =
  | 'game_start'
  | 'phase_change'
  | 'night_action'
  | 'night_complete'
  | 'death_announcement'
  | 'discussion'
  | 'agent_speaking'
  | 'vote'
  | 'agent_voting'
  | 'elimination'
  | 'game_over'
  | 'round_complete'
  | 'error';

export interface WerewolfEvent {
  type: WerewolfEventType;
  [key: string]: any;
}

export type EventHandler = (event: WerewolfEvent) => void;

function inferProvider(model: string): string | undefined {
  const normalized = model.toLowerCase();
  if (normalized.startsWith('openai/')) return 'openai';
  if (normalized.startsWith('anthropic/')) return 'anthropic';
  if (normalized.startsWith('alibaba/') || normalized.includes('qwen')) return 'alibaba';
  if (normalized.startsWith('zhipu/') || normalized.includes('glm')) return 'zhipu';
  if (normalized.startsWith('ollama/')) return 'ollama';
  return undefined;
}

export async function createGame(config: GameConfig): Promise<CreateGameResponse> {
  const provider = config.provider || inferProvider(config.model);
  const model = config.model.includes('/') ? config.model.split('/').slice(1).join('/') : config.model;

  const response = await fetch(buildApiUrl('/api/werewolf/create'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      player_count: config.playerCount,
      fast_mode: config.fastMode ?? false,
      discussion_turn_limit: config.discussionTurnLimit,
      model_config_data: {
        provider,
        model,
        api_key: config.apiKey,
        base_url: config.baseUrl,
      },
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create game');
  }

  return response.json();
}

export async function getGameState(gameId: string): Promise<GameStateResponse> {
  const response = await fetch(buildApiUrl(`/api/werewolf/state/${gameId}`));

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get game state');
  }

  return response.json();
}

export async function getAgentRole(gameId: string, agentId: string): Promise<AgentRoleResponse> {
  const response = await fetch(buildApiUrl(`/api/werewolf/agent-role/${gameId}/${agentId}`));

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get agent role');
  }

  return response.json();
}

export async function executeNightAction(
  gameId: string,
  agentId: string,
  actionType: string,
  targetId?: string
): Promise<any> {
  const response = await fetch(buildApiUrl('/api/werewolf/night-action'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      game_id: gameId,
      agent_id: agentId,
      action_type: actionType,
      target_id: targetId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to execute night action');
  }

  return response.json();
}

export async function submitVote(
  gameId: string,
  voterId: string,
  targetId: string
): Promise<any> {
  const response = await fetch(buildApiUrl('/api/werewolf/vote'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      game_id: gameId,
      voter_id: voterId,
      target_id: targetId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to submit vote');
  }

  return response.json();
}

export function connectGameStream(
  gameId: string,
  onEvent: EventHandler
): () => void {
  const eventSource = new EventSource(buildApiUrl(`/api/werewolf/stream/${gameId}`));

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onEvent(data);
    } catch (error) {
      console.error('Failed to parse SSE event:', error);
    }
  };

  eventSource.onerror = (error) => {
    console.error('SSE connection error:', error);
    onEvent({
      type: 'error',
      message: 'Connection lost. Attempting to reconnect...',
    });
  };

  return () => {
    eventSource.close();
  };
}

export function connectGameStreamWithRetry(
  gameId: string,
  onEvent: EventHandler,
  maxRetries: number = 5
): () => void {
  let retryCount = 0;
  let eventSource: EventSource | null = null;
  let isClosed = false;

  const connect = () => {
    if (isClosed) return;

    eventSource = new EventSource(buildApiUrl(`/api/werewolf/stream/${gameId}`));

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onEvent(data);
        retryCount = 0;
      } catch (error) {
        console.error('Failed to parse SSE event:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      eventSource?.close();

      if (!isClosed && retryCount < maxRetries) {
        retryCount++;
        onEvent({
          type: 'error',
          message: `Connection lost. Reconnecting (${retryCount}/${maxRetries})...`,
        });

        const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 16000);
        setTimeout(connect, delay);
      } else if (retryCount >= maxRetries) {
        onEvent({
          type: 'error',
          message: 'Failed to reconnect after multiple attempts.',
        });
      }
    };
  };

  connect();

  return () => {
    isClosed = true;
    eventSource?.close();
  };
}

export async function deleteGame(gameId: string): Promise<void> {
  const response = await fetch(buildApiUrl(`/api/werewolf/game/${gameId}`), {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete game');
  }
}

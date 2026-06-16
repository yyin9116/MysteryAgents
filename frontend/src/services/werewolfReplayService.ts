/**
 * Werewolf game replay service for timeline playback.
 * 狼人杀游戏回放服务 - 时间轴回放功能
 */

import { buildApiUrl } from './api';

export interface GameEvent {
  event_id: string;
  timestamp: string;
  event_type: string;
  round: number;
  phase: string;
  data: Record<string, any>;
  game_state_snapshot?: Record<string, any>;
}

export interface GameReplayResponse {
  game_id: string;
  events: GameEvent[];
  total_events: number;
  player_count?: number;
  alive_count?: number;
  current_round: number;
  current_phase: string;
  winner?: string | null;
  game_over_reason?: string | null;
  started_at?: string;
}

export interface ReplaySummary {
  game_id: string;
  total_events: number;
  player_count?: number;
  alive_count?: number;
  current_round: number;
  current_phase: string;
  winner?: string | null;
  game_over_reason?: string | null;
  updated_at?: string;
  started_at?: string;
  is_active?: boolean;
}

export interface ListWerewolfReplaysParams {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: 'all' | 'active' | 'finished';
  sortBy?: 'updated_at' | 'started_at' | 'total_events';
  sortOrder?: 'asc' | 'desc';
}

export interface ListWerewolfReplaysResponse {
  replays: ReplaySummary[];
  total: number;
  page: number;
  page_size: number;
  sort_by?: string;
  sort_order?: string;
  stats?: {
    total: number;
    active: number;
    finished: number;
  };
}

export interface ReplayState {
  currentEventIndex: number;
  isPlaying: boolean;
  playbackSpeed: number;
  gameState: Record<string, any> | null;
}

export async function fetchGameReplay(gameId: string): Promise<GameReplayResponse> {
  const response = await fetch(buildApiUrl(`/api/werewolf/replay/${gameId}`));

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch game replay');
  }

  return response.json();
}

export async function listWerewolfReplays(
  params: ListWerewolfReplaysParams = {}
): Promise<ListWerewolfReplaysResponse> {
  const query = new URLSearchParams();
  query.set('page', String(params.page ?? 1));
  query.set('page_size', String(params.pageSize ?? 5));
  if (params.search?.trim()) {
    query.set('search', params.search.trim());
  }
  if (params.status && params.status !== 'all') {
    query.set('status', params.status);
  }
  if (params.sortBy) {
    query.set('sort_by', params.sortBy);
  }
  if (params.sortOrder) {
    query.set('sort_order', params.sortOrder);
  }

  const response = await fetch(buildApiUrl(`/api/werewolf/replays?${query.toString()}`));

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to list werewolf replays');
  }

  return response.json();
}

export async function deleteWerewolfReplay(gameId: string): Promise<void> {
  const response = await fetch(buildApiUrl(`/api/werewolf/replay/${gameId}`), {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete werewolf replay');
  }
}

export async function deleteFinishedWerewolfReplays(): Promise<{ deleted_count: number }> {
  const response = await fetch(buildApiUrl('/api/werewolf/replays/finished'), {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete finished replays');
  }

  return response.json();
}

export async function downloadWerewolfReplay(gameId: string): Promise<void> {
  const response = await fetch(buildApiUrl(`/api/werewolf/replay/${gameId}/export`));

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to export replay');
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${gameId}-replay.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

export function getGameStateAtEvent(
  events: GameEvent[],
  eventIndex: number
): Record<string, any> | null {
  if (eventIndex < 0 || eventIndex >= events.length) {
    return null;
  }

  const event = events[eventIndex];

  if (event.game_state_snapshot) {
    return event.game_state_snapshot;
  }

  let state: Record<string, any> = {
    round: 1,
    phase: 'night',
    agents: {},
    alive_agents: [],
    dead_agents: [],
    night_actions: [],
    votes: {},
    conversation_history: []
  };

  for (let i = 0; i <= eventIndex; i++) {
    const evt = events[i];
    state = applyEventToState(state, evt);
  }

  return state;
}

function applyEventToState(state: Record<string, any>, event: GameEvent): Record<string, any> {
  const newState = { ...state };

  switch (event.event_type) {
    case 'phase_change':
      newState.phase = event.data.new_phase || event.data.to_phase || event.phase;
      newState.round = event.round;
      break;

    case 'night_action':
      if (!newState.night_actions) {
        newState.night_actions = [];
      }
      newState.night_actions.push(event.data);
      break;

    case 'death_announcement':
      if (event.game_state_snapshot) {
        return {
          ...newState,
          ...event.game_state_snapshot,
          round: event.game_state_snapshot.current_round ?? event.round,
          current_round: event.game_state_snapshot.current_round ?? event.round,
          dead_agents: event.data.dead_agents || event.data.deaths || [],
        };
      }
      if (event.data.dead_agents || event.data.deaths) {
        const deadAgents = event.data.dead_agents || event.data.deaths || [];
        newState.dead_agents = [...(newState.dead_agents || []), ...deadAgents];
        newState.alive_agents = (newState.alive_agents || []).filter((agent: any) => {
          const agentId = typeof agent === 'string' ? agent : agent?.agent_id;
          return !deadAgents.includes(agentId);
        });
      }
      break;

    case 'discussion':
      if (!newState.conversation_history) {
        newState.conversation_history = [];
      }
      newState.conversation_history.push({
        agent_id: event.data.agent_id,
        agent_name: event.data.agent_name,
        message: event.data.message || event.data.speech,
        timestamp: event.timestamp
      });
      break;

    case 'vote':
      if (!newState.votes) {
        newState.votes = {};
      }
      newState.votes[event.data.voter_id] = event.data.target_id;
      break;

    case 'elimination':
      if (event.data.eliminated_agent_id || event.data.eliminated_id) {
        const eliminatedAgentId = event.data.eliminated_agent_id || event.data.eliminated_id;
        newState.dead_agents = [...(newState.dead_agents || []), eliminatedAgentId];
        newState.alive_agents = (newState.alive_agents || []).filter((agent: any) => {
          const agentId = typeof agent === 'string' ? agent : agent?.agent_id;
          return agentId !== eliminatedAgentId;
        });
      }
      newState.votes = {};
      break;

    case 'game_over':
      newState.winner = event.data.winner;
      newState.game_over_reason = event.data.reason;
      break;
  }

  return newState;
}

export function getEventColor(eventType: string): string {
  const colorMap: Record<string, string> = {
    'phase_change': '#8b5cf6',
    'night_action': '#ef4444',
    'discussion': '#3b82f6',
    'vote': '#f59e0b',
    'elimination': '#dc2626',
    'death_announcement': '#991b1b',
    'game_over': '#10b981'
  };

  return colorMap[eventType] || '#6b7280';
}

export function getEventIcon(eventType: string): string {
  const iconMap: Record<string, string> = {
    'phase_change': '🌓',
    'night_action': '🌙',
    'discussion': '💬',
    'vote': '🗳️',
    'elimination': '💀',
    'death_announcement': '⚰️',
    'game_over': '🏆'
  };

  return iconMap[eventType] || '📌';
}

export function getEventDisplayName(eventType: string): string {
  const nameMap: Record<string, string> = {
    'phase_change': '阶段切换',
    'night_action': '夜晚行动',
    'discussion': '讨论发言',
    'vote': '投票',
    'elimination': '淘汰',
    'death_announcement': '死亡公布',
    'game_over': '游戏结束'
  };

  return nameMap[eventType] || eventType;
}

export function formatEventData(event: GameEvent): string {
  switch (event.event_type) {
    case 'phase_change':
      return `进入${event.data.new_phase || event.data.to_phase || event.phase}阶段`;
    case 'night_action': {
      const actionType = event.data.action_type || '';
      const actor = event.data.actor_name || event.data.actor_id || '未知';
      const target = event.data.target_name || event.data.target_id || '';
      return `${actor} 执行 ${actionType}${target ? ` → ${target}` : ''}`;
    }
    case 'death_announcement': {
      const deadAgents = event.data.dead_agents || event.data.deaths || [];
      if (event.data.message) {
        return event.data.message;
      }
      if (deadAgents.length === 0) {
        return '昨晚是平安夜';
      }
      return `${deadAgents.join(', ')} 死亡`;
    }
    case 'discussion': {
      const speaker = event.data.agent_name || event.data.agent_id || '未知';
      const message = event.data.message || event.data.speech || '';
      return `${speaker}: ${message.substring(0, 50)}${message.length > 50 ? '...' : ''}`;
    }
    case 'vote': {
      const voter = event.data.voter_name || event.data.voter_id || '未知';
      const voteTarget = event.data.target_name || event.data.target_id || '未知';
      return `${voter} 投票给 ${voteTarget}`;
    }
    case 'elimination': {
      const eliminated = event.data.eliminated_agent_name || event.data.eliminated_name || event.data.eliminated_agent_id || event.data.eliminated_id || '未知';
      return `${eliminated} 被淘汰`;
    }
    case 'game_over': {
      const winner = event.data.winner || '未知';
      return `${winner}阵营获胜`;
    }
    default:
      return JSON.stringify(event.data);
  }
}

export function calculateEventPosition(
  eventIndex: number,
  totalEvents: number
): number {
  if (totalEvents <= 1) return 0;
  return (eventIndex / (totalEvents - 1)) * 100;
}

export function findEventIndexFromPosition(
  position: number,
  totalEvents: number
): number {
  if (totalEvents <= 1) return 0;
  const index = Math.round((position / 100) * (totalEvents - 1));
  return Math.max(0, Math.min(index, totalEvents - 1));
}

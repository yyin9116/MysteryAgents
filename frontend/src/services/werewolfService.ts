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
  /** 按玩家槽位覆盖模型；null/undefined 表示继承全局配置 */
  agentModels?: (AgentModelOverride | null)[];
  /** 主题角色阵容（名字+MBTI+性别绑定）；提供时开局直接采用并跳过 LLM 改名 */
  roster?: RosterEntry[];
  /** 阵容角色来源作品名；让公开发言带入角色经典气质 */
  rosterWork?: string;
  /** 智能模型分配：按角色强度分档挑模型 + 思考强度 */
  autoAssign?: {
    /** 候选模型列表（在线目录，已应用禁用勾选） */
    candidates?: string[];
    /** 禁用（不参与分配）的完整模型 id 列表；精确匹配 */
    disabledModels?: string[];
    effortByRole: boolean;
  };
  /** 讨论风格：speech=圆桌发言；group_chat=QQ 群聊气泡 */
  chatStyle?: 'speech' | 'group_chat';
  /** 是否用 LLM 为玩家生成个性化昵称；关闭时使用经典角色库命名 */
  llmNaming?: boolean;
  /** 参与模式：spectate=围观（默认）；participate=玩家接管席位参与 */
  playerMode?: 'spectate' | 'participate';
  /** 参与模式下玩家接管的席位（1 起始） */
  playerSeat?: number;
}

/** 主题角色阵容中的单个角色 */
export interface RosterEntry {
  name: string;
  mbti: string;
  gender: '男' | '女' | string;
}

/** 单个玩家的模型覆盖项 */
export interface AgentModelOverride {
  provider?: string;
  model: string;
  apiKey?: string;
  baseUrl?: string;
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
  /** 该玩家使用的模型标识（多模型实验） */
  model_label?: string | null;
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
  | 'player_input_required'
  | 'game_terminated'
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

/** 单个玩家的模型覆盖项，转换为后端 model_config dict */
function toAgentModelPayload(entry: AgentModelOverride | null) {
  if (!entry || !entry.model) return null;
  const provider = entry.provider || inferProvider(entry.model) || 'openai';
  const model = entry.model.includes('/')
    ? entry.model.split('/').slice(1).join('/')
    : entry.model;
  return {
    provider,
    model,
    api_key: entry.apiKey ?? null,
    base_url: entry.baseUrl ?? null,
  };
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
      chat_style: config.chatStyle || 'speech',
      ...(config.autoAssign
        ? {
            auto_model_assign: {
              candidates: config.autoAssign.candidates ?? [],
              disabled_models: config.autoAssign.disabledModels ?? [],
              effort_by_role: config.autoAssign.effortByRole,
            },
          }
        : {}),
      model_config_data: {
        provider,
        model,
        api_key: config.apiKey,
        base_url: config.baseUrl,
      },
      ...(config.agentModels
        ? { agent_model_configs: config.agentModels.map(toAgentModelPayload) }
        : {}),
      ...(config.roster && config.roster.length
        ? {
            roster: config.roster.map((r) => ({ name: r.name, mbti: r.mbti, gender: r.gender })),
            roster_work: config.rosterWork || undefined,
          }
        : {}),
      llm_naming: config.llmNaming ?? true,
      player_mode: config.playerMode ?? 'spectate',
      ...(config.playerMode === 'participate'
        ? { player_agent_id: `werewolf_agent_${config.playerSeat ?? 1}` }
        : {}),
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create game');
  }

  return response.json();
}

/** 按作品预览主题角色阵容（名字 + MBTI + 性别绑定） */
export async function previewRoster(payload: {
  work: string;
  count: number;
  model_config_data?: Record<string, unknown>;
}): Promise<{ success: boolean; work: string; roster: RosterEntry[] }> {
  const response = await fetch(buildApiUrl('/api/werewolf/roster/preview'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to preview roster');
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

/** 对局节奏控制：mode=auto 连播 / manual 步进；action='advance' 手动放行下一步 */
/** 夺席模式：玩家为被接管的 agent 提交公开发言 */
export async function submitPlayerSpeech(
  gameId: string,
  agentId: string,
  content: string
): Promise<{ success: boolean; agent_id: string; queued: boolean }> {
  const response = await fetch(buildApiUrl('/api/werewolf/player-speech'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, agent_id: agentId, content }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to submit speech');
  }
  return response.json();
}

export async function controlGameStream(
  gameId: string,
  payload: { mode?: 'auto' | 'manual'; speed?: number; action?: 'advance' }
): Promise<{ success: boolean; auto: boolean; speed: number }> {
  const response = await fetch(buildApiUrl(`/api/werewolf/stream/${gameId}/control`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to control game stream');
  }
  return response.json();
}

export function connectGameStream(
  gameId: string,
  onEvent: EventHandler
): () => void {  const eventSource = new EventSource(buildApiUrl(`/api/werewolf/stream/${gameId}`));

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

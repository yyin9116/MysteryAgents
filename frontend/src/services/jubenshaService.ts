/**
 * Jubensha (剧本杀) service for API communication and SSE streaming.
 * 剧本杀游戏服务 - 剧本导入/对局创建/SSE 流式推送/回放导出
 */

import { buildApiUrl } from './api';

// ---------------------------------------------------------------------- //
// Types
// ---------------------------------------------------------------------- //

/** 剧本列表项（轻量 meta） */
export interface ScriptSummary {
  script_id: string;
  title: string;
  player_count: number;
  difficulty: 'easy' | 'standard' | 'hard' | string;
  estimated_minutes: number;
  tags: string[];
  source: string;
  builtin: boolean;
}

/** 剧本角色（脱敏：script/secret_knowledge 为空） */
export interface ScriptCharacter {
  char_id: string;
  name: string;
  age?: number;
  public_profile: string;
  camp?: string | null;
  script?: string;
  mission?: string;
  secret_knowledge?: string[];
}

/** 剧本详情（truth 仅结算后可见） */
export interface ScriptPackDetail {
  script_id: string;
  schema_version: number;
  meta: ScriptSummary & { language: string };
  characters: ScriptCharacter[];
  clues: Array<{
    clue_id: string;
    title: string;
    content: string;
    distribution: { round: number; pool?: string | null };
  }>;
  truth?: { murderer: string | null; timeline: Array<{ time: string; event: string }>; case_replay: string };
}

export interface JubenshaCharacterState {
  char_id: string;
  name: string;
  public_profile: string;
  camp: string | null;
  model_label?: string | null;
}

export interface JubenshaGameState {
  success?: boolean;
  game_id: string;
  script_id: string;
  title: string;
  phase: string;
  current_round: number;
  discussion_rounds: number;
  clue_rounds_done: number;
  player_mode: string;
  player_char_id: string | null;
  characters: JubenshaCharacterState[];
  conversation_history?: any[];
  votes?: Record<string, { target: string; target_name: string }>;
  reveal?: any | null;
}

/** 参与模式下玩家自己的私密剧本 */
export interface MyScript {
  char_id: string;
  name: string;
  public_profile: string;
  script: string;
  mission: string;
  secret_knowledge: string[];
  camp: string;
}

export interface CreateJubenshaResponse extends JubenshaGameState {
  my_script: MyScript | null;
}

export interface JubenshaGameConfig {
  scriptId: string;
  provider?: string;
  model: string;
  apiKey?: string;
  baseUrl?: string;
  chatStyle?: 'speech' | 'group_chat';
  /** 执行框架：agentscope（默认，ReActAgent + MsgHub）| legacy（litellm 直调回退） */
  runtime?: 'legacy' | 'agentscope';
  autoAssign?: {
    candidates?: string[];
    disabledModels?: string[];
    effortByRole: boolean;
  };
  playerMode?: 'spectate' | 'participate';
  playerCharId?: string;
}

export type JubenshaEventType =
  | 'game_start'
  | 'phase_change'
  | 'agent_speaking'
  | 'clue_granted'
  | 'agent_voting'
  | 'player_input_required'
  | 'turn_error'
  | 'reveal'
  | 'game_over'
  | 'error';

export interface JubenshaEvent {
  type: JubenshaEventType;
  [key: string]: any;
}

export type JubenshaEventHandler = (event: JubenshaEvent) => void;

// ---------------------------------------------------------------------- //
// Helpers
// ---------------------------------------------------------------------- //

// ---------------------------------------------------------------------- //
// Scripts API
// ---------------------------------------------------------------------- //

export async function listScripts(): Promise<ScriptSummary[]> {
  const response = await fetch(buildApiUrl('/api/jubensha/scripts'));
  if (!response.ok) throw new Error('获取剧本列表失败');
  const data = await response.json();
  return data.scripts ?? [];
}

export async function getScript(scriptId: string): Promise<ScriptPackDetail> {
  const response = await fetch(buildApiUrl(`/api/jubensha/scripts/${encodeURIComponent(scriptId)}`));
  if (!response.ok) throw new Error('获取剧本详情失败');
  return response.json();
}

export interface ImportScriptResult {
  success: boolean;
  report: { ok: boolean; errors: string[]; warnings: string[]; script_id: string };
  saved_path?: string | null;
}

/** 导入剧本包 JSON（可选落盘持久化） */
export async function importScript(pack: Record<string, any>, save = false): Promise<ImportScriptResult> {
  const response = await fetch(buildApiUrl('/api/jubensha/import'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pack, save }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = typeof error.detail === 'object' ? error.detail : { errors: [error.detail] };
    throw new Error(
      detail.errors?.length ? `剧本包校验失败：${detail.errors.join('；')}` : (error.detail || '导入失败')
    );
  }
  return response.json();
}

// ---------------------------------------------------------------------- //
// Game API
// ---------------------------------------------------------------------- //

function inferProvider(model: string): string | undefined {
  const normalized = model.toLowerCase();
  if (normalized.startsWith('openai/')) return 'openai';
  if (normalized.startsWith('anthropic/')) return 'anthropic';
  if (normalized.startsWith('alibaba/') || normalized.includes('qwen')) return 'alibaba';
  if (normalized.startsWith('zhipu/') || normalized.includes('glm')) return 'zhipu';
  if (normalized.startsWith('ollama/')) return 'ollama';
  return undefined;
}

export async function createJubenshaGame(config: JubenshaGameConfig): Promise<CreateJubenshaResponse> {
  const provider = config.provider || inferProvider(config.model);
  const model = config.model.includes('/') ? config.model.split('/').slice(1).join('/') : config.model;

  const response = await fetch(buildApiUrl('/api/jubensha/create'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      script_id: config.scriptId,
      chat_style: config.chatStyle || 'speech',
      runtime: config.runtime || 'agentscope',
      ...(config.autoAssign
        ? {
            auto_model_assign: {
              candidates: config.autoAssign.candidates ?? [],
              disabled_models: config.autoAssign.disabledModels ?? [],
              effort_by_role: config.autoAssign.effortByRole,
            },
          }
        : {}),
      model_config_data: { provider, model, api_key: config.apiKey, base_url: config.baseUrl },
      player_mode: config.playerMode ?? 'spectate',
      ...(config.playerMode === 'participate' && config.playerCharId
        ? { player_char_id: config.playerCharId }
        : {}),
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || '创建对局失败');
  }
  return response.json();
}

export async function getJubenshaGameState(gameId: string): Promise<JubenshaGameState> {
  const response = await fetch(buildApiUrl(`/api/jubensha/game/${gameId}`));
  if (!response.ok) throw new Error('获取对局状态失败');
  return response.json();
}

export async function deleteJubenshaGame(gameId: string): Promise<void> {
  const response = await fetch(buildApiUrl(`/api/jubensha/game/${gameId}`), { method: 'DELETE' });
  if (!response.ok) throw new Error('终止/删除对局失败');
}

/** 夺席代打：玩家为接管的角色提交公开发言 */
export async function submitJubenshaPlayerSpeech(
  gameId: string,
  charId: string,
  content: string
): Promise<{ success: boolean; char_id: string; queued: boolean }> {
  const response = await fetch(buildApiUrl('/api/jubensha/player-speech'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, char_id: charId, content }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || '提交发言失败');
  }
  return response.json();
}

/** 参与模式：玩家提交投票指认 */
export async function submitJubenshaPlayerVote(
  gameId: string,
  charId: string,
  targetCharId: string,
  reason = ''
): Promise<{ success: boolean; queued: boolean }> {
  const response = await fetch(buildApiUrl('/api/jubensha/player-vote'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId, char_id: charId, target_char_id: targetCharId, reason }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || '提交投票失败');
  }
  return response.json();
}

/** 对局节奏控制（复用狼人杀 StreamControl 协议） */
export async function controlJubenshaStream(
  gameId: string,
  payload: { mode?: 'auto' | 'manual'; speed?: number; action?: 'advance' }
): Promise<{ success: boolean; auto: boolean; speed: number }> {
  const response = await fetch(buildApiUrl(`/api/jubensha/stream/${gameId}/control`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || '节奏控制失败');
  }
  return response.json();
}

// ---------------------------------------------------------------------- //
// SSE stream（带自动重连 + 指数退避）
// ---------------------------------------------------------------------- //

export function connectJubenshaStream(gameId: string, onEvent: JubenshaEventHandler): () => void {
  let retryCount = 0;
  let eventSource: EventSource | null = null;
  let isClosed = false;

  const connect = () => {
    if (isClosed) return;
    eventSource = new EventSource(buildApiUrl(`/api/jubensha/stream/${gameId}`));

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onEvent(data);
        retryCount = 0;
      } catch (err) {
        console.error('Failed to parse jubensha SSE event:', err);
      }
    };

    eventSource.onerror = () => {
      eventSource?.close();
      if (!isClosed && retryCount < 5) {
        retryCount++;
        onEvent({ type: 'error', message: `连接中断，正在重连（${retryCount}/5）...` });
        const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 16000);
        setTimeout(connect, delay);
      } else if (retryCount >= 5) {
        onEvent({ type: 'error', message: '多次重连失败，对局仍在后台进行，请稍后刷新重试。' });
      }
    };
  };

  connect();
  return () => {
    isClosed = true;
    eventSource?.close();
  };
}

// ---------------------------------------------------------------------- //
// Replay / Export
// ---------------------------------------------------------------------- //

export interface ReplayListItem {
  game_id: string;
  title?: string;
  script_id?: string;
  mode?: string;
  finished_at?: string;
  is_active?: boolean;
  [key: string]: any;
}

export async function listJubenshaReplays(): Promise<ReplayListItem[]> {
  const response = await fetch(buildApiUrl('/api/jubensha/replays'));
  if (!response.ok) throw new Error('获取回放列表失败');
  const data = await response.json();
  return data.replays ?? [];
}

/** 导出回放 JSON（含 ScriptPack 元信息，可作为数据集样本） */
export async function exportJubenshaReplay(gameId: string): Promise<void> {
  const response = await fetch(buildApiUrl(`/api/jubensha/replay/${gameId}/export`));
  if (!response.ok) throw new Error('导出回放失败');
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${gameId}-replay.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------- //
// 智能体评估（MIRAGE 风格指标）
// ---------------------------------------------------------------------- //

export interface EvaluationReport {
  evaluated: boolean;
  murderer_name: string | null;
  victory_mrr: number | null;
  tii: number | null;
  tii_details?: Record<string, any>;
  cic: number | null;
  ici: number | null;
  sci_avg: number | null;
  ability_avg_overall: number | null;
  llm_scored: boolean;
  agents: Array<{
    char_id: string;
    name: string;
    camp: string;
    model: string | null;
    abilities: { rp: number; ra: number; cc: number; do: number; ct: number } | null;
    ability_avg: number | null;
    sci: number | null;
    comment: string;
    cic_detail: { clues_received: number; clue_usage_ratio: number | null };
    ici_detail: { speeches: number; bubbles: number; question_rate: number };
  }>;
}

/** 生成（或返回已缓存的）评估报告 */
export async function evaluateJubenshaGame(gameId: string): Promise<EvaluationReport> {
  const response = await fetch(buildApiUrl(`/api/jubensha/game/${gameId}/evaluate`), { method: 'POST' });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err?.detail?.message || err?.detail || '生成评估报告失败');
  }
  const data = await response.json();
  return data.evaluation;
}

// ---------------------------------------------------------------------- //
// AI 即兴创作（improv）
// ---------------------------------------------------------------------- //

export interface ImprovResult {
  success: boolean;
  report: { ok: boolean; errors: string[]; warnings: string[]; script_id: string };
  saved_path: string | null;
  script: ScriptSummary;
}

/** 根据玩家的天马行空设定，AI 即兴创作一个可开局的剧本 */
export async function improvScript(
  idea: string,
  playerCount: number,
  modelConfigData?: Record<string, any> | null,
): Promise<ImprovResult> {
  const response = await fetch(buildApiUrl('/api/jubensha/improv'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      idea,
      player_count: playerCount,
      model_config_data: modelConfigData ?? null,
      save: true,
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err?.detail?.message || err?.detail || 'AI 创作失败，请重试');
  }
  return response.json();
}

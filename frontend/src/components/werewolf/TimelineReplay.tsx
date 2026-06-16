/**
 * Timeline Replay Component for Werewolf Game
 * 狼人杀游戏时间轴回放组件
 *
 * Features:
 * - Horizontal scrolling timeline
 * - Event markers with different colors
 * - Drag-to-jump functionality
 * - Event details panel
 * - Playback controls (play/pause/forward/backward)
 * - State reconstruction at any point
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  fetchGameReplay,
  getGameStateAtEvent,
  getEventColor,
  getEventIcon,
  getEventDisplayName,
  calculateEventPosition,
  findEventIndexFromPosition,
  type GameEvent,
  type GameReplayResponse
} from '../../services/werewolfReplayService';

interface TimelineReplayProps {
  gameId: string;
  onClose: () => void;
}

type ProcessStepKey = 'night' | 'dawn' | 'discussion' | 'voting' | 'resolution';

interface ProcessStep {
  key: ProcessStepKey;
  label: string;
  caption: string;
  icon: string;
}

const PROCESS_STEPS: ProcessStep[] = [
  { key: 'night', label: '夜晚行动', caption: '狼人/神职暗中决策', icon: '🌙' },
  { key: 'dawn', label: '天亮结算', caption: '公布死亡与平安夜', icon: '🌅' },
  { key: 'discussion', label: '白天发言', caption: '公开站边与推理', icon: '💬' },
  { key: 'voting', label: '放逐投票', caption: '票型逐步成形', icon: '🗳️' },
  { key: 'resolution', label: '结果结算', caption: '淘汰/胜负确认', icon: '⚖️' },
];

const PHASE_LABELS: Record<string, string> = {
  night: '夜晚',
  dawn: '天亮',
  day_discussion: '讨论',
  day_voting: '投票',
  game_over: '已结束',
};

const ACTION_LABELS: Record<string, string> = {
  werewolf_kill: '狼人袭击',
  seer_check: '预言家查验',
  witch_save: '女巫解药',
  witch_poison: '女巫毒药',
  guard_protect: '守卫守护',
};

function formatPhaseLabel(phase?: string | null) {
  return phase ? PHASE_LABELS[phase] || phase : '未记录';
}

function getReplayAtmosphere(stepKey: ProcessStepKey) {
  switch (stepKey) {
    case 'night':
      return {
        shell: 'border-violet-400/25 bg-[radial-gradient(circle_at_20%_15%,rgba(124,58,237,0.22),transparent_34%),linear-gradient(135deg,rgba(15,23,42,0.96),rgba(10,7,28,0.9))]',
        accent: 'from-violet-300 via-fuchsia-300 to-slate-200',
        label: '夜雾回放',
      };
    case 'dawn':
      return {
        shell: 'border-amber-300/25 bg-[radial-gradient(circle_at_50%_0%,rgba(251,191,36,0.22),transparent_36%),linear-gradient(135deg,rgba(24,24,27,0.96),rgba(69,26,3,0.82))]',
        accent: 'from-amber-200 via-orange-300 to-rose-200',
        label: '晨光复盘',
      };
    case 'discussion':
      return {
        shell: 'border-cyan-300/25 bg-[radial-gradient(circle_at_20%_80%,rgba(14,165,233,0.18),transparent_35%),linear-gradient(135deg,rgba(12,32,48,0.96),rgba(15,23,42,0.88))]',
        accent: 'from-cyan-200 via-sky-300 to-blue-300',
        label: '声纹复盘',
      };
    case 'voting':
      return {
        shell: 'border-orange-300/25 bg-[radial-gradient(circle_at_80%_30%,rgba(249,115,22,0.2),transparent_34%),linear-gradient(135deg,rgba(43,20,7,0.94),rgba(15,23,42,0.9))]',
        accent: 'from-orange-200 via-red-300 to-yellow-200',
        label: '票压复盘',
      };
    case 'resolution':
      return {
        shell: 'border-red-300/25 bg-[radial-gradient(circle_at_50%_50%,rgba(239,68,68,0.18),transparent_34%),linear-gradient(135deg,rgba(45,10,10,0.94),rgba(15,23,42,0.9))]',
        accent: 'from-red-200 via-amber-200 to-white',
        label: '终局复盘',
      };
  }
}

function getProcessStepKey(event?: GameEvent | null): ProcessStepKey {
  if (!event) return 'night';
  if (event.event_type === 'night_action') return 'night';
  if (event.event_type === 'death_announcement') return 'dawn';
  if (event.event_type === 'discussion') return 'discussion';
  if (event.event_type === 'vote') return 'voting';
  if (event.event_type === 'elimination' || event.event_type === 'game_over') return 'resolution';
  if (event.phase === 'dawn') return 'dawn';
  if (event.phase === 'day_discussion') return 'discussion';
  if (event.phase === 'day_voting') return 'voting';
  if (event.phase === 'game_over') return 'resolution';
  return 'night';
}

function buildVoteTally(events: GameEvent[], currentIndex: number, round?: number) {
  const tally = new Map<string, { targetName: string; count: number; voters: string[] }>();
  events.slice(0, currentIndex + 1).forEach((event) => {
    if (event.event_type !== 'vote' || event.round !== round) return;
    const targetId = event.data.target_id || 'unknown';
    const targetName = event.data.target_name || targetId;
    const voterName = event.data.voter_name || event.data.voter_id || '未知玩家';
    const entry = tally.get(targetId) || { targetName, count: 0, voters: [] as string[] };
    entry.count += 1;
    entry.voters.push(voterName);
    tally.set(targetId, entry);
  });
  return Array.from(tally.values()).sort((a, b) => b.count - a.count);
}

function getStepIndex(stepKey: ProcessStepKey) {
  return PROCESS_STEPS.findIndex((step) => step.key === stepKey);
}

export const TimelineReplay: React.FC<TimelineReplayProps> = ({ gameId, onClose }) => {
  const [replayData, setReplayData] = useState<GameReplayResponse | null>(null);
  const [currentEventIndex, setCurrentEventIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<GameEvent | null>(null);
  const [gameState, setGameState] = useState<Record<string, any> | null>(null);
  const [detailPanel, setDetailPanel] = useState<null | 'event' | 'state' | 'votes' | 'night' | 'discussion'>(null);

  const timelineRef = useRef<HTMLDivElement>(null);
  const playbackIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch replay data on mount
  useEffect(() => {
    const loadReplay = async () => {
      try {
        setLoading(true);
        const data = await fetchGameReplay(gameId);
        setReplayData(data);

        // Set initial event
        if (data.events.length > 0) {
          setSelectedEvent(data.events[0]);
          const state = getGameStateAtEvent(data.events, 0);
          setGameState(state);
        }

        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load replay');
      } finally {
        setLoading(false);
      }
    };

    loadReplay();
  }, [gameId]);

  // Handle playback
  useEffect(() => {
    if (isPlaying && replayData) {
      const interval = 1000 / playbackSpeed; // Adjust speed

      playbackIntervalRef.current = setInterval(() => {
        setCurrentEventIndex((prev) => {
          if (prev >= replayData.events.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, interval);

      return () => {
        if (playbackIntervalRef.current) {
          clearInterval(playbackIntervalRef.current);
        }
      };
    }
  }, [isPlaying, playbackSpeed, replayData]);

  // Update selected event and game state when index changes
  useEffect(() => {
    if (replayData && replayData.events.length > 0) {
      const event = replayData.events[currentEventIndex];
      setSelectedEvent(event);

      const state = getGameStateAtEvent(replayData.events, currentEventIndex);
      setGameState(state);
    }
  }, [currentEventIndex, replayData]);

  // Handle timeline drag
  const handleTimelineDrag = useCallback((clientX: number) => {
    if (!timelineRef.current || !replayData) return;

    const rect = timelineRef.current.getBoundingClientRect();
    const x = clientX - rect.left;
    const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));

    const newIndex = findEventIndexFromPosition(percentage, replayData.events.length);
    setCurrentEventIndex(newIndex);
  }, [replayData]);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setIsPlaying(false);
    handleTimelineDrag(e.clientX);
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (isDragging) {
      handleTimelineDrag(e.clientX);
    }
  }, [isDragging, handleTimelineDrag]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);

      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  // Playback controls
  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  const handleStepForward = () => {
    if (replayData && currentEventIndex < replayData.events.length - 1) {
      setCurrentEventIndex(currentEventIndex + 1);
      setIsPlaying(false);
    }
  };

  const handleStepBackward = () => {
    if (currentEventIndex > 0) {
      setCurrentEventIndex(currentEventIndex - 1);
      setIsPlaying(false);
    }
  };

  const handleSpeedChange = (speed: number) => {
    setPlaybackSpeed(speed);
  };

  const handleEventClick = (index: number) => {
    setCurrentEventIndex(index);
    setIsPlaying(false);
  };

  const formatWinnerLabel = (winner?: string | null) => {
    if (winner === 'good') {
      return '好人阵营';
    }
    if (winner === 'werewolf') {
      return '狼人阵营';
    }
    return '未决出';
  };

  const getEventBrief = (event?: GameEvent | null) => {
    if (!event) return '等待选择回放事件。';
    const data = event.data || {};
    if (event.event_type === 'discussion') return data.speech || data.message || `${data.agent_name || data.agent_id || '玩家'} 正在发言`;
    if (event.event_type === 'vote') return `${data.voter_name || data.voter_id || '玩家'} → ${data.target_name || data.target_id || '目标'}`;
    if (event.event_type === 'night_action') return `${ACTION_LABELS[data.action_type] || '夜间行动'}：${data.actor_name || data.actor_id || '?'} → ${data.target_name || data.target_id || '?'}`;
    if (event.event_type === 'death_announcement') return data.message || '天亮结算完成';
    if (event.event_type === 'elimination') return `${data.eliminated_name || data.eliminated_id || '玩家'} 被淘汰`;
    if (event.event_type === 'game_over') return data.reason || replayData?.game_over_reason || '对局结束';
    if (event.event_type === 'phase_change') return `阶段切换：${formatPhaseLabel(data.from_phase)} → ${formatPhaseLabel(data.to_phase || data.new_phase || event.phase)}`;
    return data.message || getEventDisplayName(event.event_type);
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
        <div className="text-white text-xl">加载回放数据...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
        <div className="bg-gray-900 p-8 rounded-lg border border-red-500">
          <h2 className="text-red-500 text-xl mb-4">加载失败</h2>
          <p className="text-white mb-4">{error}</p>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded"
          >
            关闭
          </button>
        </div>
      </div>
    );
  }

  if (!replayData || replayData.events.length === 0) {
    return (
      <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
        <div className="bg-gray-900 p-8 rounded-lg border border-purple-500">
          <h2 className="text-purple-400 text-xl mb-4">暂无回放数据</h2>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded"
          >
            关闭
          </button>
        </div>
      </div>
    );
  }

  const currentPosition = calculateEventPosition(currentEventIndex, replayData.events.length);
  const activeStepKey = getProcessStepKey(selectedEvent);
  const activeStepIndex = getStepIndex(activeStepKey);
  const voteTally = buildVoteTally(replayData.events, currentEventIndex, selectedEvent?.round);
  const recentDiscussions = (gameState?.conversation_history || []).slice(-4);
  const recentNightActions = (gameState?.night_actions || []).slice(-4);
  const replayAtmosphere = getReplayAtmosphere(activeStepKey);

  const renderProcessSteps = () => (
    <div className="scrollbar-none flex gap-2 overflow-x-auto pb-1 lg:grid lg:grid-cols-5 lg:overflow-visible lg:pb-0" aria-label="标准游戏流程">
      {PROCESS_STEPS.map((step, index) => {
        const isComplete = index < activeStepIndex;
        const isActive = step.key === activeStepKey;
        return (
          <div
            key={step.key}
            className={[
              'relative min-w-[9.5rem] overflow-hidden rounded-xl border px-3 py-3 transition-all lg:min-w-0',
              isActive
                ? 'border-amber-300/70 bg-amber-300/15 text-amber-50 shadow-[0_0_24px_rgba(251,191,36,0.16)] animate-phase-breathe'
                : isComplete
                  ? 'border-emerald-300/30 bg-emerald-300/10 text-emerald-50'
                  : 'border-slate-600/50 bg-slate-950/45 text-slate-300',
            ].join(' ')}
          >
            <div className="flex items-center gap-2">
              <span className="text-xl" aria-hidden="true">{step.icon}</span>
              <div>
                <div className="text-sm font-semibold">{step.label}</div>
                <div className="text-xs opacity-70">{step.caption}</div>
              </div>
            </div>
            {isActive && <div className="absolute inset-x-0 bottom-0 h-0.5 bg-amber-300" />}
          </div>
        );
      })}
    </div>
  );

  const renderVoteTally = () => {
    if (voteTally.length === 0) {
      return (
        <div className="rounded-lg border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-400">
          这一轮还没有形成票型。
        </div>
      );
    }
    const maxVotes = Math.max(...voteTally.map((item) => item.count), 1);
    return (
      <div className="space-y-2">
        {voteTally.map((item) => (
          <div key={item.targetName} className="rounded-lg border border-slate-700 bg-slate-950/60 p-3">
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="font-semibold text-white">{item.targetName}</span>
              <span className="rounded-full bg-amber-300/15 px-2 py-0.5 text-xs font-semibold text-amber-100">
                {item.count} 票
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full rounded-full bg-gradient-to-r from-amber-400 to-red-400"
                style={{ width: `${(item.count / maxVotes) * 100}%` }}
              />
            </div>
            <div className="mt-2 text-xs text-slate-400">
              投票者：{item.voters.join('、')}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderSuspicionGrid = (suspicion: Record<string, number> | undefined) => {
    if (!suspicion || Object.keys(suspicion).length === 0) return null;
    return (
      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">怀疑度雷达</div>
        <div className="grid gap-2 sm:grid-cols-2">
          {Object.entries(suspicion).map(([agentId, score]) => (
            <div key={agentId} className="rounded-lg border border-slate-700 bg-slate-950/60 p-2">
              <div className="mb-1 flex justify-between text-xs">
                <span className="text-slate-300">{agentId}</span>
                <span className="font-semibold text-amber-100">{score}/10</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                <div className="h-full rounded-full bg-cyan-300" style={{ width: `${Math.min(100, Math.max(0, score * 10))}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderStandardEventCard = (event: GameEvent, compact = false) => {
    const data = event.data || {};
    const actionLabel = ACTION_LABELS[data.action_type] || data.action_type;
    const timestamp = new Date(event.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    if (compact) {
      return (
        <section className={`relative overflow-hidden rounded-2xl border p-4 text-slate-100 shadow-2xl shadow-black/20 ${replayAtmosphere.shell}`} aria-label="当前事件摘要">
          <div className="pointer-events-none absolute inset-0 opacity-60">
            <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${replayAtmosphere.accent} animate-shimmer-line`} />
            {activeStepKey === 'night' && <div className="absolute -left-20 top-8 h-32 w-[130%] rotate-[-8deg] rounded-full bg-violet-300/10 blur-3xl animate-drift-fog" />}
            {activeStepKey === 'discussion' && <div className="absolute left-8 top-16 h-20 w-20 rounded-full border border-cyan-200/20 animate-sound-ring" />}
            {activeStepKey === 'voting' && <div className="absolute inset-x-0 top-1/2 h-px bg-gradient-to-r from-transparent via-orange-200/60 to-transparent animate-vote-arrow" />}
          </div>
          <div className="relative">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-slate-800 text-2xl" aria-hidden="true">
                  {getEventIcon(event.event_type)}
                </span>
                <div className="min-w-0">
                  <div className="text-[11px] uppercase tracking-[0.2em] text-slate-400">第 {event.round} 回合 · {formatPhaseLabel(event.phase)}</div>
                  <h3 className="truncate text-xl font-black text-white">{getEventDisplayName(event.event_type)}</h3>
                  <div className="mt-1 text-xs text-slate-400">{replayAtmosphere.label}</div>
                </div>
              </div>
              <span className="shrink-0 rounded-full border border-slate-600 bg-slate-900 px-2 py-1 text-[11px] text-slate-300">
                {currentEventIndex + 1}/{replayData.events.length}
              </span>
            </div>
            <p className="line-clamp-4 min-h-24 text-sm leading-6 text-slate-100">
              {getEventBrief(event)}
            </p>
            <button
              onClick={() => setDetailPanel('event')}
              className="mt-3 w-full rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-white/[0.1]"
            >
              查看完整事件详情
            </button>
          </div>
        </section>
      );
    }

    return (
      <section className={`relative overflow-hidden rounded-2xl border p-4 text-slate-100 shadow-2xl shadow-black/20 md:p-5 ${replayAtmosphere.shell}`} aria-label="标准化事件详情">
        <div className="pointer-events-none absolute inset-0 opacity-60">
          <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${replayAtmosphere.accent} animate-shimmer-line`} />
          {activeStepKey === 'night' && <div className="absolute -left-20 top-8 h-32 w-[130%] rotate-[-8deg] rounded-full bg-violet-300/10 blur-3xl animate-drift-fog" />}
          {activeStepKey === 'dawn' && <div className="absolute -top-28 left-1/2 h-56 w-56 -translate-x-1/2 rounded-full bg-amber-200/20 blur-3xl animate-sunrise-glow" />}
          {activeStepKey === 'discussion' && <div className="absolute left-8 top-20 h-24 w-24 rounded-full border border-cyan-200/20 animate-sound-ring" />}
          {activeStepKey === 'voting' && <div className="absolute inset-x-0 top-1/3 h-px bg-gradient-to-r from-transparent via-orange-200/60 to-transparent animate-vote-arrow" />}
          {activeStepKey === 'resolution' && <div className="absolute left-1/2 top-1/2 h-px w-[80%] -translate-x-1/2 rotate-12 bg-red-200/40 animate-crack-flash" />}
        </div>
        <div className="relative">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-slate-800 text-2xl" aria-hidden="true">
              {getEventIcon(event.event_type)}
            </span>
            <div>
              <div className="text-xs uppercase tracking-[0.24em] text-slate-400">第 {event.round} 回合 · {formatPhaseLabel(event.phase)} · {timestamp}</div>
              <h3 className="text-xl font-black text-white md:text-2xl">{getEventDisplayName(event.event_type)}</h3>
              <div className="mt-1 text-xs text-slate-400">{replayAtmosphere.label}</div>
            </div>
          </div>
          <span className="rounded-full border border-slate-600 bg-slate-900 px-3 py-1 text-xs text-slate-300">
            {currentEventIndex + 1}/{replayData.events.length}
          </span>
        </div>

        {event.event_type === 'night_action' && (
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
              <div className="rounded-xl border border-blue-300/20 bg-blue-300/10 p-4">
                <div className="text-xs text-blue-100/70">行动者</div>
                <div className="text-xl font-bold text-blue-50">{data.actor_name || data.actor_id || '未知'}</div>
              </div>
              <div className="text-center text-2xl text-amber-200">→</div>
              <div className="rounded-xl border border-red-300/20 bg-red-300/10 p-4">
                <div className="text-xs text-red-100/70">目标</div>
                <div className="text-xl font-bold text-red-50">{data.target_name || data.target_id || '无目标'}</div>
              </div>
            </div>
            <div className="rounded-xl border border-amber-300/20 bg-amber-300/10 p-4">
              <div className="text-sm text-amber-100">预设步骤：{actionLabel || '夜间行动'}</div>
              {data.result && <div className="mt-1 text-sm text-slate-300">结果：{data.result === 'good' ? '好人' : data.result === 'werewolf' ? '狼人' : data.result}</div>}
              {data.reason && <div className="mt-2 text-sm leading-relaxed text-slate-300">推理：{data.reason}</div>}
            </div>
          </div>
        )}

        {event.event_type === 'death_announcement' && (
          <div className="rounded-xl border border-sky-300/20 bg-sky-300/10 p-5">
            <div className="text-sm uppercase tracking-[0.18em] text-sky-100/70">天亮播报</div>
            <div className="mt-2 text-2xl font-bold text-white">
              {data.message || ((data.deaths || []).length ? `${(data.deaths || []).join('、')} 死亡` : '平安夜，无人死亡')}
            </div>
            <div className="mt-2 text-sm text-slate-300">系统将夜晚结果标准化为公开信息，供白天讨论使用。</div>
          </div>
        )}

        {event.event_type === 'phase_change' && (
          <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
            <div className="rounded-xl border border-slate-700 bg-slate-900 p-4">
              <div className="text-xs text-slate-400">上一阶段</div>
              <div className="text-xl font-bold text-slate-100">{formatPhaseLabel(data.from_phase)}</div>
            </div>
            <div className="text-center text-2xl text-amber-200">→</div>
            <div className="rounded-xl border border-amber-300/30 bg-amber-300/10 p-4">
              <div className="text-xs text-amber-100/70">当前阶段</div>
              <div className="text-xl font-bold text-amber-50">{formatPhaseLabel(data.to_phase || data.new_phase || event.phase)}</div>
            </div>
          </div>
        )}

        {event.event_type === 'discussion' && (
          <div className="space-y-4">
            <div className="rounded-xl border border-cyan-300/20 bg-cyan-300/10 p-4">
              <div className="text-xs text-cyan-100/70">公开发言 · {data.agent_name || data.agent_id}</div>
              <blockquote className="mt-2 text-lg font-semibold leading-relaxed text-white">
                “{data.speech || data.message || '暂无发言'}”
              </blockquote>
            </div>
            {data.thought && (
              <div className="rounded-xl border border-slate-700 bg-slate-900 p-4">
                <div className="text-xs text-slate-400">内心线索</div>
                <div className="mt-2 text-sm leading-relaxed text-slate-200">{data.thought}</div>
              </div>
            )}
            {renderSuspicionGrid(data.suspicion)}
          </div>
        )}

        {event.event_type === 'vote' && (
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
              <div className="rounded-xl border border-slate-700 bg-slate-900 p-4">
                <div className="text-xs text-slate-400">投票者</div>
                <div className="text-xl font-bold text-white">{data.voter_name || data.voter_id}</div>
              </div>
              <div className="text-center text-2xl text-amber-200">投给</div>
              <div className="rounded-xl border border-red-300/25 bg-red-300/10 p-4">
                <div className="text-xs text-red-100/70">目标</div>
                <div className="text-xl font-bold text-red-50">{data.target_name || data.target_id}</div>
              </div>
            </div>
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">当前票型</div>
              {renderVoteTally()}
            </div>
            {data.used_llm === false && (
              <div className="rounded-lg border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-sm text-amber-100">
                这是一条系统保底投票，非完整模型推理。
              </div>
            )}
          </div>
        )}

        {event.event_type === 'elimination' && (
          <div className="space-y-4">
            <div className="rounded-2xl border border-red-300/30 bg-red-500/10 p-5">
              <div className="text-xs uppercase tracking-[0.22em] text-red-100/70">放逐结果</div>
              <div className="mt-2 text-3xl font-black text-white">{data.eliminated_name || data.eliminated_id} 被淘汰</div>
              <div className="mt-2 text-sm text-red-50/80">
                身份：{data.eliminated_role_cn || data.eliminated_role || '未知'} · 得票：{data.vote_count ?? '未知'}
              </div>
            </div>
            {data.votes && (
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(data.votes).map(([target, count]) => (
                  <div key={target} className="rounded-lg border border-slate-700 bg-slate-950/60 p-3">
                    <div className="text-sm font-semibold text-white">{target}</div>
                    <div className="text-xs text-slate-400">{String(count)} 票</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {event.event_type === 'game_over' && (
          <div className="rounded-2xl border border-emerald-300/30 bg-emerald-300/10 p-5">
            <div className="text-xs uppercase tracking-[0.22em] text-emerald-100/70">终局</div>
            <div className="mt-2 text-3xl font-black text-white">{formatWinnerLabel(data.winner || replayData.winner)}获胜</div>
            <div className="mt-2 text-sm text-emerald-50/80">{data.reason || replayData.game_over_reason || '对局结束'}</div>
          </div>
        )}
        </div>
      </section>
    );
  };

  const renderStateSummary = () => {
    if (!gameState) return null;

    const aliveCount = gameState.alive_agents?.length || 0;
    const deadCount = gameState.dead_agents?.length || 0;

    return (
      <div className="space-y-4">
        <div className="rounded-2xl border border-purple-300/20 bg-purple-300/10 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-purple-100/70">当前状态</div>
              <div className="mt-1 text-2xl font-black text-white">
                第 {gameState.round || selectedEvent?.round || 1} 回合
              </div>
            </div>
            <span className="rounded-full border border-amber-300/40 bg-amber-300/10 px-3 py-1 text-xs font-semibold text-amber-100">
              {formatPhaseLabel(gameState.phase || selectedEvent?.phase)}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl border border-emerald-300/20 bg-emerald-300/10 p-3">
              <div className="text-xs text-emerald-100/70">存活</div>
              <div className="text-2xl font-black text-emerald-50">{aliveCount}</div>
            </div>
            <div className="rounded-xl border border-red-300/20 bg-red-300/10 p-3">
              <div className="text-xs text-red-100/70">死亡</div>
              <div className="text-2xl font-black text-red-50">{deadCount}</div>
            </div>
          </div>
        </div>

        {gameState.winner && (
          <div className="rounded-2xl border border-emerald-300/30 bg-emerald-300/10 p-4">
            <div className="text-xs uppercase tracking-[0.2em] text-emerald-100/70">游戏结束</div>
            <div className="mt-1 text-xl font-bold text-white">
              {formatWinnerLabel(gameState.winner)}获胜
            </div>
            {gameState.game_over_reason && (
              <div className="mt-2 text-sm leading-relaxed text-emerald-50/80">
                {gameState.game_over_reason}
              </div>
            )}
          </div>
        )}

        {recentNightActions.length > 0 && (
          <div className="rounded-2xl border border-blue-300/20 bg-blue-300/10 p-4">
            <div className="mb-3 text-sm font-semibold text-blue-100">最近夜晚行动</div>
            <div className="flex flex-wrap gap-2">
              {recentNightActions.map((action: any, idx: number) => (
                <span
                  key={`${action.action_type || 'night'}-${idx}`}
                  className="rounded-full border border-blue-200/20 bg-slate-950/50 px-3 py-1 text-xs text-blue-50"
                >
                  {ACTION_LABELS[action.action_type] || action.action_type || '夜间行动'} · {action.actor_name || action.actor_id || '?'} → {action.target_name || action.target_id || '?'}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="rounded-2xl border border-slate-700 bg-slate-950/50 p-4">
          <div className="mb-3 text-sm font-semibold text-slate-100">本轮票型</div>
          {renderVoteTally()}
        </div>

        {recentDiscussions.length > 0 && (
          <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-4">
            <div className="mb-3 text-sm font-semibold text-cyan-100">最近发言</div>
            <div className="space-y-2">
              {recentDiscussions.map((msg: any, idx: number) => (
                <div
                  key={`${msg.agent_id || msg.agent_name || 'speaker'}-${idx}`}
                  className="rounded-xl border border-cyan-200/10 bg-slate-950/50 p-3"
                >
                  <div className="text-xs font-semibold text-cyan-100">
                    {msg.agent_name || msg.agent_id || '未知玩家'}
                  </div>
                  <div className="mt-1 line-clamp-3 text-xs leading-relaxed text-slate-300">
                    {msg.message || '暂无发言'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderStateCompact = () => {
    if (!gameState) return null;
    const aliveCount = gameState.alive_agents?.length || 0;
    const deadCount = gameState.dead_agents?.length || 0;
    return (
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-1">
        <button
          onClick={() => setDetailPanel('state')}
          className="rounded-2xl border border-purple-300/20 bg-purple-300/10 p-3 text-left transition-colors hover:bg-purple-300/15"
        >
          <div className="text-xs uppercase tracking-[0.18em] text-purple-100/70">当前状态</div>
          <div className="mt-1 text-xl font-black text-white">第 {gameState.round || selectedEvent?.round || 1} 回合</div>
          <div className="mt-2 text-xs text-purple-100/75">{formatPhaseLabel(gameState.phase || selectedEvent?.phase)}</div>
        </button>
        <button
          onClick={() => setDetailPanel('state')}
          className="rounded-2xl border border-white/10 bg-slate-950/50 p-3 text-left transition-colors hover:bg-white/[0.06]"
        >
          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="text-xs text-emerald-100/70">存活</div>
              <div className="text-2xl font-black text-emerald-50">{aliveCount}</div>
            </div>
            <div>
              <div className="text-xs text-red-100/70">死亡</div>
              <div className="text-2xl font-black text-red-50">{deadCount}</div>
            </div>
          </div>
        </button>
        <button
          onClick={() => setDetailPanel('votes')}
          className="rounded-2xl border border-orange-300/20 bg-orange-300/10 p-3 text-left transition-colors hover:bg-orange-300/15"
        >
          <div className="text-xs uppercase tracking-[0.18em] text-orange-100/70">票型</div>
          <div className="mt-1 text-lg font-bold text-white">{voteTally.length ? `${voteTally[0].targetName} ${voteTally[0].count} 票领先` : '暂无票型'}</div>
        </button>
        <button
          onClick={() => setDetailPanel(recentDiscussions.length > 0 ? 'discussion' : 'night')}
          className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-left transition-colors hover:bg-cyan-300/15"
        >
          <div className="text-xs uppercase tracking-[0.18em] text-cyan-100/70">更多记录</div>
          <div className="mt-1 text-lg font-bold text-white">{recentDiscussions.length} 发言 / {recentNightActions.length} 夜动</div>
        </button>
      </div>
    );
  };

  const renderDetailPanelContent = () => {
    if (detailPanel === 'event' && selectedEvent) {
      return renderStandardEventCard(selectedEvent);
    }
    if (detailPanel === 'state') {
      return renderStateSummary();
    }
    if (detailPanel === 'votes') {
      return (
        <div className="rounded-2xl border border-slate-700 bg-slate-950/50 p-4">
          <div className="mb-3 text-sm font-semibold text-slate-100">本轮票型</div>
          {renderVoteTally()}
        </div>
      );
    }
    if (detailPanel === 'night') {
      return (
        <div className="rounded-2xl border border-blue-300/20 bg-blue-300/10 p-4">
          <div className="mb-3 text-sm font-semibold text-blue-100">最近夜晚行动</div>
          {recentNightActions.length === 0 ? (
            <div className="text-sm text-slate-300">暂无夜间行动记录。</div>
          ) : (
            <div className="space-y-2">
              {recentNightActions.map((action: any, idx: number) => (
                <div key={`${action.action_type || 'night'}-${idx}`} className="rounded-xl border border-blue-200/20 bg-slate-950/50 p-3 text-sm text-blue-50">
                  {ACTION_LABELS[action.action_type] || action.action_type || '夜间行动'} · {action.actor_name || action.actor_id || '?'} → {action.target_name || action.target_id || '?'}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }
    if (detailPanel === 'discussion') {
      return (
        <div className="rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-4">
          <div className="mb-3 text-sm font-semibold text-cyan-100">最近发言</div>
          {recentDiscussions.length === 0 ? (
            <div className="text-sm text-slate-300">暂无发言记录。</div>
          ) : (
            <div className="space-y-2">
              {recentDiscussions.map((msg: any, idx: number) => (
                <div key={`${msg.agent_id || msg.agent_name || 'speaker'}-${idx}`} className="rounded-xl border border-cyan-200/10 bg-slate-950/50 p-3">
                  <div className="text-xs font-semibold text-cyan-100">{msg.agent_name || msg.agent_id || '未知玩家'}</div>
                  <div className="mt-1 text-sm leading-relaxed text-slate-300">{msg.message || '暂无发言'}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }
    return null;
  };

  const getDetailPanelTitle = () => {
    switch (detailPanel) {
      case 'event':
        return '完整事件详情';
      case 'state':
        return '完整游戏状态';
      case 'votes':
        return '本轮票型';
      case 'night':
        return '夜晚行动记录';
      case 'discussion':
        return '最近发言记录';
      default:
        return '';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-black/90">
      {/* Header */}
      <div className="shrink-0 border-b border-purple-500/60 bg-gradient-to-r from-purple-950 via-slate-950 to-indigo-950 p-2 md:p-3">
        <div className="flex items-start justify-between gap-2">
          <h2 className="line-clamp-1 min-w-0 break-all text-base font-bold text-white md:text-xl">
            游戏回放 - {gameId}
          </h2>
          <button
            onClick={onClose}
            className="shrink-0 rounded-xl border border-red-300/30 bg-red-600/80 px-3 py-1.5 text-sm text-white transition-colors hover:bg-red-700"
          >
            关闭
          </button>
        </div>
        <div className="mt-1 text-xs text-purple-200 md:text-sm">
          事件总数: {replayData.total_events} | 当前回合: {selectedEvent?.round || 1} |
          阶段: {formatPhaseLabel(selectedEvent?.phase)}
        </div>
        <div className="mt-2 grid grid-cols-4 gap-1.5 md:gap-2">
          <div className="rounded-lg border border-white/10 bg-black/20 px-2 py-1.5 md:px-3 md:py-2">
            <div className="text-[10px] uppercase tracking-[0.16em] text-purple-200/70">规模</div>
            <div className="mt-0.5 text-xs font-semibold text-white md:text-base">
              {replayData.player_count ? `${replayData.player_count} 人局` : '未记录'}
            </div>
          </div>
          <div className="rounded-lg border border-white/10 bg-black/20 px-2 py-1.5 md:px-3 md:py-2">
            <div className="text-[10px] uppercase tracking-[0.16em] text-purple-200/70">存活</div>
            <div className="mt-0.5 text-xs font-semibold text-white md:text-base">
              {typeof replayData.alive_count === 'number' ? `${replayData.alive_count} 人` : '未记录'}
            </div>
          </div>
          <div className="rounded-lg border border-white/10 bg-black/20 px-2 py-1.5 md:px-3 md:py-2">
            <div className="text-[10px] uppercase tracking-[0.16em] text-purple-200/70">胜方</div>
            <div className="mt-0.5 truncate text-xs font-semibold text-white md:text-base">
              {formatWinnerLabel(replayData.winner)}
            </div>
          </div>
          <div className="rounded-lg border border-white/10 bg-black/20 px-2 py-1.5 md:px-3 md:py-2">
            <div className="text-[10px] uppercase tracking-[0.16em] text-purple-200/70">位置</div>
            <div className="mt-0.5 text-xs font-semibold text-white md:text-base">
              {currentEventIndex + 1}/{replayData.events.length}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="min-h-0 flex-1 overflow-hidden">
        <div className="grid h-full min-h-0 gap-2 p-2 lg:grid-cols-[minmax(0,1fr)_20rem] lg:gap-0 lg:p-0 xl:grid-cols-[minmax(0,1fr)_22rem]">
        {/* Timeline Section */}
        <div className="min-h-0 min-w-0 space-y-2 overflow-hidden lg:flex lg:flex-col lg:p-4">
          {/* Event Details Panel */}
          <div className="min-h-0 rounded-2xl border border-purple-500/30 bg-gray-900/50 p-2 backdrop-blur-sm md:p-3 lg:flex-[1.2]">
            {selectedEvent && (
              <div className="flex h-full min-h-0 flex-col gap-2">
                {renderProcessSteps()}
                <div className="min-h-0 flex-1">
                  {renderStandardEventCard(selectedEvent, true)}
                </div>
              </div>
            )}
          </div>

          {/* Timeline */}
          <div className="flex shrink-0 flex-col rounded-2xl border border-purple-500/30 bg-gray-900/50 p-2 backdrop-blur-sm md:p-3 lg:flex-[0.8]">
            <h3 className="mb-2 text-sm font-bold text-purple-400 md:text-lg">时间轴</h3>

            {/* Timeline Track */}
            <div className="relative flex flex-col justify-center lg:flex-1">
              <div className="scrollbar-none overflow-x-auto pb-2">
              <div
                ref={timelineRef}
                className="relative h-16 min-w-[38rem] cursor-pointer rounded-xl bg-gray-800 md:h-20 md:min-w-0"
                onMouseDown={handleMouseDown}
              >
                {/* Timeline Base */}
                <div className="absolute inset-0 flex items-center px-4">
                  <div className="w-full h-2 bg-gray-700 rounded-full relative">
                    {/* Progress Bar */}
                    <div
                      className="absolute left-0 top-0 h-full bg-gradient-to-r from-purple-600 to-pink-600 rounded-full transition-all"
                      style={{ width: `${currentPosition}%` }}
                    />

                    {/* Current Position Indicator */}
                    <div
                      className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow-lg border-2 border-purple-500 transition-all"
                      style={{ left: `${currentPosition}%`, transform: 'translate(-50%, -50%)' }}
                    />
                  </div>
                </div>

                {/* Event Markers */}
                <div className="absolute inset-0 flex items-center px-4">
                  <div className="w-full relative h-full">
                    {replayData.events.map((event, index) => {
                      const position = calculateEventPosition(index, replayData.events.length);
                      const isActive = index === currentEventIndex;
                      const step = PROCESS_STEPS.find((item) => item.key === getProcessStepKey(event));

                      return (
                        <div
                          key={event.event_id}
                          className="absolute top-1/2 -translate-y-1/2 cursor-pointer group"
                          style={{ left: `${position}%`, transform: 'translate(-50%, -50%)' }}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEventClick(index);
                          }}
                        >
                          <div
                            className={`w-3 h-3 rounded-full transition-all ${
                              isActive ? 'scale-150 ring-2 ring-white' : 'scale-100'
                            }`}
                            style={{ backgroundColor: getEventColor(event.event_type) }}
                          />

                          {/* Tooltip */}
                          <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap">
                            <div className="bg-gray-900 text-white text-xs px-2 py-1 rounded border border-purple-500">
                              {step?.icon} {step?.label} · {getEventDisplayName(event.event_type)}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
              </div>

              {/* Playback Controls */}
              <div className="mt-2 flex flex-wrap items-center justify-center gap-1.5 md:gap-2">
                <button
                  onClick={handleStepBackward}
                  disabled={currentEventIndex === 0}
                  className="rounded-xl bg-purple-600 px-2.5 py-1.5 text-xs text-white transition-colors hover:bg-purple-700 disabled:cursor-not-allowed disabled:bg-gray-600 md:px-4 md:py-2 md:text-sm"
                >
                  ⏮ 上一个
                </button>

                <button
                  onClick={handlePlayPause}
                  className="rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 px-4 py-1.5 text-xs font-semibold text-white transition-colors hover:from-purple-700 hover:to-pink-700 md:px-6 md:py-2 md:text-sm"
                >
                  {isPlaying ? '⏸ 暂停' : '▶ 播放'}
                </button>

                <button
                  onClick={handleStepForward}
                  disabled={currentEventIndex === replayData.events.length - 1}
                  className="rounded-xl bg-purple-600 px-2.5 py-1.5 text-xs text-white transition-colors hover:bg-purple-700 disabled:cursor-not-allowed disabled:bg-gray-600 md:px-4 md:py-2 md:text-sm"
                >
                  下一个 ⏭
                </button>

                {/* Speed Control */}
                <div className="flex flex-wrap items-center justify-center gap-2 md:ml-4">
                  <span className="text-xs text-purple-300 md:text-sm">速度:</span>
                  {[0.5, 1, 2, 4].map((speed) => (
                    <button
                      key={speed}
                      onClick={() => handleSpeedChange(speed)}
                      className={`rounded-lg px-2 py-1 text-xs transition-colors md:px-3 md:text-sm ${
                        playbackSpeed === speed
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                      }`}
                    >
                      {speed}x
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Game State Panel */}
        <div className="min-h-0 min-w-0 rounded-2xl border border-purple-500/30 bg-gray-900/50 p-2 backdrop-blur-sm md:p-3 lg:rounded-none lg:border-y-0 lg:border-r-0 lg:p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="text-sm font-bold text-purple-400 md:text-lg">游戏状态</h3>
            <button onClick={() => setDetailPanel('state')} className="rounded-lg border border-white/10 bg-white/[0.06] px-2 py-1 text-xs text-white/75 hover:bg-white/[0.1]">
              全部
            </button>
          </div>
          {renderStateCompact()}
        </div>
        </div>
      </div>
      {detailPanel && (
        <div className="absolute inset-0 z-10 flex items-end bg-black/70 p-2 backdrop-blur-sm md:items-center md:justify-center md:p-6">
          <div className="max-h-[88vh] w-full overflow-hidden rounded-2xl border border-purple-400/30 bg-slate-950 shadow-2xl md:max-w-3xl">
            <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
              <h3 className="text-lg font-bold text-white">{getDetailPanelTitle()}</h3>
              <button onClick={() => setDetailPanel(null)} className="rounded-lg border border-white/10 bg-white/[0.06] px-3 py-1.5 text-sm text-white hover:bg-white/[0.1]">
                关闭
              </button>
            </div>
            <div className="scrollbar-none max-h-[calc(88vh-4rem)] overflow-y-auto p-3 md:p-4">
              {renderDetailPanelContent()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TimelineReplay;

/**
 * 回放播放器（对齐设计稿 3:1069 界面-回放播放器）
 *
 * 结构：Header（返回/标题/胜方徽标/导出）
 *      Timeline（EVENT x/y + 进度条 + 回合刻度）
 *      Controls（上一步/自动播放/下一步 + 跳转回合 + 倍速 + 结束回放）
 *      MainRow（事件流 EventStream + 右栏 当前局势 / 回合跳转）
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { ArrowLeft, Play, Pause, ChevronLeft, ChevronRight, Download, X } from 'lucide-react';
import {
  fetchGameReplay,
  getGameStateAtEvent,
  calculateEventPosition,
  findEventIndexFromPosition,
  downloadWerewolfReplay,
  getEventDisplayName,
  type GameEvent,
  type GameReplayResponse
} from '../../services/werewolfReplayService';

interface TimelineReplayProps {
  gameId: string;
  onClose: () => void;
}

const PHASE_LABELS: Record<string, string> = {
  night: '夜晚',
  dawn: '天亮',
  day_discussion: '讨论',
  day_voting: '投票',
  opening: '入座',
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

function formatWinnerLabel(winner?: string | null) {
  if (winner === 'good') return '好人阵营胜';
  if (winner === 'werewolf') return '狼人阵营胜';
  return '未决出';
}

function getEventBrief(event?: GameEvent | null) {
  if (!event) return '等待选择回放事件。';
  const data = event.data || {};
  if (event.event_type === 'discussion') return data.speech || data.message || `${data.agent_name || data.agent_id || '玩家'} 正在发言`;
  if (event.event_type === 'vote') return `${data.voter_name || data.voter_id || '玩家'} → ${data.target_name || data.target_id || '目标'}`;
  if (event.event_type === 'night_action') return `${ACTION_LABELS[data.action_type] || '夜间行动'}：${data.actor_name || data.actor_id || '?'} → ${data.target_name || data.target_id || '?'}`;
  if (event.event_type === 'death_announcement') return data.message || '天亮结算完成';
  if (event.event_type === 'elimination') return `${data.eliminated_name || data.eliminated_id || '玩家'} 被淘汰`;
  if (event.event_type === 'game_over') return data.reason || '对局结束';
  if (event.event_type === 'phase_change') return `阶段切换：${formatPhaseLabel(data.from_phase)} → ${formatPhaseLabel(data.to_phase || data.new_phase || event.phase)}`;
  return data.message || getEventDisplayName(event.event_type);
}

export const TimelineReplay: React.FC<TimelineReplayProps> = ({ gameId, onClose }) => {
  const [replayData, setReplayData] = useState<GameReplayResponse | null>(null);
  const [currentEventIndex, setCurrentEventIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const timelineRef = useRef<HTMLDivElement>(null);
  const currentEventRef = useRef<HTMLDivElement>(null);
  const playbackIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 载入回放数据
  useEffect(() => {
    const loadReplay = async () => {
      try {
        setLoading(true);
        const data = await fetchGameReplay(gameId);
        setReplayData(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load replay');
      } finally {
        setLoading(false);
      }
    };
    loadReplay();
  }, [gameId]);

  // 自动播放
  useEffect(() => {
    if (isPlaying && replayData) {
      const interval = 1000 / playbackSpeed;
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
        if (playbackIntervalRef.current) clearInterval(playbackIntervalRef.current);
      };
    }
  }, [isPlaying, playbackSpeed, replayData]);

  // 进度条拖拽
  const handleTimelineDrag = useCallback((clientX: number) => {
    if (!timelineRef.current || !replayData) return;
    const rect = timelineRef.current.getBoundingClientRect();
    const percentage = Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
    setCurrentEventIndex(findEventIndexFromPosition(percentage, replayData.events.length));
  }, [replayData]);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setIsPlaying(false);
    handleTimelineDrag(e.clientX);
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (isDragging) handleTimelineDrag(e.clientX);
  }, [isDragging, handleTimelineDrag]);

  const handleMouseUp = useCallback(() => setIsDragging(false), []);

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

  // 当前事件变化时滚动事件流
  useEffect(() => {
    currentEventRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [currentEventIndex]);

  const selectedEvent = replayData?.events[Math.min(currentEventIndex, replayData.events.length - 1)] || null;
  const gameState = useMemo(
    () => (replayData ? getGameStateAtEvent(replayData.events, currentEventIndex) : null),
    [replayData, currentEventIndex]
  );

  // 回合分组：R{n} → 事件数 / 起始下标
  const roundGroups = useMemo(() => {
    if (!replayData) return [];
    const groups: Array<{ round: number; count: number; firstIndex: number }> = [];
    replayData.events.forEach((event, index) => {
      const round = event.round || 1;
      const found = groups.find((g) => g.round === round);
      if (found) found.count += 1;
      else groups.push({ round, count: 1, firstIndex: index });
    });
    return groups;
  }, [replayData]);

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4">
        <div className="rounded-3xl border border-line bg-surface p-8 text-center shadow-2xl">
          <div className="mx-auto mb-5 h-12 w-12 rounded-full border-4 border-violet/25 border-t-violet animate-spin" />
          <h2 className="text-lg font-bold text-text-primary">正在装载回放</h2>
          <p className="mt-2 text-sm text-text-secondary">读取事件与重建局势…</p>
        </div>
      </div>
    );
  }

  if (error || !replayData || replayData.events.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4">
        <div className="max-w-md rounded-3xl border border-danger/30 bg-surface p-6 shadow-2xl">
          <h2 className="text-xl font-bold text-danger">{error ? '回放加载失败' : '暂无可展示事件'}</h2>
          <p className="mt-3 text-sm leading-6 text-text-primary/85">
            {error || '这局还没有写入时间轴，开始游戏或等待事件同步后再查看。'}
          </p>
          <button
            onClick={onClose}
            className="mt-5 rounded-xl border border-line px-4 py-2 text-sm text-text-secondary transition-colors hover:border-violet/50 hover:text-text-primary"
          >
            关闭
          </button>
        </div>
      </div>
    );
  }

  const currentPosition = calculateEventPosition(currentEventIndex, replayData.events.length);
  const aliveAgents: Array<{ name?: string; agent_id?: string }> = gameState?.alive_agents || [];
  const deadAgents: Array<{ name?: string; agent_id?: string }> = gameState?.dead_agents || [];
  const activeRound = selectedEvent?.round || 1;

  const handleStep = (delta: number) => {
    const next = currentEventIndex + delta;
    if (next >= 0 && next < replayData.events.length) {
      setCurrentEventIndex(next);
      setIsPlaying(false);
    }
  };

  const currentData = selectedEvent?.data || {};
  const currentChips: Array<{ label: string; value: string; tone?: string }> = [];
  if (selectedEvent?.event_type === 'night_action' || selectedEvent?.event_type === 'vote') {
    if (currentData.actor_name || currentData.voter_name || currentData.actor_id || currentData.voter_id) {
      currentChips.push({ label: '发起', value: String(currentData.actor_name || currentData.voter_name || currentData.actor_id || currentData.voter_id) });
    }
    if (currentData.target_name || currentData.target_id) {
      currentChips.push({ label: '目标', value: String(currentData.target_name || currentData.target_id) });
    }
    if (currentData.result) {
      currentChips.push({ label: '结果', value: String(currentData.result), tone: 'text-gold' });
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col gap-5 overflow-y-auto bg-[#0d0b14] p-4 md:p-10">
      {/* Header */}
      <header className="flex flex-wrap items-center gap-3">
        <button
          onClick={onClose}
          className="rounded-xl border border-line p-2.5 text-text-primary transition-colors hover:border-violet/50"
          aria-label="返回"
        >
          <ArrowLeft size={16} />
        </button>
        <h1 className="min-w-0 flex-1 truncate text-xl font-bold text-text-primary md:text-[22px]">
          回放 · {gameId}
        </h1>
        <span className="rounded-lg border border-violet/40 bg-violet/12 px-3 py-1.5 text-xs font-medium text-violet">
          {formatWinnerLabel(replayData.winner)}
        </span>
        <button
          onClick={() => downloadWerewolfReplay(gameId)}
          className="flex items-center gap-1.5 rounded-xl border border-line px-3 py-2 text-xs text-text-secondary transition-colors hover:border-violet/50 hover:text-text-primary"
        >
          <Download size={13} />
          JSON
        </button>
      </header>

      {/* Timeline 卡 */}
      <section className="rounded-2xl border border-line bg-surface/60 p-4 md:p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="font-hud text-sm font-bold text-violet">
            EVENT {currentEventIndex + 1} / {replayData.events.length}
          </span>
          <span className="text-[13px] text-text-secondary/70">
            R{activeRound} · {formatPhaseLabel(selectedEvent?.phase)}
          </span>
        </div>
        <div
          ref={timelineRef}
          className="relative h-3.5 cursor-pointer rounded-full bg-white/[0.07]"
          onMouseDown={handleMouseDown}
        >
          <div
            className="h-full rounded-full bg-violet/90 transition-all"
            style={{ width: `${currentPosition}%` }}
          />
          <div
            className="absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full bg-white shadow-md"
            style={{ left: `calc(${currentPosition}% - 6px)` }}
          />
        </div>
        <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1">
          {roundGroups.map((g) => (
            <button
              key={g.round}
              type="button"
              onClick={() => {
                setCurrentEventIndex(g.firstIndex);
                setIsPlaying(false);
              }}
              className={`font-hud text-[11px] transition-colors ${
                g.round === activeRound ? 'text-violet' : 'text-text-secondary/50 hover:text-text-secondary'
              }`}
            >
              R{g.round} · {g.count} 事件
            </button>
          ))}
        </div>
      </section>

      {/* Controls */}
      <section className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 rounded-xl border border-line bg-surface/60 p-1">
          <button
            onClick={() => handleStep(-1)}
            disabled={currentEventIndex === 0}
            className="flex items-center gap-1 rounded-lg px-3 py-2 text-[13px] text-text-primary transition-colors hover:bg-white/[0.06] disabled:opacity-35"
          >
            <ChevronLeft size={14} />
            上一步
          </button>
          <button
            onClick={() => setIsPlaying((v) => !v)}
            className="flex items-center gap-1.5 rounded-lg bg-violet px-3.5 py-2 text-[13px] font-bold text-white transition-colors hover:brightness-110"
          >
            {isPlaying ? <Pause size={13} /> : <Play size={13} />}
            {isPlaying ? '暂停' : '自动播放'}
          </button>
          <button
            onClick={() => handleStep(1)}
            disabled={currentEventIndex === replayData.events.length - 1}
            className="flex items-center gap-1 rounded-lg px-3 py-2 text-[13px] text-text-primary transition-colors hover:bg-white/[0.06] disabled:opacity-35"
          >
            下一步
            <ChevronRight size={14} />
          </button>
        </div>

        <select
          value={activeRound}
          onChange={(e) => {
            const g = roundGroups.find((item) => item.round === Number(e.target.value));
            if (g) {
              setCurrentEventIndex(g.firstIndex);
              setIsPlaying(false);
            }
          }}
          className="rounded-xl border border-line bg-surface/60 px-3 py-2.5 text-[13px] text-text-secondary outline-none focus:border-violet/60"
        >
          {roundGroups.map((g) => (
            <option key={g.round} value={g.round}>跳转回合 R{g.round}</option>
          ))}
        </select>

        <div className="flex items-center gap-0.5 rounded-xl border border-line p-1">
          {[1, 2, 4].map((speed) => (
            <button
              key={speed}
              onClick={() => setPlaybackSpeed(speed)}
              className={`rounded-lg px-2.5 py-1.5 font-hud text-xs font-bold transition-colors ${
                playbackSpeed === speed ? 'bg-violet text-white' : 'text-text-secondary/60 hover:text-text-primary'
              }`}
            >
              {speed}x
            </button>
          ))}
        </div>

        <button
          onClick={onClose}
          className="flex items-center gap-1.5 rounded-xl border border-danger/40 px-3 py-2.5 text-[13px] text-danger/85 transition-colors hover:bg-danger/10"
        >
          <X size={13} />
          结束回放
        </button>
      </section>

      {/* MainRow：事件流 + 右栏 */}
      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        {/* 事件流 */}
        <section className="flex min-h-0 flex-col rounded-2xl border border-line bg-surface/60 p-4 md:p-6">
          <p className="font-hud mb-3 text-[13px] text-text-secondary/60">事件流 EVENT STREAM</p>
          <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
            {replayData.events.map((event, index) => {
              const isCurrent = index === currentEventIndex;
              const isPast = index < currentEventIndex;
              if (isCurrent) {
                return (
                  <div
                    ref={currentEventRef}
                    key={event.event_id || index}
                    className="rounded-2xl border border-violet/60 bg-violet/[0.08] p-4"
                  >
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="text-[15px] font-bold text-violet">
                        {index + 1} · {getEventDisplayName(event.event_type)}
                      </span>
                      <span className="font-hud text-[11px] text-text-secondary/60">
                        R{event.round || 1} · {formatPhaseLabel(event.phase)}
                      </span>
                    </div>
                    <p className="text-sm leading-6 text-text-primary">{getEventBrief(event)}</p>
                    {currentChips.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-3 text-xs text-text-secondary/70">
                        {currentChips.map((chip) => (
                          <span key={chip.label}>
                            {chip.label} <span className={chip.tone || 'text-text-primary/85'}>{chip.value}</span>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              }
              return (
                <button
                  key={event.event_id || index}
                  type="button"
                  onClick={() => {
                    setCurrentEventIndex(index);
                    setIsPlaying(false);
                  }}
                  className={`flex items-start gap-3 rounded-xl p-3 text-left transition-colors hover:bg-white/[0.05] ${
                    isPast ? 'text-text-secondary/40' : 'text-text-secondary/70'
                  }`}
                >
                  <span className="font-hud w-6 shrink-0 text-right text-xs">{index + 1}</span>
                  <span className="line-clamp-1 text-[13px]">{getEventBrief(event)}</span>
                </button>
              );
            })}
          </div>
        </section>

        {/* 右栏 */}
        <aside className="flex min-h-0 flex-col gap-4">
          {/* 当前局势 */}
          <section className="rounded-2xl border border-line bg-surface/60 p-4 md:p-6">
            <p className="font-hud mb-3 text-[13px] text-text-secondary/60">当前局势 STATE</p>
            <div className="flex flex-wrap gap-2">
              {aliveAgents.map((agent, idx) => (
                <span
                  key={`alive-${agent.agent_id || idx}`}
                  className="flex h-12 w-12 flex-col items-center justify-center rounded-xl border border-violet/40 bg-white/[0.04]"
                  title={agent.name || agent.agent_id}
                >
                  <span className="text-sm font-bold text-text-primary">{(agent.name || '?').slice(0, 1)}</span>
                  <span className="font-hud text-[8px] text-success/80">存活</span>
                </span>
              ))}
              {deadAgents.map((agent, idx) => (
                <span
                  key={`dead-${agent.agent_id || idx}`}
                  className="flex h-12 w-12 flex-col items-center justify-center rounded-xl border border-line bg-white/[0.02] opacity-50"
                  title={agent.name || agent.agent_id}
                >
                  <span className="text-sm font-bold text-text-secondary/70 line-through">{(agent.name || '?').slice(0, 1)}</span>
                  <span className="font-hud text-[8px] text-danger/70">出局</span>
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs text-text-secondary/60">
              存活 {aliveAgents.length} · 出局 {deadAgents.length}
            </p>
          </section>

          {/* 回合跳转 */}
          <section className="flex min-h-0 flex-1 flex-col rounded-2xl border border-line bg-surface/60 p-4 md:p-6">
            <p className="font-hud mb-3 text-[13px] text-text-secondary/60">回合跳转 JUMP TO ROUND</p>
            <div className="flex flex-col gap-2 overflow-y-auto">
              {roundGroups.map((g) => (
                <button
                  key={g.round}
                  type="button"
                  onClick={() => {
                    setCurrentEventIndex(g.firstIndex);
                    setIsPlaying(false);
                  }}
                  className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors ${
                    g.round === activeRound
                      ? 'border-violet/60 bg-violet/10'
                      : 'border-line hover:border-white/25'
                  }`}
                >
                  <span className={`font-hud w-8 text-sm font-bold ${g.round === activeRound ? 'text-violet' : 'text-violet/60'}`}>
                    R{g.round}
                  </span>
                  <span className="flex-1 text-xs text-text-secondary/70">{g.count} 个事件</span>
                  <span className={`font-hud text-xs ${g.round === activeRound ? 'text-text-primary' : 'text-text-secondary/50'}`}>
                    {g.count}
                  </span>
                </button>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
};

export default TimelineReplay;

/**
 * Werewolf Game Over — 对局结算（夜幕协议 · 界面-胜负结算 3:1067）
 * 结构：Header / WinnerBanner / StatsRow / MainRow(名单+关键事件) / ActionBar
 */

import React from 'react';
import { Home, Play, RotateCcw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { Agent, WerewolfEvent } from '../../services/werewolfService';

interface WerewolfGameOverProps {
  winner: 'werewolf' | 'good';
  reason: string;
  currentRound: number;
  agents: Agent[];
  events?: WerewolfEvent[];
  gameId?: string;
  onReplay?: () => void;
  onRematch?: () => void;
}

/** 角色色（对齐设计令牌 role/*） */
const ROLE_COLOR: Record<string, string> = {
  狼人: 'text-role-wolf',
  预言家: 'text-role-seer',
  女巫: 'text-role-witch',
  守卫: 'text-role-guard',
  村民: 'text-role-civilian',
  猎人: 'text-gold',
};

const roleColorClass = (roleCn?: string) =>
  (roleCn && ROLE_COLOR[roleCn]) || 'text-text-secondary';

const ROLE_DOT: Record<string, string> = {
  狼人: 'bg-role-wolf',
  预言家: 'bg-role-seer',
  女巫: 'bg-role-witch',
  守卫: 'bg-role-guard',
  村民: 'bg-role-civilian',
  猎人: 'bg-gold',
};

const roleDotClass = (roleCn?: string) =>
  (roleCn && ROLE_DOT[roleCn]) || 'bg-white/25';

interface KeyEvent {
  tag: string;
  night: boolean;
  text: string;
  kindLabel: string;
  kindClass: string;
}

const KIND_STYLE: Record<string, string> = {
  kill: 'text-role-wolf',
  poison: 'text-role-witch',
  exile: 'text-text-secondary',
  win: 'text-gold',
};

/** 从事件流提炼关键事件（倒序，最新在上） */
function extractKeyEvents(events: WerewolfEvent[]): KeyEvent[] {
  const relevant = events.filter((e) =>
    ['elimination', 'death_announcement', 'game_over'].includes(e.type)
  );
  return relevant.slice(-14).reverse().map((e) => {
    const night = e.phase ? e.phase === 'night' : e.type === 'death_announcement';
    const round = typeof e.round === 'number' ? e.round : undefined;
    const tag = round != null ? `${night ? 'N' : 'D'}${round}` : '—';
    const cause = String(e.cause || e.death_cause || '').toLowerCase();
    let kindLabel = '事件';
    let kindKey = 'exile';
    if (e.type === 'game_over') {
      kindLabel = '终局';
      kindKey = 'win';
    } else if (cause.includes('毒') || cause.includes('poison')) {
      kindLabel = '毒杀';
      kindKey = 'poison';
    } else if (cause.includes('刀') || cause.includes('杀') || cause.includes('kill') || e.type === 'death_announcement') {
      kindLabel = '击杀';
      kindKey = 'kill';
    } else if (cause.includes('逐') || cause.includes('票') || cause.includes('exile') || e.type === 'elimination') {
      kindLabel = '放逐';
      kindKey = 'exile';
    }
    return {
      tag,
      night,
      text: String(e.message || e.text || '').trim(),
      kindLabel,
      kindClass: KIND_STYLE[kindKey] || 'text-text-secondary',
    };
  }).filter((k) => k.text);
}

const WerewolfGameOver: React.FC<WerewolfGameOverProps> = ({
  winner,
  reason,
  currentRound,
  agents,
  events = [],
  gameId,
  onReplay,
  onRematch,
}) => {
  const navigate = useNavigate();

  const aliveAgents = agents.filter((a) => a.is_alive);
  const deadAgents = agents.filter((a) => !a.is_alive);
  const keyEvents = extractKeyEvents(events);

  const isWolfWin = winner === 'werewolf';
  // 胜负横幅色调：狼人胜完全贴稿（violet），好人胜用 success 绿
  const bannerText = isWolfWin ? 'text-violet' : 'text-success';
  const bannerBg = isWolfWin
    ? 'bg-violet/[0.14] border-violet/60'
    : 'bg-success/[0.12] border-success/50';
  const winnerText = isWolfWin ? '狼人阵营 · 胜利' : '好人阵营 · 胜利';

  const stats: Array<{ label: string; value: string; valueClass: string }> = [
    { label: '总回合 ROUNDS', value: String(currentRound), valueClass: 'text-gold' },
    { label: '终局存活 ALIVE', value: `${aliveAgents.length} / ${agents.length}`, valueClass: 'text-text-primary' },
    { label: '事件总数 EVENTS', value: String(events.length), valueClass: 'text-text-primary' },
    { label: '玩家总数 PLAYERS', value: String(agents.length), valueClass: 'text-violet' },
  ];

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-[#0D0A14] animate-fadeIn">
      <div className="mx-auto flex min-h-full w-full max-w-[1180px] flex-col gap-6 px-5 py-8 sm:px-10 sm:py-10">
        {/* Header */}
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1.5">
            <span className="font-hud text-xs tracking-widest text-text-secondary">
              GAME OVER · 战局终了
            </span>
            <h1 className="text-3xl font-bold text-text-primary sm:text-[34px]">对局结算</h1>
          </div>
          {gameId && (
            <span className="font-hud text-[13px] text-text-secondary/70">{gameId}</span>
          )}
        </header>

        {/* WinnerBanner */}
        <section className={`flex flex-col gap-6 rounded-[18px] border p-6 sm:flex-row sm:items-center sm:justify-between ${bannerBg}`}>
          <div className="flex flex-col gap-2">
            <span className="font-hud text-xs tracking-widest text-text-secondary">
              WINNER · 胜出阵营
            </span>
            <p className={`font-display text-3xl font-bold sm:text-[40px] ${bannerText}`}>
              {winnerText}
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="font-hud text-xs tracking-widest text-text-secondary">结束原因</span>
            <p className="text-base text-text-primary">{reason}</p>
          </div>
        </section>

        {/* StatsRow */}
        <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="flex flex-col gap-1.5 rounded-[14px] border border-line bg-surface p-4">
              <span className="font-hud text-[11px] tracking-wider text-text-secondary">{s.label}</span>
              <span className={`font-display text-2xl font-bold sm:text-[30px] ${s.valueClass}`}>{s.value}</span>
            </div>
          ))}
        </section>

        {/* MainRow：名单 + 关键事件 */}
        <section className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-2">
          {/* RosterPanel */}
          <div className="flex min-h-0 flex-col gap-2.5 rounded-2xl border border-line bg-surface p-5 sm:p-6">
            <span className="font-hud text-[13px] tracking-widest text-text-secondary">
              终局名单 ROSTER
            </span>
            <div className="scrollbar-none -mx-1 min-h-0 flex-1 overflow-y-auto px-1">
              <div className="flex flex-col gap-2.5">
                {[...aliveAgents, ...deadAgents].map((agent) => (
                  <div
                    key={agent.agent_id}
                    className={`flex items-center gap-3 rounded-xl border border-line px-2.5 py-2.5 ${agent.is_alive ? '' : 'opacity-55'}`}
                  >
                    <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${roleDotClass(agent.role_cn)}`} />
                    <span className={`min-w-0 flex-1 truncate text-[15px] ${agent.is_alive ? 'text-text-primary' : 'text-text-primary/60 line-through'}`}>
                      {agent.name}
                    </span>
                    <span className={`shrink-0 text-xs ${roleColorClass(agent.role_cn)}`}>
                      {agent.role_cn || '身份未公开'}
                    </span>
                    <span className={`w-16 shrink-0 text-right font-hud text-xs ${agent.is_alive ? 'text-success' : 'text-text-secondary'}`}>
                      {agent.is_alive ? '存活' : '出局'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* TimelinePanel */}
          <div className="flex min-h-0 flex-col gap-2.5 rounded-2xl border border-line bg-surface p-5 sm:p-6">
            <span className="font-hud text-[13px] tracking-widest text-text-secondary">
              关键事件回顾 KEY EVENTS
            </span>
            <div className="scrollbar-none -mx-1 min-h-0 flex-1 overflow-y-auto px-1">
              {keyEvents.length > 0 ? (
                <div className="flex flex-col gap-1">
                  {keyEvents.map((k, i) => (
                    <div key={`${k.tag}-${i}`} className="flex items-start gap-3.5 rounded-xl px-3 py-3">
                      <span className={`w-8 shrink-0 pt-0.5 font-hud text-xs ${k.night ? 'text-gold' : 'text-text-secondary'}`}>
                        {k.tag}
                      </span>
                      <p className="min-w-0 flex-1 text-sm leading-6 text-text-primary">{k.text}</p>
                      <span className={`shrink-0 pt-0.5 text-[11px] ${k.kindClass}`}>{k.kindLabel}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="px-3 py-6 text-center text-sm text-text-secondary/60">
                  暂无关键事件记录
                </p>
              )}
            </div>
          </div>
        </section>

        {/* ActionBar */}
        <section className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
          <button
            onClick={onRematch}
            className="flex items-center justify-center gap-2 rounded-xl bg-violet px-4 py-4 text-base font-bold text-white transition-all hover:brightness-110 active:scale-[0.98]"
          >
            <RotateCcw className="h-5 w-5" />
            再来一局
          </button>
          {onReplay && (
            <button
              onClick={onReplay}
              className="flex items-center justify-center gap-2 rounded-xl border border-line-strong bg-surface px-4 py-4 text-base text-text-primary transition-all hover:border-violet/40 hover:text-violet active:scale-[0.98]"
            >
              <Play className="h-5 w-5" />
              查看回放
            </button>
          )}
          <button
            onClick={() => navigate('/')}
            className="flex items-center justify-center gap-2 rounded-xl border border-line-strong bg-surface px-4 py-4 text-base text-text-primary transition-all hover:border-violet/40 hover:text-violet active:scale-[0.98]"
          >
            <Home className="h-5 w-5" />
            返回大厅
          </button>
        </section>
      </div>
    </div>
  );
};

export default WerewolfGameOver;

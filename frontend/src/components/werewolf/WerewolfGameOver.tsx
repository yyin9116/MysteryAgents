/**
 * Werewolf Game Over Component
 * 狼人杀游戏结束展示组件
 */

import React, { useState } from 'react';
import { Trophy, Users, Clock, Home, RotateCcw, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { Agent } from '../../services/werewolfService';

interface WerewolfGameOverProps {
  winner: 'werewolf' | 'good';
  reason: string;
  currentRound: number;
  agents: Agent[];
  onReplay?: () => void;
}

const WerewolfGameOver: React.FC<WerewolfGameOverProps> = ({
  winner,
  reason,
  currentRound,
  agents,
  onReplay,
}) => {
  const navigate = useNavigate();
  const [showRoster, setShowRoster] = useState(false);

  const aliveAgents = agents.filter(a => a.is_alive);
  const deadAgents = agents.filter(a => !a.is_alive);

  const winnerText = winner === 'werewolf' ? '狼人阵营' : '好人阵营';
  const winnerColor = winner === 'werewolf' ? 'text-red-400' : 'text-blue-400';
  const winnerGlow = winner === 'werewolf'
    ? 'shadow-[0_0_30px_rgba(239,68,68,0.5)]'
    : 'shadow-[0_0_30px_rgba(96,165,250,0.5)]';
  const getFactionLabel = (faction?: string) => {
    if (faction === 'werewolf') return '狼人阵营';
    if (faction === 'good') return '好人阵营';
    return '阵营未公开';
  };

  return (
    <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-50 p-3 sm:p-4 animate-fadeIn">
      <div className="ww-card relative w-full max-w-3xl overflow-hidden">
        {/* Winner Announcement */}
        <div className="text-center mb-5 sm:mb-7">
          <div className={`inline-flex items-center justify-center w-16 h-16 rounded-full bg-ww-gold/20 mb-3 sm:h-20 sm:w-20 sm:mb-4 ${winnerGlow}`}>
            <Trophy className="w-8 h-8 text-ww-gold sm:w-10 sm:h-10" />
          </div>
          <h2 className="text-3xl font-bold text-ww-gold mb-2 sm:text-4xl">游戏结束</h2>
          <p className={`text-xl font-semibold ${winnerColor} mb-2 sm:text-2xl`}>
            {winnerText} 获胜！
          </p>
          <p className="mx-auto max-w-2xl text-sm leading-6 text-white/60 sm:text-base">{reason}</p>
        </div>

        {/* Game Statistics */}
        <div className="grid grid-cols-3 gap-2 mb-5 sm:gap-4 sm:mb-7">
          <div className="bg-black/30 rounded-2xl p-3 border border-ww-gold/20 text-center sm:p-4">
            <Clock className="w-5 h-5 text-ww-gold mx-auto mb-2 sm:w-6 sm:h-6" />
            <div className="text-xl font-bold text-ww-gold sm:text-2xl">{currentRound}</div>
            <div className="text-xs text-white/60 sm:text-sm">回合</div>
          </div>
          <div className="bg-black/30 rounded-2xl p-3 border border-emerald-400/20 text-center sm:p-4">
            <Users className="w-5 h-5 text-green-400 mx-auto mb-2 sm:w-6 sm:h-6" />
            <div className="text-xl font-bold text-green-400 sm:text-2xl">{aliveAgents.length}</div>
            <div className="text-xs text-white/60 sm:text-sm">存活</div>
          </div>
          <div className="bg-black/30 rounded-2xl p-3 border border-red-400/20 text-center sm:p-4">
            <Users className="w-5 h-5 text-red-400 mx-auto mb-2 sm:w-6 sm:h-6" />
            <div className="text-xl font-bold text-red-400 sm:text-2xl">{deadAgents.length}</div>
            <div className="text-xs text-white/60 sm:text-sm">淘汰</div>
          </div>
        </div>

        <button
          onClick={() => setShowRoster(true)}
          className="mb-5 w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-left transition-colors hover:border-ww-gold/30 hover:bg-ww-gold/10 sm:mb-7"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="font-semibold text-white">查看玩家名单</div>
              <div className="mt-1 text-sm text-white/45">身份、阵营、存活状态集中在详情面板展示</div>
            </div>
            <Users className="h-5 w-5 shrink-0 text-ww-gold" />
          </div>
        </button>

        {/* Action Buttons */}
        <div className="flex flex-col gap-3 sm:flex-row sm:gap-4">
          {onReplay && (
            <button
              onClick={onReplay}
              className="flex-1 px-6 py-3 bg-ww-gold/20 border border-ww-gold/50 text-ww-gold rounded-lg hover:bg-ww-gold/30 transition-colors flex items-center justify-center gap-2"
            >
              <RotateCcw className="w-5 h-5" />
              查看回放
            </button>
          )}
          <button
            onClick={() => navigate('/')}
            className="flex-1 ww-button-primary flex items-center justify-center gap-2"
          >
            <Home className="w-5 h-5" />
            返回主页
          </button>
        </div>

        {/* MVP Section (Optional Enhancement) */}
        <div className="mt-5 p-3 bg-gradient-to-r from-ww-gold/10 to-transparent rounded-2xl border border-ww-gold/20 sm:mt-6 sm:p-4">
          <p className="text-white/60 text-sm text-center">
            游戏数据已保存，可通过时间轴回放查看完整过程；未揭示身份会显示为“身份未公开”。
          </p>
        </div>

        {showRoster && (
          <div className="absolute inset-0 z-10 flex flex-col bg-slate-950/95">
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
              <div>
                <h3 className="text-lg font-bold text-ww-gold">玩家名单</h3>
                <p className="text-xs text-white/45">存活与淘汰分组展示</p>
              </div>
              <button
                onClick={() => setShowRoster(false)}
                className="rounded-xl border border-white/10 p-2 text-white/60"
                aria-label="关闭玩家名单"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="scrollbar-none min-h-0 flex-1 overflow-y-auto p-4">
              {[
                ['存活玩家', aliveAgents, 'border-green-500/30', ''],
                ['淘汰玩家', deadAgents, 'border-red-500/30 opacity-70', 'line-through'],
              ].map(([title, list, borderClass, nameClass]) => (
                <div key={title as string} className="mb-5">
                  <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ww-gold/80">
                    <Users className="w-4 h-4" />
                    {title as string} ({(list as Agent[]).length})
                  </h4>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {(list as Agent[]).map((agent) => (
                      <div
                        key={agent.agent_id}
                        className={`bg-black/30 rounded-2xl p-3 border ${borderClass as string}`}
                      >
                        <div className={`font-medium text-white ${nameClass as string}`}>{agent.name}</div>
                        <div className="text-sm text-white/60">
                          {agent.role_cn || '身份未公开'} · {agent.mbti_type}
                        </div>
                        <div className={`text-xs mt-1 ${
                          agent.faction === 'werewolf' ? 'text-red-400' : 'text-blue-400'
                        }`}>
                          {getFactionLabel(agent.faction)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default WerewolfGameOver;

/**
 * Possession Control Component
 * 夺舍控制组件 - 允许用户接管 Agent 进行操作
 */

import React, { useState, useEffect } from 'react';
import { User, X, Send, Moon, MessageCircle, Vote, Shield } from 'lucide-react';
import type { Agent, AgentRoleResponse } from '../../services/werewolfService';
import { getAgentRole, executeNightAction, submitVote } from '../../services/werewolfService';

interface PossessionControlProps {
  gameId: string;
  possessedAgent: Agent | null;
  allAgents: Agent[];
  currentPhase: string;
  onClose: () => void;
  onActionComplete?: () => void;
}

const PossessionControl: React.FC<PossessionControlProps> = ({
  gameId,
  possessedAgent,
  allAgents,
  currentPhase,
  onClose,
  onActionComplete,
}) => {
  const [roleInfo, setRoleInfo] = useState<AgentRoleResponse | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<string>('');
  const [actionType, setActionType] = useState<string>('');
  const [speechText, setSpeechText] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [showTargets, setShowTargets] = useState(false);

  useEffect(() => {
    if (possessedAgent) {
      loadRoleInfo();
    }
  }, [possessedAgent]);

  const loadRoleInfo = async () => {
    if (!possessedAgent) return;

    try {
      const info = await getAgentRole(gameId, possessedAgent.agent_id);
      setRoleInfo(info);
    } catch (err) {
      console.error('Failed to load role info:', err);
      setError('无法加载角色信息');
    }
  };

  const handleNightAction = async () => {
    if (!possessedAgent || !actionType || !selectedTarget) {
      setError('请选择行动类型和目标');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await executeNightAction(gameId, possessedAgent.agent_id, actionType, selectedTarget);
      setSelectedTarget('');
      setActionType('');
      if (onActionComplete) onActionComplete();
    } catch (err: any) {
      setError(err.message || '行动失败');
    } finally {
      setLoading(false);
    }
  };

  const handleVote = async () => {
    if (!possessedAgent || !selectedTarget) {
      setError('请选择投票目标');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await submitVote(gameId, possessedAgent.agent_id, selectedTarget);
      setSelectedTarget('');
      if (onActionComplete) onActionComplete();
    } catch (err: any) {
      setError(err.message || '投票失败');
    } finally {
      setLoading(false);
    }
  };

  if (!possessedAgent) return null;

  const aliveAgents = allAgents.filter(a => a.is_alive && a.agent_id !== possessedAgent.agent_id);
  const selectedTargetName = aliveAgents.find((agent) => agent.agent_id === selectedTarget)?.name;
  const phaseLabel = currentPhase === 'night'
    ? '夜晚行动'
    : currentPhase === 'day_discussion'
      ? '白天发言'
      : currentPhase === 'day_voting'
        ? '投票淘汰'
        : '等待阶段';
  const PhaseIcon = currentPhase === 'night'
    ? Moon
    : currentPhase === 'day_discussion'
      ? MessageCircle
      : currentPhase === 'day_voting'
        ? Vote
        : Shield;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-end justify-center z-50 p-3 sm:items-center sm:p-4">
      <div className="ww-card relative flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-[2rem] sm:rounded-[2rem]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-ww-gold/20 flex items-center justify-center">
              <User className="w-5 h-5 text-ww-gold" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-ww-gold">夺舍模式</h3>
              <p className="text-white/60 text-sm">
                {possessedAgent.name} {roleInfo?.role_cn && `· ${roleInfo.role_cn}`}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-white/60" />
          </button>
        </div>

        <div className="scrollbar-none min-h-0 flex-1 overflow-y-auto py-4">
          <div className="mb-4 grid grid-cols-[1fr_auto] gap-3">
            <div className="rounded-2xl border border-white/10 bg-black/30 p-3">
              <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-ww-gold">
                <PhaseIcon className="h-4 w-4" />
                {phaseLabel}
              </div>
              <p className="text-xs leading-5 text-white/45">只显示当前阶段可执行动作，其他信息收起避免挤满屏幕。</p>
            </div>
            {roleInfo && (
              <div className="rounded-2xl border border-ww-gold/20 bg-ww-gold/10 p-3 text-right">
                <div className="text-xs text-white/45">身份</div>
                <div className="mt-1 font-semibold text-ww-gold">{roleInfo.role_cn}</div>
                <div className="mt-1 text-xs text-white/55">{roleInfo.faction === 'werewolf' ? '狼人阵营' : '好人阵营'}</div>
              </div>
            )}
          </div>

          {roleInfo?.witch_potions && (
            <div className="mb-4 grid grid-cols-2 gap-2">
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-sm">
                <span className="text-white/50">解药：</span>
                <span className={roleInfo.witch_potions.antidote ? 'text-green-400' : 'text-red-400'}>
                  {roleInfo.witch_potions.antidote ? '可用' : '已用'}
                </span>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-sm">
                <span className="text-white/50">毒药：</span>
                <span className={roleInfo.witch_potions.poison ? 'text-green-400' : 'text-red-400'}>
                  {roleInfo.witch_potions.poison ? '可用' : '已用'}
                </span>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-300 text-sm">
              {error}
            </div>
          )}

          {/* Night Phase Actions */}
          {currentPhase === 'night' && roleInfo && (
            <div className="space-y-4">
              <h4 className="text-lg font-semibold text-ww-gold/80">选择夜晚动作</h4>

              {/* Action Type Selection */}
              {roleInfo.role === 'werewolf' && (
                <div>
                  <label className="block text-white/60 text-sm mb-2">行动类型</label>
                  <select
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value)}
                    className="w-full bg-black/40 border border-white/20 rounded-lg px-4 py-2 text-white focus:border-ww-gold focus:outline-none"
                  >
                    <option value="">选择行动</option>
                    <option value="werewolf_kill">击杀</option>
                  </select>
                </div>
              )}

              {roleInfo.role === 'seer' && (
                <div>
                  <label className="block text-white/60 text-sm mb-2">行动类型</label>
                  <select
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value)}
                    className="w-full bg-black/40 border border-white/20 rounded-lg px-4 py-2 text-white focus:border-ww-gold focus:outline-none"
                  >
                    <option value="">选择行动</option>
                    <option value="seer_check">查验</option>
                  </select>
                </div>
              )}

              {roleInfo.role === 'witch' && (
                <div>
                  <label className="block text-white/60 text-sm mb-2">行动类型</label>
                  <select
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value)}
                    className="w-full bg-black/40 border border-white/20 rounded-lg px-4 py-2 text-white focus:border-ww-gold focus:outline-none"
                  >
                    <option value="">选择行动</option>
                    {roleInfo.witch_potions?.antidote && <option value="witch_save">使用解药</option>}
                    {roleInfo.witch_potions?.poison && <option value="witch_poison">使用毒药</option>}
                  </select>
                </div>
              )}

              {roleInfo.role === 'guard' && (
                <div>
                  <label className="block text-white/60 text-sm mb-2">行动类型</label>
                  <select
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value)}
                    className="w-full bg-black/40 border border-white/20 rounded-lg px-4 py-2 text-white focus:border-ww-gold focus:outline-none"
                  >
                    <option value="">选择行动</option>
                    <option value="guard_protect">守护</option>
                  </select>
                </div>
              )}

              {actionType && (
                <button
                  onClick={() => setShowTargets(true)}
                  className="w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-left transition-colors hover:border-ww-gold/30"
                >
                  <div className="text-sm text-white/50">目标</div>
                  <div className="mt-1 font-semibold text-white">{selectedTargetName || '打开目标面板选择玩家'}</div>
                </button>
              )}

              {/* Submit Button */}
              {actionType && selectedTarget && (
                <button
                  onClick={handleNightAction}
                  disabled={loading}
                  className="w-full ww-button-primary flex items-center justify-center gap-2"
                >
                  {loading ? '执行中...' : '确认行动'}
                  <Send className="w-4 h-4" />
                </button>
              )}
            </div>
          )}

          {/* Day Discussion Phase */}
          {currentPhase === 'day_discussion' && (
            <div className="space-y-4">
              <h4 className="text-lg font-semibold text-ww-gold/80">白天发言</h4>
              <textarea
                value={speechText}
                onChange={(e) => setSpeechText(e.target.value)}
                placeholder="输入你的发言内容..."
                className="h-32 w-full resize-none rounded-2xl border border-white/20 bg-black/40 px-4 py-3 text-white focus:border-ww-gold focus:outline-none"
              />
              <button
                onClick={() => {
                  // In a real implementation, this would send the speech to the backend
                  console.log('Speech:', speechText);
                  setSpeechText('');
                  if (onActionComplete) onActionComplete();
                }}
                disabled={!speechText.trim() || loading}
                className="w-full ww-button-primary flex items-center justify-center gap-2"
              >
                发送发言
                <Send className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Day Voting Phase */}
          {currentPhase === 'day_voting' && (
            <div className="space-y-4">
              <h4 className="text-lg font-semibold text-ww-gold/80">投票淘汰</h4>
              <p className="text-white/60 text-sm">选择你要投票淘汰的玩家</p>

              <button
                onClick={() => setShowTargets(true)}
                className="w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-left transition-colors hover:border-ww-gold/30"
              >
                <div className="text-sm text-white/50">投票目标</div>
                <div className="mt-1 font-semibold text-white">{selectedTargetName || '打开目标面板选择玩家'}</div>
              </button>

              {selectedTarget && (
                <button
                  onClick={handleVote}
                  disabled={loading}
                  className="w-full ww-button-primary flex items-center justify-center gap-2"
                >
                  {loading ? '投票中...' : '确认投票'}
                  <Send className="w-4 h-4" />
                </button>
              )}
            </div>
          )}

          {/* Other Phases */}
          {!['night', 'day_discussion', 'day_voting'].includes(currentPhase) && (
            <div className="text-center py-8 text-white/60">
              <p>当前阶段无法进行操作</p>
              <p className="text-sm mt-2">阶段: {currentPhase}</p>
            </div>
          )}
        </div>

        {showTargets && (
          <div className="absolute inset-0 z-10 flex flex-col bg-slate-950/95">
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
              <div>
                <h4 className="text-lg font-bold text-ww-gold">选择目标</h4>
                <p className="text-xs text-white/45">目标列表独立显示，主操作面板保持简洁</p>
              </div>
              <button
                onClick={() => setShowTargets(false)}
                className="rounded-xl border border-white/10 p-2 text-white/60"
                aria-label="关闭目标选择"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="scrollbar-none grid min-h-0 flex-1 grid-cols-2 gap-2 overflow-y-auto p-4">
              {aliveAgents.map((agent) => (
                <button
                  key={agent.agent_id}
                  onClick={() => {
                    setSelectedTarget(agent.agent_id);
                    setShowTargets(false);
                  }}
                  className={`rounded-2xl border p-3 text-left transition-all ${
                    selectedTarget === agent.agent_id
                      ? 'border-ww-gold bg-ww-gold/10'
                      : 'border-white/10 bg-black/20 hover:border-white/30'
                  }`}
                >
                  <div className="font-medium text-white">{agent.name}</div>
                  <div className="text-xs text-white/60">{agent.mbti_type}</div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PossessionControl;

import React, { useMemo, useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { gameService } from '../services/gameService';
import { streamService, type StreamEvent } from '../services/streamService';
import PossessionModal from './PossessionModal';
import SaveLoadModal from './SaveLoadModal';
import PersonalityEditor from './PersonalityEditor';
import ModelSelector from './ModelSelector';
import VotingNotification from './VotingNotification';
import EliminationNotice from './EliminationNotice';
import GameOverModal from './GameOverModal';
import SystemMessageModal from './SystemMessageModal';
import Toast from './Toast';
import { ArrowLeft, SkipForward, Save, Brain, Cpu, KeyRound, Loader2 } from 'lucide-react';
import type { Agent } from '../types/agent';
import { generateStableNickname } from '../utils/nicknameGenerator';
import { useI18n } from '../hooks/useI18n';

/** 卧底模式强调色（对齐设计稿 3:540 的橙色语义） */
const ORANGE = {
  text: 'text-[#f0a159]',
  border: 'border-[#f0a159]/40',
  bg: 'bg-[#f0a159]/12',
  dot: 'bg-[#f0a159]',
  glow: 'shadow-[0_0_28px_rgba(240,161,89,0.15)]',
};

/** 玩家头像色板（按 agent_id 稳定取色） */
const AVATAR_COLORS = ['#5c8cf0', '#8c7df5', '#4fccc4', '#e06b6b', '#f0a159', '#7dd9a6', '#c884f0', '#e8c269'];
const avatarColor = (id: string) => AVATAR_COLORS[Math.abs([...id].reduce((h, c) => c.charCodeAt(0) + ((h << 5) - h), 0)) % AVATAR_COLORS.length];

/** 从所有描述中提取高频联想词（二元组频次） */
const extractKeywords = (descriptions: string[], limit = 8): Array<{ word: string; hot: boolean }> => {
  const STOP = new Set(['我们', '你们', '他们', '这个', '那个', '什么', '一个', '没有', '就是', '但是', '因为', '所以', '觉得', '说到']);
  const freq: Record<string, number> = {};
  for (const text of descriptions) {
    const clean = text.replace(/[，。！？、…“”"'\s]/g, '');
    for (let i = 0; i < clean.length - 1; i += 1) {
      const gram = clean.slice(i, i + 2);
      if (!/[\u4e00-\u9fa5]{2}/.test(gram) || STOP.has(gram)) continue;
      freq[gram] = (freq[gram] || 0) + 1;
    }
  }
  return Object.entries(freq)
    .filter(([, n]) => n >= 2)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([word, n], idx) => ({ word, hot: idx < 2 && n >= 3 }));
};

const GameBoard: React.FC = () => {
    const { currentGame, fetchGameState } = useGameStore();
    const [processing, setProcessing] = useState(false);
    const [thinkingAgent, setThinkingAgent] = useState<{agent_id: string; agent_name: string; index: number; total: number} | null>(null);
    const [possessedAgentData, setPossessedAgentData] = useState<Agent | null>(null);
    const [showPossessionModal, setShowPossessionModal] = useState(false);
    const [showSaveLoadModal, setShowSaveLoadModal] = useState(false);
    const [showPersonalityEditor, setShowPersonalityEditor] = useState(false);
    const [showModelSelector, setShowModelSelector] = useState(false);
    const [loadingPossession, setLoadingPossession] = useState(false);

    // 系统消息弹窗状态（只用于违规）
    const [systemMessage, setSystemMessage] = useState<{
        title: string;
        message: string;
        data?: any;
    } | null>(null);
    const [showSystemModal, setShowSystemModal] = useState(false);

    // Toast 提示状态（用于投票开始、淘汰通知）
    const [toastMessage, setToastMessage] = useState<{
        type: 'voting_start' | 'elimination' | 'info' | 'success';
        message: string;
    } | null>(null);
    const [showToast, setShowToast] = useState(false);

    // 游戏状态
    const [currentVote, setCurrentVote] = useState<{
        voterName: string;
        votedForName: string;
        confidence: number;
        index: number;
        total: number;
    } | null>(null);
    const [eliminationData, setEliminationData] = useState<{
        eliminatedName: string;
        eliminatedRole: string;
        eliminatedWord: string;
        voteCount: number;
    } | null>(null);
    const [gameOverData, setGameOverData] = useState<{
        result: 'undercover_win' | 'civilian_win' | 'draw';
        message: string;
    } | null>(null);

    const { t } = useI18n();

    if (!currentGame) return null;

    const handleStopGame = () => {
        streamService.stopGameStream();
        setProcessing(false);
        setThinkingAgent(null);
        setCurrentVote(null);
        setEliminationData(null);
        setShowToast(false);
        setToastMessage(null);

        const shouldContinue = window.confirm(
            '游戏已终止。\n\n点击"确定"继续当前游戏\n点击"取消"返回首页重新开始'
        );

        if (!shouldContinue) {
            window.location.href = '/';
        }
    };

    const handleNextRound = async () => {
        setProcessing(true);
        setThinkingAgent(null);
        setCurrentVote(null);
        setEliminationData(null);

        try {
            streamService.startGameStream(
                currentGame.game_id,
                (event: StreamEvent) => {
                    switch (event.type) {
                        case 'round_start':
                            break;

                        case 'agent_thinking':
                            if (event.phase === 'description') {
                                setThinkingAgent({
                                    agent_id: event.agent_id,
                                    agent_name: event.agent_name,
                                    index: event.index,
                                    total: event.total
                                });
                            }
                            break;

                        case 'agent_speaking':
                            setThinkingAgent(null);
                            fetchGameState(currentGame.game_id);
                            break;

                        case 'duplicate_violation':
                            setThinkingAgent(null);
                            setSystemMessage({
                                title: '违规踢出',
                                message: `${event.agent_name} 因重复发言被踢出游戏！`,
                                data: {
                                    duplicate_agent_id: event.duplicate_agent_id,
                                    duplicate_speech: event.duplicate_speech
                                }
                            });
                            setShowSystemModal(true);
                            fetchGameState(currentGame.game_id);
                            break;

                        case 'voting_start':
                            setThinkingAgent(null);
                            setToastMessage({
                                type: 'voting_start',
                                message: '开始投票！'
                            });
                            setShowToast(true);
                            break;

                        case 'agent_voting':
                            setCurrentVote({
                                voterName: event.agent_name,
                                votedForName: event.voted_for_name,
                                confidence: event.confidence,
                                index: event.index,
                                total: event.total
                            });
                            setTimeout(() => setCurrentVote(null), 2500);
                            fetchGameState(currentGame.game_id);
                            break;

                        case 'elimination':
                            setCurrentVote(null);
                            setToastMessage({
                                type: 'elimination',
                                message: `${event.eliminated_name} 被投票淘汰！`
                            });
                            setShowToast(true);
                            setEliminationData({
                                eliminatedName: event.eliminated_name,
                                eliminatedRole: event.eliminated_role,
                                eliminatedWord: event.eliminated_word,
                                voteCount: event.vote_count
                            });
                            fetchGameState(currentGame.game_id);
                            break;

                        case 'game_over':
                            setThinkingAgent(null);
                            setCurrentVote(null);
                            setEliminationData(null);
                            setProcessing(false);
                            setGameOverData({
                                result: event.result,
                                message: event.message
                            });
                            fetchGameState(currentGame.game_id);
                            break;

                        case 'round_complete':
                            setThinkingAgent(null);
                            setCurrentVote(null);
                            setEliminationData(null);
                            setProcessing(false);
                            fetchGameState(currentGame.game_id);
                            break;

                        case 'error':
                            console.error('Stream error:', event.message);
                            setThinkingAgent(null);
                            setCurrentVote(null);
                            setEliminationData(null);
                            setProcessing(false);
                            break;
                    }
                },
                (error: Error) => {
                    console.error('Stream connection error:', error);
                    setThinkingAgent(null);
                    setCurrentVote(null);
                    setEliminationData(null);
                    setProcessing(false);
                }
            );
        } catch (err) {
            console.error('Failed to start stream:', err);
            setProcessing(false);
            setThinkingAgent(null);
            setCurrentVote(null);
            setEliminationData(null);
        }
    };

    const handlePossess = async (agentId: string) => {
        try {
            const result = await gameService.possessAgent(currentGame.game_id, agentId);
            const agent = currentGame.agents.find(a => a.id === agentId);
            if (agent) {
                setPossessedAgentData({ ...agent, word: result.word, role: result.role });
                setShowPossessionModal(true);
            }
            await fetchGameState(currentGame.game_id);
        } catch (err) {
            console.error('Failed to possess agent:', err);
        }
    };

    const handleRelease = async () => {
        if (!possessedAgentData) return;
        setLoadingPossession(true);
        try {
            await gameService.releaseAgent(currentGame.game_id, possessedAgentData.id);
            setShowPossessionModal(false);
            setPossessedAgentData(null);
            await fetchGameState(currentGame.game_id);
        } catch (err) {
            console.error('Failed to release agent:', err);
        } finally {
            setLoadingPossession(false);
        }
    };

    const handleSubmitInput = async (speech: string, suspicion: Record<string, number>) => {
        if (!possessedAgentData) return;
        setLoadingPossession(true);
        try {
            await gameService.submitUserInput(currentGame.game_id, possessedAgentData.id, speech, suspicion);
            setShowPossessionModal(false);
            setPossessedAgentData(null);
            await fetchGameState(currentGame.game_id);
        } catch (err) {
            console.error('Failed to submit user input:', err);
        } finally {
            setLoadingPossession(false);
        }
    };

    const handleRestart = () => {
        window.location.reload();
    };

    const handleHome = () => {
        window.location.href = '/';
    };

    // ---------- 设计稿 3:540 数据推导 ----------
    const agentNick = (agent: Agent) => agent.name || generateStableNickname(agent.id, agent.mbti_type, agent.iq_level);

    const descriptions = useMemo(() => {
        if (!currentGame) return [];
        return currentGame.conversation_history
            .filter((entry: any) => entry.agent_id !== 'system')
            .map((entry: any) => entry);
    }, [currentGame]);

    const keywords = useMemo(
        () => extractKeywords(descriptions.map((entry: any) => entry.content || '')),
        [descriptions]
    );

    const lastVoteEntry = useMemo(() => {
        if (!currentGame) return null;
        for (let i = currentGame.conversation_history.length - 1; i >= 0; i -= 1) {
            const entry: any = currentGame.conversation_history[i];
            if (entry.agent_id === 'system' && entry.type === 'voting') return entry;
        }
        return null;
    }, [currentGame]);

    const aliveCount = currentGame.agents.filter((a: Agent) => a.is_alive).length;
    const possessedWord = possessedAgentData?.word;
    const possessedRole = possessedAgentData?.role;

    return (
        <div className="flex min-h-screen flex-col bg-[var(--ds-bg-base)] text-text-primary">
            {/* 顶栏（对齐设计稿 3:540） */}
            <header className="flex flex-wrap items-center justify-between gap-4 border-b border-line bg-surface/50 px-7 py-4 backdrop-blur-xl">
                <div className="flex min-w-0 items-center gap-4">
                    <button
                        onClick={handleHome}
                        className="rounded-xl border border-line p-2 text-gold/70 transition-colors hover:border-gold/40 hover:text-gold"
                        title="退出对局"
                    >
                        <ArrowLeft className="h-4 w-4" />
                    </button>
                    <div className="min-w-0">
                        <h1 className="truncate text-xl font-bold text-text-primary">
                            谁是卧底 · {currentGame.phase === 'description' ? '描述回合' : '投票阶段'}
                        </h1>
                        <p className="truncate text-xs text-text-secondary/60">
                            {currentGame.agents.length} 人局 · 第 {currentGame.round} 轮 · 存活 {aliveCount} 人
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 rounded-full border border-[#f0a159]/50 bg-[#f0a159]/12 px-[15px] py-[7px]">
                        <span className={`h-[7px] w-[7px] rounded-full ${processing ? 'animate-pulse-soft' : ''} ${ORANGE.dot}`} />
                        <span className="text-xs font-medium text-[#f0a159]">
                            第 {currentGame.round} 轮 · {currentGame.phase === 'description' ? '依次描述' : '投票中'}
                        </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <button
                            onClick={() => setShowModelSelector(true)}
                            className="rounded-xl border border-line p-2.5 text-text-secondary/70 transition-colors hover:border-gold/40 hover:text-gold"
                            title="模型选择"
                        >
                            <Cpu className="h-4 w-4" />
                        </button>
                        <button
                            onClick={() => setShowPersonalityEditor(true)}
                            className="rounded-xl border border-line p-2.5 text-text-secondary/70 transition-colors hover:border-gold/40 hover:text-gold"
                            title="人格编辑器"
                        >
                            <Brain className="h-4 w-4" />
                        </button>
                        <button
                            onClick={() => setShowSaveLoadModal(true)}
                            className="rounded-xl border border-line p-2.5 text-text-secondary/70 transition-colors hover:border-gold/40 hover:text-gold"
                            title={t.game.saveGame}
                        >
                            <Save className="h-4 w-4" />
                        </button>
                        <button
                            onClick={processing ? handleStopGame : handleNextRound}
                            disabled={currentGame.game_over}
                            className={`ml-1 flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold transition-all disabled:opacity-50 ${
                                processing
                                    ? 'bg-danger text-white hover:brightness-110'
                                    : 'bg-gold text-[#171424] shadow-[0_0_18px_rgba(232,194,105,0.35)] hover:brightness-110'
                            }`}
                        >
                            {processing ? (
                                <>
                                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/25 border-t-white" />
                                    终止
                                </>
                            ) : (
                                <>
                                    <SkipForward className="h-4 w-4" />
                                    {currentGame.round === 0 ? '开始游戏' : t.game.nextRound}
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </header>

            {/* 主体：左列（身份与辅助）+ 右列（玩家描述流） */}
            <div className="grid min-h-0 flex-1 gap-6 overflow-y-auto p-6 lg:grid-cols-[380px_minmax(0,1fr)] xl:grid-cols-[400px_minmax(0,1fr)]">
                {/* 左列 */}
                <div className="flex min-h-0 flex-col gap-4">
                    {/* 词语卡 / 身份提示卡 */}
                    {possessedWord ? (
                        <div className={`rounded-[20px] border ${ORANGE.border} bg-surface p-7 ${ORANGE.glow}`}>
                            <p className="font-hud text-[11px] uppercase tracking-[0.3em] text-[#f0a159]">Your Word</p>
                            <p className="mt-2 text-5xl font-black tracking-wide text-text-primary">{possessedWord}</p>
                            <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-[#7dd9a6]/10 px-3.5 py-2">
                                <span className="h-[7px] w-[7px] rounded-full bg-[#7dd9a6]" />
                                <span className="text-xs font-medium text-[#7dd9a6]">
                                    你正掌控 {possessedRole === 'Undercover' ? '卧底' : '平民'} · {agentNick(possessedAgentData!)}
                                </span>
                            </div>
                        </div>
                    ) : (
                        <div className="rounded-[20px] border border-line bg-surface p-7">
                            <p className="font-hud text-[11px] uppercase tracking-[0.3em] text-text-secondary/55">Identity</p>
                            <p className="mt-3 flex items-start gap-2.5 text-sm leading-6 text-text-secondary/80">
                                <KeyRound className={`mt-0.5 h-4 w-4 shrink-0 ${ORANGE.text}`} />
                                点击右侧任意玩家的序号圆点即可「夺席」查看你的词语与身份，并代其发言。
                            </p>
                        </div>
                    )}

                    {/* 回合进度卡 */}
                    <div className="rounded-2xl border border-line bg-surface p-[18px]">
                        <p className="font-hud mb-3 text-[11px] uppercase tracking-[0.25em] text-text-secondary/55">
                            {processing ? '回合进行中 ROUND PROGRESS' : '回合待开始 READY'}
                        </p>
                        {thinkingAgent ? (
                            <div className="flex flex-col gap-3">
                                <div className="flex items-center justify-between text-xs">
                                    <span className="font-medium text-text-primary">{thinkingAgent.agent_name} 正在描述</span>
                                    <span className="font-hud text-text-secondary/60">{thinkingAgent.index} / {thinkingAgent.total}</span>
                                </div>
                                <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
                                    <div
                                        className="h-full rounded-full bg-gold transition-all duration-500"
                                        style={{ width: `${Math.round((thinkingAgent.index / Math.max(1, thinkingAgent.total)) * 100)}%` }}
                                    />
                                </div>
                                <div className="flex flex-col gap-2">
                                    <span className="anim-name-shimmer-dim h-3 w-10/12 rounded-full" />
                                    <span className="anim-name-shimmer-dim h-3 w-2/3 rounded-full" />
                                </div>
                            </div>
                        ) : (
                            <div className="flex items-center gap-3 text-xs text-text-secondary/60">
                                {processing && <Loader2 className="h-4 w-4 animate-spin text-gold" />}
                                {processing ? '模型正在生成行动，请稍候…' : '点击右上角「下一轮」推进对局。'}
                            </div>
                        )}
                    </div>

                    {/* 高频词卡 */}
                    {keywords.length > 0 && (
                        <div className="rounded-2xl border border-line bg-surface p-[18px]">
                            <p className="font-hud mb-3 text-[11px] uppercase tracking-[0.25em] text-text-secondary/55">
                                Keywords · 本轮高频联想
                            </p>
                            <div className="flex flex-wrap gap-2">
                                {keywords.map(({ word, hot }) => (
                                    <span
                                        key={word}
                                        className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                                            hot
                                                ? 'bg-[#f0a159]/12 text-[#f0a159]'
                                                : 'bg-white/[0.06] text-text-secondary/80'
                                        }`}
                                    >
                                        {word}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* 上轮投票 */}
                    {lastVoteEntry && (
                        <div className="rounded-2xl border border-line bg-white/[0.04] p-[18px]">
                            <p className="font-hud mb-2 text-[11px] uppercase tracking-[0.25em] text-text-secondary/55">
                                第 {Math.max(1, currentGame.round - 1)} 轮投票
                            </p>
                            <p className="line-clamp-2 text-xs leading-5 text-text-secondary/80">{lastVoteEntry.content}</p>
                        </div>
                    )}
                </div>

                {/* 右列 · 玩家描述流 */}
                <section className="flex min-h-0 flex-col">
                    <p className="font-hud mb-3 text-[11px] uppercase tracking-[0.25em] text-text-secondary/60">
                        玩家描述 ROUND DESCRIPTIONS
                    </p>
                    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto scrollbar-none pr-1">
                        {descriptions.length === 0 && !thinkingAgent && (
                            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-text-secondary/50">
                                <KeyRound className="h-8 w-8 opacity-40" />
                                <p className="text-sm">对局尚未开始，描述将按座位顺序出现在这里</p>
                            </div>
                        )}
                        {descriptions.map((entry: any, idx: number) => {
                            if (entry.agent_id === 'system') {
                                const isVoting = entry.type === 'voting';
                                return (
                                    <div key={`sys-${idx}`} className="anim-log-in flex justify-center py-1">
                                        <div className={`max-w-lg rounded-xl border px-4 py-2.5 text-center text-xs font-bold ${
                                            isVoting
                                                ? 'border-info/35 bg-info/10 text-info'
                                                : 'border-danger/35 bg-danger/10 text-danger'
                                        }`}>
                                            {entry.content}
                                        </div>
                                    </div>
                                );
                            }
                            const agent = currentGame.agents.find((a: Agent) => a.id === entry.agent_id);
                            const name = agent ? agentNick(agent) : entry.agent_id;
                            const color = avatarColor(entry.agent_id);
                            const isUser = entry.user_controlled;
                            return (
                                <div
                                    key={`${entry.agent_id}-${entry.round}-${idx}`}
                                    className={`anim-log-in flex items-start gap-3 rounded-xl border bg-surface px-3.5 py-3.5 ${
                                        isUser ? 'border-gold/45' : 'border-line'
                                    }`}
                                >
                                    <button
                                        onClick={() => {
                                            if (agent) {
                                                handlePossess(agent.id);
                                            }
                                        }}
                                        className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full text-xs font-bold transition-transform hover:scale-110"
                                        style={{ backgroundColor: color, color: '#0d0b14' }}
                                        title={`夺席 ${name}`}
                                    >
                                        {(agent ? currentGame.agents.filter((a: Agent) => a.is_alive).indexOf(agent) : idx) + 1}
                                    </button>
                                    <div className="min-w-0 flex-1">
                                        <p className="text-xs font-medium text-text-primary">
                                            {isUser ? '你 · ' : '玩家 · '}{name}
                                            {agent && (
                                                <span className="ml-2 text-[10px] font-normal text-text-secondary/45">
                                                    {agent.mbti_type} · {agent.iq_level}
                                                </span>
                                            )}
                                        </p>
                                        <p className="mt-1 text-[13px] leading-5 text-text-secondary/85">{entry.content}</p>
                                        {entry.thought && (
                                            <p className="mt-1.5 border-t border-line pt-1.5 text-[11px] italic leading-4 text-text-secondary/50">
                                                {entry.thought}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            );
                        })}

                        {/* 思考中玩家 */}
                        {thinkingAgent && (
                            <div className="flex items-start gap-3 rounded-xl border border-[#f0a159]/45 bg-surface px-3.5 py-3.5">
                                <span className={`flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full text-xs font-bold ${ORANGE.dot} text-[#0d0b14]`}>
                                    {thinkingAgent.index}
                                </span>
                                <div className="min-w-0 flex-1">
                                    <p className="text-xs font-medium text-text-primary">玩家 · {thinkingAgent.agent_name}</p>
                                    <div className="mt-2 flex items-center gap-3 text-xs text-[#f0a159]/85">
                                        <div className="flex gap-1.5">
                                            <span className="anim-thinking-dot h-2 w-2 rounded-full bg-[#f0a159]" />
                                            <span className="anim-thinking-dot h-2 w-2 rounded-full bg-[#f0a159] [animation-delay:150ms]" />
                                            <span className="anim-thinking-dot h-2 w-2 rounded-full bg-[#f0a159] [animation-delay:300ms]" />
                                        </div>
                                        正在组织描述…
                                    </div>
                                    <div className="mt-2 flex flex-col gap-2">
                                        <span className="anim-name-shimmer-dim h-3 w-9/12 rounded-full" />
                                        <span className="anim-name-shimmer-dim h-3 w-1/2 rounded-full" />
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </section>
            </div>

            {/* Voting Notification */}
            {currentVote && (
                <VotingNotification
                    voterName={currentVote.voterName}
                    votedForName={currentVote.votedForName}
                    confidence={currentVote.confidence}
                    index={currentVote.index}
                    total={currentVote.total}
                />
            )}

            {/* Elimination Notice */}
            {eliminationData && (
                <EliminationNotice
                    eliminatedName={eliminationData.eliminatedName}
                    eliminatedRole={eliminationData.eliminatedRole}
                    eliminatedWord={eliminationData.eliminatedWord}
                    voteCount={eliminationData.voteCount}
                    onComplete={() => setEliminationData(null)}
                />
            )}

            {/* Game Over Modal */}
            {gameOverData && (
                <GameOverModal
                    isOpen={true}
                    result={gameOverData.result}
                    message={gameOverData.message}
                    onRestart={handleRestart}
                    onHome={handleHome}
                />
            )}

            {showPossessionModal && possessedAgentData && (
                <PossessionModal
                    agent={possessedAgentData}
                    onClose={() => setShowPossessionModal(false)}
                    onRelease={handleRelease}
                    onSubmit={handleSubmitInput}
                    loading={loadingPossession}
                />
            )}

            {showSaveLoadModal && (
                <SaveLoadModal
                    isOpen={showSaveLoadModal}
                    onClose={() => setShowSaveLoadModal(false)}
                    gameId={currentGame.game_id}
                    onLoadSuccess={(gameId) => fetchGameState(gameId)}
                />
            )}

            {showPersonalityEditor && (
                <PersonalityEditor
                    isOpen={showPersonalityEditor}
                    onClose={() => setShowPersonalityEditor(false)}
                />
            )}

            {showModelSelector && (
                <ModelSelector
                    isOpen={showModelSelector}
                    onClose={() => setShowModelSelector(false)}
                    onSave={(config) => {
                        console.log('Model configuration saved:', config);
                    }}
                />
            )}

            {/* System Message Modal - 只用于违规 */}
            {systemMessage && (
                <SystemMessageModal
                    isOpen={showSystemModal}
                    title={systemMessage.title}
                    message={systemMessage.message}
                    data={systemMessage.data}
                    onConfirm={() => {
                        setShowSystemModal(false);
                        setSystemMessage(null);
                    }}
                    onClose={() => {
                        setShowSystemModal(false);
                        setSystemMessage(null);
                    }}
                />
            )}

            {/* Toast Notification */}
            {toastMessage && (
                <Toast
                    isOpen={showToast}
                    type={toastMessage.type}
                    message={toastMessage.message}
                    duration={2000}
                    onClose={() => {
                        setShowToast(false);
                        setToastMessage(null);
                    }}
                />
            )}
        </div>
    );
};

export default GameBoard;

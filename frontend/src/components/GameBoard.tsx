import React, { useState } from 'react';
import { useGameStore } from '../store/gameStore';
import { gameService } from '../services/gameService';
import { streamService, type StreamEvent } from '../services/streamService';
import ConversationLog from './ConversationLog';
import PossessionModal from './PossessionModal';
import SaveLoadModal from './SaveLoadModal';
import PersonalityEditor from './PersonalityEditor';
import ModelSelector from './ModelSelector';
import VotingNotification from './VotingNotification';
import EliminationNotice from './EliminationNotice';
import GameOverModal from './GameOverModal';
import SystemMessageModal from './SystemMessageModal';
import Toast from './Toast';
import { SkipForward, Save, Settings, Brain, Cpu } from 'lucide-react';
import type { Agent } from '../types/agent';
import { useI18n } from '../hooks/useI18n';

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
        // 停止流式连接
        streamService.stopGameStream();
        // 重置所有状态
        setProcessing(false);
        setThinkingAgent(null);
        setCurrentVote(null);
        setEliminationData(null);
        setShowToast(false);
        setToastMessage(null);
        
        // 显示提示：可以继续游戏或重新开始
        const shouldContinue = window.confirm(
            '游戏已终止。\n\n点击"确定"继续当前游戏\n点击"取消"返回首页重新开始'
        );
        
        if (!shouldContinue) {
            // 返回首页
            window.location.href = '/';
        }
        // 否则保持在当前页面，用户可以点击"下一轮"继续
    };

    const handleNextRound = async () => {
        setProcessing(true);
        setThinkingAgent(null);
        setCurrentVote(null);
        setEliminationData(null);
        
        try {
            // 使用流式 API
            streamService.startGameStream(
                currentGame.game_id,
                (event: StreamEvent) => {
                    console.log('Stream event:', event);
                    
                    switch (event.type) {
                        case 'round_start':
                            console.log(`回合 ${event.round} 开始 - ${event.phase}`);
                            break;
                            
                        case 'agent_thinking':
                            // 显示思考状态
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
                            // Agent 发言完成，清除思考状态
                            setThinkingAgent(null);
                            // 刷新游戏状态以显示新消息
                            fetchGameState(currentGame.game_id);
                            break;
                        
                        case 'duplicate_violation':
                            // 重复发言违规 - 显示违规弹窗
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
                            // 投票阶段开始 - 显示 Toast 提示（自动消失）
                            console.log('投票阶段开始');
                            setThinkingAgent(null);
                            setToastMessage({
                                type: 'voting_start',
                                message: '🗳️ 开始投票！'
                            });
                            setShowToast(true);
                            break;
                            
                        case 'agent_voting':
                            // Agent 投票完成 - 显示投票通知
                            setCurrentVote({
                                voterName: event.agent_name,
                                votedForName: event.voted_for_name,
                                confidence: event.confidence,
                                index: event.index,
                                total: event.total
                            });
                            // 2.5秒后清除投票通知（增加显示时间）
                            setTimeout(() => setCurrentVote(null), 2500);
                            // 刷新游戏状态
                            fetchGameState(currentGame.game_id);
                            break;
                            
                        case 'elimination':
                            // 淘汰结果 - 显示 Toast 提示和淘汰动画（自动消失）
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
                            // 游戏结束
                            console.log(`游戏结束: ${event.message}`);
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
                            // 回合完成
                            console.log(`回合 ${event.round} 完成，剩余 ${event.remaining_agents} 个 Agent`);
                            setThinkingAgent(null);
                            setCurrentVote(null);
                            setEliminationData(null);
                            setProcessing(false);
                            // 最终刷新游戏状态
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
            
            // 注意：cleanup 函数会在组件卸载时调用
            // 这里我们不需要立即调用它，因为流会自动结束
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
            // Merge extra data (word, role) into the agent object for display in modal
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

    return (
        <div className="space-y-8 animate-in fade-in duration-700">
            {/* Game Header Stats */}
            <div className="flex flex-wrap items-center justify-between gap-4 glass p-6 rounded-3xl">
                <div className="flex items-center space-x-6">
                    <div className="flex flex-col">
                        <span className="text-xs font-bold text-text-muted uppercase tracking-widest">{t.game.round}</span>
                        <span className="text-3xl font-black text-primary">{currentGame.round} <span className="text-sm font-medium text-text-muted">/ 10</span></span>
                    </div>
                    <div className="h-10 w-px bg-white/10 hidden sm:block" />
                    <div className="flex flex-col">
                        <span className="text-xs font-bold text-text-muted uppercase tracking-widest">{t.game.phase}</span>
                        <span className="text-lg font-bold flex items-center space-x-2">
                            <div className={`w-2 h-2 rounded-full ${currentGame.phase === 'description' ? 'bg-green-500 animate-pulse' : 'bg-primary'}`} />
                            <span className="capitalize">
                                {t.game[currentGame.phase as keyof typeof t.game] || currentGame.phase.replace('_', ' ')}
                            </span>
                        </span>
                    </div>
                </div>

                <div className="flex items-center space-x-3">
                    <button 
                        onClick={() => setShowModelSelector(true)}
                        className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl border border-white/10 transition-colors" 
                        title="模型选择"
                    >
                        <Cpu className="w-5 h-5" />
                    </button>
                    <button 
                        onClick={() => setShowPersonalityEditor(true)}
                        className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl border border-white/10 transition-colors" 
                        title="人格编辑器"
                    >
                        <Brain className="w-5 h-5" />
                    </button>
                    <button 
                        onClick={() => setShowSaveLoadModal(true)}
                        className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl border border-white/10 transition-colors" 
                        title={t.game.saveGame}
                    >
                        <Save className="w-5 h-5" />
                    </button>
                    <button className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl border border-white/10 transition-colors" title={t.nav.settings}>
                        <Settings className="w-5 h-5" />
                    </button>
                    <button
                        onClick={processing ? handleStopGame : handleNextRound}
                        disabled={currentGame.game_over}
                        className={`flex items-center space-x-2 ${
                            processing 
                                ? 'bg-red-500 hover:bg-red-600' 
                                : 'bg-primary hover:bg-primary/90'
                        } text-white px-6 py-3 rounded-2xl font-bold shadow-lg transition-all disabled:opacity-50`}
                    >
                        {processing ? (
                            <>
                                <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                                <span>终止</span>
                            </>
                        ) : (
                            <>
                                <SkipForward className="w-5 h-5" />
                                <span>{currentGame.round === 0 ? '开始游戏' : t.game.nextRound}</span>
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* Main Content: Conversation Only */}
            <div className="space-y-6">
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

                {/* Conversation Log - Prominent */}
                <div>
                    <ConversationLog 
                        history={currentGame.conversation_history}
                        onPossess={handlePossess}
                        thinkingAgent={thinkingAgent}
                    />
                </div>

                {/* Game Over Message - Removed (using modal instead) */}
            </div>

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
                        // TODO: Save to backend settings
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

            {/* Toast Notification - 用于投票开始、淘汰通知 */}
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

import React, { useMemo, useRef, useEffect, useState } from 'react';
import type { ConversationEntry } from '../types/game';
import type { Agent } from '../types/agent';
import { MessageSquare, Brain, Loader2 } from 'lucide-react';
import { generateStableNickname } from '../utils/nicknameGenerator';
import { useGameStore } from '../store/gameStore';
import AgentDetailModal from './AgentDetailModal';

interface ConversationLogProps {
    history: ConversationEntry[];
    onPossess?: (agentId: string) => void;
    thinkingAgent?: {
        agent_id: string;
        agent_name: string;
        index: number;
        total: number;
    } | null;
}

// 生成头像颜色
function getAvatarColor(agentId: string): string {
    let hash = 0;
    for (let i = 0; i < agentId.length; i++) {
        hash = agentId.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    const colors = [
        'bg-blue-500', 'bg-purple-500', 'bg-pink-500', 'bg-red-500',
        'bg-orange-500', 'bg-yellow-500', 'bg-green-500', 'bg-teal-500',
        'bg-cyan-500', 'bg-indigo-500', 'bg-rose-500', 'bg-amber-500',
    ];
    
    return colors[Math.abs(hash) % colors.length];
}

// 获取头像字母
function getAvatarLetter(agentId: string): string {
    // 提取 Agent ID 中的数字或字母
    const match = agentId.match(/Agent\s*(\d+)/i);
    if (match) {
        return match[1];
    }
    return agentId.charAt(0).toUpperCase();
}

const ConversationLog: React.FC<ConversationLogProps> = ({ history, onPossess, thinkingAgent }) => {
    const { currentGame } = useGameStore();
    const scrollRef = useRef<HTMLDivElement>(null);
    const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
    const [showDetailModal, setShowDetailModal] = useState(false);
    
    // 自动滚动到底部
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [history]);
    
    // 生成 agent 昵称映射（仅当没有 LLM 生成的名字时使用）
    const agentNicknames = useMemo(() => {
        if (!currentGame) return {};
        
        const nicknames: Record<string, string> = {};
        currentGame.agents.forEach(agent => {
            // 如果已经有 LLM 生成的名字，就不需要生成昵称
            if (!agent.name) {
                nicknames[agent.id] = generateStableNickname(
                    agent.id,
                    agent.mbti_type,
                    agent.iq_level
                );
            }
        });
        return nicknames;
    }, [currentGame]);
    
    // 获取 agent 信息
    const getAgentInfo = (agentId: string) => {
        if (!currentGame) return null;
        return currentGame.agents.find(a => a.id === agentId);
    };
    
    if (!currentGame) return null;
    
    return (
        <div className="glass-dark rounded-3xl border border-white/10 flex flex-col h-full">
            {/* Header */}
            <div className="p-4 border-b border-white/10 flex items-center justify-between bg-white/5 flex-shrink-0">
                <div className="flex items-center space-x-3">
                    <MessageSquare className="w-5 h-5 text-primary" />
                    <h3 className="font-bold text-lg">群聊对话</h3>
                    {currentGame && currentGame.round > 0 && (
                        <span className="text-sm text-text-muted font-medium bg-white/5 px-3 py-1 rounded-full">
                            第 {currentGame.round} 回合
                        </span>
                    )}
                </div>
                <div className="text-xs text-text-muted font-medium bg-white/5 px-3 py-1 rounded-full">
                    {history.length} 条消息
                </div>
            </div>

            {/* Messages */}
            <div 
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent"
                style={{ maxHeight: 'calc(100vh - 300px)' }}
            >
                {history.length === 0 && !thinkingAgent ? (
                    <div className="h-full flex flex-col items-center justify-center text-text-muted space-y-4">
                        <div className="p-4 bg-white/5 rounded-full">
                            <MessageSquare className="w-8 h-8 opacity-20" />
                        </div>
                        <p className="text-sm">对话尚未开始...</p>
                    </div>
                ) : (
                    <>
                        {history.map((entry, idx) => {
                        // 检查是否是系统消息
                        const isSystemMessage = entry.agent_id === 'system';
                        
                        // 系统消息特殊渲染
                        if (isSystemMessage) {
                            const isVoting = entry.type === 'voting';
                            
                            return (
                                <div
                                    key={`system-${idx}`}
                                    className="flex justify-center my-4 animate-in fade-in slide-in-from-bottom-2 duration-300"
                                >
                                    <div className={`max-w-md w-full rounded-2xl p-4 border ${
                                        isVoting 
                                            ? 'bg-blue-500/10 border-blue-500/30' 
                                            : 'bg-red-500/10 border-red-500/30'
                                    }`}>
                                        <p className={`text-sm font-bold text-center ${
                                            isVoting ? 'text-blue-400' : 'text-red-400'
                                        }`}>
                                            {entry.content}
                                        </p>
                                        {entry.thought && (
                                            <p className="text-xs text-text-muted text-center mt-1">
                                                {entry.thought}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            );
                        }
                        
                        const agent = getAgentInfo(entry.agent_id);
                        // 优先使用 LLM 生成的名字，否则使用昵称生成器，最后使用 agent_id
                        const displayName = agent?.name || agentNicknames[entry.agent_id] || entry.agent_id;
                        const avatarColor = getAvatarColor(entry.agent_id);
                        const avatarLetter = getAvatarLetter(entry.agent_id);
                        const isUser = entry.user_controlled;
                        
                        // 检查是否与上一条消息是同一个 agent
                        const prevEntry = idx > 0 ? history[idx - 1] : null;
                        const isSameAgent = prevEntry?.agent_id === entry.agent_id && !isSystemMessage;
                        const showAvatar = !isSameAgent;
                        
                        return (
                            <div
                                key={`${entry.agent_id}-${entry.round}-${idx}`}
                                className={`flex items-start space-x-3 animate-in fade-in slide-in-from-bottom-2 duration-300 ${
                                    isSameAgent ? 'mt-1' : 'mt-4'
                                }`}
                            >
                                {/* Avatar */}
                                {showAvatar && (
                                    <div 
                                        className={`flex-shrink-0 w-10 h-10 rounded-full ${avatarColor} flex items-center justify-center text-white font-bold text-sm shadow-lg cursor-pointer hover:scale-110 transition-transform relative group`}
                                        onClick={() => {
                                            if (agent) {
                                                setSelectedAgent(agent);
                                                setShowDetailModal(true);
                                            }
                                        }}
                                        title="点击查看详情"
                                    >
                                        {avatarLetter}
                                        {/* Hover tooltip */}
                                        <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-black/80 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
                                            {displayName}
                                        </div>
                                    </div>
                                )}
                                
                                {/* Message Content */}
                                <div className={`flex-1 min-w-0 ${showAvatar ? '' : 'ml-13'}`}>
                                    {/* Nickname and Time */}
                                    {showAvatar && (
                                        <div className="flex items-center space-x-2 mb-1">
                                            <span className={`text-sm font-bold ${
                                                isUser ? 'text-primary' : 'text-text'
                                            }`}>
                                                {displayName}
                                            </span>
                                            {agent && (
                                                <span className="text-[10px] text-text-muted bg-white/5 px-2 py-0.5 rounded">
                                                    {agent.mbti_type} • {agent.iq_level} IQ
                                                </span>
                                            )}
                                            {isUser && (
                                                <span className="text-[10px] font-bold bg-primary/20 text-primary px-1.5 py-0.5 rounded uppercase">
                                                    你
                                                </span>
                                            )}
                                        </div>
                                    )}
                                    
                                    {/* Message Bubble */}
                                    <div className={`inline-block max-w-[85%] rounded-2xl px-4 py-2.5 ${
                                        isUser
                                            ? 'bg-primary/20 border border-primary/30 text-primary'
                                            : 'bg-white/10 border border-white/20 text-text'
                                    }`}>
                                        <p className="text-sm leading-relaxed break-words">
                                            {entry.content}
                                        </p>
                                        
                                        {/* Thought (if exists) */}
                                        {entry.thought && (
                                            <div className="mt-2 pt-2 border-t border-white/10 flex items-start space-x-2">
                                                <Brain className="w-3 h-3 text-accent mt-0.5 flex-shrink-0" />
                                                <p className="text-[11px] text-text-muted italic leading-tight">
                                                    {entry.thought}
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                    
                    {/* 思考中的 Agent */}
                    {thinkingAgent && (
                        <div className="flex items-start space-x-3 animate-in fade-in slide-in-from-bottom-2 duration-300">
                            {/* Avatar */}
                            <div className={`flex-shrink-0 w-10 h-10 rounded-full ${getAvatarColor(thinkingAgent.agent_id)} flex items-center justify-center text-white font-bold text-sm shadow-lg`}>
                                {getAvatarLetter(thinkingAgent.agent_id)}
                            </div>
                            
                            {/* Thinking Content */}
                            <div className="flex-1 min-w-0">
                                {/* Nickname */}
                                <div className="flex items-center space-x-2 mb-1">
                                    <span className="text-sm font-bold text-text">
                                        {thinkingAgent.agent_name}
                                    </span>
                                    <span className="text-[10px] text-text-muted bg-white/5 px-2 py-0.5 rounded">
                                        {thinkingAgent.index} / {thinkingAgent.total}
                                    </span>
                                </div>
                                
                                {/* Thinking Bubble */}
                                <div className="inline-flex items-center space-x-2 bg-white/10 border border-white/20 rounded-2xl px-4 py-2.5">
                                    <Loader2 className="w-4 h-4 text-primary animate-spin" />
                                    <span className="text-sm text-text-muted italic">
                                        正在思考...
                                    </span>
                                </div>
                            </div>
                        </div>
                    )}
                    </>
                )}
            </div>

            {/* Agent Detail Modal */}
            {onPossess && (
                <AgentDetailModal
                    agent={selectedAgent}
                    isOpen={showDetailModal}
                    onClose={() => {
                        setShowDetailModal(false);
                        setSelectedAgent(null);
                    }}
                    onPossess={onPossess}
                />
            )}
        </div>
    );
};

export default ConversationLog;

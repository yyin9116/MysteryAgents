/**
 * 流式显示测试页面
 * 演示实时 Agent 发言功能
 */

import React, { useState } from 'react';
import { streamService, type StreamEvent } from '../services/streamService';
import { Loader2, Play, X } from 'lucide-react';

interface Message {
    agent_id: string;
    agent_name: string;
    speech: string;
    thought: string;
}

const StreamTest: React.FC = () => {
    const [gameId, setGameId] = useState('');
    const [messages, setMessages] = useState<Message[]>([]);
    const [thinkingAgent, setThinkingAgent] = useState<{
        agent_id: string;
        agent_name: string;
        index: number;
        total: number;
    } | null>(null);
    const [isStreaming, setIsStreaming] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [cleanup, setCleanup] = useState<(() => void) | null>(null);

    const handleStart = () => {
        if (!gameId.trim()) {
            setError('请输入游戏 ID');
            return;
        }

        setError(null);
        setMessages([]);
        setThinkingAgent(null);
        setIsStreaming(true);

        const cleanupFn = streamService.startGameStream(
            gameId,
            (event: StreamEvent) => {
                console.log('Stream event:', event);

                switch (event.type) {
                    case 'round_start':
                        console.log('回合开始:', event.round);
                        break;

                    case 'agent_thinking':
                        setThinkingAgent({
                            agent_id: event.agent_id,
                            agent_name: event.agent_name,
                            index: event.index,
                            total: event.total
                        });
                        break;

                    case 'agent_speaking':
                        setMessages(prev => [...prev, {
                            agent_id: event.agent_id,
                            agent_name: event.agent_name,
                            speech: event.speech,
                            thought: event.thought
                        }]);
                        setThinkingAgent(null);
                        break;

                    case 'round_complete':
                        setIsStreaming(false);
                        setThinkingAgent(null);
                        console.log('回合完成');
                        break;

                    case 'error':
                        setError(event.message);
                        setIsStreaming(false);
                        setThinkingAgent(null);
                        break;
                }
            },
            (err) => {
                setError(err.message);
                setIsStreaming(false);
                setThinkingAgent(null);
            }
        );

        setCleanup(() => cleanupFn);
    };

    const handleStop = () => {
        if (cleanup) {
            cleanup();
            setCleanup(null);
        }
        setIsStreaming(false);
        setThinkingAgent(null);
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-background via-background-secondary to-background p-8">
            <div className="max-w-4xl mx-auto space-y-6">
                {/* Header */}
                <div className="glass p-6 rounded-3xl">
                    <h1 className="text-3xl font-black text-primary mb-4">
                        流式显示测试
                    </h1>
                    
                    {/* Input */}
                    <div className="flex gap-4">
                        <input
                            type="text"
                            value={gameId}
                            onChange={(e) => setGameId(e.target.value)}
                            placeholder="输入游戏 ID"
                            className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-text focus:outline-none focus:border-primary/50"
                            disabled={isStreaming}
                        />
                        
                        {!isStreaming ? (
                            <button
                                onClick={handleStart}
                                className="px-6 py-3 bg-primary hover:bg-primary-hover text-white font-bold rounded-xl flex items-center gap-2 transition-all"
                            >
                                <Play className="w-5 h-5" />
                                开始
                            </button>
                        ) : (
                            <button
                                onClick={handleStop}
                                className="px-6 py-3 bg-red-500 hover:bg-red-600 text-white font-bold rounded-xl flex items-center gap-2 transition-all"
                            >
                                <X className="w-5 h-5" />
                                停止
                            </button>
                        )}
                    </div>

                    {/* Error */}
                    {error && (
                        <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400">
                            {error}
                        </div>
                    )}
                </div>

                {/* Messages */}
                <div className="glass p-6 rounded-3xl min-h-[500px]">
                    <h2 className="text-xl font-bold mb-4">对话记录</h2>
                    
                    <div className="space-y-4">
                        {messages.map((msg, idx) => (
                            <div key={idx} className="bg-white/5 p-4 rounded-xl border border-white/10">
                                <div className="flex items-center gap-2 mb-2">
                                    <span className="font-bold text-primary">{msg.agent_name}</span>
                                    <span className="text-xs text-text-muted">({msg.agent_id})</span>
                                </div>
                                <p className="text-text mb-2">{msg.speech}</p>
                                <p className="text-sm text-text-muted italic">💭 {msg.thought}</p>
                            </div>
                        ))}

                        {/* Thinking Agent */}
                        {thinkingAgent && (
                            <div className="bg-primary/10 p-4 rounded-xl border border-primary/20 animate-pulse">
                                <div className="flex items-center gap-3">
                                    <Loader2 className="w-5 h-5 text-primary animate-spin" />
                                    <span className="font-bold text-primary">{thinkingAgent.agent_name}</span>
                                    <span className="text-sm text-text-muted">
                                        正在思考... ({thinkingAgent.index}/{thinkingAgent.total})
                                    </span>
                                </div>
                            </div>
                        )}

                        {messages.length === 0 && !thinkingAgent && (
                            <div className="text-center text-text-muted py-12">
                                输入游戏 ID 并点击开始
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StreamTest;

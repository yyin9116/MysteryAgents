import React from 'react';
import { X, Brain, Cpu, UserCheck, User, Shield, Sparkles } from 'lucide-react';
import type { Agent } from '../types/agent';
import { useSettingsStore } from '../store/settingsStore';
import { useI18n } from '../hooks/useI18n';

interface AgentDetailModalProps {
    agent: Agent | null;
    isOpen: boolean;
    onClose: () => void;
    onPossess: (agentId: string) => void;
}

// MBTI 类型描述
const MBTI_DESCRIPTIONS: Record<string, { name: string; traits: string[] }> = {
    "ENTJ": { name: "指挥官", traits: ["果断", "理性", "有计划", "领导力强"] },
    "INTJ": { name: "建筑师", traits: ["理性", "直觉", "有计划", "战略思维"] },
    "INFP": { name: "调停者", traits: ["感性", "理想主义", "灵活", "富有创造力"] },
    "ENFJ": { name: "主人公", traits: ["外向", "感性", "有计划", "善于沟通"] },
    "INTP": { name: "逻辑学家", traits: ["理性", "直觉", "灵活", "逻辑分析"] },
    "ESTJ": { name: "总经理", traits: ["外向", "理性", "实际", "有计划"] },
    "ISFP": { name: "探险家", traits: ["内向", "感性", "实际", "灵活"] },
    "ENTP": { name: "辩论家", traits: ["外向", "理性", "直觉", "灵活"] },
    "ISFJ": { name: "守护者", traits: ["内向", "感性", "实际", "有计划"] },
    "ESFP": { name: "表演者", traits: ["外向", "感性", "实际", "灵活"] },
    "ESFJ": { name: "执政官", traits: ["外向", "感性", "实际", "有计划"] },
    "ESTP": { name: "企业家", traits: ["外向", "理性", "实际", "灵活"] },
    "INFJ": { name: "提倡者", traits: ["内向", "感性", "直觉", "有计划"] },
    "ENFP": { name: "竞选者", traits: ["外向", "感性", "直觉", "灵活"] },
    "ISTJ": { name: "物流师", traits: ["内向", "理性", "实际", "有计划"] },
    "ISTP": { name: "鉴赏家", traits: ["内向", "理性", "实际", "灵活"] },
};

const AgentDetailModal: React.FC<AgentDetailModalProps> = ({
    agent,
    isOpen,
    onClose,
    onPossess
}) => {
    const { modelConfig } = useSettingsStore();
    const { t } = useI18n();

    if (!isOpen || !agent) return null;

    const mbtiInfo = MBTI_DESCRIPTIONS[agent.mbti_type] || { name: agent.mbti_type, traits: [] };
    
    // 根据全局配置获取模型信息
    const getModelInfo = () => {
        const modelId = modelConfig.model;
        
        if (!modelId) return { name: '未配置', provider: '未知', fullId: '' };
        
        // 解析模型 ID (格式可能是: provider/model-name 或直接是 model-name)
        const parts = modelId.split('/');
        if (parts.length === 2) {
            const provider = parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
            const modelName = parts[1];
            return {
                name: modelName,
                provider: provider,
                fullId: modelId
            };
        }
        
        // 如果没有 provider 前缀，尝试从模型名称推断
        let provider = '未知';
        const modelLower = modelId.toLowerCase();
        if (modelLower.includes('gpt') || modelLower.includes('openai')) {
            provider = 'OpenAI';
        } else if (modelLower.includes('qwen') || modelLower.includes('alibaba')) {
            provider = 'Alibaba';
        } else if (modelLower.includes('claude') || modelLower.includes('anthropic')) {
            provider = 'Anthropic';
        } else if (modelLower.includes('llama') || modelLower.includes('ollama')) {
            provider = 'Ollama';
        }
        
        return { 
            name: modelId, 
            provider: provider,
            fullId: modelId
        };
    };

    const modelInfo = getModelInfo();
    const isDead = !agent.is_alive;
    const canPossess = !isDead && !agent.is_possessed;

    return (
        <div 
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
            onClick={onClose}
        >
            <div 
                className="glass-dark w-full max-w-md rounded-3xl border border-white/10 overflow-hidden shadow-2xl animate-in zoom-in-95 duration-300"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-white/5">
                    <div className="flex items-center space-x-3">
                        <div className={`p-2 rounded-xl ${
                            agent.iq_level === 'High' ? 'bg-primary/20 text-primary' :
                            agent.iq_level === 'Mid' ? 'bg-accent/20 text-accent' :
                            'bg-secondary/20 text-secondary'
                        }`}>
                            <Brain className="w-5 h-5" />
                        </div>
                        <h2 className="text-xl font-bold">Agent 详情</h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-white/10 rounded-xl transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 space-y-6">
                    {/* Basic Info */}
                    <div className="space-y-4">
                        <div className="flex items-center space-x-4">
                            <div className={`w-16 h-16 rounded-full flex items-center justify-center text-white font-bold text-xl shadow-lg ${
                                agent.iq_level === 'High' ? 'bg-primary' :
                                agent.iq_level === 'Mid' ? 'bg-accent' :
                                'bg-secondary'
                            }`}>
                                {agent.name?.[0] || agent.id.replace('agent_', 'A').charAt(0)}
                            </div>
                            <div className="flex-1">
                                <h3 className="text-2xl font-bold mb-1">
                                    {agent.name || agent.id.replace('agent_', 'Agent ')}
                                </h3>
                                <p className="text-sm text-text-muted">
                                    {agent.id}
                                </p>
                            </div>
                        </div>

                        {/* Status Badges */}
                        <div className="flex flex-wrap gap-2">
                            {agent.is_possessed && (
                                <div className="flex items-center space-x-1 text-primary text-xs font-bold bg-primary/20 px-3 py-1.5 rounded-lg">
                                    <UserCheck className="w-3 h-3" />
                                    <span>已夺舍</span>
                                </div>
                            )}
                            {isDead && (
                                <div className="text-secondary text-xs font-bold bg-secondary/20 px-3 py-1.5 rounded-lg">
                                    已淘汰
                                </div>
                            )}
                            {agent.is_alive && !agent.is_possessed && (
                                <div className="text-green-400 text-xs font-bold bg-green-400/20 px-3 py-1.5 rounded-lg">
                                    存活中
                                </div>
                            )}
                        </div>
                    </div>

                    {/* MBTI Personality */}
                    <div className="space-y-3">
                        <div className="flex items-center space-x-2 text-lg font-semibold text-primary">
                            <Sparkles className="w-5 h-5" />
                            <h3>人格信息</h3>
                        </div>
                        <div className="bg-white/5 rounded-2xl p-4 space-y-3 border border-white/10">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-text-muted">MBTI 类型</span>
                                <div className="flex items-center space-x-2">
                                    <span className="font-bold text-lg">{agent.mbti_type}</span>
                                    <span className="text-xs text-text-muted">({mbtiInfo.name})</span>
                                </div>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-text-muted">IQ 级别</span>
                                <span className={`font-bold px-3 py-1 rounded-lg ${
                                    agent.iq_level === 'High' ? 'bg-primary/20 text-primary' :
                                    agent.iq_level === 'Mid' ? 'bg-accent/20 text-accent' :
                                    'bg-secondary/20 text-secondary'
                                }`}>
                                    {agent.iq_level} IQ
                                </span>
                            </div>
                            {mbtiInfo.traits.length > 0 && (
                                <div>
                                    <span className="text-sm text-text-muted block mb-2">性格特征</span>
                                    <div className="flex flex-wrap gap-2">
                                        {mbtiInfo.traits.map((trait, idx) => (
                                            <span
                                                key={idx}
                                                className="text-xs bg-white/5 px-2 py-1 rounded-lg border border-white/10"
                                            >
                                                {trait}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Model Information */}
                    <div className="space-y-3">
                        <div className="flex items-center space-x-2 text-lg font-semibold text-accent">
                            <Cpu className="w-5 h-5" />
                            <h3>模型信息</h3>
                        </div>
                        <div className="bg-white/5 rounded-2xl p-4 space-y-3 border border-white/10">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-text-muted">使用的模型</span>
                                <span className="font-bold text-right max-w-[60%] truncate" title={modelInfo.fullId}>
                                    {modelInfo.name}
                                </span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-text-muted">提供商</span>
                                <span className="text-sm font-medium">{modelInfo.provider}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-text-muted">适用 IQ 级别</span>
                                <span className={`text-sm font-medium px-2 py-0.5 rounded ${
                                    agent.iq_level === 'High' ? 'bg-primary/20 text-primary' :
                                    agent.iq_level === 'Mid' ? 'bg-accent/20 text-accent' :
                                    'bg-secondary/20 text-secondary'
                                }`}>
                                    {agent.iq_level}
                                </span>
                            </div>
                            {modelInfo.fullId && (
                                <div className="pt-2 border-t border-white/10">
                                    <span className="text-xs text-text-muted">模型 ID: </span>
                                    <span className="text-xs font-mono text-text-muted/80">{modelInfo.fullId}</span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Game Info */}
                    {agent.role && (
                        <div className="space-y-3">
                            <div className="flex items-center space-x-2 text-lg font-semibold text-secondary">
                                <Shield className="w-5 h-5" />
                                <h3>游戏信息</h3>
                            </div>
                            <div className="bg-white/5 rounded-2xl p-4 space-y-3 border border-white/10">
                                <div className="flex items-center justify-between">
                                    <span className="text-sm text-text-muted">角色</span>
                                    <span className={`font-bold px-3 py-1 rounded-lg ${
                                        agent.role === 'Undercover' 
                                            ? 'bg-red-500/20 text-red-400' 
                                            : 'bg-blue-500/20 text-blue-400'
                                    }`}>
                                        {agent.role === 'Undercover' ? '卧底' : '平民'}
                                    </span>
                                </div>
                                {agent.word && (
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-text-muted">词汇</span>
                                        <span className="font-bold text-primary">{agent.word}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Action Button */}
                    {canPossess && (
                        <button
                            onClick={() => {
                                onPossess(agent.id);
                                onClose();
                            }}
                            className="w-full py-3 rounded-xl bg-primary hover:bg-primary/90 text-white font-bold flex items-center justify-center space-x-2 transition-all shadow-lg shadow-primary/20"
                        >
                            <User className="w-5 h-5" />
                            <span>{t.game.possess}</span>
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AgentDetailModal;

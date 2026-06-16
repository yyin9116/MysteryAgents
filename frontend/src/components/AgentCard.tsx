import React, { useState } from 'react';
import type { Agent } from '../types/agent';
import { Brain, UserCheck } from 'lucide-react';
import { useI18n } from '../hooks/useI18n';
import AgentDetailModal from './AgentDetailModal';

interface AgentCardProps {
    agent: Agent;
    onPossess: (agentId: string) => void;
}

const AgentCard: React.FC<AgentCardProps> = ({ agent, onPossess }) => {
    const isDead = !agent.is_alive;
    const { t } = useI18n();
    const [showDetailModal, setShowDetailModal] = useState(false);

    return (
        <>
            <div 
                className={`relative overflow-hidden group transition-all duration-300 ${isDead ? 'grayscale opacity-60' : 'hover:-translate-y-1 cursor-pointer'
                    }`}
                onClick={() => setShowDetailModal(true)}
            >
                <div className={`glass-dark p-5 rounded-3xl border ${agent.is_possessed ? 'border-primary ring-2 ring-primary/20' : 'border-white/10'
                    }`}>
                    <div className="flex items-start justify-between mb-4">
                        <div 
                            className={`p-3 rounded-2xl cursor-pointer hover:scale-110 transition-transform ${agent.iq_level === 'High' ? 'bg-primary/20 text-primary' :
                                agent.iq_level === 'Mid' ? 'bg-accent/20 text-accent' :
                                    'bg-secondary/20 text-secondary'
                                }`}
                            onClick={(e) => {
                                e.stopPropagation();
                                setShowDetailModal(true);
                            }}
                            title="点击查看详情"
                        >
                            <Brain className="w-6 h-6" />
                        </div>
                    <div className="flex flex-col items-end">
                        <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
                            {agent.mbti_type}
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full mt-1 ${agent.iq_level === 'High' ? 'bg-primary/10 text-primary border border-primary/20' :
                            agent.iq_level === 'Mid' ? 'bg-accent/10 text-accent border border-accent/20' :
                                'bg-secondary/10 text-secondary border border-secondary/20'
                            }`}>
                            {agent.iq_level} IQ
                        </span>
                    </div>
                </div>

                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <h4 className="font-bold text-lg">
                            {agent.name || agent.id.replace('agent_', 'Agent ')}
                        </h4>
                        {agent.is_possessed && (
                            <div className="flex items-center space-x-1 text-primary text-xs font-bold bg-primary/10 px-2 py-1 rounded-lg">
                                <UserCheck className="w-3 h-3" />
                                <span>{t.game.possessed.toUpperCase()}</span>
                            </div>
                        )}
                    </div>

                    <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                        <div
                            className="bg-primary h-full transition-all duration-500"
                            style={{ width: `${agent.is_alive ? 100 : 0}%` }}
                        />
                    </div>

                    {!isDead && !agent.is_possessed && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onPossess(agent.id);
                            }}
                            className="w-full mt-2 py-2 rounded-xl bg-white/5 border border-white/10 text-xs font-semibold hover:bg-primary/20 hover:border-primary/30 transition-all opacity-0 group-hover:opacity-100"
                        >
                            {t.game.possess}
                        </button>
                    )}

                    {isDead && (
                        <div className="mt-2 text-center py-2 text-xs font-bold text-secondary tracking-widest uppercase">
                            {t.game.elimination}
                        </div>
                    )}
                </div>
            </div>

            {/* Suspicion Heat Indicator */}
            {agent.is_alive && (
                <div className="absolute top-2 right-2 flex space-x-1">
                    {[1, 2, 3].map((i) => (
                        <div
                            key={i}
                            className={`w-1 h-1 rounded-full ${(Object.values(agent.suspicion_scores) as number[]).some(s => s > 7) && i === 3 ? 'bg-secondary animate-pulse' :
                                (Object.values(agent.suspicion_scores) as number[]).some(s => s > 4) && i <= 2 ? 'bg-yellow-500' :
                                    'bg-white/10'
                                }`}
                        />
                    ))}
                </div>
            )}
        </div>

        {/* Agent Detail Modal */}
        <AgentDetailModal
            agent={agent}
            isOpen={showDetailModal}
            onClose={() => setShowDetailModal(false)}
            onPossess={onPossess}
        />
        </>
    );
};

export default AgentCard;

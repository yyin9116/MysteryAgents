import React, { useState } from 'react';
import type { Agent } from '../types/agent';
import { X, Send, UserX, AlertTriangle, Zap } from 'lucide-react';
import { useI18n } from '../hooks/useI18n';

interface PossessionModalProps {
    agent: Agent;
    onClose: () => void;
    onSubmit: (speech: string, suspicion: Record<string, number>) => void;
    onRelease: () => void;
    loading: boolean;
}

const PossessionModal: React.FC<PossessionModalProps> = ({ agent, onClose, onSubmit, onRelease, loading }) => {
    const [speech, setSpeech] = useState('');
    const [suspicion, setSuspicion] = useState<Record<string, number>>(agent.suspicion_scores || {});
    const { t, language } = useI18n();

    const handleSuspicionChange = (targetId: string, value: number) => {
        setSuspicion(prev => ({ ...prev, [targetId]: value }));
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
            <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={onClose} />

            <div className="relative glass-dark w-full max-w-2xl rounded-[2rem] border border-white/10 shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
                <div className="p-6 border-b border-white/5 flex items-center justify-between bg-primary/10">
                    <div className="flex items-center space-x-3">
                        <Zap className="w-5 h-5 text-primary fill-primary" />
                        <h3 className="text-xl font-bold">{t.game.possess} {agent.id.replace('agent_', 'Agent ')}</h3>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-8 space-y-8 max-h-[70vh] overflow-y-auto">
                    {/* Secrets Section */}
                    <div className="grid grid-cols-2 gap-4">
                        <div className="bg-primary/5 p-4 rounded-2xl border border-primary/10">
                            <span className="text-[10px] font-bold text-primary uppercase tracking-widest">
                                {language === 'en' ? 'Your Assigned Word' : '分配给你的词汇'}
                            </span>
                            <p className="text-2xl font-black text-text mt-1">{agent.word || '???'}</p>
                        </div>
                        <div className="bg-secondary/5 p-4 rounded-2xl border border-secondary/10">
                            <span className="text-[10px] font-bold text-secondary uppercase tracking-widest">
                                {language === 'en' ? 'Secret Role' : '你的身份角色'}
                            </span>
                            <p className="text-2xl font-black text-text mt-1">{agent.role || '???'}</p>
                        </div>
                    </div>

                    {/* User Input Section */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between px-1">
                            <label className="text-sm font-bold text-text-muted uppercase">
                                {t.game.description}
                            </label>
                            <span className="text-[10px] text-text-muted italic">
                                {language === 'en' ? 'Describe your word without giving it away' : '描述你的词汇，但不要直接说出它'}
                            </span>
                        </div>
                        <textarea
                            value={speech}
                            onChange={(e) => setSpeech(e.target.value)}
                            placeholder={language === 'en' ? 'Type your description here...' : '在此输入你的描述...'}
                            className="w-full h-32 bg-white/5 border border-white/10 rounded-2xl p-4 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all text-text resize-none"
                        />
                    </div>

                    {/* Suspicion Sliders */}
                    <div className="space-y-4">
                        <h4 className="text-sm font-bold text-text-muted uppercase px-1">{t.game.suspicion}</h4>
                        <div className="space-y-3">
                            {Object.entries(suspicion).map(([targetId, score]) => (
                                <div key={targetId} className="flex items-center space-x-4 bg-white/5 p-3 rounded-xl border border-white/5">
                                    <span className="text-xs font-bold w-20 uppercase">{targetId.replace('_', ' ')}</span>
                                    <input
                                        type="range"
                                        min="0"
                                        max="10"
                                        value={score}
                                        onChange={(e) => handleSuspicionChange(targetId, parseInt(e.target.value))}
                                        className="flex-1 accent-primary h-1.5"
                                    />
                                    <span className={`text-xs font-bold w-6 text-center ${score > 7 ? 'text-secondary' : 'text-primary'}`}>
                                        {score}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="bg-yellow-500/10 border border-yellow-500/20 p-4 rounded-2xl flex items-start space-x-3">
                        <AlertTriangle className="w-5 h-5 text-yellow-500 shrink-0" />
                        <p className="text-xs text-yellow-200/80 leading-relaxed">
                            <strong>{language === 'en' ? 'Caution:' : '提示：'}</strong> {language === 'en'
                                ? "While possessed, your actions directly affect the Agent's survival. Be strategic to avoid being voted out by other AI agents."
                                : "在夺舍期间，你的行动将直接影响 Agent 的生死。请运用策略，避免被其他 AI Agent 投票出局。"}
                        </p>
                    </div>
                </div>

                <div className="p-6 bg-white/5 border-t border-white/5 flex gap-4">
                    <button
                        onClick={onRelease}
                        disabled={loading}
                        className="flex-1 flex items-center justify-center space-x-2 py-4 rounded-2xl bg-white/5 border border-white/10 font-bold text-text-muted hover:bg-secondary/10 hover:text-secondary hover:border-secondary/30 transition-all disabled:opacity-50"
                    >
                        <UserX className="w-5 h-5" />
                        <span>{language === 'en' ? 'Release Control' : '放弃夺舍'}</span>
                    </button>
                    <button
                        onClick={() => onSubmit(speech, suspicion)}
                        disabled={loading || !speech.trim()}
                        className="flex-[2] flex items-center justify-center space-x-2 py-4 rounded-2xl bg-primary text-white font-bold shadow-lg shadow-primary/20 hover:bg-primary/90 transition-all disabled:opacity-50"
                    >
                        {loading ? (
                            <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                        ) : (
                            <>
                                <Send className="w-5 h-5" />
                                <span>{language === 'en' ? 'Submit Statement' : '提交描述'}</span>
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default PossessionModal;

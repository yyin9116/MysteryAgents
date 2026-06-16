/**
 * System Message Modal Component
 * 
 * 显示系统级消息（投票、淘汰、违规等），需要用户确认才能继续游戏
 */

import React from 'react';
import { X, Ban } from 'lucide-react';

interface SystemMessageModalProps {
    isOpen: boolean;
    title: string;
    message: string;
    data?: any;
    onConfirm: () => void;
    onClose: () => void;
}

const SystemMessageModal: React.FC<SystemMessageModalProps> = ({
    isOpen,
    title,
    message,
    data,
    onConfirm,
    onClose
}) => {
    if (!isOpen) return null;

    // 违规类型的图标和颜色
    const config = {
        icon: <Ban className="w-12 h-12" />,
        bgColor: 'bg-orange-500/20',
        borderColor: 'border-orange-500/30',
        iconColor: 'text-orange-400'
    };



    return (
        <div 
            className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={(e) => {
                // 点击背景不关闭
                e.stopPropagation();
            }}
        >
            <div 
                className="bg-slate-900 rounded-2xl border border-white/10 max-w-lg w-full shadow-2xl animate-in fade-in zoom-in duration-300"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className={`p-6 border-b border-white/10 ${config.bgColor} ${config.borderColor}`}>
                    <div className="flex items-center gap-4">
                        <div className={`p-3 rounded-xl ${config.bgColor} ${config.iconColor}`}>
                            {config.icon}
                        </div>
                        <div className="flex-1">
                            <h2 className="text-2xl font-bold text-white">{title}</h2>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/10 rounded-lg transition-colors text-white/70 hover:text-white"
                        >
                            <X size={24} />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6">
                    <p className="text-lg text-white/90 leading-relaxed whitespace-pre-wrap">
                        {message}
                    </p>

                    {/* 违规详情 */}
                    {data && (
                        <div className="mt-4 p-4 bg-orange-500/10 rounded-xl border border-orange-500/20">
                            <h3 className="text-sm font-semibold text-orange-400 mb-2">违规详情</h3>
                            <div className="space-y-2 text-sm text-white/70">
                                {data.duplicate_agent_id && (
                                    <p>重复了 <span className="text-orange-400">{data.duplicate_agent_id}</span> 的发言</p>
                                )}
                                {data.duplicate_speech && (
                                    <p className="mt-2">
                                        <span className="text-white/50">原发言：</span>
                                        <span className="text-white/80 italic">"{data.duplicate_speech}"</span>
                                    </p>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-white/10 bg-white/5 flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        className="px-6 py-3 rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors"
                    >
                        关闭
                    </button>
                    <button
                        onClick={onConfirm}
                        className="px-6 py-3 rounded-xl bg-primary hover:bg-primary/90 text-white font-medium transition-colors"
                    >
                        确认
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SystemMessageModal;

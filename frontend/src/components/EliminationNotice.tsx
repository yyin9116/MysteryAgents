import React, { useEffect, useState } from 'react';
import { Skull } from 'lucide-react';

interface EliminationNoticeProps {
    eliminatedName: string;
    eliminatedRole: string;
    eliminatedWord: string;
    voteCount: number;
    onComplete: () => void;
}

const EliminationNotice: React.FC<EliminationNoticeProps> = ({
    eliminatedName,
    eliminatedRole,
    eliminatedWord,
    voteCount,
    onComplete
}) => {
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        // 淡入动画
        setTimeout(() => setVisible(true), 100);
        
        // 5秒后自动关闭（增加显示时间）
        const timer = setTimeout(() => {
            setVisible(false);
            setTimeout(onComplete, 300);
        }, 5000);

        return () => clearTimeout(timer);
    }, [onComplete]);

    return (
        <div className={`fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm transition-opacity duration-300 ${
            visible ? 'opacity-100' : 'opacity-0'
        }`}>
            <div className={`glass-dark border-2 border-red-500/50 rounded-3xl p-8 max-w-md w-full mx-4 transform transition-all duration-500 ${
                visible ? 'scale-100 rotate-0' : 'scale-75 rotate-12'
            }`}>
                {/* Skull Icon */}
                <div className="flex justify-center mb-6">
                    <div className="p-4 bg-red-500/20 rounded-full animate-pulse">
                        <Skull className="w-16 h-16 text-red-500" />
                    </div>
                </div>

                {/* Title */}
                <h2 className="text-3xl font-black text-center mb-4 text-red-500 uppercase tracking-tight">
                    淘汰
                </h2>

                {/* Eliminated Agent Info */}
                <div className="space-y-3 mb-6">
                    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                        <p className="text-sm text-text-muted mb-1">被淘汰者</p>
                        <p className="text-2xl font-bold text-text">{eliminatedName}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                            <p className="text-xs text-text-muted mb-1">角色</p>
                            <p className="text-lg font-bold text-primary">{eliminatedRole}</p>
                        </div>
                        <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                            <p className="text-xs text-text-muted mb-1">词汇</p>
                            <p className="text-lg font-bold text-accent">{eliminatedWord}</p>
                        </div>
                    </div>

                    <div className="bg-red-500/10 rounded-xl p-3 border border-red-500/30">
                        <p className="text-xs text-text-muted mb-1">得票数</p>
                        <p className="text-xl font-black text-red-500">{voteCount} 票</p>
                    </div>
                </div>

                {/* Auto-close indicator */}
                <div className="flex items-center justify-center space-x-2 text-xs text-text-muted">
                    <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                    <span>自动关闭中...</span>
                </div>
            </div>
        </div>
    );
};

export default EliminationNotice;

import React from 'react';
import { Trophy, Skull, RotateCcw, Home } from 'lucide-react';

interface GameOverModalProps {
    isOpen: boolean;
    result: 'undercover_win' | 'civilian_win' | 'draw';
    message: string;
    onRestart: () => void;
    onHome: () => void;
}

const GameOverModal: React.FC<GameOverModalProps> = ({
    isOpen,
    result,
    message,
    onRestart,
    onHome
}) => {
    if (!isOpen) return null;

    const isWin = result === 'civilian_win';
    const isDraw = result === 'draw';

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md animate-in fade-in duration-500">
            <div className="glass-dark border-2 border-primary/50 rounded-3xl p-10 max-w-lg w-full mx-4 animate-in zoom-in-95 duration-500">
                {/* Icon */}
                <div className="flex justify-center mb-6">
                    <div className={`p-6 rounded-full ${
                        isWin ? 'bg-green-500/20' : isDraw ? 'bg-yellow-500/20' : 'bg-red-500/20'
                    } animate-pulse`}>
                        {isWin ? (
                            <Trophy className="w-20 h-20 text-green-500" />
                        ) : isDraw ? (
                            <Skull className="w-20 h-20 text-yellow-500" />
                        ) : (
                            <Skull className="w-20 h-20 text-red-500" />
                        )}
                    </div>
                </div>

                {/* Title */}
                <h2 className={`text-4xl font-black text-center mb-4 uppercase tracking-tight ${
                    isWin ? 'text-green-500' : isDraw ? 'text-yellow-500' : 'text-red-500'
                }`}>
                    {isWin ? '平民胜利' : isDraw ? '平局' : '卧底胜利'}
                </h2>

                {/* Message */}
                <p className="text-center text-lg text-text mb-8 leading-relaxed">
                    {message}
                </p>

                {/* Result Badge */}
                <div className="bg-white/5 rounded-2xl p-4 mb-8 border border-white/10">
                    <div className="flex items-center justify-center space-x-2">
                        <div className={`w-3 h-3 rounded-full ${
                            isWin ? 'bg-green-500' : isDraw ? 'bg-yellow-500' : 'bg-red-500'
                        } animate-pulse`} />
                        <span className="text-sm font-bold text-text-muted uppercase tracking-wider">
                            游戏结束
                        </span>
                    </div>
                </div>

                {/* Actions */}
                <div className="flex flex-col sm:flex-row gap-3">
                    <button
                        onClick={onRestart}
                        className="flex-1 flex items-center justify-center space-x-2 bg-primary hover:bg-primary/90 text-white px-6 py-4 rounded-2xl font-bold shadow-lg shadow-primary/20 transition-all hover:scale-105"
                    >
                        <RotateCcw className="w-5 h-5" />
                        <span>重新开始</span>
                    </button>
                    <button
                        onClick={onHome}
                        className="flex-1 flex items-center justify-center space-x-2 bg-white/10 hover:bg-white/20 text-text px-6 py-4 rounded-2xl font-bold border border-white/20 transition-all hover:scale-105"
                    >
                        <Home className="w-5 h-5" />
                        <span>返回主页</span>
                    </button>
                </div>
            </div>
        </div>
    );
};

export default GameOverModal;

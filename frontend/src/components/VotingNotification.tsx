import React from 'react';
import { Vote, TrendingUp } from 'lucide-react';

interface VotingNotificationProps {
    voterName: string;
    votedForName: string;
    confidence: number;
    index: number;
    total: number;
}

const VotingNotification: React.FC<VotingNotificationProps> = ({
    voterName,
    votedForName,
    confidence,
    index,
    total
}) => {
    return (
        <div className="animate-in slide-in-from-bottom-4 duration-500">
            <div className="glass-dark border border-primary/30 rounded-2xl p-4 mb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                        <div className="p-2 bg-primary/20 rounded-full">
                            <Vote className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <p className="text-sm font-bold text-text">
                                {voterName} <span className="text-text-muted">投票给</span> {votedForName}
                            </p>
                            <div className="flex items-center space-x-2 mt-1">
                                <TrendingUp className="w-3 h-3 text-accent" />
                                <p className="text-xs text-text-muted">
                                    置信度: {(confidence * 100).toFixed(0)}%
                                </p>
                            </div>
                        </div>
                    </div>
                    <div className="text-xs text-text-muted bg-white/5 px-3 py-1 rounded-full">
                        {index}/{total}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default VotingNotification;

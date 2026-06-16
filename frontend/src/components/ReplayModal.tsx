import React, { useState, useEffect } from 'react';
import { Play, Pause, SkipBack, SkipForward, ChevronsLeft, ChevronsRight, X, Download, User } from 'lucide-react';
import { replayService } from '../services/replayService';
import type { ReplayEvent, ReplayProgress } from '../services/replayService';

interface ReplayModalProps {
    isOpen: boolean;
    onClose: () => void;
    snapshotId: string;
}

const ReplayModal: React.FC<ReplayModalProps> = ({
    isOpen,
    onClose,
    snapshotId
}) => {
    const [loading, setLoading] = useState(false);
    const [playing, setPlaying] = useState(false);
    const [currentEvent, setCurrentEvent] = useState<ReplayEvent | null>(null);
    const [progress, setProgress] = useState<ReplayProgress>({ active: false });
    const [playbackSpeed, setPlaybackSpeed] = useState(1);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen && snapshotId) {
            initializeReplay();
        }
        return () => {
            if (isOpen) {
                handleStop();
            }
        };
    }, [isOpen, snapshotId]);

    useEffect(() => {
        let interval: ReturnType<typeof setInterval>;
        if (playing && progress.active && !progress.at_end) {
            interval = setInterval(() => {
                handleStepForward();
            }, 1000 / playbackSpeed);
        }
        return () => clearInterval(interval);
    }, [playing, playbackSpeed, progress]);

    const initializeReplay = async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await replayService.startReplay(snapshotId);
            setProgress({
                active: true,
                current_index: result.current_index,
                total_events: result.total_events,
                total_rounds: result.total_rounds,
                progress_percentage: 0,
                at_start: true,
                at_end: false
            });
            // Load first event
            await handleStepForward();
        } catch (err: any) {
            setError(err.response?.data?.detail || '初始化回放失败');
        } finally {
            setLoading(false);
        }
    };

    const handleStepForward = async () => {
        try {
            const result = await replayService.stepForward();
            if (result.status === 'end_reached') {
                setPlaying(false);
                return;
            }
            if (result.event) {
                setCurrentEvent(result.event);
            }
            if (result.progress) {
                setProgress(result.progress);
            }
        } catch (err: any) {
            setError('前进失败');
            setPlaying(false);
        }
    };

    const handleStepBackward = async () => {
        setPlaying(false);
        try {
            const result = await replayService.stepBackward();
            if (result.status === 'start_reached') {
                return;
            }
            if (result.event) {
                setCurrentEvent(result.event);
            }
            if (result.progress) {
                setProgress(result.progress);
            }
        } catch (err: any) {
            setError('后退失败');
        }
    };

    const handleJumpToRound = async (roundNum: number) => {
        setPlaying(false);
        try {
            const result = await replayService.jumpToRound(roundNum);
            if (result.events.length > 0) {
                setCurrentEvent(result.events[0]);
            }
            setProgress(result.progress);
        } catch (err: any) {
            setError(`跳转到第${roundNum}回合失败`);
        }
    };

    const handleStop = async () => {
        setPlaying(false);
        try {
            await replayService.stopReplay();
        } catch (err) {
            // Ignore errors on stop
        }
    };

    const handleExport = async () => {
        try {
            const data = await replayService.exportReplay();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `replay_${snapshotId}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (err: any) {
            setError('导出失败');
        }
    };

    const renderEventContent = () => {
        if (!currentEvent) {
            return (
                <div className="text-center py-12 text-text-muted">
                    <Play className="w-16 h-16 mx-auto mb-4 opacity-50" />
                    <p>点击播放开始回放</p>
                </div>
            );
        }

        if (currentEvent.event_type === 'description') {
            return (
                <div className="space-y-4">
                    <div className="flex items-center gap-3">
                        <div className="p-3 bg-primary/20 rounded-xl">
                            <User className="w-6 h-6 text-primary" />
                        </div>
                        <div>
                            <div className="font-bold text-lg">{currentEvent.data.agent_id}</div>
                            <div className="text-sm text-text-muted">第 {currentEvent.round_num} 回合 - 描述阶段</div>
                        </div>
                    </div>

                    <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                        <div className="text-sm text-text-muted mb-2">💭 内心想法</div>
                        <div className="text-text">{currentEvent.data.thought}</div>
                    </div>

                    <div className="p-4 rounded-xl bg-primary/10 border border-primary/20">
                        <div className="text-sm text-primary mb-2">💬 公开发言</div>
                        <div className="text-lg font-medium">{currentEvent.data.speech}</div>
                    </div>

                    {currentEvent.data.suspicion && Object.keys(currentEvent.data.suspicion).length > 0 && (
                        <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                            <div className="text-sm text-text-muted mb-3">🔍 怀疑度</div>
                            <div className="space-y-2">
                                {Object.entries(currentEvent.data.suspicion).map(([agentId, score]: [string, any]) => (
                                    <div key={agentId} className="flex items-center justify-between">
                                        <span className="text-sm">{agentId}</span>
                                        <div className="flex items-center gap-2">
                                            <div className="w-32 h-2 bg-white/10 rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-secondary rounded-full transition-all"
                                                    style={{ width: `${(score / 10) * 100}%` }}
                                                />
                                            </div>
                                            <span className="text-sm font-medium w-8 text-right">{score}/10</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            );
        }

        if (currentEvent.event_type === 'elimination') {
            return (
                <div className="space-y-4">
                    <div className="flex items-center gap-3">
                        <div className="p-3 bg-red-500/20 rounded-xl">
                            <X className="w-6 h-6 text-red-500" />
                        </div>
                        <div>
                            <div className="font-bold text-lg text-red-400">淘汰事件</div>
                            <div className="text-sm text-text-muted">第 {currentEvent.round_num} 回合</div>
                        </div>
                    </div>

                    <div className="p-6 rounded-xl bg-red-500/10 border border-red-500/20 text-center">
                        <div className="text-2xl font-bold mb-2">{currentEvent.data.eliminated_id}</div>
                        <div className="text-red-400 mb-4">被投票淘汰</div>
                        <div className="flex items-center justify-center gap-4 text-sm">
                            <div>
                                <span className="text-text-muted">词汇: </span>
                                <span className="font-medium">{currentEvent.data.eliminated_word}</span>
                            </div>
                            <div>
                                <span className="text-text-muted">身份: </span>
                                <span className={`font-medium ${
                                    currentEvent.data.eliminated_role === 'Undercover' ? 'text-red-400' : 'text-green-400'
                                }`}>
                                    {currentEvent.data.eliminated_role === 'Undercover' ? '卧底' : '平民'}
                                </span>
                            </div>
                        </div>
                    </div>

                    {currentEvent.data.vote_details && currentEvent.data.vote_details.length > 0 && (
                        <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                            <div className="text-sm text-text-muted mb-3">📊 投票详情</div>
                            <div className="space-y-2">
                                {currentEvent.data.vote_details.map((vote: any, i: number) => (
                                    <div key={i} className="flex items-center justify-between text-sm">
                                        <span>{vote.voter}</span>
                                        <span className="text-text-muted">→</span>
                                        <span className="font-medium">{vote.voted_for}</span>
                                        <span className="text-xs text-text-muted">
                                            ({Math.round(vote.confidence * 100)}% 确信)
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            );
        }

        return null;
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-900 rounded-3xl border border-white/10 max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-white/10">
                    <div>
                        <h2 className="text-2xl font-bold">游戏回放</h2>
                        {progress.active && (
                            <p className="text-sm text-text-muted mt-1">
                                第 {progress.current_round} 回合 · {progress.current_index}/{progress.total_events} 事件
                            </p>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleExport}
                            className="p-2 hover:bg-white/10 rounded-xl transition-colors"
                            title="导出回放数据"
                        >
                            <Download className="w-5 h-5" />
                        </button>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/10 rounded-xl transition-colors"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                {/* Progress Bar */}
                {progress.active && (
                    <div className="px-6 pt-4">
                        <div className="relative">
                            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-primary rounded-full transition-all duration-300"
                                    style={{ width: `${progress.progress_percentage}%` }}
                                />
                            </div>
                            <div className="flex justify-between mt-2 text-xs text-text-muted">
                                <span>开始</span>
                                <span>{progress.progress_percentage?.toFixed(1)}%</span>
                                <span>结束</span>
                            </div>
                        </div>
                    </div>
                )}

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {loading ? (
                        <div className="text-center py-12">
                            <div className="w-12 h-12 border-4 border-white/10 border-t-primary rounded-full animate-spin mx-auto mb-4" />
                            <p className="text-text-muted">加载回放...</p>
                        </div>
                    ) : error ? (
                        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400">
                            {error}
                        </div>
                    ) : (
                        renderEventContent()
                    )}
                </div>

                {/* Controls */}
                <div className="border-t border-white/10 p-6 space-y-4">
                    {/* Playback Controls */}
                    <div className="flex items-center justify-center gap-3">
                        <button
                            onClick={() => handleJumpToRound(1)}
                            disabled={loading || progress.at_start}
                            className="p-3 rounded-xl bg-white/5 hover:bg-white/10 disabled:opacity-30 transition-colors"
                            title="跳到开始"
                        >
                            <ChevronsLeft className="w-5 h-5" />
                        </button>
                        <button
                            onClick={handleStepBackward}
                            disabled={loading || progress.at_start}
                            className="p-3 rounded-xl bg-white/5 hover:bg-white/10 disabled:opacity-30 transition-colors"
                            title="上一个事件"
                        >
                            <SkipBack className="w-5 h-5" />
                        </button>
                        <button
                            onClick={() => setPlaying(!playing)}
                            disabled={loading || progress.at_end}
                            className="p-4 rounded-xl bg-primary hover:bg-primary/90 disabled:opacity-30 transition-colors"
                            title={playing ? '暂停' : '播放'}
                        >
                            {playing ? (
                                <Pause className="w-6 h-6" />
                            ) : (
                                <Play className="w-6 h-6" />
                            )}
                        </button>
                        <button
                            onClick={handleStepForward}
                            disabled={loading || progress.at_end}
                            className="p-3 rounded-xl bg-white/5 hover:bg-white/10 disabled:opacity-30 transition-colors"
                            title="下一个事件"
                        >
                            <SkipForward className="w-5 h-5" />
                        </button>
                        <button
                            onClick={() => progress.total_rounds && handleJumpToRound(progress.total_rounds)}
                            disabled={loading || progress.at_end}
                            className="p-3 rounded-xl bg-white/5 hover:bg-white/10 disabled:opacity-30 transition-colors"
                            title="跳到结束"
                        >
                            <ChevronsRight className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Speed Control */}
                    <div className="flex items-center justify-center gap-4">
                        <span className="text-sm text-text-muted">播放速度:</span>
                        {[0.5, 1, 1.5, 2].map(speed => (
                            <button
                                key={speed}
                                onClick={() => setPlaybackSpeed(speed)}
                                className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                                    playbackSpeed === speed
                                        ? 'bg-primary text-white'
                                        : 'bg-white/5 hover:bg-white/10'
                                }`}
                            >
                                {speed}x
                            </button>
                        ))}
                    </div>

                    {/* Round Jump */}
                    {progress.total_rounds && progress.total_rounds > 1 && (
                        <div className="flex items-center justify-center gap-2">
                            <span className="text-sm text-text-muted">跳转到回合:</span>
                            <select
                                value={progress.current_round || 1}
                                onChange={(e) => handleJumpToRound(parseInt(e.target.value))}
                                className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                            >
                                {Array.from({ length: progress.total_rounds }, (_, i) => i + 1).map(round => (
                                    <option key={round} value={round}>第 {round} 回合</option>
                                ))}
                            </select>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ReplayModal;

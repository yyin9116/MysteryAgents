import React, { useState, useEffect } from 'react';
import { Save, FolderOpen, Trash2, Clock, Users, X, AlertCircle, Play } from 'lucide-react';
import { gameService } from '../services/gameService';
import ReplayModal from './ReplayModal';

interface Snapshot {
    snapshot_id: string;
    game_id: string;
    timestamp: string;
    round: number;
    phase: string;
    agent_count: number;
    alive_count: number;
    snapshot_type: 'manual' | 'checkpoint' | 'auto';
}

interface SaveLoadModalProps {
    isOpen: boolean;
    onClose: () => void;
    gameId: string;
    onLoadSuccess?: (gameId: string) => void;
}

const SaveLoadModal: React.FC<SaveLoadModalProps> = ({
    isOpen,
    onClose,
    gameId,
    onLoadSuccess
}) => {
    const [activeTab, setActiveTab] = useState<'save' | 'load'>('save');
    const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [snapshotName, setSnapshotName] = useState('');
    const [showReplay, setShowReplay] = useState(false);
    const [replaySnapshotId, setReplaySnapshotId] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen && activeTab === 'load') {
            loadSnapshots();
        }
    }, [isOpen, activeTab]);

    const loadSnapshots = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await gameService.listSnapshots(gameId);
            setSnapshots(response.snapshots || []);
        } catch (err: any) {
            setError('加载存档列表失败');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setLoading(true);
        setError(null);
        setSuccess(null);

        try {
            await gameService.saveGame(gameId, snapshotName || undefined);
            setSuccess('游戏已保存！');
            setSnapshotName('');
            setTimeout(() => {
                setActiveTab('load');
                loadSnapshots();
            }, 1000);
        } catch (err: any) {
            setError(err.response?.data?.detail || '保存失败');
        } finally {
            setLoading(false);
        }
    };

    const handleLoad = async (snapshotId: string) => {
        setLoading(true);
        setError(null);

        try {
            const result = await gameService.loadGame(snapshotId);
            setSuccess('游戏已加载！');
            setTimeout(() => {
                onLoadSuccess?.(result.game_id);
                onClose();
            }, 1000);
        } catch (err: any) {
            setError(err.response?.data?.detail || '加载失败');
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (snapshotId: string) => {
        if (!confirm('确定要删除此存档吗？')) return;

        try {
            await gameService.deleteSnapshot(snapshotId);
            setSuccess('存档已删除');
            loadSnapshots();
        } catch (err: any) {
            setError('删除失败');
        }
    };

    const formatDate = (timestamp: string) => {
        const date = new Date(timestamp);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const getSnapshotTypeLabel = (type: string) => {
        switch (type) {
            case 'manual': return '手动';
            case 'checkpoint': return '检查点';
            case 'auto': return '自动';
            default: return type;
        }
    };

    const handleReplay = (snapshotId: string) => {
        setReplaySnapshotId(snapshotId);
        setShowReplay(true);
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-900 rounded-3xl border border-white/10 max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-white/10">
                    <h2 className="text-2xl font-bold">存档管理</h2>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-white/10 rounded-xl transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-white/10">
                    <button
                        onClick={() => setActiveTab('save')}
                        className={`flex-1 px-6 py-4 font-medium transition-colors ${
                            activeTab === 'save'
                                ? 'bg-white/5 border-b-2 border-primary text-primary'
                                : 'text-text-muted hover:bg-white/5'
                        }`}
                    >
                        <Save className="w-4 h-4 inline mr-2" />
                        保存游戏
                    </button>
                    <button
                        onClick={() => setActiveTab('load')}
                        className={`flex-1 px-6 py-4 font-medium transition-colors ${
                            activeTab === 'load'
                                ? 'bg-white/5 border-b-2 border-secondary text-secondary'
                                : 'text-text-muted hover:bg-white/5'
                        }`}
                    >
                        <FolderOpen className="w-4 h-4 inline mr-2" />
                        加载游戏
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {activeTab === 'save' ? (
                        <div className="space-y-6">
                            <div>
                                <label className="block text-sm font-medium mb-2">
                                    存档名称（可选）
                                </label>
                                <input
                                    type="text"
                                    value={snapshotName}
                                    onChange={(e) => setSnapshotName(e.target.value)}
                                    placeholder="留空则使用时间戳"
                                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/50"
                                />
                            </div>

                            <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                                <h4 className="font-medium mb-2">当前游戏状态</h4>
                                <div className="space-y-1 text-sm text-text-muted">
                                    <div>游戏ID: {gameId}</div>
                                    <div>将保存完整的游戏状态，包括所有Agent状态和对话历史</div>
                                </div>
                            </div>

                            {success && (
                                <div className="p-4 rounded-xl bg-green-500/10 border border-green-500/20 flex items-center gap-3">
                                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                                    <span className="text-green-400">{success}</span>
                                </div>
                            )}

                            {error && (
                                <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-start gap-3">
                                    <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                                    <span className="text-red-400 text-sm">{error}</span>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {loading && snapshots.length === 0 ? (
                                <div className="text-center py-12">
                                    <div className="w-12 h-12 border-4 border-white/10 border-t-primary rounded-full animate-spin mx-auto mb-4" />
                                    <p className="text-text-muted">加载存档列表...</p>
                                </div>
                            ) : snapshots.length === 0 ? (
                                <div className="text-center py-12">
                                    <FolderOpen className="w-16 h-16 text-text-muted mx-auto mb-4 opacity-50" />
                                    <p className="text-text-muted">暂无存档</p>
                                </div>
                            ) : (
                                snapshots.map((snapshot) => (
                                    <div
                                        key={snapshot.snapshot_id}
                                        className="p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
                                    >
                                        <div className="flex items-start justify-between mb-3">
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <Clock className="w-4 h-4 text-text-muted" />
                                                    <span className="font-medium">
                                                        {formatDate(snapshot.timestamp)}
                                                    </span>
                                                    <span className="px-2 py-0.5 rounded-full bg-primary/20 text-primary text-xs">
                                                        {getSnapshotTypeLabel(snapshot.snapshot_type)}
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-4 text-sm text-text-muted">
                                                    <span>第 {snapshot.round} 回合</span>
                                                    <span className="flex items-center gap-1">
                                                        <Users className="w-3 h-3" />
                                                        {snapshot.alive_count}/{snapshot.agent_count}
                                                    </span>
                                                    <span className="capitalize">{snapshot.phase}</span>
                                                </div>
                                            </div>
                                            <div className="flex gap-2">
                                                <button
                                                    onClick={() => handleReplay(snapshot.snapshot_id)}
                                                    className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium transition-colors flex items-center gap-1"
                                                >
                                                    <Play className="w-4 h-4" />
                                                    回放
                                                </button>
                                                <button
                                                    onClick={() => handleLoad(snapshot.snapshot_id)}
                                                    disabled={loading}
                                                    className="px-4 py-2 rounded-xl bg-secondary hover:bg-secondary/90 text-white text-sm font-medium transition-colors disabled:opacity-50"
                                                >
                                                    加载
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(snapshot.snapshot_id)}
                                                    className="p-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-colors"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}

                            {error && (
                                <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-start gap-3">
                                    <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                                    <span className="text-red-400 text-sm">{error}</span>
                                </div>
                            )}

                            {success && (
                                <div className="p-4 rounded-xl bg-green-500/10 border border-green-500/20 flex items-center gap-3">
                                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                                    <span className="text-green-400">{success}</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Footer */}
                {activeTab === 'save' && (
                    <div className="flex items-center justify-end gap-3 p-6 border-t border-white/10">
                        <button
                            onClick={onClose}
                            className="px-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
                        >
                            取消
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={loading}
                            className="px-6 py-3 rounded-xl bg-primary hover:bg-primary/90 text-white font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
                        >
                            {loading ? (
                                <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                            ) : (
                                <Save className="w-5 h-5" />
                            )}
                            保存游戏
                        </button>
                    </div>
                )}
            </div>

            {showReplay && replaySnapshotId && (
                <ReplayModal
                    isOpen={showReplay}
                    onClose={() => setShowReplay(false)}
                    snapshotId={replaySnapshotId}
                />
            )}
        </div>
    );
};

export default SaveLoadModal;

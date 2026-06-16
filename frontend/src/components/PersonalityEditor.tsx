import React, { useState, useEffect } from 'react';
import { Brain, RotateCcw, Save, X, AlertCircle, CheckCircle, Download, Upload } from 'lucide-react';
import api from '../services/api';

interface PersonalityPreset {
    mbti_type: string;
    traits: string;
    speaking_style: string;
    thinking_pattern: string;
    is_modified: boolean;
}

interface PersonalityEditorProps {
    isOpen: boolean;
    onClose: () => void;
}

const MBTI_TYPES = [
    'INTJ', 'INTP', 'ENTJ', 'ENTP',
    'INFJ', 'INFP', 'ENFJ', 'ENFP',
    'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
    'ISTP', 'ISFP', 'ESTP', 'ESFP'
];

const PersonalityEditor: React.FC<PersonalityEditorProps> = ({
    isOpen,
    onClose
}) => {
    const [selectedMBTI, setSelectedMBTI] = useState('ENTJ');
    const [presets, setPresets] = useState<Record<string, PersonalityPreset>>({});
    const [currentPreset, setCurrentPreset] = useState<PersonalityPreset | null>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen) {
            loadPresets();
        }
    }, [isOpen]);

    useEffect(() => {
        if (presets[selectedMBTI]) {
            setCurrentPreset({ ...presets[selectedMBTI] });
        }
    }, [selectedMBTI, presets]);

    const loadPresets = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.get('/api/personality/presets');
            const presetsData: Record<string, PersonalityPreset> = {};
            response.data.presets.forEach((preset: PersonalityPreset) => {
                presetsData[preset.mbti_type] = preset;
            });
            setPresets(presetsData);
        } catch (err: any) {
            setError('加载人格预设失败');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        if (!currentPreset) return;

        setSaving(true);
        setError(null);
        setSuccess(null);

        try {
            await api.put(`/api/personality/preset/${selectedMBTI}`, {
                traits: currentPreset.traits,
                speaking_style: currentPreset.speaking_style,
                thinking_pattern: currentPreset.thinking_pattern
            });

            setSuccess('保存成功！');
            await loadPresets();
        } catch (err: any) {
            setError(err.response?.data?.detail || '保存失败');
        } finally {
            setSaving(false);
        }
    };

    const handleReset = async () => {
        if (!confirm(`确定要重置 ${selectedMBTI} 的人格设置吗？`)) return;

        setSaving(true);
        setError(null);
        setSuccess(null);

        try {
            await api.post(`/api/personality/preset/${selectedMBTI}/reset`);
            setSuccess('重置成功！');
            await loadPresets();
        } catch (err: any) {
            setError(err.response?.data?.detail || '重置失败');
        } finally {
            setSaving(false);
        }
    };

    const handleResetAll = async () => {
        if (!confirm('确定要重置所有人格设置吗？此操作不可撤销！')) return;

        setSaving(true);
        setError(null);
        setSuccess(null);

        try {
            await api.post('/api/personality/reset-all');
            setSuccess('全部重置成功！');
            await loadPresets();
        } catch (err: any) {
            setError(err.response?.data?.detail || '重置失败');
        } finally {
            setSaving(false);
        }
    };

    const handleExport = () => {
        // Export all presets (both default and custom)
        const exportData = {
            version: "1.0.0",
            exported_at: new Date().toISOString(),
            presets: presets
        };
        
        const data = JSON.stringify(exportData, null, 2);
        const blob = new Blob([data], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `personality_presets_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        
        setSuccess('配置已导出到本地！');
        setTimeout(() => setSuccess(null), 3000);
    };

    const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        setSaving(true);
        setError(null);
        setSuccess(null);

        try {
            const text = await file.text();
            const imported = JSON.parse(text);

            // Support both old and new format
            const presetsToImport = imported.presets || imported;

            // Validate and save each preset
            let importedCount = 0;
            const presetsArray = Array.isArray(presetsToImport)
                ? presetsToImport
                : Object.entries(presetsToImport).map(([mbti, data]: [string, any]) => ({ mbti_type: mbti, ...(data as object) }));

            for (const preset of presetsArray) {
                const mbti = preset.mbti_type || preset.mbti;
                if (MBTI_TYPES.includes(mbti)) {
                    await api.put(`/api/personality/preset/${mbti}`, {
                        traits: preset.traits,
                        speaking_style: preset.speaking_style,
                        thinking_pattern: preset.thinking_pattern
                    });
                    importedCount++;
                }
            }

            setSuccess(`导入成功！已导入 ${importedCount} 个人格配置`);
            await loadPresets();
        } catch (err: any) {
            setError('导入失败：文件格式错误或数据无效');
        } finally {
            setSaving(false);
            // Reset file input
            event.target.value = '';
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-900 rounded-3xl border border-white/10 max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-white/10">
                    <div className="flex items-center gap-3">
                        <div className="p-3 bg-purple-500/20 rounded-xl">
                            <Brain className="w-6 h-6 text-purple-400" />
                        </div>
                        <div>
                            <h2 className="text-2xl font-bold">人格编辑器</h2>
                            <p className="text-sm text-text-muted">自定义16种MBTI人格的提示词</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleExport}
                            className="p-2 hover:bg-white/10 rounded-xl transition-colors"
                            title="导出配置"
                        >
                            <Download className="w-5 h-5" />
                        </button>
                        <label className="p-2 hover:bg-white/10 rounded-xl transition-colors cursor-pointer" title="导入配置">
                            <Upload className="w-5 h-5" />
                            <input
                                type="file"
                                accept=".json"
                                onChange={handleImport}
                                className="hidden"
                            />
                        </label>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/10 rounded-xl transition-colors"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-hidden flex">
                    {/* MBTI Selector */}
                    <div className="w-64 border-r border-white/10 overflow-y-auto p-4">
                        <div className="space-y-1">
                            {MBTI_TYPES.map(mbti => (
                                <button
                                    key={mbti}
                                    onClick={() => setSelectedMBTI(mbti)}
                                    className={`w-full px-4 py-3 rounded-xl text-left transition-colors flex items-center justify-between ${
                                        selectedMBTI === mbti
                                            ? 'bg-primary text-white'
                                            : 'hover:bg-white/5'
                                    }`}
                                >
                                    <span className="font-medium">{mbti}</span>
                                    {presets[mbti]?.is_modified && (
                                        <div className="w-2 h-2 bg-secondary rounded-full" title="已自定义" />
                                    )}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Editor */}
                    <div className="flex-1 overflow-y-auto p-6">
                        {loading ? (
                            <div className="text-center py-12">
                                <div className="w-12 h-12 border-4 border-white/10 border-t-primary rounded-full animate-spin mx-auto mb-4" />
                                <p className="text-text-muted">加载中...</p>
                            </div>
                        ) : currentPreset ? (
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-xl font-bold mb-2">{selectedMBTI}</h3>
                                    <p className="text-sm text-text-muted">
                                        编辑此人格类型的特征、说话风格和思维模式
                                    </p>
                                </div>

                                <div className="space-y-4">
                                    <div>
                                        <div className="flex items-center justify-between mb-2">
                                            <label className="block text-sm font-medium">
                                                性格特征 (Traits)
                                            </label>
                                            {presets[selectedMBTI]?.is_modified && (
                                                <button
                                                    onClick={handleReset}
                                                    className="text-xs text-secondary hover:text-secondary/80 transition-colors flex items-center gap-1"
                                                    title="恢复此项默认值"
                                                >
                                                    <RotateCcw className="w-3 h-3" />
                                                    恢复默认
                                                </button>
                                            )}
                                        </div>
                                        <textarea
                                            value={currentPreset.traits}
                                            onChange={(e) => setCurrentPreset({
                                                ...currentPreset,
                                                traits: e.target.value
                                            })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/50 h-32 resize-none font-mono text-sm"
                                            placeholder="描述这个MBTI类型的核心性格特征..."
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-sm font-medium mb-2">
                                            说话风格 (Speaking Style)
                                        </label>
                                        <textarea
                                            value={currentPreset.speaking_style}
                                            onChange={(e) => setCurrentPreset({
                                                ...currentPreset,
                                                speaking_style: e.target.value
                                            })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/50 h-32 resize-none font-mono text-sm"
                                            placeholder="描述这个类型的说话方式和表达习惯..."
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-sm font-medium mb-2">
                                            思维模式 (Thinking Pattern)
                                        </label>
                                        <textarea
                                            value={currentPreset.thinking_pattern}
                                            onChange={(e) => setCurrentPreset({
                                                ...currentPreset,
                                                thinking_pattern: e.target.value
                                            })}
                                            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/50 h-32 resize-none font-mono text-sm"
                                            placeholder="描述这个类型的思考方式和决策逻辑..."
                                        />
                                    </div>
                                </div>

                                {/* Preview */}
                                <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                                    <h4 className="font-medium mb-2 text-sm text-text-muted">提示词预览</h4>
                                    <div className="text-xs font-mono text-text-muted space-y-2">
                                        <div>
                                            <span className="text-primary">## 性格特征:</span>
                                            <div className="ml-4 mt-1">{currentPreset.traits || '(未设置)'}</div>
                                        </div>
                                        <div>
                                            <span className="text-primary">## 说话风格:</span>
                                            <div className="ml-4 mt-1">{currentPreset.speaking_style || '(未设置)'}</div>
                                        </div>
                                        <div>
                                            <span className="text-primary">## 思维模式:</span>
                                            <div className="ml-4 mt-1">{currentPreset.thinking_pattern || '(未设置)'}</div>
                                        </div>
                                    </div>
                                </div>

                                {/* Messages */}
                                {error && (
                                    <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-start gap-3">
                                        <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                                        <span className="text-red-400 text-sm">{error}</span>
                                    </div>
                                )}

                                {success && (
                                    <div className="p-4 rounded-xl bg-green-500/10 border border-green-500/20 flex items-center gap-3">
                                        <CheckCircle className="w-5 h-5 text-green-500" />
                                        <span className="text-green-400 text-sm">{success}</span>
                                    </div>
                                )}
                            </div>
                        ) : null}
                    </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between p-6 border-t border-white/10">
                    <div className="flex gap-2">
                        <button
                            onClick={handleReset}
                            disabled={saving}
                            className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 transition-colors text-sm disabled:opacity-50 flex items-center gap-2"
                        >
                            <RotateCcw className="w-4 h-4" />
                            重置当前
                        </button>
                        <button
                            onClick={handleResetAll}
                            disabled={saving}
                            className="px-4 py-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-colors text-sm disabled:opacity-50"
                        >
                            重置全部
                        </button>
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={onClose}
                            className="px-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
                        >
                            取消
                        </button>
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className="px-6 py-3 rounded-xl bg-primary hover:bg-primary/90 text-white font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
                        >
                            {saving ? (
                                <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                            ) : (
                                <Save className="w-5 h-5" />
                            )}
                            保存修改
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PersonalityEditor;

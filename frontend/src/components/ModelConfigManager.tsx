import React, { useState, useEffect, useMemo } from 'react';
import { Download, Upload, BarChart2 } from 'lucide-react';
import { ModelConfigList } from './ModelConfigList';
import { ModelConfigEditor } from './ModelConfigEditor';
import { UsageChart } from './UsageChart';
import { useSettingsStore } from '../store/settingsStore';
import type { ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '../types/modelConfig';
import type { UsageStatsResponse } from '../types/usage';
import '../styles/modelConfig.css';

export const ModelConfigManager: React.FC = () => {
    const {
        modelConfigs,
        modelConfigsLoading,
        fetchModelConfigs,
        createModelConfig,
        updateModelConfig,
        deleteModelConfig,
        exportModelConfigs,
        importModelConfigs,
        getUsageStats,
    } = useSettingsStore();

    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const [usageData, setUsageData] = useState<UsageStatsResponse | null>(null);
    const [, setUsageLoading] = useState(false);

    useEffect(() => {
        fetchModelConfigs();
    }, [fetchModelConfigs]);

    const selectedConfig = useMemo(() => {
        return modelConfigs.find((c) => c.id === selectedId) || null;
    }, [modelConfigs, selectedId]);

    // Fetch usage stats when selected config changes
    useEffect(() => {
        if (selectedId) {
            setUsageLoading(true);
            getUsageStats({ model: selectedConfig?.model, group_by: 'day' })
                .then(setUsageData)
                .finally(() => setUsageLoading(false));
        } else {
            setUsageData(null);
        }
    }, [selectedId, selectedConfig?.model, getUsageStats]);

    const handleSelect = (config: ModelConfig) => {
        setSelectedId(config.id);
        setIsCreating(false);
    };

    const handleAdd = () => {
        setSelectedId(null);
        setIsCreating(true);
    };

    const handleDuplicate = async (config: ModelConfig) => {
        const payload: ModelConfigCreate = {
            ...config,
            name: `${config.name} (复制)`,
        };
        const created = await createModelConfig(payload);
        setSelectedId(created.id);
        setIsCreating(false);
    };

    const handleSave = async (payload: ModelConfigCreate | ModelConfigUpdate) => {
        if (isCreating) {
            const created = await createModelConfig(payload as ModelConfigCreate);
            setSelectedId(created.id);
            setIsCreating(false);
        } else if (selectedId) {
            await updateModelConfig(selectedId, payload as ModelConfigUpdate);
        }
    };

    const handleExport = async () => {
        const data = await exportModelConfigs();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `model-configs-export-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const handleImport = async () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.onchange = async (e) => {
            const file = (e.target as HTMLInputElement).files?.[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = async (re) => {
                    try {
                        const content = re.target?.result as string;
                        const data = JSON.parse(content);
                        await importModelConfigs(data);
                        alert('导入成功');
                    } catch (err) {
                        alert('导入失败: ' + (err instanceof Error ? err.message : '无效的 JSON'));
                    }
                };
                reader.readAsText(file);
            }
        };
        input.click();
    };

    return (
        <div className="model-config-container bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl overflow-hidden border border-white/5 shadow-2xl">
            <ModelConfigList
                configs={modelConfigs}
                selectedId={selectedId || undefined}
                onSelect={handleSelect}
                onAdd={handleAdd}
                onDuplicate={handleDuplicate}
                onDelete={deleteModelConfig}
                searchTerm={searchTerm}
                setSearchTerm={setSearchTerm}
            />

            <div className="flex-1 flex flex-col h-full overflow-hidden">
                <div className="border-b border-gray-700/50 p-6 flex justify-between items-center bg-gray-800/40 backdrop-blur-md">
                    <div>
                        <h2 className="text-xl font-bold text-gray-100 mb-1">模型配置管理</h2>
                        <div className="text-xs text-gray-400">
                            {modelConfigsLoading ? '正在加载配置...' : `${modelConfigs.length} 个可用配置`}
                        </div>
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={handleImport}
                            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-300 bg-gray-700/40 border border-gray-600/50 rounded-xl hover:bg-gray-600/60 transition-all hover:scale-105 active:scale-95"
                        >
                            <Upload size={16} />
                            导入
                        </button>
                        <button
                            onClick={handleExport}
                            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-300 bg-gray-700/40 border border-gray-600/50 rounded-xl hover:bg-gray-600/60 transition-all hover:scale-105 active:scale-95"
                        >
                            <Download size={16} />
                            导出
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto">
                    <ModelConfigEditor
                        config={selectedConfig}
                        isNew={isCreating}
                        onSave={handleSave}
                    />

                    {selectedId && usageData && (
                        <div className="px-8 pb-12 max-w-4xl mx-auto mt-8">
                            <div className="bg-gray-800/50 backdrop-blur-sm p-6 rounded-xl border border-gray-700 shadow-sm">
                                <div className="flex items-center gap-2 mb-6">
                                    <BarChart2 className="text-blue-400" size={20} />
                                    <h3 className="text-lg font-bold text-gray-200">使用统计 (过去 30 天)</h3>
                                </div>

                                <div className="grid grid-cols-3 gap-6 mb-8">
                                    <div className="bg-blue-500/10 p-4 rounded-lg border border-blue-500/20">
                                        <div className="text-xs text-blue-400 font-semibold uppercase tracking-wider">总 Tokens</div>
                                        <div className="text-2xl font-bold text-blue-300">{usageData.summary.total_tokens.toLocaleString()}</div>
                                    </div>
                                    <div className="bg-green-500/10 p-4 rounded-lg border border-green-500/20">
                                        <div className="text-xs text-green-400 font-semibold uppercase tracking-wider">总成本</div>
                                        <div className="text-2xl font-bold text-green-300">${usageData.summary.total_cost.toFixed(4)}</div>
                                    </div>
                                    <div className="bg-purple-500/10 p-4 rounded-lg border border-purple-500/20">
                                        <div className="text-xs text-purple-400 font-semibold uppercase tracking-wider">调用次数</div>
                                        <div className="text-2xl font-bold text-purple-300">{usageData.summary.call_count}</div>
                                    </div>
                                </div>

                                <div className="space-y-6">
                                    <div>
                                        <div className="text-sm font-medium text-gray-400 mb-2">每日 Token 消耗</div>
                                        <div className="h-40">
                                            <UsageChart data={usageData.by_time} type="tokens" color="bg-blue-500" height={160} />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
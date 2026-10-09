import React, { useState, useEffect, useMemo } from 'react';
import { Download, Upload, BarChart2 } from 'lucide-react';
import { ModelConfigList } from './ModelConfigList';
import { ModelConfigEditor } from './ModelConfigEditor';
import { UsageChart } from './UsageChart';
import { useSettingsStore } from '../store/settingsStore';
import { pickPreferredModelConfig } from '../lib/modelProviders';
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

    // 进入页面默认选中推荐配置（OpenCode Go 优先），避免编辑区空转
    useEffect(() => {
        if (!selectedId && !isCreating && modelConfigs.length > 0) {
            const preferred = pickPreferredModelConfig(modelConfigs);
            if (preferred) setSelectedId(preferred.id);
        }
    }, [modelConfigs, selectedId, isCreating]);

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
        <div className="model-config-container bg-black/20 rounded-2xl overflow-hidden border border-line shadow-2xl">
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
                <div className="border-b border-line p-4 sm:p-6 flex justify-between items-center gap-3 bg-white/[0.03]">
                    <div className="min-w-0">
                        <h2 className="text-lg sm:text-xl font-bold text-text-primary mb-1">模型配置管理</h2>
                        <div className="text-xs text-text-secondary/80">
                            {modelConfigsLoading ? '正在加载配置...' : `${modelConfigs.length} 个可用配置`}
                        </div>
                    </div>
                    <div className="flex shrink-0 gap-2 sm:gap-3">
                        <button
                            onClick={handleImport}
                            className="flex items-center gap-2 px-3 sm:px-4 py-2 text-sm font-medium text-text-secondary whitespace-nowrap rounded-xl border border-line bg-white/[0.04] hover:border-violet/40 hover:text-violet hover:bg-violet/10 transition-all active:scale-95"
                        >
                            <Upload size={16} />
                            导入
                        </button>
                        <button
                            onClick={handleExport}
                            className="flex items-center gap-2 px-3 sm:px-4 py-2 text-sm font-medium text-text-secondary whitespace-nowrap rounded-xl border border-line bg-white/[0.04] hover:border-violet/40 hover:text-violet hover:bg-violet/10 transition-all active:scale-95"
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
                        <div className="px-4 sm:px-8 pb-12 max-w-4xl mx-auto mt-8">
                            <div className="bg-white/[0.03] p-4 sm:p-6 rounded-2xl border border-line">
                                <div className="flex items-center gap-2 mb-4 sm:mb-6">
                                    <BarChart2 className="text-info" size={20} />
                                    <h3 className="text-base sm:text-lg font-bold text-text-primary">使用统计 (过去 30 天)</h3>
                                </div>

                                <div className="grid grid-cols-3 gap-2 sm:gap-6 mb-6 sm:mb-8">
                                    <div className="bg-info/10 p-3 sm:p-4 rounded-xl border border-info/25">
                                        <div className="text-[10px] sm:text-xs text-info font-semibold uppercase tracking-wider">总 Tokens</div>
                                        <div className="text-lg sm:text-2xl font-bold text-info/90 font-hud truncate">{usageData.summary.total_tokens.toLocaleString()}</div>
                                    </div>
                                    <div className="bg-success/10 p-3 sm:p-4 rounded-xl border border-success/25">
                                        <div className="text-[10px] sm:text-xs text-success font-semibold uppercase tracking-wider">总成本</div>
                                        <div className="text-lg sm:text-2xl font-bold text-success/90 font-hud truncate">${usageData.summary.total_cost.toFixed(4)}</div>
                                    </div>
                                    <div className="bg-violet/10 p-3 sm:p-4 rounded-xl border border-violet/25">
                                        <div className="text-[10px] sm:text-xs text-violet font-semibold uppercase tracking-wider">调用次数</div>
                                        <div className="text-lg sm:text-2xl font-bold text-violet/90 font-hud truncate">{usageData.summary.call_count}</div>
                                    </div>
                                </div>

                                <div className="space-y-6">
                                    <div>
                                        <div className="text-sm font-medium text-text-secondary mb-2">每日 Token 消耗</div>
                                        <div className="h-40">
                                            <UsageChart data={usageData.by_time} type="tokens" color="bg-info" height={160} />
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
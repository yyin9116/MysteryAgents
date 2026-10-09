import React from 'react';
import { Search, Plus, Copy, Trash2 } from 'lucide-react';
import type { ModelConfig } from '../types/modelConfig';

interface ModelConfigListProps {
    configs: ModelConfig[];
    selectedId?: string;
    onSelect: (config: ModelConfig) => void;
    onAdd: () => void;
    onDuplicate: (config: ModelConfig) => void;
    onDelete: (id: string) => void;
    searchTerm: string;
    setSearchTerm: (term: string) => void;
}

export const ModelConfigList: React.FC<ModelConfigListProps> = ({
    configs,
    selectedId,
    onSelect,
    onAdd,
    onDuplicate,
    onDelete,
    searchTerm,
    setSearchTerm,
}) => {
    const filteredConfigs = configs.filter((c) =>
        c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.model.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.provider.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="model-config-sidebar flex flex-col h-full bg-black/25 border-r border-line">
            <div className="p-5 border-b border-line">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-base font-bold text-text-primary">配置列表</h2>
                    <button
                        onClick={onAdd}
                        className="p-2 rounded-xl bg-gold/15 text-gold border border-gold/30 hover:bg-gold/25 transition-all hover:scale-105 active:scale-95"
                        title="添加新配置"
                        aria-label="添加新配置"
                    >
                        <Plus size={18} />
                    </button>
                </div>
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary/50" size={16} />
                    <input
                        type="text"
                        placeholder="搜索配置..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 bg-white/[0.04] border border-line rounded-xl text-sm text-text-primary placeholder:text-text-secondary/40 focus:ring-2 focus:ring-violet/40 focus:border-violet/50 outline-none transition-all"
                    />
                </div>
            </div>

            <div className="flex-1 overflow-y-auto py-2 space-y-1">
                {filteredConfigs.length > 0 ? (
                    filteredConfigs.map((config) => {
                        const selected = selectedId === config.id;
                        return (
                            <div
                                key={config.id}
                                onClick={() => onSelect(config)}
                                className={`group mx-2 px-4 py-3 rounded-xl cursor-pointer border transition-all ${
                                    selected
                                        ? 'bg-violet/10 border-violet/45 shadow-[0_0_18px_rgba(140,125,245,0.15)]'
                                        : 'bg-white/[0.02] border-line hover:border-line-strong hover:bg-white/[0.05]'
                                }`}
                            >
                                <div className="flex justify-between items-start gap-2 mb-1">
                                    <span className={`font-semibold truncate text-sm ${selected ? 'text-violet' : 'text-text-primary'}`}>
                                        {config.name}
                                    </span>
                                    <span className="shrink-0 font-hud text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] border border-line text-text-secondary/70 uppercase tracking-wider">
                                        {config.provider}
                                    </span>
                                </div>
                                <div className="flex justify-between items-center">
                                    <span className="text-xs text-text-secondary/75 font-mono truncate mr-2">{config.model}</span>
                                    <div className="flex gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onDuplicate(config);
                                            }}
                                            className="p-1.5 text-text-secondary/60 hover:text-violet hover:bg-violet/10 rounded-lg transition-colors"
                                            title="复制"
                                            aria-label="复制配置"
                                        >
                                            <Copy size={14} />
                                        </button>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                if (confirm('确定要删除此配置吗？')) {
                                                    onDelete(config.id);
                                                }
                                            }}
                                            className="p-1.5 text-text-secondary/60 hover:text-danger hover:bg-danger/10 rounded-lg transition-colors"
                                            title="删除"
                                            aria-label="删除配置"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        );
                    })
                ) : (
                    <div className="p-8 text-center text-text-secondary/50 text-sm">
                        未找到匹配的配置
                    </div>
                )}
            </div>
        </div>
    );
};

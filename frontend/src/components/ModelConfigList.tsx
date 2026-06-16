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
        <div className="model-config-sidebar flex flex-col h-full bg-gray-900/50 border-r border-gray-700/50 backdrop-blur-md">
            <div className="p-6 border-b border-gray-700/50">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-lg font-bold text-gray-100">配置列表</h2>
                    <button
                        onClick={onAdd}
                        className="p-2 rounded-xl bg-blue-600/80 text-white hover:bg-blue-500 transition-all hover:scale-110 active:scale-95 shadow-lg shadow-blue-500/20"
                        title="添加新配置"
                    >
                        <Plus size={20} />
                    </button>
                </div>
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
                    <input
                        type="text"
                        placeholder="搜索配置..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 bg-gray-800/50 border border-gray-700/50 rounded-xl text-sm text-gray-200 focus:ring-2 focus:ring-blue-500/50 outline-none transition-all placeholder:text-gray-600"
                    />
                </div>
            </div>

            <div className="flex-1 overflow-y-auto py-2">
                {filteredConfigs.length > 0 ? (
                    filteredConfigs.map((config) => (
                        <div
                            key={config.id}
                            onClick={() => onSelect(config)}
                            className={`config-item group mx-2 px-4 py-3 rounded-xl cursor-pointer transition-all mb-1 ${
                                selectedId === config.id 
                                ? 'bg-blue-600/20 border-blue-500/30 text-blue-100' 
                                : 'hover:bg-gray-800/40 text-gray-400 border-transparent hover:text-gray-200'
                            } border`}
                        >
                            <div className="flex justify-between items-start mb-1">
                                <span className={`font-semibold truncate ${selectedId === config.id ? 'text-blue-200' : 'text-gray-200'}`}>
                                    {config.name}
                                </span>
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-500 uppercase tracking-wider font-medium">
                                    {config.provider}
                                </span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-xs opacity-60 font-mono truncate mr-2">{config.model}</span>
                                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onDuplicate(config);
                                        }}
                                        className="p-1.5 text-gray-500 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-colors"
                                        title="复制"
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
                                        className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                                        title="删除"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="p-8 text-center text-gray-600 text-sm italic">
                        未找到匹配的配置
                    </div>
                )}
            </div>
        </div>
    );
};
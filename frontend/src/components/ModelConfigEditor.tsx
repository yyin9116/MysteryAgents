import React, { useState, useEffect } from 'react';
import { Save, Play, AlertCircle, CheckCircle2 } from 'lucide-react';
import type { ModelConfig, ModelConfigUpdate, ModelConfigCreate, ModelConfigTestResponse } from '../types/modelConfig';
import { useSettingsStore } from '../store/settingsStore';

interface ModelConfigEditorProps {
    config: ModelConfig | null;
    onSave: (payload: ModelConfigCreate | ModelConfigUpdate) => Promise<void>;
    isNew?: boolean;
}

export const ModelConfigEditor: React.FC<ModelConfigEditorProps> = ({
    config,
    onSave,
    isNew = false,
}) => {
    const { testModelConfig } = useSettingsStore();
    const [formData, setFormData] = useState<Partial<ModelConfig>>({
        name: '',
        provider: 'openai',
        model: '',
        temperature: 0.7,
        max_tokens: 2000,
        top_p: 1.0,
        frequency_penalty: 0,
        presence_penalty: 0,
        api_key: '',
        base_url: '',
        description: '',
        extra_params: {},
    });

    const [testing, setTesting] = useState(false);
    const [testResult, setTestResult] = useState<ModelConfigTestResponse | null>(null);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (config) {
            setFormData(config);
            setTestResult(null);
        } else if (isNew) {
            setFormData({
                name: '新配置',
                provider: 'openai',
                model: '',
                temperature: 0.7,
                max_tokens: 2000,
                extra_params: {},
            });
            setTestResult(null);
        }
    }, [config, isNew]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
        const { name, value, type } = e.target;
        
        let parsedValue: string | number | null = value;
        if (type === 'number') {
            parsedValue = value === '' ? null : parseFloat(value);
        }

        setFormData((prev) => ({
            ...prev,
            [name]: parsedValue,
        }));
    };

    const handleExtraParamsChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        try {
            const json = JSON.parse(e.target.value);
            setFormData((prev) => ({
                ...prev,
                extra_params: json,
            }));
        } catch (err) {
            // Keep as string if invalid JSON for now, but in a real app we'd show an error
        }
    };

    const handleTest = async () => {
        if (!config?.id && !isNew) return;
        
        setTesting(true);
        setTestResult(null);
        try {
            // For new unsaved configs, we might need a special test endpoint or save first
            // But usually we test the existing one
            if (config?.id) {
                const res = await testModelConfig(config.id);
                setTestResult(res);
            } else {
                setTestResult({ success: false, message: '请先保存配置后再测试' });
            }
        } catch (error) {
            setTestResult({ success: false, message: error instanceof Error ? error.message : '测试失败' });
        } finally {
            setTesting(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            await onSave(formData as ModelConfigCreate);
        } finally {
            setSaving(false);
        }
    };

    if (!config && !isNew) {
        return (
            <div className="flex-1 flex items-center justify-center text-gray-400">
                请选择或创建一个模型配置
            </div>
        );
    }

    return (
        <div className="flex-1 p-8 overflow-y-auto bg-gray-900">
            <form onSubmit={handleSubmit} className="max-w-4xl mx-auto bg-gray-800/50 backdrop-blur-sm p-8 rounded-xl shadow-sm border border-gray-700">
                <div className="flex justify-between items-center mb-8 pb-4 border-b border-gray-700">
                    <h2 className="text-2xl font-bold text-gray-200">
                        {isNew ? '新建配置' : `编辑: ${config?.name}`}
                    </h2>
                    <div className="flex gap-3">
                        <button
                            type="button"
                            onClick={handleTest}
                            disabled={testing || isNew}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                                testing || isNew
                                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                                    : 'bg-indigo-50 text-indigo-600 hover:bg-indigo-100'
                            }`}
                        >
                            {testing ? (
                                <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                            ) : (
                                <Play size={18} />
                            )}
                            测试连接
                        </button>
                        <button
                            type="submit"
                            disabled={saving}
                            className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors shadow-sm disabled:opacity-50"
                        >
                            <Save size={18} />
                            {saving ? '保存中...' : '保存配置'}
                        </button>
                    </div>
                </div>

                {testResult && (
                    <div className={`mb-6 p-4 rounded-lg flex items-start gap-3 ${testResult.success ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-700'}`}>
                        {testResult.success ? <CheckCircle2 size={20} className="mt-0.5" /> : <AlertCircle size={20} className="mt-0.5" />}
                        <div>
                            <p className="font-semibold">{testResult.success ? '连接成功' : '连接失败'}</p>
                            <p className="text-sm opacity-90">{testResult.message}</p>
                            {testResult.duration_ms && <p className="text-xs mt-1">耗时: {testResult.duration_ms}ms</p>}
                        </div>
                    </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                        <label className="text-sm font-semibold text-gray-300">配置名称</label>
                        <input
                            type="text"
                            name="name"
                            value={formData.name || ''}
                            onChange={handleChange}
                            required
                            className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none placeholder-gray-500"
                            placeholder="如: GPT-4o 生产环境"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-semibold text-gray-300">服务商 (Provider)</label>
                        <select
                            name="provider"
                            value={formData.provider || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none appearance-none cursor-pointer"
                            style={{
                                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%239CA3AF' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3E%3C/svg%3E")`,
                                backgroundPosition: 'right 0.5rem center',
                                backgroundRepeat: 'no-repeat',
                                backgroundSize: '1.5em 1.5em',
                                paddingRight: '2.5rem'
                            }}
                        >
                            <option value="openai">OpenAI</option>
                            <option value="anthropic">Anthropic</option>
                            <option value="google">Google Gemini</option>
                            <option value="ollama">Ollama</option>
                            <option value="deepseek">DeepSeek</option>
                            <option value="alibaba">Alibaba DashScope</option>
                        </select>
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-semibold text-gray-300">模型名称 (Model ID)</label>
                        <input
                            type="text"
                            name="model"
                            value={formData.model || ''}
                            onChange={handleChange}
                            required
                            className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none placeholder-gray-500"
                            placeholder="如: gpt-4o, claude-3-5-sonnet"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-semibold text-gray-300">API Key (可选)</label>
                        <input
                            type="password"
                            name="api_key"
                            value={formData.api_key || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none placeholder-gray-500"
                            placeholder="环境变量中已设置则留空"
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-semibold text-gray-300">Base URL (可选)</label>
                        <input
                            type="text"
                            name="base_url"
                            value={formData.base_url || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none placeholder-gray-500"
                            placeholder="自定义 API 端点"
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-gray-300">Temperature ({formData.temperature})</label>
                            <input
                                type="range"
                                name="temperature"
                                min="0"
                                max="2"
                                step="0.1"
                                value={formData.temperature || 0}
                                onChange={handleChange}
                                className="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-600"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-semibold text-gray-300">Max Tokens</label>
                            <input
                                type="number"
                                name="max_tokens"
                                value={formData.max_tokens || ''}
                                onChange={handleChange}
                                className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none placeholder-gray-500"
                            />
                        </div>
                    </div>

                    <div className="md:col-span-2 space-y-2">
                        <label className="text-sm font-semibold text-gray-300">描述</label>
                        <textarea
                            name="description"
                            value={formData.description || ''}
                            onChange={handleChange}
                            rows={2}
                            className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none placeholder-gray-500"
                            placeholder="简短说明此配置的用途"
                        />
                    </div>

                    <div className="md:col-span-2 space-y-2">
                        <label className="text-sm font-semibold text-gray-300">额外参数 (JSON)</label>
                        <textarea
                            name="extra_params"
                            value={JSON.stringify(formData.extra_params || {}, null, 2)}
                            onChange={handleExtraParamsChange}
                            rows={4}
                            className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none font-mono text-sm placeholder-gray-500"
                            placeholder="{}"
                        />
                    </div>
                </div>
            </form>
        </div>
    );
};
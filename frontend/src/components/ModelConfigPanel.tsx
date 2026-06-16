import React, { useEffect, useState } from 'react';
import { X, Save, Key, Cpu, Globe, CheckCircle2 } from 'lucide-react';
import { useSettingsStore } from '../store/settingsStore';
import type { Language } from '../store/settingsStore';
import { useI18n } from '../hooks/useI18n';
import type { ModelConfig } from '../types/model';
import { MODEL_PRESETS } from '../types/model';

const ModelConfigPanel: React.FC = () => {
    const { t } = useI18n();
    const {
        language,
        setLanguage,
        modelConfig,
        setModelConfig,
        setShowSettings,
    } = useSettingsStore();

    const [saved, setSaved] = useState(false);
    const [draft, setDraft] = useState<ModelConfig>(() => ({
        model: modelConfig.model || '',
        api_key: modelConfig.api_key || '',
        base_url: modelConfig.base_url || '',
    }));

    useEffect(() => {
        setDraft({
            model: modelConfig.model || '',
            api_key: modelConfig.api_key || '',
            base_url: modelConfig.base_url || '',
        });
    }, [modelConfig.model, modelConfig.api_key, modelConfig.base_url]);

    const handleSave = () => {
        setModelConfig({
            model: draft.model.trim(),
            api_key: draft.api_key.trim(),
            base_url: draft.base_url?.trim() || '',
        });
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="glass-dark w-full max-w-2xl rounded-3xl border border-white/10 overflow-hidden shadow-2xl animate-in zoom-in-95 duration-300">
                {/* Header */}
                <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-white/5">
                    <div className="flex items-center space-x-3">
                        <Cpu className="text-primary w-6 h-6" />
                        <h2 className="text-xl font-bold">{t.settings.title}</h2>
                    </div>
                    <button
                        onClick={() => setShowSettings(false)}
                        className="p-2 hover:bg-white/10 rounded-xl transition-colors"
                    >
                        <X className="w-6 h-6" />
                    </button>
                </div>

                <div className="p-6 space-y-8 max-h-[70vh] overflow-y-auto custom-scrollbar">
                    {/* Language Section */}
                    <section className="space-y-4">
                        <div className="flex items-center space-x-2 text-lg font-semibold text-primary">
                            <Globe className="w-5 h-5" />
                            <h3>{t.settings.language}</h3>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            {(['en', 'zh'] as Language[]).map((lang) => (
                                <button
                                    key={lang}
                                    onClick={() => setLanguage(lang)}
                                    className={`py-3 rounded-2xl border transition-all font-medium ${language === lang
                                        ? 'bg-primary/20 border-primary text-primary'
                                        : 'bg-white/5 border-white/10 text-text-muted hover:bg-white/10'
                                        }`}
                                >
                                    {lang === 'en' ? 'English' : '简体中文'}
                                </button>
                            ))}
                        </div>
                    </section>

                    {/* API Keys Section */}
                    <section className="space-y-4">
                        <div className="flex items-center space-x-2 text-lg font-semibold text-accent">
                            <Key className="w-5 h-5" />
                            <h3>{t.settings.apiKeys}</h3>
                        </div>
                        <div className="space-y-3">
                            <div className="space-y-1">
                                <label className="text-xs font-bold uppercase tracking-wider text-text-muted px-1">
                                    API Key
                                </label>
                                <input
                                    type="password"
                                    value={draft.api_key}
                                    onChange={(e) => setDraft((prev) => ({ ...prev, api_key: e.target.value }))}
                                    placeholder="Enter API key..."
                                    className="w-full bg-white/5 border rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 transition-all text-sm border-white/10 focus:ring-accent/50"
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs font-bold uppercase tracking-wider text-text-muted px-1">
                                    Base URL
                                </label>
                                <input
                                    type="text"
                                    value={draft.base_url || ''}
                                    onChange={(e) => setDraft((prev) => ({ ...prev, base_url: e.target.value }))}
                                    placeholder="https://api.openai.com/v1"
                                    className="w-full bg-white/5 border rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 transition-all text-sm border-white/10 focus:ring-accent/50"
                                />
                            </div>
                        </div>
                    </section>

                    {/* Model Selection Section */}
                    <section className="space-y-4">
                        <div className="flex items-center space-x-2 text-lg font-semibold text-secondary">
                            <Cpu className="w-5 h-5" />
                            <h3>{t.settings.modelSelection}</h3>
                        </div>
                        <div className="space-y-2">
                            <input
                                list="settings-model-presets"
                                value={draft.model}
                                onChange={(e) => setDraft((prev) => ({ ...prev, model: e.target.value }))}
                                placeholder="gpt-4o"
                                className="w-full bg-white/5 border rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 transition-all text-sm border-white/10 focus:ring-secondary/50"
                            />
                            <datalist id="settings-model-presets">
                                {MODEL_PRESETS.map((preset) => (
                                    <option key={preset.id} value={preset.model} label={preset.label} />
                                ))}
                            </datalist>
                            <p className="text-xs text-text-muted px-1">
                                可选择预设模型或输入自定义模型名称
                            </p>
                        </div>
                    </section>
                </div>

                {/* Footer */}
                <div className="px-6 py-4 bg-white/5 border-t border-white/10 flex justify-end items-center space-x-3">
                    <button
                        onClick={() => setShowSettings(false)}
                        className="px-6 py-2.5 rounded-xl font-semibold text-text-muted hover:bg-white/10 transition-colors"
                    >
                        {t.settings.close}
                    </button>
                    <button
                        onClick={handleSave}
                        className={`px-8 py-2.5 rounded-xl font-bold flex items-center space-x-2 transition-all ${saved
                            ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                            : 'bg-primary text-white hover:bg-primary/90'
                            }`}
                    >
                        {saved ? (
                            <>
                                <CheckCircle2 className="w-5 h-5" />
                                <span>Saved</span>
                            </>
                        ) : (
                            <>
                                <Save className="w-5 h-5" />
                                <span>{t.settings.save}</span>
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ModelConfigPanel;

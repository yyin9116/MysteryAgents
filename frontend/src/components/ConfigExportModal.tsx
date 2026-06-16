import React, { useState } from 'react';
import { Download, Upload, FileJson, FileText, X, AlertCircle, CheckCircle } from 'lucide-react';
import { configService } from '../services/configService';
import type { GameConfigExport, ValidationResult } from '../services/configService';

interface ConfigExportModalProps {
    isOpen: boolean;
    onClose: () => void;
    currentConfig?: any;
    currentAgents?: any[];
}

const ConfigExportModal: React.FC<ConfigExportModalProps> = ({
    isOpen,
    onClose,
    currentConfig,
    currentAgents
}) => {
    const [activeTab, setActiveTab] = useState<'export' | 'import'>('export');
    const [configName, setConfigName] = useState('我的游戏配置');
    const [configDescription, setConfigDescription] = useState('');
    const [exportFormat, setExportFormat] = useState<'json' | 'yaml'>('json');
    const [importContent, setImportContent] = useState('');
    const [importFormat, setImportFormat] = useState<'json' | 'yaml'>('json');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [importedConfig, setImportedConfig] = useState<GameConfigExport | null>(null);
    const [validation, setValidation] = useState<ValidationResult | null>(null);

    if (!isOpen) return null;

    const handleExport = async () => {
        setLoading(true);
        setError(null);
        setSuccess(null);

        try {
            const blob = await configService.exportConfig(
                configName,
                currentConfig || {},
                currentAgents || [],
                undefined,
                exportFormat,
                configDescription
            );

            const filename = `${configName.replace(/\s+/g, '_')}.${exportFormat}`;
            configService.downloadConfig(blob, filename);
            setSuccess(`配置已导出为 ${filename}`);
        } catch (err: any) {
            setError(err.message || '导出失败');
        } finally {
            setLoading(false);
        }
    };

    const handleImportText = async () => {
        if (!importContent.trim()) {
            setError('请输入配置内容');
            return;
        }

        setLoading(true);
        setError(null);
        setSuccess(null);

        try {
            const result = await configService.importConfig(importContent, importFormat);
            setImportedConfig(result.config);
            setValidation(result.validation);

            if (result.validation.valid) {
                setSuccess('配置导入成功！');
            } else {
                setError('配置验证失败，请检查问题');
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || '导入失败');
        } finally {
            setLoading(false);
        }
    };

    const handleImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        setLoading(true);
        setError(null);
        setSuccess(null);

        try {
            const result = await configService.importConfigFile(file);
            setImportedConfig(result.config);
            setValidation(result.validation);

            if (result.validation.valid) {
                setSuccess(`配置从 ${result.filename} 导入成功！`);
            } else {
                setError('配置验证失败，请检查问题');
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message || '文件导入失败');
        } finally {
            setLoading(false);
        }
    };

    const handleApplyConfig = () => {
        if (importedConfig && validation?.valid) {
            // Emit event or callback to apply configuration
            window.dispatchEvent(new CustomEvent('applyGameConfig', { detail: importedConfig }));
            setSuccess('配置已应用！');
            setTimeout(() => onClose(), 1500);
        }
    };

    const handleLoadExample = async () => {
        setLoading(true);
        setError(null);

        try {
            const example = await configService.getExampleConfig('json') as GameConfigExport;
            setImportContent(JSON.stringify(example, null, 2));
            setImportFormat('json');
            setSuccess('示例配置已加载');
        } catch (err: any) {
            setError('加载示例失败');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-900 rounded-3xl border border-white/10 max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-white/10">
                    <h2 className="text-2xl font-bold">配置管理</h2>
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
                        onClick={() => setActiveTab('export')}
                        className={`flex-1 px-6 py-4 font-medium transition-colors ${
                            activeTab === 'export'
                                ? 'bg-white/5 border-b-2 border-primary text-primary'
                                : 'text-text-muted hover:bg-white/5'
                        }`}
                    >
                        <Download className="w-4 h-4 inline mr-2" />
                        导出配置
                    </button>
                    <button
                        onClick={() => setActiveTab('import')}
                        className={`flex-1 px-6 py-4 font-medium transition-colors ${
                            activeTab === 'import'
                                ? 'bg-white/5 border-b-2 border-secondary text-secondary'
                                : 'text-text-muted hover:bg-white/5'
                        }`}
                    >
                        <Upload className="w-4 h-4 inline mr-2" />
                        导入配置
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    {activeTab === 'export' ? (
                        <>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium mb-2">配置名称</label>
                                    <input
                                        type="text"
                                        value={configName}
                                        onChange={(e) => setConfigName(e.target.value)}
                                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/50"
                                        placeholder="例如：经典6人局"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium mb-2">配置描述（可选）</label>
                                    <textarea
                                        value={configDescription}
                                        onChange={(e) => setConfigDescription(e.target.value)}
                                        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/50 h-24 resize-none"
                                        placeholder="描述这个配置的特点..."
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium mb-2">导出格式</label>
                                    <div className="flex gap-3">
                                        <button
                                            onClick={() => setExportFormat('json')}
                                            className={`flex-1 p-4 rounded-xl border transition-all ${
                                                exportFormat === 'json'
                                                    ? 'bg-primary/20 border-primary text-primary'
                                                    : 'bg-white/5 border-white/10 hover:bg-white/10'
                                            }`}
                                        >
                                            <FileJson className="w-6 h-6 mx-auto mb-2" />
                                            <div className="font-medium">JSON</div>
                                            <div className="text-xs text-text-muted">通用格式</div>
                                        </button>
                                        <button
                                            onClick={() => setExportFormat('yaml')}
                                            className={`flex-1 p-4 rounded-xl border transition-all ${
                                                exportFormat === 'yaml'
                                                    ? 'bg-primary/20 border-primary text-primary'
                                                    : 'bg-white/5 border-white/10 hover:bg-white/10'
                                            }`}
                                        >
                                            <FileText className="w-6 h-6 mx-auto mb-2" />
                                            <div className="font-medium">YAML</div>
                                            <div className="text-xs text-text-muted">易读格式</div>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium mb-2">导入方式</label>
                                    <div className="flex gap-3">
                                        <label className="flex-1 p-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 cursor-pointer transition-colors">
                                            <Upload className="w-6 h-6 mx-auto mb-2" />
                                            <div className="font-medium text-center">上传文件</div>
                                            <input
                                                type="file"
                                                accept=".json,.yaml,.yml"
                                                onChange={handleImportFile}
                                                className="hidden"
                                            />
                                        </label>
                                        <button
                                            onClick={handleLoadExample}
                                            className="flex-1 p-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-colors"
                                        >
                                            <FileJson className="w-6 h-6 mx-auto mb-2" />
                                            <div className="font-medium">加载示例</div>
                                        </button>
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-sm font-medium mb-2">或粘贴配置内容</label>
                                    <div className="flex gap-2 mb-2">
                                        <button
                                            onClick={() => setImportFormat('json')}
                                            className={`px-3 py-1 rounded-lg text-sm ${
                                                importFormat === 'json'
                                                    ? 'bg-primary text-white'
                                                    : 'bg-white/5 hover:bg-white/10'
                                            }`}
                                        >
                                            JSON
                                        </button>
                                        <button
                                            onClick={() => setImportFormat('yaml')}
                                            className={`px-3 py-1 rounded-lg text-sm ${
                                                importFormat === 'yaml'
                                                    ? 'bg-primary text-white'
                                                    : 'bg-white/5 hover:bg-white/10'
                                            }`}
                                        >
                                            YAML
                                        </button>
                                    </div>
                                    <textarea
                                        value={importContent}
                                        onChange={(e) => setImportContent(e.target.value)}
                                        className="w-full bg-slate-950 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-secondary/50 h-64 resize-none font-mono text-sm"
                                        placeholder={`粘贴 ${importFormat.toUpperCase()} 配置内容...`}
                                    />
                                </div>

                                {validation && (
                                    <div className={`p-4 rounded-xl border ${
                                        validation.valid
                                            ? 'bg-green-500/10 border-green-500/20'
                                            : 'bg-red-500/10 border-red-500/20'
                                    }`}>
                                        <div className="flex items-center gap-2 mb-2">
                                            {validation.valid ? (
                                                <CheckCircle className="w-5 h-5 text-green-500" />
                                            ) : (
                                                <AlertCircle className="w-5 h-5 text-red-500" />
                                            )}
                                            <span className="font-medium">
                                                {validation.valid ? '验证通过' : '验证失败'}
                                            </span>
                                        </div>
                                        {validation.issues.length > 0 && (
                                            <div className="space-y-1 text-sm">
                                                {validation.issues.map((issue, i) => (
                                                    <div key={i} className="text-red-400">• {issue}</div>
                                                ))}
                                            </div>
                                        )}
                                        {validation.warnings.length > 0 && (
                                            <div className="space-y-1 text-sm mt-2">
                                                {validation.warnings.map((warning, i) => (
                                                    <div key={i} className="text-yellow-400">⚠ {warning}</div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {importedConfig && validation?.valid && (
                                    <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                                        <h4 className="font-medium mb-2">配置预览</h4>
                                        <div className="space-y-1 text-sm text-text-muted">
                                            <div>名称: {importedConfig.name}</div>
                                            <div>Agent数量: {importedConfig.agent_count}</div>
                                            <div>平民词: {importedConfig.civilian_word}</div>
                                            <div>卧底词: {importedConfig.undercover_word}</div>
                                            <div>最大回合: {importedConfig.max_rounds}</div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </>
                    )}

                    {/* Messages */}
                    {error && (
                        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 flex items-start gap-3">
                            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                            <span className="text-red-400 text-sm">{error}</span>
                        </div>
                    )}

                    {success && (
                        <div className="p-4 rounded-xl bg-green-500/10 border border-green-500/20 flex items-start gap-3">
                            <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                            <span className="text-green-400 text-sm">{success}</span>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 p-6 border-t border-white/10">
                    <button
                        onClick={onClose}
                        className="px-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
                    >
                        取消
                    </button>
                    {activeTab === 'export' ? (
                        <button
                            onClick={handleExport}
                            disabled={loading || !configName.trim()}
                            className="px-6 py-3 rounded-xl bg-primary hover:bg-primary/90 text-white font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
                        >
                            {loading ? (
                                <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                            ) : (
                                <Download className="w-5 h-5" />
                            )}
                            导出配置
                        </button>
                    ) : (
                        <>
                            <button
                                onClick={handleImportText}
                                disabled={loading || !importContent.trim()}
                                className="px-6 py-3 rounded-xl bg-secondary hover:bg-secondary/90 text-white font-medium transition-colors disabled:opacity-50"
                            >
                                {loading ? (
                                    <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                                ) : (
                                    '验证配置'
                                )}
                            </button>
                            {importedConfig && validation?.valid && (
                                <button
                                    onClick={handleApplyConfig}
                                    className="px-6 py-3 rounded-xl bg-green-600 hover:bg-green-700 text-white font-medium transition-colors flex items-center gap-2"
                                >
                                    <CheckCircle className="w-5 h-5" />
                                    应用配置
                                </button>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ConfigExportModal;

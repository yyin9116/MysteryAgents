import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Braces,
    Check,
    FileText,
    FlaskConical,
    Loader2,
    Play,
    RotateCcw,
    Save,
    TriangleAlert,
    X,
} from 'lucide-react';
import {
    promptService,
    type PromptTemplateDetail,
    type PromptTemplateSummary,
    type PromptTestRunResult,
} from '../services/promptService';
import { modelConfigService } from '../services/modelConfigService';
import type { ModelConfig } from '../types/modelConfig';
import { getProviderMeta, pickPreferredModelConfig } from '../lib/modelProviders';

interface TestRunState {
    open: boolean;
    running: boolean;
    error: string | null;
    result: PromptTestRunResult | null;
    selectedConfigId: string;
    sampleVars: Record<string, string>;
    showRendered: boolean;
}

const toLlmConfig = (config: ModelConfig | null) => {
    if (!config) return null;
    return {
        provider: config.provider || undefined,
        model: config.model,
        api_key: config.api_key || undefined,
        base_url: config.base_url || undefined,
    };
};

export const PromptManagement: React.FC = () => {
    const [templates, setTemplates] = useState<PromptTemplateSummary[]>([]);
    const [selectedKey, setSelectedKey] = useState<string | null>(null);
    const [detail, setDetail] = useState<PromptTemplateDetail | null>(null);
    const [draft, setDraft] = useState('');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [notice, setNotice] = useState<{ type: 'ok' | 'error'; text: string } | null>(null);
    const [configs, setConfigs] = useState<ModelConfig[]>([]);
    const editorRef = useRef<HTMLTextAreaElement>(null);
    const [testRun, setTestRun] = useState<TestRunState>({
        open: false,
        running: false,
        error: null,
        result: null,
        selectedConfigId: '',
        sampleVars: {},
        showRendered: false,
    });

    const grouped = useMemo(() => {
        const map = new Map<string, PromptTemplateSummary[]>();
        for (const item of templates) {
            const list = map.get(item.group) ?? [];
            list.push(item);
            map.set(item.group, list);
        }
        return Array.from(map.entries());
    }, [templates]);

    const loadTemplates = useCallback(async (preferKey?: string) => {
        setLoading(true);
        try {
            const items = await promptService.listTemplates();
            setTemplates(items);
            setSelectedKey((current) => preferKey ?? current ?? items[0]?.key ?? null);
        } catch {
            setNotice({ type: 'error', text: '模板列表加载失败，请确认后端已启动' });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadTemplates();
        modelConfigService
            .listConfigs()
            .then(setConfigs)
            .catch(() => setConfigs([]));
    }, [loadTemplates]);

    // 选中模板变化时拉详情
    useEffect(() => {
        if (!selectedKey) return;
        let cancelled = false;
        promptService
            .getTemplate(selectedKey)
            .then((data) => {
                if (cancelled) return;
                setDetail(data);
                setDraft(data.content);
                setNotice(null);
            })
            .catch(() => setNotice({ type: 'error', text: '模板详情加载失败' }));
        return () => {
            cancelled = true;
        };
    }, [selectedKey]);

    const dirty = detail !== null && draft !== detail.content;
    const customCount = templates.filter((t) => t.source === 'custom').length;

    const insertVariable = (variable: string) => {
        const el = editorRef.current;
        if (!el) {
            setDraft((d) => `${d}{${variable}}`);
            return;
        }
        const start = el.selectionStart ?? draft.length;
        const end = el.selectionEnd ?? draft.length;
        const next = `${draft.slice(0, start)}{${variable}}${draft.slice(end)}`;
        setDraft(next);
        requestAnimationFrame(() => {
            el.focus();
            const caret = start + variable.length + 2;
            el.setSelectionRange(caret, caret);
        });
    };

    const handleSave = async () => {
        if (!selectedKey || !dirty) return;
        setSaving(true);
        setNotice(null);
        try {
            await promptService.updateTemplate(selectedKey, draft);
            const items = await promptService.listTemplates();
            setTemplates(items);
            const refreshed = await promptService.getTemplate(selectedKey);
            setDetail(refreshed);
            setDraft(refreshed.content);
            setNotice({ type: 'ok', text: '已保存并同步 prompts.yaml，下一局生效' });
        } catch (error) {
            setNotice({ type: 'error', text: error instanceof Error ? error.message : '保存失败' });
        } finally {
            setSaving(false);
        }
    };

    const handleReset = async () => {
        if (!selectedKey || !detail) return;
        setSaving(true);
        setNotice(null);
        try {
            await promptService.resetTemplate(selectedKey);
            const items = await promptService.listTemplates();
            setTemplates(items);
            const refreshed = await promptService.getTemplate(selectedKey);
            setDetail(refreshed);
            setDraft(refreshed.content);
            setNotice({ type: 'ok', text: '已恢复内置默认模板' });
        } catch (error) {
            setNotice({ type: 'error', text: error instanceof Error ? error.message : '恢复失败' });
        } finally {
            setSaving(false);
        }
    };

    const openTestRun = () => {
        if (!detail) return;
        const preferred = pickPreferredModelConfig(configs);
        setTestRun({
            open: true,
            running: false,
            error: null,
            result: null,
            selectedConfigId: preferred?.id ?? configs[0]?.id ?? '',
            sampleVars: { ...detail.sample_vars },
            showRendered: false,
        });
    };

    const runTest = async () => {
        if (!selectedKey) return;
        setTestRun((s) => ({ ...s, running: true, error: null, result: null }));
        try {
            const config = configs.find((c) => c.id === testRun.selectedConfigId) ?? null;
            const result = await promptService.testRun(selectedKey, {
                llm_config: toLlmConfig(config),
                sample_vars: testRun.sampleVars,
            });
            setTestRun((s) => ({ ...s, running: false, result }));
        } catch (error) {
            setTestRun((s) => ({
                ...s,
                running: false,
                error: error instanceof Error ? error.message : '试运行失败',
            }));
        }
    };

    const renderTestModal = () => {
        if (!testRun.open || !detail) return null;
        return (
            <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                <div className="w-full max-w-3xl max-h-[85vh] overflow-y-auto rounded-2xl border border-white/10 bg-gray-900 shadow-2xl">
                    <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
                        <div className="flex items-center gap-3">
                            <FlaskConical className="w-5 h-5 text-primary" />
                            <div>
                                <h3 className="font-bold text-gray-100">试运行 · {detail.name}</h3>
                                <p className="text-xs text-gray-500">
                                    用样例变量渲染模板，真实调用一次模型（不计入对局）
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={() => setTestRun((s) => ({ ...s, open: false }))}
                            className="p-2 rounded-lg text-gray-500 hover:text-gray-200 hover:bg-white/5 transition-colors"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>

                    <div className="px-6 py-4 space-y-4">
                        <div>
                            <label className="text-xs font-medium text-gray-400 mb-1 block">使用模型配置</label>
                            <div className="flex flex-wrap gap-2">
                                {configs.length === 0 && (
                                    <p className="text-sm text-gray-500">
                                        暂无已保存配置，将使用环境变量默认模型
                                    </p>
                                )}
                                {configs.map((config) => {
                                    const meta = getProviderMeta(config.provider);
                                    const selected = testRun.selectedConfigId === config.id;
                                    return (
                                        <button
                                            key={config.id}
                                            onClick={() => setTestRun((s) => ({ ...s, selectedConfigId: config.id }))}
                                            className={`px-3 py-1.5 rounded-lg border text-sm transition-all ${
                                                selected
                                                    ? 'border-primary/60 bg-primary/15 text-gray-100'
                                                    : 'border-white/10 bg-white/5 text-gray-400 hover:text-gray-200'
                                            }`}
                                        >
                                            {config.name}
                                            <span className="ml-2 text-[10px] uppercase tracking-wider opacity-70">
                                                {meta.label}
                                            </span>
                                            {config.provider === 'opencode' && (
                                                <span className="ml-1.5 text-[10px] text-amber-400">推荐</span>
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        <div>
                            <label className="text-xs font-medium text-gray-400 mb-2 block">
                                样例变量（可修改后重跑）
                            </label>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
                                {detail.variables.map((variable) => (
                                    <div key={variable} className="flex items-center gap-2">
                                        <span className="font-mono text-[11px] text-violet-300 w-32 shrink-0 truncate" title={variable}>
                                            {`{${variable}}`}
                                        </span>
                                        <input
                                            value={testRun.sampleVars[variable] ?? ''}
                                            onChange={(e) =>
                                                setTestRun((s) => ({
                                                    ...s,
                                                    sampleVars: { ...s.sampleVars, [variable]: e.target.value },
                                                }))
                                            }
                                            className="flex-1 min-w-0 px-2 py-1.5 bg-gray-800/60 border border-white/10 rounded-lg text-xs text-gray-200 outline-none focus:border-primary/50"
                                        />
                                    </div>
                                ))}
                            </div>
                        </div>

                        {testRun.error && (
                            <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                                <TriangleAlert className="w-4 h-4 mt-0.5 shrink-0" />
                                {testRun.error}
                            </div>
                        )}

                        {testRun.result && (
                            <div className="rounded-xl border border-white/10 bg-black/30 overflow-hidden">
                                <div className="flex items-center gap-2 border-b border-white/10 px-4 py-2">
                                    <button
                                        onClick={() => setTestRun((s) => ({ ...s, showRendered: false }))}
                                        className={`px-3 py-1 rounded-lg text-xs transition-colors ${
                                            !testRun.showRendered
                                                ? 'bg-emerald-500/20 text-emerald-300'
                                                : 'text-gray-500 hover:text-gray-300'
                                        }`}
                                    >
                                        模型输出
                                    </button>
                                    <button
                                        onClick={() => setTestRun((s) => ({ ...s, showRendered: true }))}
                                        className={`px-3 py-1 rounded-lg text-xs transition-colors ${
                                            testRun.showRendered
                                                ? 'bg-violet-500/20 text-violet-300'
                                                : 'text-gray-500 hover:text-gray-300'
                                        }`}
                                    >
                                        渲染后的完整提示词
                                    </button>
                                </div>
                                <pre className="px-4 py-3 text-xs leading-relaxed whitespace-pre-wrap text-gray-200 max-h-72 overflow-y-auto font-mono">
                                    {testRun.showRendered
                                        ? testRun.result.rendered_prompt
                                        : testRun.result.output || '（模型返回为空）'}
                                </pre>
                            </div>
                        )}
                    </div>

                    <div className="flex justify-end gap-3 border-t border-white/10 px-6 py-4">
                        <button
                            onClick={runTest}
                            disabled={testRun.running}
                            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary/90 transition-all active:scale-95 disabled:opacity-50"
                        >
                            {testRun.running ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                                <Play className="w-4 h-4" />
                            )}
                            {testRun.running ? '调用中…' : '运行一次'}
                        </button>
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="space-y-6">
            {/* 顶栏 */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-100">提示词管理</h1>
                    <p className="text-sm text-gray-500 mt-1">
                        玩家模型调用的提示词模板 · 共 {templates.length} 个 · {customCount} 个已自定义 · 保存即写入 prompts.yaml，下一局生效
                    </p>
                </div>
            </div>

            {notice && (
                <div
                    className={`flex items-center gap-2 rounded-xl border px-4 py-3 text-sm ${
                        notice.type === 'ok'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                            : 'border-red-500/30 bg-red-500/10 text-red-300'
                    }`}
                >
                    {notice.type === 'ok' ? <Check className="w-4 h-4" /> : <TriangleAlert className="w-4 h-4" />}
                    {notice.text}
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6">
                {/* 移动端：紧凑下拉选择，避免模板列表占满首屏 */}
                <div className="lg:hidden rounded-2xl border border-white/10 bg-gray-900/50 p-3">
                    <label className="font-mono text-[11px] uppercase tracking-wider text-gray-600 block mb-2">
                        模板库 Templates
                    </label>
                    {loading ? (
                        <div className="flex items-center gap-2 text-sm text-gray-500 py-3 justify-center">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            加载中…
                        </div>
                    ) : (
                        <select
                            value={selectedKey ?? ''}
                            onChange={(e) => setSelectedKey(e.target.value)}
                            className="w-full rounded-xl border border-white/10 bg-[#12101c] px-3 py-2.5 text-sm text-gray-100 outline-none focus:border-primary/60"
                        >
                            {grouped.map(([group, items]) => (
                                <optgroup key={group} label={group}>
                                    {items.map((item) => (
                                        <option key={item.key} value={item.key}>
                                            {item.source === 'custom' ? '已自定义 · ' : ''}
                                            {item.name}
                                        </option>
                                    ))}
                                </optgroup>
                            ))}
                        </select>
                    )}
                    <p className="mt-2 text-[11px] text-gray-600">
                        「已自定义」= 覆盖了默认模板的条目
                    </p>
                </div>

                {/* 左栏：模板库（桌面端） */}
                <div className="hidden lg:block rounded-2xl border border-white/10 bg-gray-900/50 p-4 h-fit">
                    <p className="font-mono text-[11px] uppercase tracking-wider text-gray-600 mb-3">
                        模板库 Templates
                    </p>
                    {loading ? (
                        <div className="flex items-center gap-2 text-sm text-gray-500 py-6 justify-center">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            加载中…
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {grouped.map(([group, items]) => (
                                <div key={group}>
                                    <p className="text-xs font-medium text-gray-400 mb-2">{group}</p>
                                    <div className="space-y-1.5">
                                        {items.map((item) => {
                                            const selected = selectedKey === item.key;
                                            return (
                                                <button
                                                    key={item.key}
                                                    onClick={() => setSelectedKey(item.key)}
                                                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border text-left transition-all ${
                                                        selected
                                                            ? 'border-primary/60 bg-primary/15'
                                                            : 'border-transparent bg-white/[0.04] hover:bg-white/[0.08]'
                                                    }`}
                                                >
                                                    <span
                                                        className={`w-2 h-2 rounded-full shrink-0 ${
                                                            item.source === 'custom'
                                                                ? 'bg-amber-400'
                                                                : 'bg-violet-400/50'
                                                        }`}
                                                    />
                                                    <span className="min-w-0">
                                                        <span
                                                            className={`block text-sm truncate ${
                                                                selected ? 'text-gray-100 font-medium' : 'text-gray-300'
                                                            }`}
                                                        >
                                                            {item.name}
                                                        </span>
                                                        <span className="block font-mono text-[10px] text-gray-500 truncate">
                                                            {item.key} · ~{item.tokens} tokens
                                                        </span>
                                                    </span>
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                    <p className="mt-4 text-[11px] leading-relaxed text-gray-600">
                        <span className="inline-block w-2 h-2 rounded-full bg-amber-400 mr-1.5 align-middle" />
                        金点 = 已自定义（prompts.yaml）
                        <br />
                        <span className="inline-block w-2 h-2 rounded-full bg-violet-400/50 mr-1.5 align-middle" />
                        紫点 = 内置默认
                    </p>
                </div>

                {/* 右栏：编辑器 */}
                <div className="space-y-4">
                    {detail ? (
                        <>
                            <div className="flex flex-wrap items-center gap-3">
                                <h2 className="text-lg font-bold text-gray-100">{detail.name}</h2>
                                <span className="px-2.5 py-0.5 rounded-full border border-white/10 bg-white/5 text-[11px] text-gray-400">
                                    {detail.source === 'custom' ? '自定义 · prompts.yaml' : '内置默认 · 可覆盖'}
                                </span>
                                <span className="font-mono text-[11px] text-gray-500">
                                    {detail.key}
                                </span>
                                {dirty && (
                                    <span className="px-2.5 py-0.5 rounded-full border border-amber-400/40 bg-amber-400/10 text-[11px] text-amber-300">
                                        ● 未保存修改
                                    </span>
                                )}
                            </div>

                            <p className="text-sm text-gray-500">{detail.description}</p>

                            {/* 变量卡 */}
                            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
                                <p className="font-mono text-[11px] uppercase tracking-wider text-gray-600 mb-3 flex items-center gap-1.5">
                                    <Braces className="w-3.5 h-3.5" />
                                    可用变量 · 点击插入光标处
                                </p>
                                <div className="flex flex-wrap gap-2">
                                    {detail.variables.map((variable) => (
                                        <button
                                            key={variable}
                                            onClick={() => insertVariable(variable)}
                                            className="px-2.5 py-1 rounded-lg border border-violet-400/30 bg-violet-500/10 font-mono text-xs text-violet-300 hover:bg-violet-500/20 transition-colors"
                                        >
                                            {`{${variable}}`}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* 编辑器卡 */}
                            <div className="rounded-2xl border border-white/10 bg-gray-900/50 overflow-hidden">
                                <div className="flex items-center justify-between border-b border-white/10 bg-black/25 px-5 py-2.5">
                                    <span className="font-mono text-xs text-gray-400 flex items-center gap-2">
                                        <FileText className="w-3.5 h-3.5" />
                                        {detail.key}.yaml
                                    </span>
                                    <span className="font-mono text-[11px] text-gray-600">
                                        {draft.split('\n').length} 行 · ~
                                        {Math.max(1, Math.round(draft.length * 0.55))} tokens
                                    </span>
                                </div>
                                <textarea
                                    ref={editorRef}
                                    value={draft}
                                    onChange={(e) => setDraft(e.target.value)}
                                    spellCheck={false}
                                    className="w-full h-[420px] bg-black/30 px-5 py-4 font-mono text-xs leading-relaxed text-gray-300 outline-none resize-y placeholder:text-gray-600"
                                    placeholder="模板内容，使用 {variable} 占位符…"
                                />
                            </div>

                            {/* 底部按钮行 */}
                            <div className="flex flex-wrap items-center gap-3">
                                <button
                                    onClick={handleReset}
                                    disabled={saving || detail.source !== 'custom' && !dirty}
                                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-white/10 bg-white/5 text-sm text-gray-400 hover:text-gray-200 hover:bg-white/10 transition-all active:scale-95 disabled:opacity-40"
                                >
                                    <RotateCcw className="w-4 h-4" />
                                    恢复默认
                                </button>
                                <button
                                    onClick={openTestRun}
                                    disabled={saving}
                                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-primary/50 bg-primary/15 text-sm text-gray-100 hover:bg-primary/25 transition-all active:scale-95 disabled:opacity-40"
                                >
                                    <Play className="w-4 h-4" />
                                    试运行（真实调用一次模型）
                                </button>
                                <div className="flex-1" />
                                <button
                                    onClick={handleSave}
                                    disabled={saving || !dirty}
                                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gold text-[#171420] text-sm font-bold hover:bg-gold/85 transition-all active:scale-95 disabled:opacity-40"
                                >
                                    {saving ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Save className="w-4 h-4" />
                                    )}
                                    保存并同步 YAML
                                </button>
                            </div>
                        </>
                    ) : (
                        !loading && (
                            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-10 text-center text-sm text-gray-500">
                                从左侧选择一个提示词模板开始编辑
                            </div>
                        )
                    )}
                </div>
            </div>

            {renderTestModal()}
        </div>
    );
};

export default PromptManagement;

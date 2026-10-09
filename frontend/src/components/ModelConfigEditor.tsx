import { useEffect, useMemo, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AlertCircle, CheckCircle2, Eye, EyeOff, Play, RefreshCw, Save } from 'lucide-react';
import type { ModelConfig, ModelConfigCreate, ModelConfigTestResponse, ModelConfigUpdate } from '../types/modelConfig';
import { modelConfigService } from '../services/modelConfigService';
import { PROVIDER_META, RECOMMENDED_PROVIDER, getProviderMeta, shouldAutoFillBaseUrl } from '../lib/modelProviders';
import { Button } from './ui';
import { Input, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Slider, Textarea } from './shadcn';

interface ModelConfigEditorProps {
    config: ModelConfig | null;
    onSave: (payload: ModelConfigCreate | ModelConfigUpdate) => Promise<void>;
    isNew?: boolean;
}

/** 表单校验规则：全部声明在 zod schema，组件内不再手写 if 判断 */
const formSchema = z.object({
    name: z.string().trim().min(1, '请填写配置名称').max(100, '不超过 100 个字符'),
    provider: z.string().min(1, '请选择服务商'),
    model: z.string().trim().min(1, '请填写模型 ID（如 gpt-4o、deepseek-chat）').max(100, '不超过 100 个字符'),
    api_key: z.string().trim().max(255, '不超过 255 个字符').optional(),
    base_url: z
        .string()
        .trim()
        .max(255)
        .refine((v) => v === '' || /^https?:\/\//.test(v), 'Base URL 需以 http(s):// 开头')
        .optional(),
    temperature: z.number().min(0, '不能小于 0').max(2, '不能大于 2'),
    max_tokens: z
        .string()
        .refine((v) => v === '' || (/^\d+$/.test(v) && Number(v) >= 1), '需为正整数（可留空）'),
    description: z.string().max(500, '不超过 500 个字符').optional(),
    extra_params_json: z.string().refine(
        (v) => {
            try {
                JSON.parse(v || '{}');
                return true;
            } catch {
                return false;
            }
        },
        { message: 'JSON 格式错误' }
    ),
});

type FormValues = z.infer<typeof formSchema>;

const buildDefaultValues = (config: ModelConfig | null, isNew: boolean): FormValues => ({
    name: config?.name ?? (isNew ? '新配置' : ''),
    provider: config?.provider ?? RECOMMENDED_PROVIDER,
    model: config?.model ?? '',
    api_key: config?.api_key ?? '',
    base_url: config?.base_url ?? '',
    temperature: config?.temperature ?? 0.7,
    max_tokens: config?.max_tokens != null ? String(config.max_tokens) : '2000',
    description: config?.description ?? '',
    extra_params_json: JSON.stringify(config?.extra_params ?? {}, null, 2),
});

const extractApiError = (error: unknown, fallback: string): string => {
    const axiosDetail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    if (axiosDetail) return axiosDetail;
    if (error instanceof Error && error.message) return error.message;
    return fallback;
};

export const ModelConfigEditor: React.FC<ModelConfigEditorProps> = ({ config, onSave, isNew = false }) => {
    const [testing, setTesting] = useState(false);
    const [testResult, setTestResult] = useState<ModelConfigTestResponse | null>(null);
    const [saving, setSaving] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);
    const [showKey, setShowKey] = useState(false);

    const {
        register,
        handleSubmit: handleSubmitForm,
        reset,
        watch,
        setValue,
        getValues,
        trigger,
        formState: { errors },
    } = useForm<FormValues>({
        resolver: zodResolver(formSchema),
        mode: 'onTouched',
        defaultValues: buildDefaultValues(config, isNew),
    });

    useEffect(() => {
        reset(buildDefaultValues(config, isNew));
        setTestResult(null);
        setSubmitError(null);
    }, [config, isNew, reset]);

    const provider = watch('provider');
    const model = watch('model');
    const apiKey = watch('api_key');
    const baseUrl = watch('base_url');
    const temperature = watch('temperature');
    const meta = getProviderMeta(provider);
    const isGpt5 = /^gpt-5/i.test(model ?? '');

    // ---- 服务商模型列表自动获取：防抖请求端点 /models，失败静默回退静态目录 ----
    const [remoteModels, setRemoteModels] = useState<string[] | null>(null);
    const [remoteStatus, setRemoteStatus] = useState<'idle' | 'loading' | 'ok' | 'fail'>('idle');
    const fetchSeq = useRef(0);

    useEffect(() => {
        const seq = ++fetchSeq.current;
        setRemoteModels(null);
        const effectiveBase = (baseUrl ?? '').trim() || meta.defaultBaseUrl;
        const canFetch =
            !!provider &&
            provider !== 'mock' &&
            !!effectiveBase &&
            ((apiKey ?? '').trim() !== '' || !meta.keyRequired);
        if (!canFetch) {
            setRemoteStatus('idle');
            return;
        }
        setRemoteStatus('loading');
        const timer = setTimeout(() => {
            modelConfigService
                .listModelsDraft({
                    provider,
                    api_key: (apiKey ?? '').trim() || null,
                    base_url: effectiveBase,
                })
                .then((res) => {
                    if (fetchSeq.current !== seq) return;
                    setRemoteModels(res.models);
                    setRemoteStatus(res.models.length ? 'ok' : 'fail');
                })
                .catch(() => {
                    if (fetchSeq.current !== seq) return;
                    setRemoteModels(null);
                    setRemoteStatus('fail');
                });
        }, 700);
        return () => clearTimeout(timer);
        // meta 随 provider 派生，无需单独依赖
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [provider, apiKey, baseUrl]);

    /** 模型建议：远端列表优先，静态目录兜底，去重合并 */
    const modelSuggestions = useMemo(() => {
        const seen = new Set<string>();
        const merged: string[] = [];
        for (const m of [...(remoteModels ?? []), ...meta.models]) {
            if (!seen.has(m)) {
                seen.add(m);
                merged.push(m);
            }
        }
        return merged;
    }, [remoteModels, meta.models]);

    /** 服务商切换：base_url 自动预填（仅当当前值为空或等于其它默认值），模型建议列表随映射切换 */
    const handleProviderChange = (next: string) => {
        setValue('provider', next, { shouldDirty: true });
        if (shouldAutoFillBaseUrl(getValues('base_url'))) {
            setValue('base_url', getProviderMeta(next).defaultBaseUrl, { shouldDirty: true });
        }
        setTestResult(null);
    };

    const buildPayload = (values: FormValues): ModelConfigCreate =>
        ({
            name: values.name.trim(),
            provider: values.provider,
            model: values.model.trim(),
            temperature: values.temperature,
            max_tokens: values.max_tokens === '' ? null : Number(values.max_tokens),
            api_key: values.api_key?.trim() || null,
            base_url: values.base_url?.trim() || null,
            description: values.description?.trim() || null,
            extra_params: JSON.parse(values.extra_params_json || '{}'),
        }) as ModelConfigCreate;

    const handleSave = handleSubmitForm(async (values) => {
        setSubmitError(null);
        setSaving(true);
        try {
            await onSave(buildPayload(values));
        } catch (error) {
            setSubmitError(extractApiError(error, '保存失败，请稍后重试'));
        } finally {
            setSaving(false);
        }
    });

    const handleTest = async () => {
        if (testing) return;
        setTestResult(null);
        const valid = await trigger(['name', 'provider', 'model', 'max_tokens', 'extra_params_json']);
        if (!valid) return;

        setTesting(true);
        try {
            const payload = buildPayload(getValues());
            // 统一用草稿测试接口：无论是否已保存，测的都是表单当前值
            const res = await modelConfigService.testDraft({
                provider: payload.provider,
                model: payload.model,
                api_key: payload.api_key,
                base_url: payload.base_url,
                temperature: payload.temperature,
                max_tokens: payload.max_tokens,
                extra_params: payload.extra_params,
            });
            setTestResult(res);
        } catch (error) {
            setTestResult({ success: false, message: extractApiError(error, '测试失败') });
        } finally {
            setTesting(false);
        }
    };

    const fieldError = (msg?: string) =>
        msg ? <p className="text-xs text-danger">{msg}</p> : null;

    return (
        <form noValidate onSubmit={handleSave} className="max-w-4xl mx-auto p-4 sm:p-8">
            {/* 头部：标题 + 协议徽标 + 操作 */}
            <div className="flex flex-wrap justify-between items-center gap-3 sm:gap-4 mb-5 sm:mb-8 pb-4 sm:pb-5 border-b border-line">
                <div className="min-w-0">
                    <h2 className="text-xl sm:text-2xl font-bold text-text-primary truncate">
                        {isNew ? '新建配置' : config ? `编辑：${config.name}` : '选择或新建配置'}
                    </h2>
                    <div className="mt-2 flex items-center gap-2 text-xs">
                        <span className="rounded-full border border-violet/40 bg-violet/12 px-3 py-1 font-hud uppercase tracking-wider text-violet">
                            {meta.label}
                        </span>
                        <span
                            className={`rounded-full border px-3 py-1 ${
                                meta.keyRequired
                                    ? 'border-gold/35 bg-gold/10 text-gold'
                                    : 'border-success/30 bg-success/10 text-success'
                            }`}
                        >
                            {meta.keyRequired ? '需要 API Key' : '无需 API Key'}
                        </span>
                    </div>
                </div>
                <div className="flex gap-3">
                    <Button variant="ghost" onClick={handleTest} disabled={testing}>
                        {testing ? (
                            <span className="h-4 w-4 rounded-full border-2 border-violet border-t-transparent animate-spin" />
                        ) : (
                            <Play size={16} />
                        )}
                        测试连接
                    </Button>
                    <Button variant="gold" type="submit" disabled={saving}>
                        <Save size={16} />
                        {saving ? '保存中...' : '保存配置'}
                    </Button>
                </div>
            </div>

            {/* 测试结果 / 保存错误横幅 */}
            {testResult && (
                <div
                    className={`mb-6 p-4 rounded-xl flex items-start gap-3 border ${
                        testResult.success
                            ? 'bg-success/10 border-success/35 text-success'
                            : 'bg-danger/10 border-danger/40 text-danger'
                    }`}
                >
                    {testResult.success ? (
                        <CheckCircle2 size={20} className="mt-0.5 shrink-0" />
                    ) : (
                        <AlertCircle size={20} className="mt-0.5 shrink-0" />
                    )}
                    <div className="min-w-0">
                        <p className="font-semibold">{testResult.success ? '连接成功' : '连接失败'}</p>
                        <p className="text-sm opacity-90 break-all">{testResult.message}</p>
                        {testResult.duration_ms != null && (
                            <p className="font-hud text-xs mt-1 opacity-75">耗时 {testResult.duration_ms}ms</p>
                        )}
                    </div>
                </div>
            )}
            {submitError && (
                <div className="mb-6 p-4 rounded-xl flex items-start gap-3 bg-danger/10 border border-danger/40 text-danger">
                    <AlertCircle size={20} className="mt-0.5 shrink-0" />
                    <div>
                        <p className="font-semibold">保存失败</p>
                        <p className="text-sm opacity-90 break-all">{submitError}</p>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-5">
                <div className="space-y-2">
                    <Label htmlFor="mc-name">配置名称</Label>
                    <Input id="mc-name" placeholder="如：GPT-4o 生产环境" {...register('name')} />
                    {fieldError(errors.name?.message)}
                </div>

                <div className="space-y-2">
                    <Label>服务商（协议）</Label>
                    <Select value={provider} onValueChange={handleProviderChange}>
                        <SelectTrigger>
                            <SelectValue placeholder="选择服务商" />
                        </SelectTrigger>
                        <SelectContent>
                            {Object.entries(PROVIDER_META).map(([key, m]) => (
                                <SelectItem key={key} value={key}>
                                    {m.label}
                                    {m.recommended && (
                                        <span className="ml-2 rounded-full bg-[--ds-accent-gold]/15 px-1.5 py-0.5 text-[10px] leading-none text-[--ds-accent-gold]">
                                            推荐
                                        </span>
                                    )}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    {fieldError(errors.provider?.message)}
                </div>

                <div className="space-y-2">
                    <Label htmlFor="mc-model">模型 ID</Label>
                    <Input id="mc-model" list="provider-model-suggestions" placeholder="如 gpt-4o、deepseek-chat" {...register('model')} />
                    <datalist id="provider-model-suggestions">
                        {modelSuggestions.map((m) => (
                            <option key={m} value={m} />
                        ))}
                    </datalist>
                    {remoteStatus === 'loading' && (
                        <p className="flex items-center gap-1.5 font-hud text-[11px] text-text-secondary/60">
                            <RefreshCw size={11} className="animate-spin" />
                            正在从服务商同步模型列表…
                        </p>
                    )}
                    {remoteStatus === 'ok' && (
                        <p className="font-hud text-[11px] text-success/80">
                            已从服务商同步 {remoteModels?.length ?? 0} 个模型
                        </p>
                    )}
                    {remoteStatus === 'fail' && (
                        <p className="font-hud text-[11px] text-text-secondary/45">
                            在线获取不可用（未填 Key 或端点不通），已显示常用模型，仍可自由输入
                        </p>
                    )}
                    {fieldError(errors.model?.message)}
                </div>

                <div className="space-y-2">
                    <Label htmlFor="mc-key">API Key{!meta.keyRequired && '（可选）'}</Label>
                    <div className="relative">
                        <Input
                            id="mc-key"
                            type={showKey ? 'text' : 'password'}
                            placeholder={meta.keyPlaceholder}
                            className="pr-10"
                            {...register('api_key')}
                        />
                        <button
                            type="button"
                            onClick={() => setShowKey((v) => !v)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary/60 hover:text-text-primary"
                            tabIndex={-1}
                        >
                            {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                    </div>
                    {fieldError(errors.api_key?.message)}
                </div>

                <div className="md:col-span-2 space-y-2">
                    <Label htmlFor="mc-base-url">Base URL（可留空使用协议默认值）</Label>
                    <Input id="mc-base-url" placeholder={meta.defaultBaseUrl || 'https://...'} {...register('base_url')} />
                    {fieldError(errors.base_url?.message)}
                </div>

                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <Label>Temperature</Label>
                        <span className="font-hud text-sm text-violet">{temperature?.toFixed(1)}</span>
                    </div>
                    <Slider
                        min={0}
                        max={2}
                        step={0.1}
                        value={[temperature ?? 0.7]}
                        onValueChange={([v]) => setValue('temperature', v, { shouldDirty: true })}
                    />
                    {fieldError(errors.temperature?.message)}
                    {isGpt5 && (
                        <p className="text-xs text-gold/85">注意：GPT-5 系列仅支持 temperature=1，过高值会被上游拒绝。</p>
                    )}
                </div>

                <div className="space-y-2">
                    <Label htmlFor="mc-max-tokens">Max Tokens（可留空）</Label>
                    <Input id="mc-max-tokens" inputMode="numeric" placeholder="2000" {...register('max_tokens')} />
                    {fieldError(errors.max_tokens?.message)}
                </div>

                <div className="md:col-span-2 space-y-2">
                    <Label htmlFor="mc-desc">描述</Label>
                    <Textarea id="mc-desc" rows={2} placeholder="简短说明此配置的用途" {...register('description')} />
                    {fieldError(errors.description?.message)}
                </div>

                <div className="md:col-span-2 space-y-2">
                    <Label htmlFor="mc-extra">额外参数（JSON）</Label>
                    <Textarea id="mc-extra" rows={4} className="font-mono text-xs" placeholder="{}" {...register('extra_params_json')} />
                    {fieldError(errors.extra_params_json?.message)}
                </div>
            </div>

            {/* 协议说明 */}
            {(meta.hint || isGpt5) && (
                <p className="mt-6 text-xs text-text-secondary/70">{meta.hint}</p>
            )}
        </form>
    );
};

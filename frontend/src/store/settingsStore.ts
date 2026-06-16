import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ModelConfig as LegacyModelConfig } from '../types/model';
import { MODEL_PRESETS } from '../types/model';
import type {
    ModelConfig as ApiModelConfig,
    ModelConfigCreate,
    ModelConfigExport,
    ModelConfigImport,
    ModelConfigImportResult,
    ModelConfigTestResponse,
    ModelConfigUpdate,
} from '../types/modelConfig';
import type { UsageStatsFilters, UsageStatsResponse } from '../types/usage';
import { modelConfigService } from '../services/modelConfigService';
import { usageService } from '../services/usageService';

export type Language = 'en' | 'zh';

interface SettingsStore {
    language: Language;
    modelConfig: LegacyModelConfig;
    showSettings: boolean;
    modelConfigs: ApiModelConfig[];
    modelConfigsLoading: boolean;
    modelConfigsError: string | null;
    usageStatsCache: Record<string, UsageStatsResponse>;
    usageStatsLoading: boolean;
    usageStatsError: string | null;

    setLanguage: (lang: Language) => void;
    setModelConfig: (config: Partial<LegacyModelConfig>) => void;
    setShowSettings: (show: boolean) => void;
    fetchModelConfigs: (options?: { skip?: number; limit?: number }) => Promise<ApiModelConfig[]>;
    createModelConfig: (payload: ModelConfigCreate) => Promise<ApiModelConfig>;
    updateModelConfig: (configId: string, payload: ModelConfigUpdate) => Promise<ApiModelConfig>;
    deleteModelConfig: (configId: string) => Promise<ApiModelConfig>;
    exportModelConfigs: () => Promise<ModelConfigExport>;
    importModelConfigs: (payload: ModelConfigImport) => Promise<ModelConfigImportResult>;
    testModelConfig: (configId: string, prompt?: string) => Promise<ModelConfigTestResponse>;
    getUsageStats: (
        filters?: UsageStatsFilters,
        options?: { force?: boolean }
    ) => Promise<UsageStatsResponse>;
    invalidateUsageCache: () => void;
}

const DEFAULT_MODEL_CONFIG: LegacyModelConfig = {
    model: MODEL_PRESETS[0]?.model || 'gpt-4o',
    api_key: '',
    base_url: '',
};

const getErrorMessage = (error: unknown) =>
    error instanceof Error ? error.message : 'Unknown error';

const normalizeUsageFilters = (filters: UsageStatsFilters = {}): UsageStatsFilters => ({
    ...filters,
    group_by: filters.group_by ?? 'day',
});

const buildUsageCacheKey = (filters: UsageStatsFilters = {}) => {
    const normalized = normalizeUsageFilters(filters);
    const params = new URLSearchParams();
    if (normalized.start_date) {
        params.set('start_date', normalized.start_date);
    }
    if (normalized.end_date) {
        params.set('end_date', normalized.end_date);
    }
    if (normalized.model) {
        params.set('model', normalized.model);
    }
    if (normalized.group_by) {
        params.set('group_by', normalized.group_by);
    }
    return params.toString();
};

const buildOptimisticConfig = (payload: ModelConfigCreate, tempId: string): ApiModelConfig => {
    const now = new Date().toISOString();
    return {
        ...payload,
        id: tempId,
        version: 1,
        created_at: now,
        updated_at: now,
        extra_params: payload.extra_params ?? {},
    };
};

const stripSensitiveFields = (config: LegacyModelConfig): LegacyModelConfig => ({
    model: config.model,
    api_key: '',
    base_url: config.base_url ?? '',
});

export const useSettingsStore = create<SettingsStore>()(
    persist(
        (set, get) => ({
            language: 'zh',
            modelConfig: DEFAULT_MODEL_CONFIG,
            showSettings: false,
            modelConfigs: [],
            modelConfigsLoading: false,
            modelConfigsError: null,
            usageStatsCache: {},
            usageStatsLoading: false,
            usageStatsError: null,

            setLanguage: (language) => set({ language }),
            setModelConfig: (config) =>
                set((state) => ({
                    modelConfig: { ...state.modelConfig, ...config },
                })),
            setShowSettings: (showSettings) => set({ showSettings }),
            fetchModelConfigs: async (options) => {
                set({ modelConfigsLoading: true, modelConfigsError: null });
                try {
                    const configs = await modelConfigService.listConfigs(
                        options?.skip ?? 0,
                        options?.limit ?? 100
                    );
                    set({ modelConfigs: configs, modelConfigsLoading: false });
                    return configs;
                } catch (error) {
                    set({
                        modelConfigsLoading: false,
                        modelConfigsError: getErrorMessage(error),
                    });
                    throw error;
                }
            },
            createModelConfig: async (payload) => {
                const tempId = `temp-${Date.now()}`;
                const optimistic = buildOptimisticConfig(payload, tempId);
                set((state) => ({
                    modelConfigs: [optimistic, ...state.modelConfigs],
                    modelConfigsError: null,
                    usageStatsCache: {},
                }));
                try {
                    const created = await modelConfigService.createConfig(payload);
                    set((state) => ({
                        modelConfigs: state.modelConfigs.map((config) =>
                            config.id === tempId ? created : config
                        ),
                    }));
                    return created;
                } catch (error) {
                    set((state) => ({
                        modelConfigs: state.modelConfigs.filter((config) => config.id !== tempId),
                        modelConfigsError: getErrorMessage(error),
                    }));
                    throw error;
                }
            },
            updateModelConfig: async (configId, payload) => {
                const currentConfigs = get().modelConfigs;
                const previous = currentConfigs.find((config) => config.id === configId);
                if (previous) {
                    const updatedOptimistic: ApiModelConfig = {
                        ...previous,
                        ...payload,
                        extra_params:
                            payload.extra_params === undefined
                                ? previous.extra_params
                                : payload.extra_params ?? {},
                    };
                    set((state) => ({
                        modelConfigs: state.modelConfigs.map((config) =>
                            config.id === configId ? updatedOptimistic : config
                        ),
                        modelConfigsError: null,
                        usageStatsCache: {},
                    }));
                }

                try {
                    const updated = await modelConfigService.updateConfig(configId, payload);
                    set((state) => ({
                        modelConfigs: state.modelConfigs.some((config) => config.id === configId)
                            ? state.modelConfigs.map((config) =>
                                  config.id === configId ? updated : config
                              )
                            : [updated, ...state.modelConfigs],
                    }));
                    return updated;
                } catch (error) {
                    if (previous) {
                        set((state) => ({
                            modelConfigs: state.modelConfigs.map((config) =>
                                config.id === configId ? previous : config
                            ),
                            modelConfigsError: getErrorMessage(error),
                        }));
                    } else {
                        set({ modelConfigsError: getErrorMessage(error) });
                    }
                    throw error;
                }
            },
            deleteModelConfig: async (configId) => {
                const previousConfigs = get().modelConfigs;
                set((state) => ({
                    modelConfigs: state.modelConfigs.filter((config) => config.id !== configId),
                    modelConfigsError: null,
                    usageStatsCache: {},
                }));
                try {
                    const deleted = await modelConfigService.deleteConfig(configId);
                    return deleted;
                } catch (error) {
                    set({
                        modelConfigs: previousConfigs,
                        modelConfigsError: getErrorMessage(error),
                    });
                    throw error;
                }
            },
            exportModelConfigs: async () => modelConfigService.exportConfigs(),
            importModelConfigs: async (payload) => {
                set({ modelConfigsError: null });
                try {
                    const result = await modelConfigService.importConfigs(payload);
                    await get().fetchModelConfigs();
                    set({ usageStatsCache: {} });
                    return result;
                } catch (error) {
                    set({ modelConfigsError: getErrorMessage(error) });
                    throw error;
                }
            },
            testModelConfig: async (configId, prompt) =>
                modelConfigService.testConfig(configId, { prompt }),
            getUsageStats: async (filters, options) => {
                const normalized = normalizeUsageFilters(filters);
                const cacheKey = buildUsageCacheKey(normalized);
                if (!options?.force) {
                    const cached = get().usageStatsCache[cacheKey];
                    if (cached) {
                        return cached;
                    }
                }
                set({ usageStatsLoading: true, usageStatsError: null });
                try {
                    const stats = await usageService.getUsageStats(normalized);
                    set((state) => ({
                        usageStatsCache: { ...state.usageStatsCache, [cacheKey]: stats },
                        usageStatsLoading: false,
                    }));
                    return stats;
                } catch (error) {
                    set({
                        usageStatsLoading: false,
                        usageStatsError: getErrorMessage(error),
                    });
                    throw error;
                }
            },
            invalidateUsageCache: () => set({ usageStatsCache: {} }),
        }),
        {
            name: 'app-settings',
            version: 5,
            partialize: (state) => ({
                language: state.language,
                modelConfig: stripSensitiveFields(state.modelConfig),
                modelConfigs: state.modelConfigs,
            }),
            migrate: (persistedState) => {
                const state = persistedState as any;
                const rawConfig = state?.modelConfig;

                const modelConfig: LegacyModelConfig = stripSensitiveFields({
                    model: typeof rawConfig?.model === 'string' ? rawConfig.model : DEFAULT_MODEL_CONFIG.model,
                    api_key: typeof rawConfig?.api_key === 'string' ? rawConfig.api_key : DEFAULT_MODEL_CONFIG.api_key,
                    base_url: typeof rawConfig?.base_url === 'string' ? rawConfig.base_url : DEFAULT_MODEL_CONFIG.base_url,
                });

                return {
                    language: state?.language === 'en' || state?.language === 'zh' ? state.language : 'zh',
                    modelConfig,
                    modelConfigs: Array.isArray(state?.modelConfigs) ? state.modelConfigs : [],
                } as any;
            },
        }
    )
);

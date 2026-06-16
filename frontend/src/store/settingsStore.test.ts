import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
    ModelConfig,
    ModelConfigCreate,
    ModelConfigImportResult,
    ModelConfigUpdate,
} from '../types/modelConfig';
import type { UsageStatsResponse } from '../types/usage';
import { useSettingsStore } from './settingsStore';
import { modelConfigService } from '../services/modelConfigService';
import { usageService } from '../services/usageService';

vi.mock('../services/modelConfigService', () => {
    return {
        modelConfigService: {
            listConfigs: vi.fn(),
            createConfig: vi.fn(),
            updateConfig: vi.fn(),
            deleteConfig: vi.fn(),
            exportConfigs: vi.fn(),
            importConfigs: vi.fn(),
            testConfig: vi.fn(),
        },
    };
});

vi.mock('../services/usageService', () => {
    return {
        usageService: {
            getUsageStats: vi.fn(),
        },
    };
});

const sampleConfig: ModelConfig = {
    id: 'config-1',
    name: 'Primary',
    description: 'Main config',
    provider: 'openai',
    model: 'gpt-4o',
    temperature: 0.7,
    max_tokens: 256,
    top_p: 1,
    frequency_penalty: 0,
    presence_penalty: 0,
    api_key: 'key',
    base_url: 'https://api.openai.com/v1',
    extra_params: {},
    version: 1,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
};

const sampleStats: UsageStatsResponse = {
    summary: {
        total_tokens: 100,
        total_cost: 1.5,
        call_count: 4,
    },
    by_model: [],
    by_time: [],
    group_by: 'day',
    start_date: null,
    end_date: null,
    model: null,
};

const createPayload: ModelConfigCreate = {
    name: 'New Config',
    description: 'Created config',
    provider: 'openai',
    model: 'gpt-4o-mini',
    temperature: 0.6,
    max_tokens: 256,
    top_p: 1,
    frequency_penalty: 0,
    presence_penalty: 0,
    api_key: 'key',
    base_url: 'https://api.openai.com/v1',
    extra_params: {},
};

beforeEach(() => {
    localStorage.clear();
    useSettingsStore.setState({
        language: 'zh',
        modelConfig: {
            model: 'gpt-4o',
            api_key: '',
            base_url: '',
        },
        showSettings: false,
        modelConfigs: [],
        modelConfigsLoading: false,
        modelConfigsError: null,
        usageStatsCache: {},
        usageStatsLoading: false,
        usageStatsError: null,
    });
    vi.clearAllMocks();
});

describe('settingsStore', () => {
    it('fetches model configs into state', async () => {
        (modelConfigService.listConfigs as ReturnType<typeof vi.fn>).mockResolvedValue([sampleConfig]);

        const result = await useSettingsStore.getState().fetchModelConfigs();

        expect(result).toEqual([sampleConfig]);
        expect(useSettingsStore.getState().modelConfigs).toEqual([sampleConfig]);
    });

    it('optimistically creates model config and clears usage cache', async () => {
        (modelConfigService.createConfig as ReturnType<typeof vi.fn>).mockResolvedValue(sampleConfig);
        useSettingsStore.setState({
            usageStatsCache: { 'group_by=day': sampleStats },
        });

        const promise = useSettingsStore.getState().createModelConfig(createPayload);

        expect(useSettingsStore.getState().modelConfigs).toHaveLength(1);
        expect(useSettingsStore.getState().usageStatsCache).toEqual({});

        await promise;

        expect(useSettingsStore.getState().modelConfigs[0]).toEqual(sampleConfig);
    });

    it('rolls back optimistic update on failure', async () => {
        const updatePayload: ModelConfigUpdate = { name: 'Updated' };
        (modelConfigService.updateConfig as ReturnType<typeof vi.fn>).mockRejectedValue(
            new Error('update failed')
        );
        useSettingsStore.setState({ modelConfigs: [sampleConfig] });

        const promise = useSettingsStore.getState().updateModelConfig(sampleConfig.id, updatePayload);

        expect(useSettingsStore.getState().modelConfigs[0].name).toBe('Updated');

        await expect(promise).rejects.toThrow('update failed');

        expect(useSettingsStore.getState().modelConfigs[0].name).toBe(sampleConfig.name);
    });

    it('restores state when delete fails', async () => {
        (modelConfigService.deleteConfig as ReturnType<typeof vi.fn>).mockRejectedValue(
            new Error('delete failed')
        );
        useSettingsStore.setState({ modelConfigs: [sampleConfig] });

        const promise = useSettingsStore.getState().deleteModelConfig(sampleConfig.id);

        expect(useSettingsStore.getState().modelConfigs).toHaveLength(0);

        await expect(promise).rejects.toThrow('delete failed');

        expect(useSettingsStore.getState().modelConfigs).toHaveLength(1);
    });

    it('caches usage stats by filter', async () => {
        (usageService.getUsageStats as ReturnType<typeof vi.fn>).mockResolvedValue(sampleStats);

        const first = await useSettingsStore.getState().getUsageStats({ group_by: 'day' });
        const second = await useSettingsStore.getState().getUsageStats({ group_by: 'day' });

        expect(first).toEqual(sampleStats);
        expect(second).toEqual(sampleStats);
        expect(usageService.getUsageStats).toHaveBeenCalledTimes(1);
    });

    it('refreshes model configs after import', async () => {
        const importResult: ModelConfigImportResult = { created: 1, updated: 0, skipped: 0 };
        (modelConfigService.importConfigs as ReturnType<typeof vi.fn>).mockResolvedValue(importResult);
        (modelConfigService.listConfigs as ReturnType<typeof vi.fn>).mockResolvedValue([sampleConfig]);

        const result = await useSettingsStore.getState().importModelConfigs({
            version: '1.0.0',
            configs: [sampleConfig],
        });

        expect(result).toEqual(importResult);
        expect(useSettingsStore.getState().modelConfigs).toEqual([sampleConfig]);
    });
});

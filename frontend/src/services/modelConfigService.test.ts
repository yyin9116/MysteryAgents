import { beforeEach, describe, expect, it, vi } from 'vitest';
import { modelConfigService } from './modelConfigService';
import api from './api';
import type { ModelConfig, ModelConfigCreate } from '../types/modelConfig';

vi.mock('./api', () => {
    const apiMock = {
        get: vi.fn(),
        post: vi.fn(),
        put: vi.fn(),
        delete: vi.fn(),
    };
    return { default: apiMock, api: apiMock };
});

const mockedApi = api as unknown as {
    get: ReturnType<typeof vi.fn>;
    post: ReturnType<typeof vi.fn>;
    put: ReturnType<typeof vi.fn>;
    delete: ReturnType<typeof vi.fn>;
};

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
    mockedApi.get.mockReset();
    mockedApi.post.mockReset();
    mockedApi.put.mockReset();
    mockedApi.delete.mockReset();
});

describe('modelConfigService', () => {
    it('lists model configs', async () => {
        mockedApi.get.mockResolvedValue({ data: [sampleConfig] });

        const result = await modelConfigService.listConfigs();

        expect(result).toEqual([sampleConfig]);
        expect(mockedApi.get).toHaveBeenCalledWith('/api/model-configs', { params: { skip: 0, limit: 100 } });
    });

    it('creates model config with retry on retryable errors', async () => {
        vi.useFakeTimers();
        const retryError = { isAxiosError: true, response: { status: 503 } };
        mockedApi.post.mockRejectedValueOnce(retryError).mockResolvedValueOnce({ data: sampleConfig });

        const promise = modelConfigService.createConfig(createPayload);
        await vi.runAllTimersAsync();
        const result = await promise;

        expect(result).toEqual(sampleConfig);
        expect(mockedApi.post).toHaveBeenCalledTimes(2);
        expect(mockedApi.post).toHaveBeenCalledWith('/api/model-configs', createPayload);
        vi.useRealTimers();
    });

    it('tests model config', async () => {
        const response = { success: true, message: 'ok', response: 'pong', duration_ms: 10 };
        mockedApi.post.mockResolvedValue({ data: response });

        const result = await modelConfigService.testConfig('config-1', { prompt: 'ping' });

        expect(result).toEqual(response);
        expect(mockedApi.post).toHaveBeenCalledWith('/api/model-configs/config-1/test', { prompt: 'ping' });
    });
});

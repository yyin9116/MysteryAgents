import axios from 'axios';
import api from './api';
import type {
    ModelConfig,
    ModelConfigCreate,
    ModelConfigExport,
    ModelConfigImport,
    ModelConfigImportResult,
    ModelConfigTestRequest,
    ModelConfigTestResponse,
    ModelConfigUpdate,
} from '../types/modelConfig';

const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504]);
const DEFAULT_RETRIES = 2;
const DEFAULT_RETRY_DELAY_MS = 300;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const shouldRetry = (error: unknown) => {
    if (!axios.isAxiosError(error)) {
        return false;
    }
    if (!error.response) {
        return true;
    }
    return RETRYABLE_STATUS.has(error.response.status);
};

const requestWithRetry = async <T>(
    request: () => Promise<T>,
    retries = DEFAULT_RETRIES,
    delayMs = DEFAULT_RETRY_DELAY_MS
): Promise<T> => {
    let attempt = 0;
    while (true) {
        try {
            return await request();
        } catch (error) {
            if (!shouldRetry(error) || attempt >= retries) {
                throw error;
            }
            const backoff = delayMs * Math.pow(2, attempt);
            attempt += 1;
            await sleep(backoff);
        }
    }
};

export const modelConfigService = {
    async listConfigs(skip = 0, limit = 100): Promise<ModelConfig[]> {
        const response = await requestWithRetry(() =>
            api.get<ModelConfig[]>('/api/model-configs', { params: { skip, limit } })
        );
        return response.data;
    },

    async getConfig(configId: string): Promise<ModelConfig> {
        const response = await requestWithRetry(() =>
            api.get<ModelConfig>(`/api/model-configs/${configId}`)
        );
        return response.data;
    },

    async createConfig(payload: ModelConfigCreate): Promise<ModelConfig> {
        const response = await requestWithRetry(() =>
            api.post<ModelConfig>('/api/model-configs', payload)
        );
        return response.data;
    },

    async updateConfig(configId: string, payload: ModelConfigUpdate): Promise<ModelConfig> {
        const response = await requestWithRetry(() =>
            api.put<ModelConfig>(`/api/model-configs/${configId}`, payload)
        );
        return response.data;
    },

    async deleteConfig(configId: string): Promise<ModelConfig> {
        const response = await requestWithRetry(() =>
            api.delete<ModelConfig>(`/api/model-configs/${configId}`)
        );
        return response.data;
    },

    async exportConfigs(): Promise<ModelConfigExport> {
        const response = await requestWithRetry(() =>
            api.get<ModelConfigExport>('/api/model-configs/export')
        );
        return response.data;
    },

    async importConfigs(payload: ModelConfigImport): Promise<ModelConfigImportResult> {
        const response = await requestWithRetry(() =>
            api.post<ModelConfigImportResult>('/api/model-configs/import', payload)
        );
        return response.data;
    },

    async testConfig(configId: string, payload: ModelConfigTestRequest): Promise<ModelConfigTestResponse> {
        const response = await requestWithRetry(() =>
            api.post<ModelConfigTestResponse>(`/api/model-configs/${configId}/test`, payload)
        );
        return response.data;
    },
};

export default modelConfigService;

import axios from 'axios';
import api from './api';
import type { UsageStatsFilters, UsageStatsResponse } from '../types/usage';

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

export const usageService = {
    async getUsageStats(filters: UsageStatsFilters = {}): Promise<UsageStatsResponse> {
        const params: UsageStatsFilters = {
            ...filters,
        };

        const response = await requestWithRetry(() =>
            api.get<UsageStatsResponse>('/api/usage/stats', { params })
        );
        return response.data;
    },
};

export default usageService;

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { usageService } from './usageService';
import api from './api';
import type { UsageStatsResponse } from '../types/usage';

vi.mock('./api', () => {
    const apiMock = {
        get: vi.fn(),
    };
    return { default: apiMock, api: apiMock };
});

const mockedApi = api as unknown as {
    get: ReturnType<typeof vi.fn>;
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

beforeEach(() => {
    mockedApi.get.mockReset();
});

describe('usageService', () => {
    it('fetches usage stats with filters', async () => {
        mockedApi.get.mockResolvedValue({ data: sampleStats });

        const result = await usageService.getUsageStats({
            start_date: '2024-01-01',
            end_date: '2024-01-31',
            model: 'gpt-4o',
            group_by: 'day',
        });

        expect(result).toEqual(sampleStats);
        expect(mockedApi.get).toHaveBeenCalledWith('/api/usage/stats', {
            params: {
                start_date: '2024-01-01',
                end_date: '2024-01-31',
                model: 'gpt-4o',
                group_by: 'day',
            },
        });
    });
});

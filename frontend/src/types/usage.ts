export type UsageGroupBy = 'hour' | 'day' | 'week' | 'month';

export interface UsageSummary {
    total_tokens: number;
    total_cost: number;
    call_count: number;
}

export interface UsageAggregate extends UsageSummary {
    group_by: string;
    group_value: string;
}

export interface UsageStatsResponse {
    summary: UsageSummary;
    by_model: UsageAggregate[];
    by_time: UsageAggregate[];
    group_by: UsageGroupBy;
    start_date?: string | null;
    end_date?: string | null;
    model?: string | null;
}

export interface UsageStatsFilters {
    start_date?: string;
    end_date?: string;
    model?: string;
    group_by?: UsageGroupBy;
}

/**
 * 提示词模板管理服务。
 * 对应后端 /api/prompts —— 模板列表、读写、恢复默认、试运行。
 */
import api from './api';

export interface PromptTemplateSummary {
    key: string;
    name: string;
    group: string;
    description: string;
    variables: string[];
    source: 'default' | 'custom';
    tokens: number;
    lines: number;
    preview: string;
}

export interface PromptTemplateDetail extends PromptTemplateSummary {
    content: string;
    default_content: string;
    sample_vars: Record<string, string>;
}

export interface PromptSaveResult {
    key: string;
    saved: boolean;
    source: 'default' | 'custom';
    missing_vars?: string[];
    unused_vars?: string[];
    error?: string | null;
}

export interface PromptTestRunResult {
    key: string;
    rendered_prompt: string;
    variables_used: Record<string, string>;
    output: string;
}

export interface PromptTestRunPayload {
    llm_config?: {
        provider?: string;
        model?: string;
        api_key?: string;
        base_url?: string;
    } | null;
    sample_vars?: Record<string, string>;
    temperature?: number;
    max_tokens?: number;
}

const extractDetail = (error: unknown, fallback: string): string => {
    if (typeof error === 'object' && error !== null && 'response' in error) {
        const response = (error as { response?: { data?: { detail?: unknown } } }).response;
        const detail = response?.data?.detail;
        if (typeof detail === 'string') return detail;
        if (detail && typeof detail === 'object' && 'message' in detail) {
            const missing = (detail as { missing_vars?: string[] }).missing_vars ?? [];
            return `${(detail as { message?: string }).message ?? '模板校验失败'}：缺失变量 ${missing.join('、')}`;
        }
    }
    return fallback;
};

export const promptService = {
    async listTemplates(): Promise<PromptTemplateSummary[]> {
        const response = await api.get<PromptTemplateSummary[]>('/api/prompts');
        return response.data;
    },

    async getTemplate(key: string): Promise<PromptTemplateDetail> {
        const response = await api.get<PromptTemplateDetail>(`/api/prompts/${key}`);
        return response.data;
    },

    async updateTemplate(key: string, content: string): Promise<PromptSaveResult> {
        try {
            const response = await api.put<PromptSaveResult>(`/api/prompts/${key}`, { content });
            return response.data;
        } catch (error) {
            throw new Error(extractDetail(error, '保存失败，请稍后重试'));
        }
    },

    async resetTemplate(key: string): Promise<void> {
        await api.post(`/api/prompts/${key}/reset`);
    },

    async testRun(key: string, payload: PromptTestRunPayload): Promise<PromptTestRunResult> {
        try {
            const response = await api.post<PromptTestRunResult>(`/api/prompts/${key}/test-run`, payload);
            return response.data;
        } catch (error) {
            throw new Error(extractDetail(error, '试运行失败，请检查模型配置'));
        }
    },
};

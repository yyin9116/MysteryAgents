export interface ModelInfo {
    provider: string;
    model_name: string;
    display_name: string;
    description?: string;
}

export interface ModelConfig {
    model: string;
    api_key: string;
    base_url?: string;
}

export interface ModelPreset {
    id: string;
    label: string;
    model: string;
    base_url?: string;
}

export interface ModelHealthStatus {
    provider: string;
    status: "healthy" | "unhealthy" | "unknown";
    message?: string;
}

export const MODEL_PRESETS: ModelPreset[] = [
    { id: 'gpt-4o', label: 'OpenAI GPT-4o', model: 'gpt-4o' },
    { id: 'gpt-4o-mini', label: 'OpenAI GPT-4o mini', model: 'gpt-4o-mini' },
    { id: 'gpt-3.5-turbo', label: 'OpenAI GPT-3.5 Turbo', model: 'gpt-3.5-turbo' },
    { id: 'qwen-plus', label: 'Qwen Plus', model: 'qwen-plus' },
    { id: 'qwen-turbo', label: 'Qwen Turbo', model: 'qwen-turbo' },
    { id: 'deepseek-chat', label: 'DeepSeek Chat', model: 'deepseek-chat' },
];

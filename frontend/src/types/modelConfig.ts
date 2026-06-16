export type ModelConfigExtraParams = Record<string, unknown>;

export interface ModelConfigBase {
    name: string;
    description?: string;
    provider: string;
    model: string;
    temperature: number;
    max_tokens?: number | null;
    top_p?: number | null;
    frequency_penalty?: number | null;
    presence_penalty?: number | null;
    api_key?: string | null;
    base_url?: string | null;
    extra_params: ModelConfigExtraParams;
}

export interface ModelConfigCreate extends ModelConfigBase {}

export interface ModelConfigUpdate {
    name?: string;
    description?: string;
    provider?: string;
    model?: string;
    temperature?: number;
    max_tokens?: number | null;
    top_p?: number | null;
    frequency_penalty?: number | null;
    presence_penalty?: number | null;
    api_key?: string | null;
    base_url?: string | null;
    extra_params?: ModelConfigExtraParams | null;
    version?: number;
}

export interface ModelConfig extends ModelConfigBase {
    id: string;
    version: number;
    created_at: string;
    updated_at: string;
}

export interface ModelConfigExport {
    version: string;
    exported_at: string;
    configs: ModelConfig[];
}

export interface ModelConfigImportItem extends ModelConfigBase {
    id?: string | null;
    version?: number | null;
    created_at?: string | null;
    updated_at?: string | null;
}

export interface ModelConfigImport {
    version: string;
    configs: ModelConfigImportItem[];
    overwrite?: boolean;
}

export interface ModelConfigImportResult {
    created: number;
    updated: number;
    skipped: number;
}

export interface ModelConfigTestRequest {
    prompt?: string;
}

export interface ModelConfigTestResponse {
    success: boolean;
    message: string;
    response?: string | null;
    duration_ms?: number | null;
}

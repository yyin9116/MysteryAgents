import api from './api';

export interface GameConfigExport {
    version: string;
    name: string;
    description?: string;
    created_at: string;
    agent_count: number;
    civilian_word: string;
    undercover_word: string;
    max_rounds: number;
    agents: AgentConfigExport[];
    custom_personalities?: PersonalityPresetExport[];
    memory_decay_high: number;
    memory_decay_mid: number;
    memory_decay_low: number;
    memory_cascade_probability: number;
    model_high_iq?: string;
    model_mid_iq?: string;
    model_low_iq?: string;
}

export interface AgentConfigExport {
    id: string;
    mbti_type: string;
    iq_level: string;
    template?: string;
}

export interface PersonalityPresetExport {
    mbti_type: string;
    traits: string;
    speaking_style: string;
    thinking_pattern: string;
}

export interface ValidationResult {
    valid: boolean;
    issues: string[];
    warnings: string[];
}

export const configService = {
    /**
     * Export game configuration
     */
    exportConfig: async (
        name: string,
        config: any,
        agents: any[],
        customPersonalities?: any[],
        format: 'json' | 'yaml' = 'json',
        description?: string
    ): Promise<Blob> => {
        const response = await api.post('/api/config/export', {
            name,
            description,
            config,
            agents,
            custom_personalities: customPersonalities,
            format
        }, {
            responseType: 'blob'
        });
        return response.data;
    },

    /**
     * Import game configuration from string
     */
    importConfig: async (
        content: string,
        format: 'json' | 'yaml' = 'json'
    ): Promise<{ status: string; config: GameConfigExport; validation: ValidationResult }> => {
        const response = await api.post('/api/config/import', {
            content,
            format
        });
        return response.data;
    },

    /**
     * Import game configuration from file
     */
    importConfigFile: async (file: File): Promise<{
        status: string;
        config: GameConfigExport;
        validation: ValidationResult;
        filename: string;
    }> => {
        const formData = new FormData();
        formData.append('file', file);

        const response = await api.post('/api/config/import-file', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        });
        return response.data;
    },

    /**
     * Validate configuration
     */
    validateConfig: async (config: GameConfigExport): Promise<ValidationResult> => {
        const response = await api.post('/api/config/validate', config);
        return response.data;
    },

    /**
     * Get example configuration
     */
    getExampleConfig: async (format: 'json' | 'yaml' = 'json'): Promise<GameConfigExport | string> => {
        const response = await api.get(`/api/config/example?format=${format}`);
        return response.data;
    },

    /**
     * Download configuration as file
     */
    downloadConfig: (blob: Blob, filename: string) => {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
    }
};

export default configService;

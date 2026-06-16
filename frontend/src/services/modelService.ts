/**
 * Model Service
 * 
 * Handles LLM model listing and configuration
 */

import api from './api';

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  description: string;
  recommended_for: string[];
}

export interface ModelListResponse {
  models: ModelInfo[];
  providers: string[];
}

export interface ModelRecommendations {
  High: ModelInfo[];
  Mid: ModelInfo[];
  Low: ModelInfo[];
}

export const modelService = {
  /**
   * Get list of available models (mock catalog)
   */
  async listModels(provider?: string, iqLevel?: string): Promise<ModelListResponse> {
    const params = new URLSearchParams();
    if (provider) params.append('provider', provider);
    if (iqLevel) params.append('iq_level', iqLevel);
    
    const response = await api.get(`/api/models/list?${params.toString()}`);
    return response.data;
  },

  /**
   * Get list of available models by actually querying provider API with API key
   */
  async listModelsWithKey(provider: string, apiKey: string): Promise<ModelListResponse> {
    const response = await api.post('/api/models/list-with-key', {
      provider,
      api_key: apiKey
    });
    return response.data;
  },

  /**
   * Get list of providers
   */
  async listProviders(): Promise<string[]> {
    const response = await api.get('/api/models/providers');
    return response.data.providers;
  },

  /**
   * Check model health
   */
  async checkModelHealth(modelId: string): Promise<any> {
    const response = await api.post('/api/models/health-check', null, {
      params: { model_id: modelId }
    });
    return response.data;
  },

  /**
   * Get model recommendations for each IQ level
   */
  async getRecommendations(): Promise<ModelRecommendations> {
    const response = await api.get('/api/models/recommendations');
    return response.data;
  },

  /**
   * Test if an API key is valid for a provider
   */
  async testApiKey(provider: string, apiKey: string): Promise<{ valid: boolean; message: string }> {
    const response = await api.post('/api/models/test-api-key', {
      provider,
      api_key: apiKey
    });
    return response.data;
  },

  /**
   * Test if a specific model is available and working
   */
  async testModel(modelId: string, apiKey?: string): Promise<{ available: boolean; message: string }> {
    const response = await api.post('/api/models/test-model', {
      model_id: modelId,
      api_key: apiKey
    });
    return response.data;
  }
};

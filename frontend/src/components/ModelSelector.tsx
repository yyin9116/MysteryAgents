/**
 * Model Selector Component
 *
 * Allows users to select a model from configured modelConfigs
 */

import React, { useEffect, useState } from 'react';
import { AlertCircle, Check, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useSettingsStore } from '../store/settingsStore';
import type { ModelConfig } from '../types/modelConfig';

interface ModelSelectorProps {
  isOpen: boolean;
  onClose: () => void;
  onSave?: (config: unknown) => void;
}

const getPreferredConfig = (configs: ModelConfig[]) => configs[0] || null;

const ModelSelector: React.FC<ModelSelectorProps> = ({
  isOpen,
  onClose,
  onSave,
}) => {
  const navigate = useNavigate();
  const { modelConfigs, fetchModelConfigs, modelConfigsLoading } = useSettingsStore();
  const [selectedConfigId, setSelectedConfigId] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      fetchModelConfigs();
    }
  }, [isOpen, fetchModelConfigs]);

  useEffect(() => {
    if (modelConfigs.length > 0 && !selectedConfigId) {
      const preferredConfig = getPreferredConfig(modelConfigs);
      setSelectedConfigId(preferredConfig?.id || '');
    }
  }, [modelConfigs, selectedConfigId]);

  const handleSave = () => {
    const selectedConfig = modelConfigs.find((c) => c.id === selectedConfigId);
    if (onSave && selectedConfig) {
      onSave({
        model: selectedConfig.model,
        api_key: selectedConfig.api_key,
        base_url: selectedConfig.base_url,
        provider: selectedConfig.provider,
      });
    }
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        <div className="bg-gradient-to-r from-purple-600 to-blue-600 text-white p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold">模型选择器</h2>
              <p className="text-purple-100 mt-1">选择游戏使用的 LLM 模型</p>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg p-2 transition-colors"
            >
              <X size={24} />
            </button>
          </div>
        </div>

        <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
          <div className="space-y-6">
            {modelConfigsLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="w-8 h-8 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin"></div>
              </div>
            ) : modelConfigs.length === 0 ? (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-6 h-6 text-yellow-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-yellow-900 mb-2">未找到模型配置</h4>
                    <p className="text-sm text-yellow-800 mb-3">
                      请先在设置页面配置至少一个模型，然后再返回此处选择。
                    </p>
                    <button
                      onClick={() => navigate('/settings')}
                      className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors text-sm font-medium"
                    >
                      前往设置页面
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <h3 className="text-lg font-semibold text-gray-900">选择模型</h3>
                  </div>

                  <select
                    value={selectedConfigId}
                    onChange={(e) => setSelectedConfigId(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  >
                    {modelConfigs.map((config) => (
                      <option key={config.id} value={config.id}>
                        {config.name} ({config.provider}/{config.model})
                      </option>
                    ))}
                  </select>

                  {selectedConfigId && (() => {
                    const selected = modelConfigs.find((c) => c.id === selectedConfigId);
                    return selected ? (
                      <div className="mt-4 p-3 bg-gray-50 rounded-lg text-sm space-y-1">
                        <div className="flex justify-between">
                          <span className="text-gray-600">提供商:</span>
                          <span className="font-medium text-gray-900">{selected.provider}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">模型:</span>
                          <span className="font-medium text-gray-900">{selected.model}</span>
                        </div>
                        {selected.base_url && (
                          <div className="flex justify-between">
                            <span className="text-gray-600">Base URL:</span>
                            <span className="font-medium text-gray-900 truncate ml-2">{selected.base_url}</span>
                          </div>
                        )}
                      </div>
                    ) : null;
                  })()}
                </div>

                <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                  <h4 className="font-semibold text-purple-900 mb-2">提示</h4>
                  <ul className="text-sm text-purple-800 space-y-1">
                    <li>选择的模型配置将应用于所有 Agent。</li>
                    <li>如需修改模型配置，请前往设置页面。</li>
                    <li>列表顺序按服务端返回结果展示。</li>
                  </ul>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="border-t border-gray-200 p-6 bg-gray-50 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={modelConfigs.length === 0 || !selectedConfigId}
            className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Check size={20} />
            保存配置
          </button>
        </div>
      </div>
    </div>
  );
};

export default ModelSelector;

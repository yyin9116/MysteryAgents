import React, { useEffect, useMemo, useState } from 'react';
import { Users, Cpu, Play, Clock } from 'lucide-react';
import '../../styles/werewolf-theme.css';
import { useSettingsStore } from '../../store/settingsStore';

interface WerewolfGameConfigProps {
  onStart: (config: GameConfig) => void;
}

export interface GameConfig {
  playerCount: number;
  provider: string;
  model: string;
  apiKey?: string;
  baseUrl?: string;
  fastMode?: boolean;
  discussionTurnLimit?: number;
}

type MatchPreset = 'standard' | 'quick';

const WerewolfGameConfig: React.FC<WerewolfGameConfigProps> = ({ onStart }) => {
  const [playerCount, setPlayerCount] = useState(9);
  const [selectedModelId, setSelectedModelId] = useState('');
  const [preset, setPreset] = useState<MatchPreset>('standard');
  const {
    modelConfigs,
    modelConfigsLoading,
    modelConfigsError,
    fetchModelConfigs,
  } = useSettingsStore();

  useEffect(() => {
    fetchModelConfigs().catch((error) => {
      console.error('Failed to load model configs for werewolf mode:', error);
    });
  }, [fetchModelConfigs]);

  useEffect(() => {
    if (!selectedModelId && modelConfigs.length > 0) {
      setSelectedModelId(modelConfigs[0].id);
    }
  }, [modelConfigs, selectedModelId]);

  const selectedModel = useMemo(
    () => modelConfigs.find((item) => item.id === selectedModelId) || modelConfigs[0],
    [modelConfigs, selectedModelId]
  );

  const handleStart = () => {
    if (!selectedModel) {
      return;
    }
    onStart({
      playerCount,
      provider: selectedModel.provider,
      model: selectedModel.model,
      apiKey: selectedModel.api_key || undefined,
      baseUrl: selectedModel.base_url || undefined,
      fastMode: preset === 'quick',
      discussionTurnLimit: preset === 'quick' ? Math.min(4, playerCount) : undefined,
    });
  };

  return (
    <div className="flex flex-col items-center justify-center w-full max-w-md mx-auto p-4 sm:p-8 ww-card animate-slideUp">
      <h2 className="text-2xl sm:text-3xl font-bold mb-5 sm:mb-8 text-ww-gold tracking-widest uppercase">
        游戏配置
      </h2>

      {/* 玩家数量选择 */}
      <div className="w-full mb-5 sm:mb-8">
        <div className="flex items-center justify-between mb-3 sm:mb-4">
          <label className="flex items-center text-ww-gold/80 gap-2">
            <Users size={20} />
            <span>玩家数量</span>
          </label>
          <span className="text-2xl font-bold text-ww-gold">{playerCount}</span>
        </div>
        <input
          type="range"
          min="6"
          max="12"
          step="1"
          value={playerCount}
          onChange={(e) => setPlayerCount(parseInt(e.target.value))}
          className="ww-slider"
        />
        <div className="flex justify-between mt-2 text-xs text-white/40">
          <span>6人</span>
          <span>9人</span>
          <span>12人</span>
        </div>
      </div>

      <div className="w-full mb-5 sm:mb-8">
        <label className="flex items-center text-ww-gold/80 gap-2 mb-3 sm:mb-4">
          <Clock size={20} />
          <span>对局节奏</span>
        </label>
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setPreset('standard')}
            className={`rounded-lg border p-2.5 text-left transition-all sm:p-3 ${
              preset === 'standard'
                ? 'border-ww-gold bg-ww-gold/10 shadow-[0_0_15px_rgba(255,215,0,0.3)]'
                : 'border-white/10 bg-black/20 hover:border-white/30'
            }`}
          >
            <div className={preset === 'standard' ? 'text-ww-gold font-medium' : 'text-white/80'}>
              标准局
            </div>
            <p className="mt-1 hidden text-xs text-white/50 sm:line-clamp-2">
              默认推荐，发言更完整，更容易打到 2 回合以上
            </p>
          </button>
          <button
            type="button"
            onClick={() => setPreset('quick')}
            className={`rounded-lg border p-2.5 text-left transition-all sm:p-3 ${
              preset === 'quick'
                ? 'border-ww-gold bg-ww-gold/10 shadow-[0_0_15px_rgba(255,215,0,0.3)]'
                : 'border-white/10 bg-black/20 hover:border-white/30'
            }`}
          >
            <div className={preset === 'quick' ? 'text-ww-gold font-medium' : 'text-white/80'}>
              快测局
            </div>
            <p className="mt-1 hidden text-xs text-white/50 sm:line-clamp-2">
              缩短等待时间，适合快速验模型，不保证局时长
            </p>
          </button>
        </div>
      </div>

      {/* 模型选择 */}
      <div className="w-full mb-5 sm:mb-10">
        <label className="flex items-center text-ww-gold/80 gap-2 mb-3 sm:mb-4">
          <Cpu size={20} />
          <span>选择推理模型</span>
        </label>
        {modelConfigsLoading ? (
          <div className="rounded-lg border border-white/10 bg-black/20 px-4 py-6 text-center text-white/60">
            正在读取真实模型配置...
          </div>
        ) : modelConfigs.length === 0 ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-4 text-sm text-amber-100">
            {modelConfigsError || '当前没有可用模型配置，请先到设置页添加真实模型配置。'}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {modelConfigs.map((config) => (
              <div
                key={config.id}
                onClick={() => setSelectedModelId(config.id)}
                className={`p-2.5 sm:p-3 rounded-lg border cursor-pointer transition-all ${
                  selectedModelId === config.id
                    ? 'border-ww-gold bg-ww-gold/10 shadow-[0_0_15px_rgba(255,215,0,0.3)]'
                    : 'border-white/10 bg-black/20 hover:border-white/30'
                }`}
              >
                <div className={selectedModelId === config.id ? 'text-ww-gold font-medium' : 'text-white/80'}>
                  {config.name}
                </div>
                <div className="mt-1 text-xs text-white/45">
                  {config.provider}/{config.model}
                </div>
                {config.description && (
                  <div className="mt-1 hidden text-xs text-white/55 sm:mt-2 sm:line-clamp-2">
                    {config.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 开始按钮 */}
      <button
        onClick={handleStart}
        disabled={!selectedModel || modelConfigsLoading}
        className="w-full ww-button-primary flex items-center justify-center gap-3 group disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Play size={20} className="group-hover:scale-110 transition-transform" />
        进入游戏
      </button>

      <p className="mt-4 hidden text-white/30 text-xs text-center sm:mt-6 sm:block">
        默认推荐 9-12 人标准局，6 人局更容易出现一回合速通
      </p>
    </div>
  );
};

export default WerewolfGameConfig;

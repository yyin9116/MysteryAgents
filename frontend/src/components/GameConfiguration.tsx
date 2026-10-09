import React, { useState } from 'react';
import { Play, Dices, Sparkles } from 'lucide-react';
import CommonGameSetup, { type CommonSetupState } from './setup/CommonGameSetup';
import { gameService } from '../services/gameService';
import { buildApiUrl } from '../services/api';
import { useGameStore } from '../store/gameStore';

/** 谁是卧底配置页：与狼人杀统一的设计语言（共享 CommonGameSetup + 卧底专属词库） */
const GameConfiguration: React.FC = () => {
  const [agentCount, setAgentCount] = useState(6);
  const [civilianWord, setCivilianWord] = useState('牛奶');
  const [undercoverWord, setUndercoverWord] = useState('豆浆');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [setup, setSetup] = useState<CommonSetupState | null>(null);
  const [wordsGenerating, setWordsGenerating] = useState(false);

  const setGame = useGameStore((state) => state.setGame);

  const generateRandomWords = () => {
    const pairs = [
      ['苹果', '梨'], ['手机', '平板'], ['大海', '湖泊'],
      ['自行车', '电动车'], ['猫', '狗'], ['教师', '教授'],
    ];
    const pair = pairs[Math.floor(Math.random() * pairs.length)];
    setCivilianWord(pair[0]);
    setUndercoverWord(pair[1]);
  };

  /** LLM 生成一对词，避免玩家无从下手 */
  const generateWordsWithLLM = async () => {
    if (wordsGenerating) return;
    setWordsGenerating(true);
    setError(null);
    try {
      const { selectedModel } = setup || {};
      const body = {
        hint: '',
        model_config_data: selectedModel
          ? {
              provider: selectedModel.provider,
              model: setup?.globalModel || selectedModel.model,
              api_key: selectedModel.api_key || undefined,
              base_url: selectedModel.base_url || undefined,
            }
          : undefined,
      };
      const res = await fetch(buildApiUrl('/api/game/generate-words'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || '词对生成失败');
      const data = await res.json();
      setCivilianWord(data.civilian_word);
      setUndercoverWord(data.undercover_word);
    } catch (err: any) {
      setError(err?.message || '词对生成失败');
    } finally {
      setWordsGenerating(false);
    }
  };

  const handleCreateGame = async () => {
    if (!setup?.selectedModel) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { selectedModel } = setup;
      const gameConfig: Record<string, unknown> = {
        agent_count: agentCount,
        civilian_word: civilianWord,
        undercover_word: undercoverWord,
        use_balanced_team: true,
        llm_config: {
          provider: selectedModel.provider || undefined,
          model: setup.globalModel || selectedModel.model,
          api_key: selectedModel.api_key || undefined,
          base_url: selectedModel.base_url || undefined,
        },
        ...(setup.roster ? { roster: setup.roster, roster_work: setup.rosterWork } : {}),
        ...(setup.autoAssign
          ? {
              auto_assign: {
                candidates: setup.autoAssign.candidates,
                disabled_models: setup.autoAssign.disabledModels,
                effort_by_role: setup.autoAssign.effortByRole,
              },
            }
          : {}),
      };

      const result = await gameService.createGame(gameConfig);
      const fullState = await gameService.getGameState(result.game_id);
      setGame(fullState);
    } catch (err: any) {
      console.error('Failed to create or start game:', err);
      setError(err.response?.data?.detail || err.message || '创建对局失败，请检查模型配置。');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl pb-12">
      <div className="flex flex-col gap-section rounded-[20px] border border-line bg-surface p-panel">
        <h2 className="text-[15px] font-bold text-text-primary">对局参数</h2>

        {/* 三游戏共享：玩家数量 / 全局推理模型 / 智能分配 / 角色阵容 */}
        <CommonGameSetup
          playerCount={agentCount}
          onPlayerCountChange={setAgentCount}
          minPlayers={3}
          maxPlayers={10}
          playerLabel="参与人数"
          showChatStyle={false}
          autoAssignTierText="按智力分档自动挑选模型：High 用最强推理，Mid 次之，Low 用轻量模型。"
          onChange={setSetup}
        />

        {/* 卧底专属：词库 */}
        <div className="rounded-xl bg-white/[0.04] p-card">
          <div className="mb-2.5 flex items-center justify-between">
            <p className="text-xs text-text-secondary">词库设置</p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={generateWordsWithLLM}
                disabled={wordsGenerating}
                title="由 AI 生成一对相近的词"
                className="flex items-center gap-1.5 rounded-lg border border-violet/50 bg-violet/12 px-2.5 py-1 text-[11px] text-violet transition-colors hover:bg-violet/20 disabled:opacity-40"
              >
                <Sparkles size={12} className={wordsGenerating ? 'animate-pulse' : ''} />
                {wordsGenerating ? '生成中…' : 'AI 生成'}
              </button>
              <button
                type="button"
                onClick={generateRandomWords}
                title="随机换词"
                className="flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-[11px] text-text-secondary transition-colors hover:border-violet/50 hover:text-text-primary"
              >
                <Dices size={12} />
                随机
              </button>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-[11px] text-text-secondary/60">平民词</span>
              <input
                type="text"
                value={civilianWord}
                onChange={(e) => setCivilianWord(e.target.value)}
                className="w-full rounded-lg border border-line bg-[#12101c] px-3 py-2 text-xs text-text-primary outline-none focus:border-violet/60"
              />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[11px] text-text-secondary/60">卧底词</span>
              <input
                type="text"
                value={undercoverWord}
                onChange={(e) => setUndercoverWord(e.target.value)}
                className="w-full rounded-lg border border-line bg-[#12101c] px-3 py-2 text-xs text-text-primary outline-none focus:border-violet/60"
              />
            </label>
          </div>
          <p className="mt-2 text-[11px] leading-5 text-text-secondary/50">
            两个词需要相近但不同，卧底拿到的是其中更难描述的一个。
          </p>
        </div>

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-xs text-danger">
            {error}
          </div>
        )}

        {/* CTA：金色主按钮，与狼人杀一致 */}
        <button
          onClick={handleCreateGame}
          disabled={loading || !setup?.selectedModel}
          className="flex items-center justify-center gap-2.5 rounded-xl bg-gold py-4 text-[15px] font-medium text-[#2B2836] shadow-[0_0_24px_rgba(232,194,105,0.3)] transition-all hover:shadow-[0_0_36px_rgba(232,194,105,0.45)] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Play size={17} />
          {loading ? '创建中…' : '开始对局'}
        </button>

        <p className="text-center text-[11px] text-text-secondary/45">
          推荐 6 人局：1 名卧底，其余为平民
        </p>
      </div>
    </div>
  );
};

export default GameConfiguration;

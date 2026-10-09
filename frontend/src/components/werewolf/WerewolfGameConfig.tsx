import React, { useState } from 'react';
import { Play, Wand2, UserRound, Eye } from 'lucide-react';
import CommonGameSetup, { Toggle, type CommonSetupState } from '../setup/CommonGameSetup';

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
  /** 按玩家槽位覆盖模型；null 表示继承全局模型 */
  agentModels?: Array<{ provider: string; model: string; apiKey?: string; baseUrl?: string } | null>;
  /** 主题角色阵容（名字+MBTI+性别绑定）；为空时走经典角色库 */
  roster?: Array<{ name: string; mbti: string; gender: string }>;
  /** 阵容角色来源作品名 */
  rosterWork?: string;
  /** 智能模型分配：按角色强度分档挑模型 + 思考强度 */
  autoAssign?: { candidates: string[]; disabledModels: string[]; effortByRole: boolean };
  /** 讨论风格：speech=圆桌发言；group_chat=QQ 群聊气泡 */
  chatStyle?: 'speech' | 'group_chat';
  /** 是否用 LLM 为玩家生成个性化昵称 */
  llmNaming?: boolean;
  /** 参与模式：spectate=围观（默认）；participate=玩家接管席位参与 */
  playerMode?: 'spectate' | 'participate';
  /** 参与模式下玩家接管的席位（1 起始） */
  playerSeat?: number;
}

type MatchPreset = 'standard' | 'quick';

const presets: Array<{ key: MatchPreset; title: string; desc: string }> = [
  { key: 'standard', title: '标准局', desc: '默认推荐，发言更完整' },
  { key: 'quick', title: '快测局', desc: '缩短等待，快速验证模型' },
];

/** 设计稿 3:789 对局参数卡语言：共享配置组件 + 狼人杀专属节奏/多模型分配 */
const WerewolfGameConfig: React.FC<WerewolfGameConfigProps> = ({ onStart }) => {
  const [playerCount, setPlayerCount] = useState(6);
  const [preset, setPreset] = useState<MatchPreset>('standard');
  const [llmNaming, setLlmNaming] = useState(true);
  const [playerMode, setPlayerMode] = useState<'spectate' | 'participate'>('spectate');
  const [playerSeat, setPlayerSeat] = useState(1);
  const [setup, setSetup] = useState<CommonSetupState | null>(null);

  const handleStart = () => {
    if (!setup?.selectedModel) {
      return;
    }
    const { selectedModel } = setup;
    const effectiveModel = setup.globalModel || selectedModel.model;
    onStart({
      playerCount,
      provider: selectedModel.provider,
      model: effectiveModel,
      apiKey: selectedModel.api_key || undefined,
      baseUrl: selectedModel.base_url || undefined,
      fastMode: preset === 'quick',
      discussionTurnLimit: preset === 'quick' ? Math.min(4, playerCount) : undefined,
      agentModels: setup.agentModels,
      roster: setup.roster ?? undefined,
      rosterWork: setup.rosterWork || undefined,
      autoAssign: setup.autoAssign ?? undefined,
      chatStyle: setup.chatStyle,
      llmNaming,
      playerMode,
      playerSeat,
    });
  };

  return (
    <div className="flex flex-col gap-section rounded-[20px] border border-line bg-surface p-panel">
      <h2 className="text-[15px] font-bold text-text-primary">对局参数</h2>

      {/* 三游戏共享：玩家数量 / 全局推理模型 / 智能分配 / 群聊开关 / 角色阵容 / 按玩家分配 */}
      <CommonGameSetup
        playerCount={playerCount}
        onPlayerCountChange={setPlayerCount}
        minPlayers={6}
        maxPlayers={12}
        playerLabel="玩家数量"
        showChatStyle
        showPerAgentAssign
        autoAssignTierText="按角色强度分档自动挑选模型：狼人 / 预言家 / 女巫用最强推理，猎人 / 守卫次之，村民用轻量模型。"
        onChange={setSetup}
      />

      {/* 参与方式：围观 AI / 玩家接管席位 */}
      <div className="rounded-xl bg-white/[0.04] p-card">
        <p className="mb-2.5 text-xs text-text-secondary">参与方式</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setPlayerMode('spectate')}
            className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs transition-all ${
              playerMode === 'spectate'
                ? 'bg-violet font-medium text-[#14121f]'
                : 'bg-white/[0.06] text-text-secondary hover:bg-white/[0.1]'
            }`}
          >
            <Eye size={13} />
            围观 AI 对局
          </button>
          <button
            type="button"
            onClick={() => setPlayerMode('participate')}
            className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs transition-all ${
              playerMode === 'participate'
                ? 'bg-violet font-medium text-[#14121f]'
                : 'bg-white/[0.06] text-text-secondary hover:bg-white/[0.1]'
            }`}
          >
            <UserRound size={13} />
            亲自参与
          </button>
        </div>
        {playerMode === 'participate' && (
          <div className="mt-2.5 flex items-center gap-2">
            <span className="text-[11px] text-text-secondary/60">我的席位</span>
            <select
              value={playerSeat}
              onChange={(e) => setPlayerSeat(Number(e.target.value))}
              className="rounded-lg border border-line bg-[#12101c] px-2.5 py-1.5 text-xs text-text-primary outline-none focus:border-violet/60"
            >
              {Array.from({ length: playerCount }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>第 {n} 号位</option>
              ))}
            </select>
            <span className="text-[11px] text-text-secondary/45">
              轮到你的席位发言 / 投票时暂停等你操作，超时由 AI 代打。
            </span>
          </div>
        )}
      </div>

      {/* 玩家昵称：LLM 个性化 / 经典角色库 */}
      <div className="rounded-xl bg-white/[0.04] p-card">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-2 text-xs text-text-secondary">
            <Wand2 size={13} className={llmNaming ? 'text-success' : 'text-text-secondary/50'} />
            LLM 生成玩家昵称
          </span>
          <Toggle checked={llmNaming} onClick={() => setLlmNaming((v) => !v)} label="LLM 生成玩家昵称" />
        </div>
        <p className="mt-2 text-[11px] leading-5 text-text-secondary/50">
          {llmNaming
            ? '开局时由每个玩家自己的模型生成个性化昵称；生成失败自动保留经典角色库名字。'
            : '直接使用经典角色库命名（历史 / 神话 / 影视角色，按 MBTI 匹配）。'}
        </p>
      </div>

      {/* 对局节奏：pills（选中紫色填充，对齐设计稿选项语言） */}
      <div className="rounded-xl bg-white/[0.04] p-card">
        <p className="mb-2.5 text-xs text-text-secondary">对局节奏</p>
        <div className="flex flex-wrap gap-2">
          {presets.map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => setPreset(p.key)}
              title={p.desc}
              className={`rounded-full px-4 py-1.5 text-xs transition-all ${
                preset === p.key
                  ? 'bg-violet font-medium text-[#14121f]'
                  : 'bg-white/[0.06] text-text-secondary hover:bg-white/[0.1]'
              }`}
            >
              {p.title}
            </button>
          ))}
        </div>
        <p className="mt-2 text-[11px] leading-5 text-text-secondary/50">
          {presets.find((p) => p.key === preset)?.desc}
        </p>
      </div>

      {/* CTA：金色主按钮（对齐设计稿主按钮语言） */}
      <button
        onClick={handleStart}
        disabled={!setup?.selectedModel}
        className="flex items-center justify-center gap-2.5 rounded-xl bg-gold py-4 text-[15px] font-medium text-[#2B2836] shadow-[0_0_24px_rgba(232,194,105,0.3)] transition-all hover:shadow-[0_0_36px_rgba(232,194,105,0.45)] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Play size={17} />
        开始对局
      </button>

      <p className="text-center text-[11px] text-text-secondary/45">
        推荐标准局 6-9 人；快测局更容易速通
      </p>
    </div>
  );
};

export default WerewolfGameConfig;

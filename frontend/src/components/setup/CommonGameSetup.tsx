import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Cpu, Minus, Plus, RefreshCw, Shuffle, Sparkles, Theater, Wand2, MessagesSquare, Ban } from 'lucide-react';
import { useSettingsStore } from '../../store/settingsStore';
import { getProviderMeta, pickPreferredModelConfig } from '../../lib/modelProviders';
import { modelConfigService } from '../../services/modelConfigService';
import { previewRoster, type RosterEntry } from '../../services/werewolfService';
import type { ModelConfig } from '../../types/modelConfig';

/** 单个玩家的模型覆盖配置（按玩家分配用） */
export interface AgentModelOverride {
  provider: string;
  model: string;
  apiKey?: string;
  baseUrl?: string;
}

/** 智能模型分配：候选由所选配置的在线目录决定，勾选禁用不参与的模型 */
export interface AutoModelAssign {
  candidates: string[];
  /** 禁用（不参与自动分配）的完整模型 id 列表 */
  disabledModels: string[];
  effortByRole: boolean;
}

/** 三游戏共享配置状态（由 CommonGameSetup 上抛） */
export interface CommonSetupState {
  selectedModel: ModelConfig | null;
  /** 全局模型下钻；'' = 用配置默认模型 */
  globalModel: string;
  /** 主题角色阵容；null = 经典角色库 */
  roster: RosterEntry[] | null;
  rosterWork: string;
  autoAssign: AutoModelAssign | null;
  chatStyle: 'speech' | 'group_chat';
  /** 按玩家分配的槽位覆盖；仅 showPerAgentAssign 时有意义 */
  agentModels?: Array<AgentModelOverride | null>;
}

/** 禁用模型列表本地持久化 key（沿用旧 key，历史关键字数据会被自然忽略） */
const DISABLED_MODELS_STORAGE_KEY = 'werewolf_model_blacklist';

function loadDisabledModels(): string[] {
  try {
    const raw = localStorage.getItem(DISABLED_MODELS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string' && item.trim()) : [];
  } catch {
    return [];
  }
}

/** 预设命名主题：经典角色库 = 不生成阵容；其余作为作品名交给 LLM 生成 */
const THEME_PRESETS: Array<{ key: string; label: string; work: string }> = [
  { key: 'classic', label: '经典角色库', work: '' },
  { key: 'xiyou', label: '西游记', work: '西游记' },
  { key: 'sanguo', label: '三国演义', work: '三国演义' },
  { key: 'wuxia', label: '金庸武侠', work: '笑傲江湖' },
  { key: 'rdr2', label: '荒野大镖客 2', work: '荒野大镖客 2' },
];

/** 设计稿同款开关 */
export const Toggle: React.FC<{ checked: boolean; onClick: () => void; label?: string }> = ({ checked, onClick, label }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-label={label}
    onClick={onClick}
    className={`relative h-[22px] w-10 shrink-0 rounded-full transition-colors ${
      checked ? 'bg-success' : 'bg-white/10'
    }`}
  >
    <span
      className={`absolute top-[3px] h-4 w-4 rounded-full transition-all ${
        checked ? 'left-[23px] bg-[#14121f]' : 'left-[3px] bg-white'
      }`}
    />
  </button>
);

interface CommonGameSetupProps {
  /** 玩家数量（受控） */
  playerCount: number;
  onPlayerCountChange: (n: number) => void;
  minPlayers?: number;
  maxPlayers?: number;
  /** 是否显示玩家数量步进器 */
  showPlayerStepper?: boolean;
  /** 是否显示 QQ 群聊讨论开关（仅狼人杀支持群聊风格） */
  showChatStyle?: boolean;
  /** 是否显示按玩家分配不同模型（需后端支持按槽位覆盖） */
  showPerAgentAssign?: boolean;
  /** 智能分配的分档说明文案（各游戏不同） */
  autoAssignTierText?: string;
  /** 玩家数量标签 */
  playerLabel?: string;
  /** 是否显示主题角色阵容（剧本杀角色由剧本决定，应关闭） */
  showRoster?: boolean;
  /** 状态上抛 */
  onChange: (state: CommonSetupState) => void;
}

/**
 * 三游戏共享的对局配置卡：全局推理模型（下钻）+ 智能模型分配（勾选禁用）
 * + QQ 群聊讨论开关 + 主题角色阵容 + 按玩家分配（可选）。
 */
const CommonGameSetup: React.FC<CommonGameSetupProps> = ({
  playerCount,
  onPlayerCountChange,
  minPlayers = 3,
  maxPlayers = 12,
  showPlayerStepper = true,
  showChatStyle = true,
  showPerAgentAssign = false,
  autoAssignTierText = '核心角色用最强推理，辅助角色次之，普通角色用轻量模型。',
  playerLabel = '玩家数量',
  showRoster = true,
  onChange,
}) => {
  const [selectedModelId, setSelectedModelId] = useState('');
  // 全局模型：始终是具体模型名（模型优先选择，凭据配置仅作为分组与凭据来源）
  const [globalModel, setGlobalModel] = useState('');
  // 按玩家分配
  const [perAgentEnabled, setPerAgentEnabled] = useState(false);
  const [agentPicks, setAgentPicks] = useState<Array<{ configId: string; model: string } | null>>([]);
  // 主题角色阵容
  const [themeKey, setThemeKey] = useState('classic');
  const [customWork, setCustomWork] = useState('');
  const [roster, setRoster] = useState<RosterEntry[] | null>(null);
  const [rosterGenerating, setRosterGenerating] = useState(false);
  const [rosterError, setRosterError] = useState('');
  // 智能模型分配
  const [autoAssignEnabled, setAutoAssignEnabled] = useState(false);
  const [effortByRole, setEffortByRole] = useState(true);
  const [disabledModels, setDisabledModels] = useState<string[]>(() => loadDisabledModels());
  // 讨论风格
  const [chatStyle, setChatStyle] = useState<'speech' | 'group_chat'>('speech');

  const { modelConfigs, modelConfigsLoading, modelConfigsError, fetchModelConfigs } = useSettingsStore();

  // ---- 在线模型目录：按配置实时拉取 /models，失败回退静态目录 ----
  const [remoteCatalog, setRemoteCatalog] = useState<Record<string, string[]>>({});
  const [catalogLoading, setCatalogLoading] = useState(false);
  const catalogFetchedRef = useRef(false);

  useEffect(() => {
    fetchModelConfigs().catch((error) => {
      console.error('Failed to load model configs:', error);
    });
  }, [fetchModelConfigs]);

  useEffect(() => {
    if (!selectedModelId && modelConfigs.length > 0) {
      const preferred = pickPreferredModelConfig(modelConfigs) || modelConfigs[0];
      setSelectedModelId(preferred.id);
      setGlobalModel(preferred.model || '');
    }
  }, [modelConfigs, selectedModelId]);

  // 玩家数量变化时同步槽位列表长度
  useEffect(() => {
    setAgentPicks((prev) => {
      const next = prev.slice(0, playerCount);
      while (next.length < playerCount) next.push(null);
      return next;
    });
  }, [playerCount]);

  const selectedModel = useMemo(
    () => modelConfigs.find((item) => item.id === selectedModelId) || modelConfigs[0],
    [modelConfigs, selectedModelId]
  );

  /** 当前生效的作品名；空 = 经典角色库（不生成阵容） */
  const activeWork = useMemo(() => {
    if (themeKey === 'custom') return customWork.trim();
    return THEME_PRESETS.find((t) => t.key === themeKey)?.work ?? '';
  }, [themeKey, customWork]);

  // 人数变化导致阵容数量不符时作废，需要重新生成
  useEffect(() => {
    if (roster && roster.length !== playerCount) setRoster(null);
  }, [playerCount, roster?.length]);

  // 禁用模型列表本地持久化
  useEffect(() => {
    try {
      localStorage.setItem(DISABLED_MODELS_STORAGE_KEY, JSON.stringify(disabledModels));
    } catch {
      /* 忽略存储失败 */
    }
  }, [disabledModels]);

  // 首次展开时批量同步所有配置的在线模型目录
  useEffect(() => {
    if (catalogFetchedRef.current || modelConfigs.length === 0) return;
    catalogFetchedRef.current = true;
    setCatalogLoading(true);
    Promise.allSettled(
      modelConfigs.map((cfg) => modelConfigService.listModelsForConfig(cfg.id))
    )
      .then((results) => {
        const map: Record<string, string[]> = {};
        results.forEach((result, index) => {
          const cfg = modelConfigs[index];
          if (result.status === 'fulfilled' && result.value.models.length) {
            map[cfg.id] = result.value.models;
          }
        });
        setRemoteCatalog(map);
      })
      .finally(() => setCatalogLoading(false));
  }, [modelConfigs]);

  /** 选定具体模型（含其所属凭据配置）：分组下拉的唯一入口 */
  const handleModelPick = (raw: string) => {
    const [configId, model] = raw.split('::');
    if (!configId || !model) return;
    setSelectedModelId(configId);
    setGlobalModel(model);
  };

  /** 某配置可下钻的模型清单：在线目录优先，静态目录兜底，并保证配置默认模型在列 */
  const modelOptionsFor = (cfg: ModelConfig): string[] => {
    const catalog = remoteCatalog[cfg.id] ?? getProviderMeta(cfg.provider).models;
    return catalog.includes(cfg.model) ? catalog : [cfg.model, ...catalog];
  };

  /** 智能分配候选：全局配置的模型目录（未禁用的） */
  const autoAssignCandidates = useMemo(() => {
    if (!selectedModel) return [];
    const catalog = remoteCatalog[selectedModel.id] ?? getProviderMeta(selectedModel.provider).models;
    const list = catalog.includes(selectedModel.model) ? catalog : [selectedModel.model, ...catalog];
    const disabled = new Set(disabledModels.map((m) => m.toLowerCase()));
    return list.filter((m) => !disabled.has(m.toLowerCase()));
  }, [selectedModel?.id, selectedModel?.model, selectedModel?.provider, remoteCatalog, disabledModels]);

  const generateRoster = async () => {
    const work = activeWork;
    if (!work || rosterGenerating) return;
    setRosterGenerating(true);
    setRosterError('');
    try {
      const res = await previewRoster({
        work,
        count: playerCount,
        model_config_data: selectedModel
          ? {
              provider: selectedModel.provider,
              model: globalModel || selectedModel.model,
              api_key: selectedModel.api_key || undefined,
              base_url: selectedModel.base_url || undefined,
            }
          : undefined,
      });
      setRoster(res.roster);
    } catch (err: any) {
      setRosterError(err?.message || '角色阵容生成失败，请重试');
      setRoster(null);
    } finally {
      setRosterGenerating(false);
    }
  };

  // 选中全局配置后拉取该配置的在线模型目录（失败静默回退静态目录）
  useEffect(() => {
    if (!selectedModel || remoteCatalog[selectedModel.id]) return;
    let cancelled = false;
    modelConfigService
      .listModelsForConfig(selectedModel.id)
      .then((res) => {
        if (!cancelled && res.models.length) {
          setRemoteCatalog((prev) => ({ ...prev, [selectedModel.id]: res.models }));
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedModel?.id]);

  // 状态上抛（ref 避免 onChange 身份变化导致循环）
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const agentModels = useMemo(
    () =>
      perAgentEnabled
        ? agentPicks.map((pick) => {
            if (!pick) return null;
            const cfg = modelConfigs.find((item) => item.id === pick.configId);
            if (!cfg) return null;
            return {
              provider: cfg.provider,
              model: pick.model || cfg.model,
              apiKey: cfg.api_key || undefined,
              baseUrl: cfg.base_url || undefined,
            };
          })
        : undefined,
    [perAgentEnabled, agentPicks, modelConfigs]
  );
  useEffect(() => {
    onChangeRef.current({
      selectedModel,
      globalModel,
      roster: activeWork && roster && roster.length === playerCount ? roster : null,
      rosterWork: activeWork && roster && roster.length === playerCount ? activeWork : '',
      autoAssign:
        autoAssignEnabled && autoAssignCandidates.length > 0
          ? { candidates: autoAssignCandidates, disabledModels, effortByRole }
          : null,
      chatStyle,
      agentModels,
    });
  }, [selectedModel, globalModel, activeWork, roster, playerCount, autoAssignEnabled, autoAssignCandidates, disabledModels, effortByRole, chatStyle, agentModels]);

  return (
    <>
      {/* 玩家数量：步进器 */}
      {showPlayerStepper && (
        <div className="rounded-xl bg-white/[0.04] p-card">
          <p className="mb-2.5 text-xs text-text-secondary">{playerLabel}</p>
          <div className="flex items-center justify-between">
            <button
              type="button"
              aria-label="减少玩家"
              onClick={() => onPlayerCountChange(Math.max(minPlayers, playerCount - 1))}
              disabled={playerCount <= minPlayers}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-line text-lg text-text-secondary transition-colors hover:border-violet/50 hover:text-text-primary disabled:opacity-30"
            >
              <Minus size={16} />
            </button>
            <span key={playerCount} className="anim-pill-pop font-hud text-2xl font-bold text-text-primary">
              {playerCount}
            </span>
            <button
              type="button"
              aria-label="增加玩家"
              onClick={() => onPlayerCountChange(Math.min(maxPlayers, playerCount + 1))}
              disabled={playerCount >= maxPlayers}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-gold/40 bg-gold/10 text-gold transition-colors hover:bg-gold/20 disabled:opacity-30"
            >
              <Plus size={16} />
            </button>
          </div>
          <div className="mt-2 flex justify-between font-hud text-[10px] tracking-wider text-text-secondary/40">
            <span>MIN {minPlayers}</span>
            <span>MAX {maxPlayers}</span>
          </div>
        </div>
      )}

      {/* 全局推理模型：直接选具体模型（按凭据配置分组，不暴露协议前缀） */}
      <div className="rounded-xl bg-white/[0.04] p-card">
        <p className="mb-2.5 flex items-center gap-2 text-xs text-text-secondary">
          <Cpu size={13} className="text-violet" />
          全局推理模型
        </p>
        {modelConfigsLoading ? (
          <div className="rounded-lg border border-line px-4 py-5 text-center text-xs text-text-secondary/60">
            正在读取模型配置…
          </div>
        ) : modelConfigs.length === 0 ? (
          <div className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-xs text-warning">
            {modelConfigsError || '当前没有可用模型配置，请先到「模型配置」页添加。'}
          </div>
        ) : (
          <>
            <select
              value={selectedModel ? `${selectedModelId}::${globalModel || selectedModel.model}` : ''}
              onChange={(e) => handleModelPick(e.target.value)}
              className="w-full rounded-lg border border-line bg-[#12101c] px-3 py-2.5 text-[13px] text-text-primary outline-none transition-colors focus:border-violet/60"
            >
              {!selectedModel && <option value="">— 请选择模型 —</option>}
              {modelConfigs.map((cfg) => (
                <optgroup key={cfg.id} label={cfg.name}>
                  {modelOptionsFor(cfg).map((m) => (
                    <option key={`${cfg.id}::${m}`} value={`${cfg.id}::${m}`}>
                      {m}
                      {m === cfg.model ? ' · 默认' : ''}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            {selectedModel && (
              <p className="mt-1.5 font-hud text-[10px] text-text-secondary/45">
                凭据：{selectedModel.name}
                {remoteCatalog[selectedModel.id]
                  ? ` · 已同步 ${remoteCatalog[selectedModel.id].length} 个在线模型`
                  : ' · 在线目录同步中，暂显示常用模型…'}
              </p>
            )}
          </>
        )}
      </div>

      {/* 智能模型分配：候选模型列表勾选禁用 + 思考强度 */}
      {selectedModel && (
        <div className="rounded-xl bg-white/[0.04] p-card">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs text-text-secondary">
              <Wand2 size={13} className={autoAssignEnabled ? 'text-success' : 'text-text-secondary/50'} />
              智能模型分配
            </span>
            <Toggle checked={autoAssignEnabled} onClick={() => setAutoAssignEnabled((v) => !v)} label="智能模型分配" />
          </div>

          {autoAssignEnabled && (
            <div className="mt-3">
              <p className="text-[11px] leading-5 text-text-secondary/50">
                {autoAssignTierText}候选来自
                <span className="text-text-secondary/80"> {selectedModel.name} </span>
                的在线模型列表，当前可用 <span className="font-hud text-success/80">{autoAssignCandidates.length}</span> 个。
              </p>

              {/* 思考强度开关 */}
              <div className="mt-3 flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2">
                <span className="flex items-center gap-2 text-xs text-text-secondary">
                  <Sparkles size={12} className={effortByRole ? 'text-gold' : 'text-text-secondary/40'} />
                  按角色注入思考强度
                </span>
                <Toggle checked={effortByRole} onClick={() => setEffortByRole((v) => !v)} label="按角色注入思考强度" />
              </div>
              <p className="mt-1.5 text-[11px] leading-5 text-text-secondary/45">
                核心角色 high、辅助角色 medium、普通角色 low（仅对支持思考的推理系模型生效）。
              </p>

              {/* 模型列表勾选禁用 */}
              <div className="mt-3">
                <p className="mb-2 flex items-center gap-2 text-xs text-text-secondary">
                  <Ban size={12} className="text-danger/80" />
                  禁用模型
                  <span className="text-[10px] text-text-secondary/40">（勾选后不参与自动分配）</span>
                </p>
                {catalogLoading ? (
                  <div className="flex items-center gap-2 rounded-lg border border-line px-3 py-2.5 text-[11px] text-text-secondary/60">
                    <RefreshCw size={11} className="animate-spin" />
                    正在同步在线模型列表…
                  </div>
                ) : (
                  <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-line bg-[#12101c] p-1.5">
                    {(selectedModel
                      ? (() => {
                          const catalog = remoteCatalog[selectedModel.id] ?? getProviderMeta(selectedModel.provider).models;
                          return catalog.includes(selectedModel.model) ? catalog : [selectedModel.model, ...catalog];
                        })()
                      : []
                    ).map((modelId) => {
                      const isDisabled = disabledModels.some((m) => m.toLowerCase() === modelId.toLowerCase());
                      return (
                        <button
                          key={modelId}
                          type="button"
                          role="checkbox"
                          aria-checked={isDisabled}
                          onClick={() =>
                            setDisabledModels((prev) =>
                              prev.some((m) => m.toLowerCase() === modelId.toLowerCase())
                                ? prev.filter((m) => m.toLowerCase() !== modelId.toLowerCase())
                                : [...prev, modelId]
                            )
                          }
                          className={`flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-left text-xs transition-colors ${
                            isDisabled ? 'text-text-secondary/40' : 'text-text-primary hover:bg-white/[0.05]'
                          }`}
                        >
                          <span className="truncate font-hud text-[11px]">{modelId}</span>
                          <span
                            className={`ml-2 flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors ${
                              isDisabled ? 'border-danger/60 bg-danger/25 text-danger' : 'border-line'
                            }`}
                          >
                            {isDisabled && (
                              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                                <path d="M1.5 5.5L4 8L8.5 2.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                              </svg>
                            )}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
                {autoAssignCandidates.length === 0 && (
                  <p className="mt-2 text-[11px] text-warning/90">
                    候选为空：全部模型都被禁用，请取消勾选至少一个模型。
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 讨论风格：圆桌发言 / QQ 群聊气泡 */}
      {showChatStyle && (
        <div className="rounded-xl bg-white/[0.04] p-card">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs text-text-secondary">
              <MessagesSquare size={13} className={chatStyle === 'group_chat' ? 'text-success' : 'text-text-secondary/50'} />
              QQ 群聊式讨论
            </span>
            <Toggle
              checked={chatStyle === 'group_chat'}
              onClick={() => setChatStyle((v) => (v === 'group_chat' ? 'speech' : 'group_chat'))}
              label="QQ 群聊式讨论"
            />
          </div>
          <p className="mt-2 text-[11px] leading-5 text-text-secondary/50">
            {chatStyle === 'group_chat'
              ? '玩家像在 QQ 群里聊天：发言拆成几条短消息连发，支持 @名字，历史消息作为群聊上下文。'
              : '默认圆桌发言：每位玩家一次完整陈述。开启后切换为群聊短消息风格。'}
          </p>
        </div>
      )}

      {/* 角色阵容：经典角色库 / 指定作品 LLM 生成（名字+MBTI+性别绑定）；剧本杀由剧本决定角色，不显示 */}
      {showRoster && (
      <div className="rounded-xl bg-white/[0.04] p-card">
        <p className="mb-2.5 flex items-center gap-2 text-xs text-text-secondary">
          <Theater size={13} className="text-violet" />
          角色阵容
        </p>
        <div className="flex flex-wrap gap-2">
          {THEME_PRESETS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => {
                setThemeKey(t.key);
                setRoster(null);
                setRosterError('');
              }}
              className={`rounded-full px-3.5 py-1.5 text-xs transition-all ${
                themeKey === t.key
                  ? 'bg-violet font-medium text-[#14121f]'
                  : 'bg-white/[0.06] text-text-secondary hover:bg-white/[0.1]'
              }`}
            >
              {t.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => {
              setThemeKey('custom');
              setRoster(null);
              setRosterError('');
            }}
            className={`rounded-full px-3.5 py-1.5 text-xs transition-all ${
              themeKey === 'custom'
                ? 'bg-violet font-medium text-[#14121f]'
                : 'bg-white/[0.06] text-text-secondary hover:bg-white/[0.1]'
            }`}
          >
            自定义作品…
          </button>
        </div>

        {themeKey === 'custom' && (
          <input
            value={customWork}
            onChange={(e) => {
              setCustomWork(e.target.value);
              setRoster(null);
            }}
            placeholder="输入你喜欢的作品，如：红楼梦、赛博朋克 2077"
            className="mt-2.5 w-full rounded-lg border border-line bg-[#12101c] px-3 py-2 text-xs text-text-primary outline-none placeholder:text-text-secondary/35 focus:border-violet/60"
          />
        )}

        {activeWork ? (
          <>
            <div className="mt-2.5 flex items-center gap-2">
              <button
                type="button"
                onClick={generateRoster}
                disabled={rosterGenerating || !activeWork || modelConfigsLoading}
                className="flex items-center gap-1.5 rounded-lg border border-violet/50 bg-violet/12 px-3.5 py-1.5 text-xs text-violet transition-all hover:bg-violet/20 disabled:opacity-40"
              >
                {rosterGenerating ? (
                  <RefreshCw size={12} className="animate-spin" />
                ) : (
                  <Sparkles size={12} />
                )}
                {rosterGenerating
                  ? '生成中…'
                  : roster && roster.length === playerCount
                    ? '重新生成阵容'
                    : `生成 ${playerCount} 个角色`}
              </button>
              {roster && roster.length === playerCount && (
                <span className="font-hud text-[10px] text-success/70">
                  {activeWork} · {roster.length} 个角色已就绪
                </span>
              )}
            </div>
            {rosterError && (
              <p className="mt-2 text-[11px] text-danger/90">{rosterError}</p>
            )}
            {roster && roster.length === playerCount && (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {roster.map((r) => (
                  <span
                    key={r.name}
                    className="rounded-lg border border-line bg-white/[0.05] px-2 py-1 text-[11px] text-text-secondary"
                  >
                    <span className="text-text-primary">{r.name}</span>
                    <span className="ml-1.5 font-hud text-[10px] text-violet/80">{r.mbti}</span>
                    <span className="ml-1 text-[10px] text-text-secondary/50">{r.gender}</span>
                  </span>
                ))}
              </div>
            )}
            <p className="mt-2 text-[11px] leading-5 text-text-secondary/50">
              角色名、MBTI 与性别由 AI 按作品世界观统一生成，一局内风格一致；译名自动带「·」分隔。
            </p>
          </>
        ) : (
          <p className="mt-2 text-[11px] leading-5 text-text-secondary/50">
            使用内置经典角色库（历史 / 神话人物，按 MBTI 匹配）。
          </p>
        )}
      </div>
      )}

      {/* 按玩家分配模型（多模型实验） */}
      {showPerAgentAssign && selectedModel && modelConfigs.length > 1 && (
        <div className="rounded-xl bg-white/[0.04] p-card">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs text-text-secondary">
              <Shuffle size={13} className={perAgentEnabled ? 'text-success' : 'text-text-secondary/50'} />
              按玩家分配不同模型
            </span>
            <Toggle checked={perAgentEnabled} onClick={() => setPerAgentEnabled((v) => !v)} label="按玩家分配不同模型" />
          </div>

          {perAgentEnabled && (
            <div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
              <p className="flex flex-wrap items-center gap-1.5 text-[11px] leading-5 text-text-secondary/50">
                {catalogLoading ? (
                  <>
                    <RefreshCw size={11} className="animate-spin" />
                    正在从各服务商同步在线模型列表…
                  </>
                ) : (
                  <>
                    先选凭据配置，再下钻到具体模型；未设置的玩家继承全局模型。
                    {Object.keys(remoteCatalog).length > 0 && (
                      <span className="font-hud text-success/70">
                        已同步 {Object.keys(remoteCatalog).length} 个配置的在线列表
                      </span>
                    )}
                  </>
                )}
              </p>
              {agentPicks.map((pick, index) => (
                <div key={index} className="flex items-center gap-2">
                  <span className="w-12 shrink-0 font-hud text-[10px] text-text-secondary/50">P{index + 1}</span>
                  <select
                    value={pick ? `${pick.configId}::${pick.model}` : ''}
                    onChange={(e) =>
                      setAgentPicks((prev) => {
                        const next = [...prev];
                        const raw = e.target.value;
                        if (!raw) {
                          next[index] = null;
                        } else {
                          const [configId, model] = raw.split('::');
                          next[index] = { configId, model };
                        }
                        return next;
                      })
                    }
                    className="min-w-0 flex-1 rounded-lg border border-line bg-[#12101c] px-2 py-1.5 text-xs text-text-primary outline-none focus:border-violet/60"
                  >
                    <option value="">继承全局模型</option>
                    {modelConfigs.map((cfg) => (
                      <optgroup key={cfg.id} label={cfg.name}>
                        {modelOptionsFor(cfg).map((m) => (
                          <option key={m} value={`${cfg.id}::${m}`}>
                            {m}
                            {m === cfg.model ? ' · 默认' : ''}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );
};

export default CommonGameSetup;

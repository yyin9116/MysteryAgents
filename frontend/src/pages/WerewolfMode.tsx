import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Moon, Sun, MessageCircle, Vote, AlertCircle, ArrowLeft, History, Clock, RefreshCcw, Search, Trash2, Users, Activity, Brain, X, Pause, SkipForward, OctagonX, Sparkles, Check } from 'lucide-react';
import DarkMysticLayout from '../components/werewolf/DarkMysticLayout';
import WerewolfGameConfig from '../components/werewolf/WerewolfGameConfig';
import PossessionControl from '../components/werewolf/PossessionControl';
import WerewolfGameOver from '../components/werewolf/WerewolfGameOver';
import TimelineReplay from '../components/werewolf/TimelineReplay';
import type { GameConfig } from '../components/werewolf/WerewolfGameConfig';
import { deleteFinishedWerewolfReplays, deleteWerewolfReplay, downloadWerewolfReplay, listWerewolfReplays, type ReplaySummary } from '../services/werewolfReplayService';
import { useSettingsStore } from '../store/settingsStore';
import {
  createGame,
  connectGameStreamWithRetry,
  controlGameStream,
  deleteGame,
  type Agent,
  type WerewolfEvent,
  type CreateGameResponse,
} from '../services/werewolfService';

type GameState = 'config' | 'loading' | 'playing' | 'game_over';
type ReplaySortOption = 'updated_desc' | 'started_desc' | 'started_asc' | 'events_desc';
type MobilePanel = 'history' | 'players' | 'events' | null;

interface GameData {
  gameId: string;
  phase: string;
  currentRound: number;
  agents: Agent[];
  winner?: 'werewolf' | 'good';
  winReason?: string;
}

const WerewolfMode: React.FC = () => {
  const REPLAYS_PAGE_SIZE = 5;
  const REPLAY_POLL_INTERVAL_MS = 15000;
  const navigate = useNavigate();
  const [gameState, setGameState] = useState<GameState>('config');
  const [gameData, setGameData] = useState<GameData | null>(null);
  const [events, setEvents] = useState<WerewolfEvent[]>([]);
  const [currentEvent, setCurrentEvent] = useState<WerewolfEvent | null>(null);
  const [possessedAgent, setPossessedAgent] = useState<Agent | null>(null);
  const [showPossessionControl, setShowPossessionControl] = useState(false);
  const [showTimelineReplay, setShowTimelineReplay] = useState(false);
  const [selectedReplayGameId, setSelectedReplayGameId] = useState<string | null>(null);
  const [replays, setReplays] = useState<ReplaySummary[]>([]);
  const [replaysTotal, setReplaysTotal] = useState(0);
  const [replayStats, setReplayStats] = useState({ total: 0, active: 0, finished: 0 });
  const [replaysLoading, setReplaysLoading] = useState(false);
  const [replaySearch, setReplaySearch] = useState('');
  const [replayFilter, setReplayFilter] = useState<'all' | 'active' | 'finished'>('all');
  const [replaySort, setReplaySort] = useState<ReplaySortOption>('updated_desc');
  const [replayPage, setReplayPage] = useState(1);
  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [activeModelLabel, setActiveModelLabel] = useState<string>('');
  const [tokenPlayback, setTokenPlayback] = useState({ speech: 0, thought: 0 });
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>(null);
  const [nowTick, setNowTick] = useState<number>(() => Date.now());
  const [pendingPlayerCount, setPendingPlayerCount] = useState(6);
  // 对局节奏：auto=自动连播（可调速）；manual=手动步进，等用户点「下一步」
  const [paceMode, setPaceMode] = useState<'auto' | 'manual'>('auto');
  const [paceSpeed, setPaceSpeed] = useState<number>(1.0);
  const cleanupRef = useRef<(() => void) | null>(null);
  const gameStartedAtRef = useRef<number>(0);
  const phaseStartedAtRef = useRef<number>(0);
  const eventUidRef = useRef(0);
  // 已处理的最新事件 seq（断线重连回放去重）
  const lastSeqRef = useRef(0);
  // gameData 的实时镜像（事件回调闭包中读取最新值）
  const gameDataRef = useRef<GameData | null>(null);
  gameDataRef.current = gameData;
  const fallbackModelConfig = useSettingsStore((state) => state.modelConfig);

  useEffect(() => {
    return () => {
      // Cleanup SSE connection on unmount
      if (cleanupRef.current) {
        cleanupRef.current();
      }
    };
  }, []);

  useEffect(() => {
    loadReplayHistory();
  }, [replayPage, replaySearch, replayFilter, replaySort]);

  useEffect(() => {
    if (gameState !== 'config' || showTimelineReplay) {
      return;
    }

    const intervalId = window.setInterval(() => {
      loadReplayHistory();
    }, REPLAY_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [gameState, showTimelineReplay, replayPage, replaySearch, replayFilter, replaySort]);

  const loadReplayHistory = async () => {
    const sortConfig = {
      updated_desc: { sortBy: 'updated_at', sortOrder: 'desc' },
      started_desc: { sortBy: 'started_at', sortOrder: 'desc' },
      started_asc: { sortBy: 'started_at', sortOrder: 'asc' },
      events_desc: { sortBy: 'total_events', sortOrder: 'desc' },
    } as const;

    try {
      setReplaysLoading(true);
      const payload = await listWerewolfReplays({
        page: replayPage,
        pageSize: REPLAYS_PAGE_SIZE,
        search: replaySearch,
        status: replayFilter,
        sortBy: sortConfig[replaySort].sortBy,
        sortOrder: sortConfig[replaySort].sortOrder,
      });
      setReplays(payload.replays || []);
      setReplaysTotal(payload.total || 0);
      setReplayStats(payload.stats || { total: payload.total || 0, active: 0, finished: 0 });
    } catch (err: any) {
      console.error('Failed to load werewolf replays:', err);
    } finally {
      setReplaysLoading(false);
    }
  };

  const handleStartGame = async (gameConfig: GameConfig) => {
    setGameState('loading');
    setError('');
    setPendingPlayerCount(gameConfig.playerCount);
    setChatStyle(gameConfig.chatStyle || 'speech');

    try {
      // Create game
      const response: CreateGameResponse = await createGame({
        ...gameConfig,
        apiKey: gameConfig.apiKey || fallbackModelConfig.api_key || undefined,
        baseUrl: gameConfig.baseUrl || fallbackModelConfig.base_url || undefined,
      });
      setSuccessMessage('');
      setActiveModelLabel(gameConfig.model || fallbackModelConfig.model || '未记录模型');

      setGameData({
        gameId: response.game_id,
        phase: 'night',
        currentRound: 1,
        agents: response.agents,
      });

      // Connect to SSE stream
      lastSeqRef.current = 0;
      const cleanup = connectGameStreamWithRetry(
        response.game_id,
        handleGameEvent,
        5
      );
      cleanupRef.current = cleanup;
      setSelectedReplayGameId(response.game_id);
      loadReplayHistory();

      // 同步当前节奏偏好到新对局（默认自动 1x）
      try {
        await controlGameStream(response.game_id, { mode: paceMode, speed: paceSpeed });
      } catch (paceErr) {
        console.warn('Failed to sync pace preference:', paceErr);
      }

      setGameState('playing');
    } catch (err: any) {
      console.error('Failed to start game:', err);
      setError(err.message || '游戏创建失败');
      setGameState('config');
    }
  };

  /** 应用节奏到运行中的对局 */
  const applyPace = React.useCallback(
    async (mode: 'auto' | 'manual', speed: number) => {
      if (!gameData?.gameId) return;
      try {
        await controlGameStream(gameData.gameId, { mode, speed });
      } catch (err) {
        console.warn('Failed to change pace:', err);
      }
    },
    [gameData?.gameId]
  );

  const handlePaceMode = (mode: 'auto' | 'manual') => {
    setPaceMode(mode);
    applyPace(mode, paceSpeed);
  };

  const handlePaceSpeed = (speed: number) => {
    setPaceSpeed(speed);
    applyPace('auto', speed);
  };

  const handleManualAdvance = () => {
    if (!gameData?.gameId) return;
    controlGameStream(gameData.gameId, { action: 'advance' }).catch((err) =>
      console.warn('Failed to advance:', err)
    );
  };

  // 终止对局：断开事件流 + 删除后端对局，回到配置页
  const [terminating, setTerminating] = useState(false);
  const handleTerminateGame = () => {
    const gameId = gameData?.gameId;
    if (!gameId || terminating) return;
    if (!window.confirm('确定终止本局游戏？对局将被结束并清理。')) return;
    setTerminating(true);
    if (cleanupRef.current) {
      cleanupRef.current();
      cleanupRef.current = null;
    }
    deleteGame(gameId)
      .catch((err) => console.warn('Failed to delete game:', err))
      .finally(() => {
        setTerminating(false);
        setGameData(null);
        setEvents([]);
        setCurrentEvent(null);
        setGameState('config');
      });
  };

  // 手动模式下：空格 / → 键放行下一步
  useEffect(() => {
    if (gameState !== 'playing' || paceMode !== 'manual') return;
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
      if (e.code === 'Space' || e.code === 'ArrowRight') {
        e.preventDefault();
        handleManualAdvance();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameState, paceMode, gameData?.gameId]);

  const handleOpenReplay = () => {    if (gameData?.gameId) {
      setSelectedReplayGameId(gameData.gameId);
    }
    setShowTimelineReplay(true);
  };

  const handleOpenHistoricalReplay = (gameId: string) => {
    setSelectedReplayGameId(gameId);
    setShowTimelineReplay(true);
  };

  const handleCloseReplay = () => {
    setShowTimelineReplay(false);
  };

  /** 结算页「再来一局」：清场回到配置页（沿用上一次的配置表单） */
  const handleRematch = () => {
    if (cleanupRef.current) {
      cleanupRef.current();
      cleanupRef.current = null;
    }
    setEvents([]);
    setGameData(null);
    setGameState('config');
  };

  const handleDeleteReplay = async (gameId: string) => {
    if (!window.confirm(`确定删除回放 ${gameId} 吗？`)) {
      return;
    }
    try {
      await deleteWerewolfReplay(gameId);
      setSuccessMessage(`已删除回放 ${gameId}`);
      if (selectedReplayGameId === gameId) {
        setShowTimelineReplay(false);
        setSelectedReplayGameId(null);
      }
      await loadReplayHistory();
    } catch (err: any) {
      setError(err.message || '删除回放失败');
    }
  };

  const handleDeleteFinishedReplays = async () => {
    if (!window.confirm('确定清理全部已结束回放吗？进行中的对局会被保留。')) {
      return;
    }
    try {
      const result = await deleteFinishedWerewolfReplays();
      await loadReplayHistory();
      if (result.deleted_count > 0) {
        setError('');
        setSuccessMessage(`已清理 ${result.deleted_count} 个已结束回放`);
      } else {
        setSuccessMessage('没有可清理的已结束回放');
      }
    } catch (err: any) {
      setError(err.message || '批量清理回放失败');
    }
  };

  const handleExportReplay = async (gameId: string) => {
    try {
      await downloadWerewolfReplay(gameId);
      setSuccessMessage(`已导出回放 ${gameId}`);
      setError('');
    } catch (err: any) {
      setError(err.message || '导出回放失败');
    }
  };

  const formatRelativeTime = (timestamp?: string) => {
    if (!timestamp) {
      return '未记录';
    }
    const diffMs = Date.now() - new Date(timestamp).getTime();
    if (Number.isNaN(diffMs)) {
      return '未记录';
    }
    const diffMinutes = Math.max(0, Math.floor(diffMs / 60000));
    if (diffMinutes < 1) {
      return '刚刚';
    }
    if (diffMinutes < 60) {
      return `${diffMinutes} 分钟前`;
    }
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) {
      return `${diffHours} 小时前`;
    }
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} 天前`;
  };

  const handleGameEvent = (event: WerewolfEvent) => {
    // seq 去重：断线重连后服务端会回放 backlog，已处理过的事件直接跳过
    const seq = typeof event.seq === 'number' ? event.seq : null;
    if (seq !== null) {
      if (seq <= lastSeqRef.current) return;
      lastSeqRef.current = seq;
    }
    const arrivedAt = Date.now();
    if (!gameStartedAtRef.current) {
      gameStartedAtRef.current = arrivedAt;
    }
    (event as WerewolfEvent & { arrivedAt?: number }).arrivedAt = arrivedAt;
    eventUidRef.current += 1;
    (event as WerewolfEvent & { uid?: string }).uid = `evt-${arrivedAt}-${eventUidRef.current}`;
    setEvents(prev => [...prev, event]);
    setCurrentEvent(event);

    switch (event.type) {
      case 'game_start':
        gameStartedAtRef.current = arrivedAt;
        phaseStartedAtRef.current = arrivedAt;
        break;

      case 'phase_change':
        phaseStartedAtRef.current = arrivedAt;
        setGameData(prev => prev ? {
          ...prev,
          phase: normalizePhase(event.phase || event.to_phase),
          currentRound: event.round || prev.currentRound,
        } : null);

        // Handle deaths in dawn phase
        if (event.phase === 'dawn' && event.deaths) {
          updateAgentStatus(event.deaths, false);
        }
        break;

      case 'night_action':
        // Night action performed
        break;

      case 'agent_speaking':
        // Agent is speaking
        break;

      case 'discussion':
        // Persisted replay-style discussion event.
        break;

      case 'agent_voting':
        // Agent voted
        break;

      case 'vote':
        // Persisted replay-style vote event.
        break;

      case 'death_announcement':
        if (event.deaths?.length) {
          updateAgentStatus(event.deaths, false);
        }
        break;

      case 'elimination':
        // Player eliminated
        if (event.eliminated_id) {
          updateAgentStatus([event.eliminated_id], false);

          // Update agent role info
          setGameData(prev => {
            if (!prev) return null;
            return {
              ...prev,
              agents: prev.agents.map(a =>
                a.agent_id === event.eliminated_id
                  ? { ...a, role: event.eliminated_role, role_cn: event.eliminated_role_cn, faction: event.eliminated_role === 'werewolf' ? 'werewolf' : 'good' }
                  : a
              ),
            };
          });
        }
        break;

      case 'game_over':
        if (cleanupRef.current) {
          cleanupRef.current();
          cleanupRef.current = null;
        }
        setGameData(prev => prev ? {
          ...prev,
          winner: event.winner,
          winReason: event.reason,
        } : null);

        // Reveal all roles
        revealAllRoles();

        setTimeout(() => {
          setGameState('game_over');
        }, 2000);
        break;

      case 'player_input_required': {
        // 参与模式：轮到玩家席位，自动打开夺舍控制面板（发言 / 投票）
        const agentId = event.agent_id as string | undefined;
        const target = gameDataRef.current?.agents.find((a) => a.agent_id === agentId);
        if (target && target.is_alive) {
          setPossessedAgent(target);
          setShowPossessionControl(true);
        }
        setSuccessMessage(event.message || '轮到你操作');
        break;
      }

      case 'game_terminated':
        // 对局在服务端被终止（本端终止时已提前离开对局页）
        if (cleanupRef.current) {
          cleanupRef.current();
          cleanupRef.current = null;
        }
        setSuccessMessage(event.message || '对局已终止');
        setGameState('config');
        break;

      case 'error':
        setError(event.message || '发生错误');
        break;
    }
  };

  const updateAgentStatus = (agentIds: string[], isAlive: boolean) => {
    setGameData(prev => {
      if (!prev) return null;
      return {
        ...prev,
        agents: prev.agents.map(agent =>
          agentIds.includes(agent.agent_id)
            ? { ...agent, is_alive: isAlive }
            : agent
        ),
      };
    });
  };

  const revealAllRoles = () => {
    // Role visibility is driven by persisted agent state from the stream.
  };

  const handleAgentClick = (agent: Agent) => {
    if (!agent.is_alive) return;

    setPossessedAgent(agent);
    setShowPossessionControl(true);
  };

  const handleClosePossession = () => {
    setShowPossessionControl(false);
  };

  const normalizePhase = (phase?: string) => {
    switch (phase) {
      case 'discussion':
        return 'day_discussion';
      case 'voting':
        return 'day_voting';
      default:
        return phase || 'night';
    }
  };

  const getPhaseIcon = (phase: string) => {
    switch (normalizePhase(phase)) {
      case 'opening':
        return <Sparkles className="w-5 h-5" />;
      case 'night':
        return <Moon className="w-5 h-5" />;
      case 'dawn':
        return <Sun className="w-5 h-5" />;
      case 'day_discussion':
        return <MessageCircle className="w-5 h-5" />;
      case 'day_voting':
        return <Vote className="w-5 h-5" />;
      default:
        return null;
    }
  };

  const getPhaseText = (phase: string) => {
    switch (normalizePhase(phase)) {
      case 'opening':
        return '开场';
      case 'night':
        return '夜晚';
      case 'dawn':
        return '天亮';
      case 'day_discussion':
        return '讨论';
      case 'day_voting':
        return '投票';
      default:
        return '待同步';
    }
  };

  const getEventPhase = (event?: WerewolfEvent | null) => normalizePhase(event?.phase || event?.to_phase || event?.data?.to_phase || gameData?.phase);
  const currentVisualPhase = currentEvent?.type === 'elimination' || currentEvent?.type === 'game_over'
    ? 'result'
    : getEventPhase(currentEvent);

  const getPhaseAtmosphere = (phase?: string) => {
    switch (normalizePhase(phase)) {
      case 'opening':
        return {
          shell: 'border-gold/35 bg-[radial-gradient(circle_at_50%_10%,rgba(232,194,105,0.14),transparent_34%),linear-gradient(135deg,rgba(40,32,16,0.6),rgba(23,20,36,0.88))]',
          accent: 'from-gold via-[#f2d99a] to-[#b09a6a]',
          label: '入座宣言',
          motion: '灯牌亮起 / 逐一入场',
        };
      case 'night':
        return {
          shell: 'border-violet/35 bg-[radial-gradient(circle_at_20%_20%,rgba(140,125,245,0.16),transparent_34%),linear-gradient(135deg,rgba(13,10,20,0.94),rgba(23,20,36,0.85))]',
          accent: 'from-violet via-[#b3a8ff] to-[#8f8bb0]',
          label: '夜雾潜行',
          motion: '雾线流动 / 暗杀轨迹',
        };
      case 'dawn':
        return {
          shell: 'border-gold/35 bg-[radial-gradient(circle_at_50%_0%,rgba(232,194,105,0.18),transparent_36%),linear-gradient(135deg,rgba(64,48,16,0.55),rgba(23,20,36,0.88))]',
          accent: 'from-gold via-[#f2d99a] to-[#c9a06a]',
          label: '晨光结算',
          motion: '日出扫光 / 伤亡公布',
        };
      case 'day_discussion':
        return {
          shell: 'border-info/35 bg-[radial-gradient(circle_at_15%_80%,rgba(92,140,240,0.16),transparent_35%),linear-gradient(135deg,rgba(18,32,58,0.75),rgba(23,20,36,0.88))]',
          accent: 'from-info via-[#8fb0f5] to-[#6f8fd0]',
          label: '圆桌发言',
          motion: '声波扩散 / 视线交锋',
        };
      case 'day_voting':
        return {
          shell: 'border-role-undercover/35 bg-[radial-gradient(circle_at_80%_30%,rgba(240,161,89,0.16),transparent_34%),linear-gradient(135deg,rgba(58,36,18,0.62),rgba(23,20,36,0.88))]',
          accent: 'from-role-undercover via-[#f5c08f] to-[#d09a6a]',
          label: '票压倒计',
          motion: '投票箭线 / 压迫热浪',
        };
      case 'result':
        return {
          shell: 'border-danger/40 bg-[radial-gradient(circle_at_50%_50%,rgba(224,107,107,0.18),transparent_36%),linear-gradient(135deg,rgba(58,18,18,0.7),rgba(23,20,36,0.9))]',
          accent: 'from-danger via-gold to-white',
          label: '命运揭示',
          motion: '裂纹冲击 / 阵营落幕',
        };
      default:
        return {
          shell: 'border-gold/25 bg-black/35',
          accent: 'from-gold via-white to-gold',
          label: '实时剧场',
          motion: '事件同步',
        };
    }
  };

  const atmosphere = getPhaseAtmosphere(currentVisualPhase);

  const getEventTone = (event?: WerewolfEvent | null) => {
    const type = event?.type;
    const phase = getEventPhase(event);
    if (type === 'error') return 'border-danger/40 bg-danger/10 text-danger';
    if (type === 'elimination' || type === 'game_over' || type === 'death_announcement') return 'border-danger/35 bg-danger/10 text-danger';
    if (type === 'agent_voting' || type === 'vote' || phase === 'day_voting') return 'border-role-undercover/35 bg-role-undercover/10 text-role-undercover';
    if (type === 'agent_speaking' || type === 'discussion' || phase === 'day_discussion') return 'border-info/35 bg-info/10 text-info';
    if (type === 'night_action' || phase === 'night') return 'border-violet/35 bg-violet/10 text-violet';
    if (phase === 'opening') return 'border-gold/35 bg-gold/10 text-gold';
    if (phase === 'dawn') return 'border-gold/35 bg-gold/10 text-gold';
    return 'border-gold/30 bg-gold/10 text-gold';
  };

  const getEventTitle = (event?: WerewolfEvent | null) => {
    if (!event) return '等待对局事件';
    switch (event.type) {
      case 'game_start':
        return '游戏开始';
      case 'phase_change':
        return `${getPhaseText(event.phase || event.to_phase)}阶段`;
      case 'night_action':
        return '夜间行动';
      case 'death_announcement':
        return '天亮结算';
      case 'agent_speaking':
      case 'discussion':
        return `${event.agent_name || '一名玩家'}发言`;
      case 'agent_voting':
      case 'vote':
        return `${event.agent_name || event.voter_name || '一名玩家'}投票`;
      case 'elimination':
        return '放逐结果';
      case 'round_complete':
        return `第 ${event.round || gameData?.currentRound || '-'} 回合结束`;
      case 'game_over':
        return '游戏结束';
      case 'error':
        return '连接提示';
      default:
        return '对局事件';
    }
  };

  const getEventSummary = (event?: WerewolfEvent | null) => {
    if (!event) return '模型和玩家席位已就绪，等待下一条实时事件。';
    if (event.message) return event.message;
    switch (event.type) {
      case 'game_start':
        return '所有玩家已入座，身份牌已经暗中分发。';
      case 'phase_change':
        return `进入${getPhaseText(event.phase || event.to_phase)}阶段。`;
      case 'night_action':
        return [event.actor_name, event.target_name ? `→ ${event.target_name}` : '完成夜间行动'].filter(Boolean).join(' ');
      case 'death_announcement':
        return event.deaths?.length ? `昨晚有 ${event.deaths.length} 名玩家死亡。` : '昨晚是平安夜，无人死亡。';
      case 'agent_speaking':
      case 'discussion':
        return event.speech || event.content || `${event.agent_name || '玩家'}正在组织发言，模型仍在生成内容。`;
      case 'agent_voting':
      case 'vote':
        return event.voted_for_name || event.target_name
          ? `${event.agent_name || event.voter_name || '玩家'} 投给 ${event.voted_for_name || event.target_name}`
          : `${event.agent_name || event.voter_name || '玩家'}正在权衡投票对象。`;
      case 'elimination':
        return `${event.eliminated_name || '一名玩家'}被放逐出局。`;
      case 'round_complete':
        return `进入第 ${event.next_round || '-'} 回合前的短暂整理。`;
      case 'game_over':
        return event.reason || event.message || '胜负已经判定。';
      case 'error':
        return event.message || '实时连接出现波动，系统会自动重连。';
      default:
        return '收到一条暂未命名的系统事件。';
    }
  };

  const aliveAgents = gameData?.agents.filter((agent) => agent.is_alive) || [];
  const deadAgents = gameData?.agents.filter((agent) => !agent.is_alive) || [];

  // 群聊模式：聊天区新消息到达时自动滚到底；普通模式不自动滚动（避免干扰阅读）
  const [chatStyle, setChatStyle] = useState<'speech' | 'group_chat'>('speech');
  const stageScrollRef = useRef<HTMLDivElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (chatStyle !== 'group_chat') return;
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [events.length, chatStyle]);
  const currentActorId = currentEvent?.agent_id || currentEvent?.actor_id || currentEvent?.voter_id || currentEvent?.eliminated_id;
  const recentSpeeches = events
    .filter((event) => (event.type === 'agent_speaking' || event.type === 'discussion') && (event.speech || event.content))
    .slice(-3)
    .reverse();

  // 群聊模式：把所有玩家的发言整理成聊天消息流（含 opening / discussion）
  const chatMessages = useMemo(() => {
    return events
      .filter((event) => {
        if (event.type !== 'agent_speaking' && event.type !== 'discussion') return false;
        const phase = event.phase || '';
        return phase === 'opening' || phase === 'day_discussion' || phase === 'discussion' || !phase;
      })
      .map((event) => {
        const bubbles = Array.isArray(event.bubbles)
          ? (event.bubbles as unknown[]).filter((b): b is string => typeof b === 'string' && Boolean(b.trim()))
          : [];
        return {
          uid: event.uid || `${event.agent_id}-${event.round}-${bubbles[0]?.slice(0, 8) || ''}`,
          agentId: event.agent_id || '',
          agentName: event.agent_name || '玩家',
          bubbles: bubbles.length > 0 ? bubbles : [event.speech || event.content || ''].filter(Boolean),
          round: event.round,
          phase: event.phase || 'day_discussion',
          playerControlled: !!event.player_controlled,
        };
      })
      .filter((msg) => msg.bubbles.length > 0);
  }, [events]);

  // 群聊头像配色：按名字稳定取色
  const avatarTones = ['bg-info', 'bg-violet', 'bg-gold', 'bg-danger', 'bg-success', 'bg-role-undercover'];
  const avatarToneOf = (name: string) => {
    let hash = 0;
    for (let i = 0; i < name.length; i += 1) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    return avatarTones[hash % avatarTones.length];
  };
  const latestChatUid = chatMessages.length > 0 ? chatMessages[chatMessages.length - 1].uid : null;
  const recentVotes = events
    .filter((event) => (event.type === 'agent_voting' || event.type === 'vote') && (event.voted_for_name || event.target_name))
    .slice(-4)
    .reverse();
  const liveVoteTally = events
    .filter((event) => (event.type === 'agent_voting' || event.type === 'vote') && event.round === gameData?.currentRound)
    .reduce((tally, event) => {
      const targetName = event.voted_for_name || event.target_name || event.voted_for_id || event.target_id || '未知目标';
      tally.set(targetName, (tally.get(targetName) || 0) + 1);
      return tally;
    }, new Map<string, number>());
  const leadingLiveVote = Array.from(liveVoteTally.entries()).sort((a, b) => b[1] - a[1])[0];
  const currentActor = gameData?.agents.find((agent) => agent.agent_id === currentActorId);
  const latestPublicSignal = events
    .filter((event) => ['death_announcement', 'elimination', 'game_over', 'phase_change'].includes(event.type))
    .slice(-1)[0];
  const tensionScore = Math.min(100, Math.round((events.length * 3) + (recentVotes.length * 10) + (deadAgents.length * 16)));

  // HUD 时钟：阶段开始至今的 mm:ss
  useEffect(() => {
    if (gameState !== 'playing') {
      return;
    }
    const timer = window.setInterval(() => setNowTick(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [gameState]);

  const formatDuration = (fromMs: number, toMs: number) => {
    if (!fromMs) {
      return '00:00';
    }
    const total = Math.max(0, Math.floor((toMs - fromMs) / 1000));
    const mm = String(Math.floor(total / 60)).padStart(2, '0');
    const ss = String(total % 60).padStart(2, '0');
    return `${mm}:${ss}`;
  };

  const phaseClock = formatDuration(phaseStartedAtRef.current || gameStartedAtRef.current, nowTick);
  const eventClock = (event?: WerewolfEvent | null) =>
    formatDuration(gameStartedAtRef.current, (event as WerewolfEvent & { arrivedAt?: number } | null | undefined)?.arrivedAt || nowTick);

  const getPhaseBadge = (phase?: string) => {
    switch (normalizePhase(phase)) {
      case 'night':
        return '夜阶段 · 狼人行动';
      case 'opening':
        return '开局 · 入座开场白';
      case 'dawn':
        return '黎明 · 天亮结算';
      case 'day_discussion':
        return '白昼 · 圆桌发言';
      case 'day_voting':
        return '白昼 · 放逐投票';
      case 'result':
        return '终局 · 命运揭示';
      default:
        return '等待开局';
    }
  };

  const getEventLogTone = (event: WerewolfEvent) => {
    if (event.type === 'error') return 'text-danger';
    if (event.type === 'elimination' || event.type === 'death_announcement' || event.type === 'game_over') return 'text-danger';
    if (event.type === 'agent_voting' || event.type === 'vote') return 'text-gold';
    if (event.type === 'night_action') return 'text-violet';
    if (event.type === 'agent_speaking' || event.type === 'discussion') return 'text-white/70';
    return 'text-white/45';
  };

  const totalReplayPages = Math.max(1, Math.ceil(replaysTotal / REPLAYS_PAGE_SIZE));
  const currentReplayPage = Math.min(replayPage, totalReplayPages);

  useEffect(() => {
    setReplayPage(1);
  }, [replaySearch, replayFilter, replaySort]);

  useEffect(() => {
    if (replayPage > totalReplayPages) {
      setReplayPage(totalReplayPages);
    }
  }, [replayPage, totalReplayPages]);

  const tokenizeForPlayback = (text?: string) => {
    const normalized = (text || '').trim();
    if (!normalized) {
      return [];
    }
    return normalized.match(/[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]/g) || [];
  };

  const joinPlaybackTokens = (tokens: string[]) => {
    return tokens.reduce((text, token, index) => {
      const prev = tokens[index - 1];
      const needsSpace = Boolean(prev && /[A-Za-z0-9_]$/.test(prev) && /^[A-Za-z0-9_]/.test(token));
      return `${text}${needsSpace ? ' ' : ''}${token}`;
    }, '');
  };

  const speechPlaybackTokens = tokenizeForPlayback(currentEvent?.speech || currentEvent?.content);
  const thoughtPlaybackTokens = tokenizeForPlayback(currentEvent?.thought);
  // 群聊模式：当前事件的短消息气泡列表
  const currentBubbles: string[] = Array.isArray(currentEvent?.bubbles)
    ? currentEvent.bubbles.filter((bubble: unknown) => typeof bubble === 'string' && bubble.trim())
    : [];
  const visibleSpeech = joinPlaybackTokens(speechPlaybackTokens.slice(0, tokenPlayback.speech));
  const visibleThought = joinPlaybackTokens(thoughtPlaybackTokens.slice(0, tokenPlayback.thought));
  const isSpeechPlaying = speechPlaybackTokens.length > 0 && tokenPlayback.speech < speechPlaybackTokens.length;
  const isThoughtPlaying = thoughtPlaybackTokens.length > 0 && tokenPlayback.thought < thoughtPlaybackTokens.length;
  const hasPlaybackContent = speechPlaybackTokens.length > 0 || thoughtPlaybackTokens.length > 0;

  useEffect(() => {
    const speechText = currentEvent?.speech || currentEvent?.content || '';
    const thoughtText = currentEvent?.thought || '';
    const speechTokens = tokenizeForPlayback(speechText);
    const thoughtTokens = tokenizeForPlayback(thoughtText);

    setTokenPlayback({ speech: 0, thought: 0 });

    if (speechTokens.length === 0 && thoughtTokens.length === 0) {
      return;
    }

    let speechIndex = 0;
    let thoughtIndex = 0;
    let thoughtStarted = speechTokens.length === 0;

    const intervalId = window.setInterval(() => {
      if (speechIndex < speechTokens.length) {
        speechIndex = Math.min(speechTokens.length, speechIndex + 2);
        if (speechIndex >= Math.min(18, speechTokens.length)) {
          thoughtStarted = true;
        }
      } else {
        thoughtStarted = true;
      }

      if (thoughtStarted && thoughtIndex < thoughtTokens.length) {
        thoughtIndex = Math.min(thoughtTokens.length, thoughtIndex + 1);
      }

      setTokenPlayback({ speech: speechIndex, thought: thoughtIndex });

      if (speechIndex >= speechTokens.length && thoughtIndex >= thoughtTokens.length) {
        window.clearInterval(intervalId);
      }
    }, 36);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [
    currentEvent?.type,
    currentEvent?.agent_id,
    currentEvent?.index,
    currentEvent?.speech,
    currentEvent?.content,
    currentEvent?.thought,
  ]);

  const getReplayStatusLabel = (replay: ReplaySummary) => {
    if (replay.is_active) {
      return '进行中';
    }
    if (replay.winner === 'good') {
      return '好人胜';
    }
    if (replay.winner === 'werewolf') {
      return '狼人胜';
    }
    return '已结束';
  };

  const getReplayStatusClassName = (replay: ReplaySummary) => {
    if (replay.is_active) {
      return 'border-success/50 text-success bg-success/10';
    }
    if (replay.winner === 'good') {
      return 'border-info/50 text-info bg-info/10';
    }
    if (replay.winner === 'werewolf') {
      return 'border-danger/50 text-danger bg-danger/10';
    }
    return 'border-line-strong text-text-muted bg-white/[0.03]';
  };

  const renderReplayHistory = (compact = false) => (
    <div className={`${compact ? 'p-4' : 'p-6 md:p-8'} w-full rounded-3xl border border-line bg-surface/60 backdrop-blur-sm animate-slideUp`}>
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <p className="font-hud text-[11px] uppercase tracking-[0.25em] text-gold/70">Replay Archive · 对局档案</p>
          <h2 className={`${compact ? 'text-xl' : 'text-2xl'} font-bold text-text-primary mt-1.5`}>对局记录中心</h2>
        </div>
        <button
          onClick={loadReplayHistory}
          className="p-2 rounded-xl border border-line bg-white/[0.03] text-text-muted hover:text-gold hover:border-gold/40 transition-colors"
          title="刷新历史回放"
        >
          <RefreshCcw className={`w-4 h-4 ${replaysLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* 统计芯片：全部 / 进行中 / 已结束 */}
      <div className="mb-4 grid grid-cols-3 gap-2 sm:gap-3">
        <div className="rounded-[10px] border border-line bg-white/[0.03] px-3 py-3 sm:px-4">
          <div className="text-[11px] text-text-secondary/70 sm:text-xs">总数</div>
          <div className="mt-1 font-hud text-lg font-semibold text-text-primary sm:text-xl">{replayStats.total}</div>
        </div>
        <div className="rounded-[10px] border border-success/25 bg-success/10 px-3 py-3 sm:px-4">
          <div className="text-[11px] text-success/70 sm:text-xs">进行中</div>
          <div className="mt-1 font-hud text-lg font-semibold text-success sm:text-xl">{replayStats.active}</div>
        </div>
        <div className="rounded-[10px] border border-line bg-white/[0.03] px-3 py-3 sm:px-4">
          <div className="text-[11px] text-text-secondary/70 sm:text-xs">已结束</div>
          <div className="mt-1 font-hud text-lg font-semibold text-text-primary sm:text-xl">{replayStats.finished}</div>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] mb-4">
        <label className="flex items-center gap-2 px-3 py-2 rounded-[10px] border border-line bg-black/20 text-text-muted">
          <Search className="w-4 h-4" />
          <input
            value={replaySearch}
            onChange={(event) => setReplaySearch(event.target.value)}
            placeholder="搜索 game_id"
            className="w-full bg-transparent outline-none text-sm text-text-primary placeholder:text-text-muted/40"
          />
        </label>
        <div className="scrollbar-none flex gap-2 overflow-x-auto">
          {[
            ['all', '全部'],
            ['active', '进行中'],
            ['finished', '已结束'],
          ].map(([value, label]) => (
            <button
              key={value}
              onClick={() => setReplayFilter(value as 'all' | 'active' | 'finished')}
              className={`shrink-0 px-3 py-2 rounded-[10px] text-sm border transition-colors ${
                replayFilter === value
                  ? 'border-gold/45 bg-gold/10 text-gold'
                  : 'border-line bg-white/[0.03] text-text-secondary hover:border-white/25'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-text-secondary/50">排序会作用于当前筛选结果</p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            <span>排序</span>
            <select
              value={replaySort}
              onChange={(event) => setReplaySort(event.target.value as ReplaySortOption)}
              className="rounded-[10px] border border-line bg-surface px-3 py-2 text-sm text-text-primary outline-none"
            >
              <option value="updated_desc">最近更新</option>
              <option value="started_desc">最近开始</option>
              <option value="started_asc">最早开始</option>
              <option value="events_desc">事件最多</option>
            </select>
          </label>
          <button
            onClick={handleDeleteFinishedReplays}
            className="rounded-[10px] border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger transition-colors hover:border-danger/50 hover:bg-danger/20"
            title="清理全部已结束回放"
          >
            清理已结束
          </button>
        </div>
      </div>

      {replaysLoading && replays.length === 0 ? (
        <div className="py-10 text-center text-text-secondary">加载历史回放中...</div>
      ) : replays.length === 0 ? (
        <div className="py-10 text-center text-text-secondary/60">
          <History className="w-10 h-10 mx-auto mb-3 opacity-60" />
          <p>{replaysTotal === 0 && replayFilter === 'all' && replaySearch.trim() === '' ? '还没有可回放的历史对局' : '没有符合筛选条件的回放'}</p>
        </div>
      ) : (
        <div className={`${compact ? 'max-h-[52vh] overflow-y-auto pr-1 scrollbar-none' : ''} space-y-3`}>
          {replays.map((replay) => (
            <div
              key={replay.game_id}
              className="w-full p-4 rounded-xl border border-line bg-white/[0.03] hover:border-gold/40 hover:bg-gold/5 transition-colors"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <button
                    onClick={() => handleOpenHistoricalReplay(replay.game_id)}
                    className="flex max-w-full items-center gap-2 mb-2 text-left"
                  >
                    <span className="truncate font-hud font-semibold text-text-primary">{replay.game_id}</span>
                    <span className={`shrink-0 px-2 py-0.5 text-[11px] rounded-full border ${getReplayStatusClassName(replay)}`}>
                      {getReplayStatusLabel(replay)}
                    </span>
                  </button>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-text-secondary">
                    <span>事件 {replay.total_events}</span>
                    <span>{replay.player_count ? `${replay.player_count} 人局` : '人数未同步'}</span>
                    {typeof replay.alive_count === 'number' && (
                      <span>存活 {replay.alive_count}</span>
                    )}
                    <span>第 {replay.current_round} 回合</span>
                    <span>阶段 {replay.current_phase}</span>
                  </div>
                  {replay.game_over_reason && (
                    <p className="mt-2 line-clamp-2 text-sm text-text-secondary/60">
                      结局：{replay.game_over_reason}
                    </p>
                  )}
                </div>
                <div className="flex items-center justify-between gap-3 sm:items-start">
                  <div className="text-xs text-text-secondary/60 flex items-center gap-1 whitespace-nowrap">
                    <Clock className="w-3 h-3" />
                    <span title={replay.updated_at ? new Date(replay.updated_at).toLocaleString('zh-CN') : '未记录时间'}>
                      {formatRelativeTime(replay.updated_at)}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleExportReplay(replay.game_id)}
                      className="rounded-[10px] border border-line px-2 py-1.5 text-xs text-text-secondary hover:text-info hover:border-info/40 transition-colors"
                      title={`导出 ${replay.game_id}`}
                    >
                      导出
                    </button>
                    <button
                      onClick={() => handleDeleteReplay(replay.game_id)}
                      className="p-2 rounded-[10px] border border-line text-text-secondary/70 hover:text-danger hover:border-danger/40 transition-colors"
                      title={`删除 ${replay.game_id}`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}

          {replaysTotal > REPLAYS_PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2 text-sm text-text-secondary">
              <span>
                第 {currentReplayPage} / {totalReplayPages} 页，共 {replaysTotal} 条
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setReplayPage((page) => Math.max(1, page - 1))}
                  disabled={currentReplayPage === 1}
                  className="px-3 py-1.5 rounded-lg border border-line disabled:opacity-40 disabled:cursor-not-allowed hover:border-white/25 transition-colors"
                >
                  上一页
                </button>
                <button
                  onClick={() => setReplayPage((page) => Math.min(totalReplayPages, page + 1))}
                  disabled={currentReplayPage === totalReplayPages}
                  className="px-3 py-1.5 rounded-lg border border-line disabled:opacity-40 disabled:cursor-not-allowed hover:border-white/25 transition-colors"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );

  // 左栏：在局智能体 HUD 列表（对齐设计稿 3:360）
  const renderAgentList = (compact = false) => (
    <section className={`${compact ? 'p-3' : ''} flex flex-col`}>
      <p className="font-hud mb-3 text-[11px] uppercase tracking-[0.25em] text-text-secondary/60">
        在场玩家 PLAYERS
      </p>
      <div className={`scrollbar-none flex flex-col gap-2 ${compact ? 'max-h-[64vh] overflow-y-auto pr-1' : ''}`}>
        {gameData?.agents.map((agent) => {
          const isCurrent = currentActorId === agent.agent_id;
          const isSpeaking = isCurrent && (currentEvent?.type === 'agent_speaking' || currentEvent?.type === 'discussion');
          const initial = agent.name.slice(0, 1);
          return (
            <button
              key={agent.agent_id}
              onClick={() => handleAgentClick(agent)}
              disabled={!agent.is_alive}
              title={agent.is_alive
                ? `夺舍 ${agent.name}${agent.model_label ? `（由 ${agent.model_label} 驱动）` : ''}`
                : `${agent.name} 已出局`}
              className={`group flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-all ${
                isCurrent
                  ? 'border-violet/60 bg-violet/12 shadow-[0_0_20px_rgba(140,125,245,0.16)]'
                  : agent.is_alive
                    ? 'border-line bg-white/[0.03] hover:border-gold/40 hover:bg-gold/5'
                    : 'border-line/60 bg-white/[0.015] opacity-55'
              }`}
            >
              <span
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg font-hud text-sm font-bold ${
                  !agent.is_alive
                    ? 'bg-danger/15 text-danger/70'
                    : agent.is_possessed
                      ? 'bg-gold/20 text-gold'
                      : isCurrent
                        ? 'bg-violet/25 text-violet'
                        : 'bg-white/8 text-white/70'
                }`}
              >
                {initial}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-text-primary">{agent.name}</span>
                <span className={`font-hud block truncate text-[11px] ${
                  isSpeaking ? 'text-violet' : !agent.is_alive ? 'text-danger/70' : agent.is_possessed ? 'text-gold' : 'text-text-secondary/55'
                }`}>
                  {isSpeaking ? (
                    <span className="flex items-center gap-1.5">
                      <span className="flex h-2.5 items-end gap-[2px]">
                        <span className="anim-eq-bar h-full w-[3px] rounded-full bg-violet" />
                        <span className="anim-eq-bar h-full w-[3px] rounded-full bg-violet [animation-delay:150ms]" />
                        <span className="anim-eq-bar h-full w-[3px] rounded-full bg-violet [animation-delay:300ms]" />
                      </span>
                      发言中
                    </span>
                  ) : !agent.is_alive
                    ? `${agent.role_cn || '已出局'} · 出局`
                    : agent.is_possessed
                      ? '已夺舍 · 受控'
                      : '待行动'}
                </span>
              </span>
              {agent.is_alive && (
                <span className={`font-hud shrink-0 text-[10px] uppercase tracking-wider text-gold opacity-0 transition-opacity group-hover:opacity-100`}>
                  夺舍
                </span>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );

  // 右栏：事件日志 HUD（等宽时间戳 + 语义色，对齐设计稿 3:360）
  const renderEventLog = (compact = false) => {
    const logEvents = events.slice(-14).reverse();
    return (
      <section className={`${compact ? 'p-3' : ''} flex flex-col`}>
        <p className="font-hud mb-3 text-[11px] uppercase tracking-[0.25em] text-text-secondary/60">
          事件日志 EVENT LOG
        </p>
        <div className={`scrollbar-none overflow-y-auto rounded-2xl border border-line bg-black/30 px-3 py-3 ${compact ? 'max-h-[52vh]' : 'flex-1 min-h-0'}`}>
          {logEvents.length === 0 ? (
            <p className="py-6 text-center font-hud text-xs text-text-secondary/45">等待实时事件…</p>
          ) : (
            <div className="space-y-2.5">
              {logEvents.map((event, index) => (
                <div
                  key={(event as WerewolfEvent & { uid?: string }).uid || `${event.type}-${index}`}
                  className={`anim-log-in flex items-start gap-2.5 rounded-lg border border-transparent px-2 py-1 text-xs leading-5 ${index === 0 ? 'anim-log-flash' : ''}`}
                >
                  <span className="font-hud shrink-0 text-text-secondary/45">{eventClock(event)}</span>
                  <span className={`min-w-0 flex-1 ${getEventLogTone(event)}`}>
                    {event === currentEvent && hasPlaybackContent
                      ? (visibleSpeech || visibleThought || '生成中…').slice(0, 60)
                      : getEventSummary(event)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    );
  };

  const renderMobilePanel = () => {
    if (!mobilePanel) {
      return null;
    }

    const titleMap = {
      history: '历史回放',
      players: '玩家席位',
      events: '事件流',
    } as const;

    return (
      <div className="fixed inset-0 z-[60] bg-black/85 p-3 backdrop-blur-md lg:hidden">
        <div className="flex h-full flex-col overflow-hidden rounded-[1.75rem] border border-white/10 bg-[#0b0917]/95 shadow-2xl">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <div className="text-lg font-bold text-gold">{titleMap[mobilePanel]}</div>
            <button
              onClick={() => setMobilePanel(null)}
              className="rounded-xl border border-white/10 p-2 text-white/60"
              aria-label="关闭移动端面板"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-hidden">
            {mobilePanel === 'history' && renderReplayHistory(true)}
            {mobilePanel === 'players' && renderAgentList(true)}
            {mobilePanel === 'events' && renderEventLog(true)}
          </div>
        </div>
      </div>
    );
  };

  return (
    <DarkMysticLayout>
      <div className={`flex flex-col p-3 md:p-4 ${gameState === 'playing' ? 'h-screen overflow-hidden' : 'min-h-screen'}`}>
        {/* Config State：对齐设计稿「模式选择/对局参数」语言（3:789） */}
        {gameState === 'config' && (
          <div className="flex-1">
            {/* 顶栏：标题 + 步骤徽章 + 返回 */}
            <header className="mb-6 flex items-center justify-between gap-4">
              <div className="flex items-baseline gap-4">
                <h1 className="text-[22px] font-bold text-text-primary">狼人杀 · 对局配置</h1>
                <span className="font-hud text-xs tracking-[0.18em] text-text-secondary/45">
                  STEP 1 / 2 · MATCH SETUP
                </span>
              </div>
              <button
                onClick={() => navigate('/')}
                className="flex items-center gap-2 rounded-xl border border-line bg-white/[0.04] px-4 py-2 text-sm text-text-secondary transition-colors hover:border-white/25 hover:text-text-primary"
              >
                <ArrowLeft className="h-4 w-4" />
                返回
              </button>
            </header>

            {error && (
              <div className="mb-5 p-4 bg-danger/15 border border-danger/50 rounded-xl text-danger flex items-center gap-2">
                <AlertCircle className="w-5 h-5" />
                {error}
              </div>
            )}

            {successMessage && (
              <div className="mb-5 p-4 bg-success/15 border border-success/40 rounded-xl text-success flex items-center gap-2">
                <History className="w-5 h-5" />
                {successMessage}
              </div>
            )}

            <div className="w-full grid gap-5 lg:grid-cols-[minmax(0,400px)_minmax(0,1fr)] items-start">
              <WerewolfGameConfig onStart={handleStartGame} />

              <div className="w-full lg:hidden rounded-[20px] border border-line bg-surface p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="mb-2 flex items-center gap-2 text-text-primary">
                      <History className="w-5 h-5" />
                      <h2 className="text-lg font-bold">对局记录</h2>
                    </div>
                    <p className="hidden text-xs leading-5 text-text-secondary/60 min-[430px]:block">回放和筛选放进独立面板。</p>
                  </div>
                  <button
                    onClick={() => setMobilePanel('history')}
                    className="shrink-0 rounded-xl border border-gold/40 bg-gold/10 px-4 py-2 text-sm font-medium text-gold"
                  >
                    打开
                  </button>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2">
                  <div className="rounded-xl bg-white/[0.04] px-3 py-2">
                    <div className="text-[10px] text-text-secondary/50">总数</div>
                    <div className="text-lg font-semibold text-text-primary">{replayStats.total}</div>
                  </div>
                  <div className="rounded-xl bg-success/10 px-3 py-2">
                    <div className="text-[10px] text-success/70">进行中</div>
                    <div className="font-hud text-lg font-semibold text-success">{replayStats.active}</div>
                  </div>
                  <div className="rounded-xl bg-white/[0.04] px-3 py-2">
                    <div className="text-[10px] text-text-secondary/50">已结束</div>
                    <div className="text-lg font-semibold text-text-primary">{replayStats.finished}</div>
                  </div>
                </div>
              </div>

              <div className="hidden lg:block">
                {renderReplayHistory()}
              </div>
            </div>
          </div>
        )}

        {/* Loading State：召唤序列（对齐设计系统「等待与转场」规范） */}
        {gameState === 'loading' && (
          <div className="flex-1 flex flex-col items-center justify-center animate-fadeIn">
            <div className="w-16 h-16 border-4 border-gold/20 border-t-gold rounded-full animate-spin mb-8 shadow-[0_0_15px_rgba(232,194,105,0.3)]"></div>
            <div className="mb-8 flex flex-col gap-1.5 font-hud text-sm">
              <span className="anim-step-in text-text-secondary/60" style={{ animationDelay: '0ms' }}><Check size={12} className="inline -mt-0.5" />&nbsp; 连接模型网关</span>
              <span className="anim-step-in text-text-secondary/60" style={{ animationDelay: '250ms' }}><Check size={12} className="inline -mt-0.5" />&nbsp; 分配角色与性格（MBTI / IQ）</span>
              <span className="anim-step-in text-sm font-bold text-gold animate-pulse-soft" style={{ animationDelay: '500ms' }}>◆&nbsp; 为玩家注入灵魂 · LLM 起名中…</span>
              <span className="anim-step-in text-white/25" style={{ animationDelay: '750ms' }}>○&nbsp; 夜幕降临，迷雾散开</span>
            </div>
            <div className="flex max-w-md flex-wrap items-center justify-center gap-2">
              {Array.from({ length: pendingPlayerCount }).map((_, i) => {
                const lit = i < Math.max(2, Math.ceil(pendingPlayerCount / 3));
                return (
                  <span
                    key={i}
                    className={`anim-seat-in flex w-14 flex-col items-center gap-1.5 rounded-xl border px-2 py-2 ${
                      lit ? 'border-gold/35 bg-gold/8' : 'border-white/8 bg-white/[0.03]'
                    }`}
                    style={{ animationDelay: `${900 + i * 180}ms` }}
                  >
                    <span className={`h-5 w-5 rounded-full ${lit ? 'bg-gold/40' : 'bg-white/10'}`} />
                    <span className={`h-1.5 w-full rounded-full ${lit ? 'anim-name-shimmer' : 'anim-name-shimmer-dim'}`} />
                  </span>
                );
              })}
            </div>
          </div>
        )}

        {/* Playing State */}
        {gameState === 'playing' && gameData && (
          <div className="flex min-h-0 flex-1 flex-col animate-fadeIn">
            {/* HUD 顶栏：标题 + 阶段胶囊 + 行动时钟 */}
            <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    if (cleanupRef.current) cleanupRef.current();
                    navigate('/');
                  }}
                  className="rounded-xl border border-line p-2 text-gold/70 transition-colors hover:border-gold/40 hover:text-gold"
                  title="退出对局"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
                <div>
                  <h1 className="text-xl font-black tracking-wide text-text-primary md:text-2xl">
                    狼人杀 · 第
                    <span key={gameData.currentRound} className="anim-pill-pop mx-1 inline-block text-gold">
                      {gameData.currentRound}
                    </span>
                    回合
                  </h1>
                  <p className="font-hud text-[11px] uppercase tracking-[0.2em] text-text-secondary/55">
                    {gameData.agents.length} 人局 · 实时对局
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <button
                  onClick={() => {
                    if (gameData.gameId) {
                      setSelectedReplayGameId(gameData.gameId);
                    }
                    setShowTimelineReplay(true);
                  }}
                  className="flex items-center gap-2 rounded-full border border-line px-4 py-2 text-sm text-text-secondary/75 transition-colors hover:border-gold/40 hover:text-gold"
                  title="查看回放"
                >
                  <History className="h-4 w-4" />
                  回放
                </button>
                <button
                  onClick={handleTerminateGame}
                  disabled={terminating}
                  className="flex items-center gap-2 rounded-full border border-danger/40 bg-danger/10 px-4 py-2 text-sm text-danger transition-colors hover:border-danger/70 hover:bg-danger/20 disabled:opacity-50"
                  title="终止本局游戏"
                >
                  <OctagonX className="h-4 w-4" />
                  {terminating ? '终止中…' : '终止对局'}
                </button>
                <div className="flex items-center gap-2 rounded-full border border-violet/45 bg-violet/12 px-4 py-2 text-violet">
                  <span key={gameData.phase} className="anim-pill-pop flex items-center gap-2">
                    {getPhaseIcon(gameData.phase)}
                    <span className="text-sm font-semibold">{getPhaseBadge(gameData.phase)}</span>
                  </span>
                </div>
                <div className="text-right">
                  <div className="font-hud text-[10px] uppercase tracking-[0.25em] text-text-secondary/50">行动剩余</div>
                  <div className="font-hud text-3xl font-black leading-none text-gold md:text-4xl">{phaseClock}</div>
                </div>
              </div>
            </header>

            {/* 节奏控制条：自动连播（可调速）/ 手动步进 */}
            <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface/60 px-3 py-2">
              <span className="font-hud text-[10px] uppercase tracking-[0.2em] text-text-secondary/50">
                节奏 PACE
              </span>
              <div className="flex gap-1.5">
                <button
                  type="button"
                  onClick={() => handlePaceMode('auto')}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs transition-all ${
                    paceMode === 'auto'
                      ? 'bg-violet font-medium text-[#14121f]'
                      : 'bg-white/[0.06] text-text-secondary hover:bg-white/[0.1]'
                  }`}
                >
                  <Pause size={12} className="rotate-180" />
                  自动连播
                </button>
                <button
                  type="button"
                  onClick={() => handlePaceMode('manual')}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs transition-all ${
                    paceMode === 'manual'
                      ? 'bg-violet font-medium text-[#14121f]'
                      : 'bg-white/[0.06] text-text-secondary hover:bg-white/[0.1]'
                  }`}
                >
                  手动步进
                </button>
              </div>

              {paceMode === 'auto' ? (
                <div className="flex items-center gap-1.5">
                  <span className="font-hud text-[10px] uppercase tracking-wider text-text-secondary/40">速度</span>
                  {[0.5, 1, 2].map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => handlePaceSpeed(s)}
                      className={`rounded-lg px-2.5 py-1 font-hud text-[11px] transition-all ${
                        paceSpeed === s
                          ? 'border border-gold/50 bg-gold/15 text-gold'
                          : 'border border-line text-text-secondary/60 hover:border-white/25'
                      }`}
                    >
                      {s}x
                    </button>
                  ))}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={handleManualAdvance}
                  className="flex items-center gap-1.5 rounded-lg bg-gold px-4 py-1.5 text-xs font-medium text-[#2B2836] shadow-[0_0_16px_rgba(232,194,105,0.28)] transition-all hover:shadow-[0_0_24px_rgba(232,194,105,0.4)] active:scale-[0.98]"
                  title="快捷键：空格 / →"
                >
                  <SkipForward size={12} />
                  下一步
                </button>
              )}
              <span className="ml-auto hidden font-hud text-[10px] text-text-secondary/35 sm:block">
                {paceMode === 'manual' ? '空格 / → 放行' : '长发言自动停留更久'}
              </span>
            </div>

            <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[230px_minmax(0,1fr)_300px] xl:grid-cols-[250px_minmax(0,1fr)_320px]">
              {/* 左栏 · 在局智能体 */}
              <aside className="hidden min-h-0 flex-col overflow-y-auto scrollbar-none rounded-[1.5rem] border border-line bg-surface/40 p-4 backdrop-blur-xl lg:flex">
                {renderAgentList()}
              </aside>

              {/* 中栏 · 发言舞台 */}
              <section className={`relative flex min-h-0 flex-col overflow-hidden rounded-[1.5rem] border p-4 shadow-2xl backdrop-blur-xl md:rounded-[2rem] md:p-6 ${getEventTone(currentEvent)}`}>
                <div className="pointer-events-none absolute inset-0 opacity-60">
                  {/* 阶段切换：雾气横扫一次（key 随视觉阶段变化触发） */}
                  <div
                    key={`fog-${currentVisualPhase}`}
                    className="anim-fog-sweep pointer-events-none absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-white/10 to-transparent"
                  />
                  <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${atmosphere.accent} animate-shimmer-line`} />
                  {currentVisualPhase === 'night' && (
                    <>
                      <div className="absolute -left-24 top-10 h-40 w-[130%] rotate-[-8deg] rounded-full bg-violet-300/10 blur-3xl animate-drift-fog" />
                      <div className="absolute right-8 top-12 h-2 w-2 rounded-full bg-white/70 shadow-[0_0_24px_rgba(255,255,255,0.8)] animate-star-blink" />
                    </>
                  )}
                  {currentVisualPhase === 'dawn' && (
                    <div className="absolute -top-36 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-gold/20 blur-3xl animate-sunrise-glow" />
                  )}
                  {currentVisualPhase === 'day_discussion' && (
                    <>
                      <div className="absolute left-10 top-20 h-28 w-28 rounded-full border border-info/20 animate-sound-ring" />
                      <div className="absolute inset-x-10 bottom-8 h-px bg-gradient-to-r from-transparent via-info/50 to-transparent animate-dialogue-scan" />
                    </>
                  )}
                  {currentVisualPhase === 'day_voting' && (
                    <div className="absolute right-8 top-20 h-28 w-28 rounded-full bg-danger/10 blur-2xl animate-heat-pulse" />
                  )}
                  {currentVisualPhase === 'result' && (
                    <div className="absolute left-1/2 top-1/2 h-px w-[80%] -translate-x-1/2 rotate-12 bg-danger/40 animate-crack-flash" />
                  )}
                </div>

                <div ref={stageScrollRef} className="relative flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto scrollbar-none">
                  {chatStyle === 'group_chat' ? (
                    /* 群聊讨论区：所有人的消息都在这里，像 QQ 群一样刷屏 */
                    <div className="flex min-h-0 flex-1 flex-col">
                      <div className="mb-2.5 flex items-center justify-between rounded-xl border border-line bg-black/25 px-3.5 py-2">
                        <span className="font-hud text-[11px] uppercase tracking-[0.3em] text-info">Group Chat</span>
                        <span className="font-hud text-[11px] text-text-secondary/50">
                          第 {gameData.currentRound} 天 · {chatMessages.length} 条消息
                        </span>
                      </div>
                      <div className="flex flex-1 flex-col gap-bubble-loose pb-2">
                        <div className="mx-auto rounded-full bg-white/[0.05] px-3.5 py-1 text-[10px] text-text-secondary/50">
                          群聊已建立，请文明发言
                        </div>
                        {chatMessages.map((msg) => {
                          const isNew = msg.uid === latestChatUid;
                          return (
                            <div key={msg.uid} className="flex items-start gap-2.5">
                              <span
                                className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg font-hud text-sm font-bold text-white ${avatarToneOf(msg.agentName)}`}
                              >
                                {msg.agentName.slice(0, 1)}
                              </span>
                              <div className="min-w-0">
                                <div className="mb-1 flex items-center gap-1.5">
                                  <span className="text-xs font-medium text-text-secondary/75">{msg.agentName}</span>
                                  {msg.playerControlled && (
                                    <span className="rounded border border-gold/40 bg-gold/10 px-1.5 py-px font-hud text-[9px] text-gold">
                                      玩家代打
                                    </span>
                                  )}
                                  {msg.phase === 'opening' && (
                                    <span className="rounded border border-gold/30 bg-gold/8 px-1.5 py-px font-hud text-[9px] text-gold/80">
                                      入座
                                    </span>
                                  )}
                                </div>
                                <div className="flex flex-col items-start gap-bubble">
                                  {msg.bubbles.map((bubble, bubbleIndex) => (
                                    <div
                                      key={`${msg.uid}-b-${bubbleIndex}`}
                                      className={`max-w-[85%] rounded-2xl rounded-tl-sm border border-info/20 bg-info/[0.08] px-3.5 py-2 text-[14px] leading-6 text-text-primary md:text-[15px] md:leading-7 ${
                                        isNew ? 'anim-pill-pop' : ''
                                      }`}
                                      style={isNew ? { animationDelay: `${bubbleIndex * 140}ms` } : undefined}
                                    >
                                      {bubble}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                        {currentEvent?.type === 'agent_speaking' && !currentEvent?.speech && currentBubbles.length === 0 && (
                          <div className="flex items-center gap-2.5 pl-1 text-sm text-violet/80">
                            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet/20 font-hud text-xs font-bold text-violet">
                              {(currentEvent?.agent_name || '…').slice(0, 1)}
                            </span>
                            <span className="flex items-center gap-2">
                              {currentEvent?.agent_name || '有人'} 正在输入
                              <span className="flex gap-1">
                                <span className="anim-thinking-dot h-1.5 w-1.5 rounded-full bg-violet" />
                                <span className="anim-thinking-dot h-1.5 w-1.5 rounded-full bg-violet [animation-delay:150ms]" />
                                <span className="anim-thinking-dot h-1.5 w-1.5 rounded-full bg-violet [animation-delay:300ms]" />
                              </span>
                            </span>
                          </div>
                        )}
                        <div ref={chatEndRef} />
                      </div>
                    </div>
                  ) : (
                  <>
                  {/* NOW SPEAKING 大卡 */}
                  <div className="rounded-2xl border border-violet/30 bg-black/45 p-5 backdrop-blur">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <span className="font-hud text-[11px] uppercase tracking-[0.3em] text-violet">Now Speaking</span>
                      <span className="font-hud text-[11px] text-text-secondary/50">
                        {eventClock(currentEvent)} · {getPhaseText(getEventPhase(currentEvent))}
                      </span>
                    </div>
                    {currentBubbles.length > 0 ? (
                      <div className="flex min-h-16 flex-col items-start gap-bubble">
                        {currentBubbles.map((bubble, bubbleIndex) => (
                          <div
                            key={`${currentEvent?.uid || 'evt'}-bubble-${bubbleIndex}`}
                            className="anim-pill-pop max-w-[88%] rounded-2xl rounded-tl-sm border border-violet/25 bg-violet/10 px-3.5 py-2 text-[15px] leading-7 text-text-primary md:text-base"
                            style={{ animationDelay: `${bubbleIndex * 140}ms` }}
                          >
                            {bubble}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="min-h-16 text-lg leading-8 text-text-primary md:text-xl md:leading-9">
                        {(visibleSpeech || getEventSummary(currentEvent)) && (
                          <>“{visibleSpeech || getEventSummary(currentEvent)}”</>
                        )}
                        {isSpeechPlaying && <span className="ml-0.5 inline-block h-5 w-2 translate-y-1 bg-violet/70 animate-pulse" />}
                      </p>
                    )}
                    <div className="mt-4 flex items-center gap-3">
                      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet/25 font-hud text-sm font-bold text-violet">
                        {(currentActor?.name || currentEvent?.agent_name || '系').slice(0, 1)}
                      </span>
                      <div className="min-w-0">
                        <div className="truncate text-sm font-bold text-text-primary">
                          {currentActor?.name || currentEvent?.agent_name || currentEvent?.actor_name || '主持人'}
                        </div>
                        <div className="font-hud text-[10px] uppercase tracking-[0.2em] text-violet/80">
                          {isSpeechPlaying ? 'Speaking' : currentActor ? 'Standby' : 'Host'} · {getEventTitle(currentEvent)}
                        </div>
                      </div>
                      {currentActor && (
                        <span className="font-hud ml-auto shrink-0 rounded-full border border-white/10 bg-black/30 px-3 py-1 text-[10px] text-text-secondary/60">
                          {currentActor.mbti_type} / {currentActor.iq_level}
                        </span>
                      )}
                    </div>
                    {!hasPlaybackContent && currentEvent?.type === 'agent_speaking' && !currentEvent?.speech && (
                      <div className="mt-3 flex flex-col gap-3">
                        <div className="flex items-center gap-3 text-sm text-info/80">
                          <div className="flex gap-1.5">
                            <span className="anim-thinking-dot h-2 w-2 rounded-full bg-violet" />
                            <span className="anim-thinking-dot h-2 w-2 rounded-full bg-violet [animation-delay:150ms]" />
                            <span className="anim-thinking-dot h-2 w-2 rounded-full bg-violet [animation-delay:300ms]" />
                          </div>
                          模型正在生成发言…
                        </div>
                        <div className="flex flex-col gap-2">
                          <span className="anim-name-shimmer-dim h-3 w-11/12 rounded-full" />
                          <span className="anim-name-shimmer-dim h-3 w-2/3 rounded-full" />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* 思考过程回放 */}
                  {thoughtPlaybackTokens.length > 0 && (
                    <div className="rounded-2xl border border-gold/20 bg-gold/10 p-4">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 text-sm font-semibold text-gold">
                          <Brain className="h-4 w-4" />
                          思考过程回放
                        </div>
                        <span className="font-hud text-[11px] text-gold/80">
                          {Math.min(tokenPlayback.thought, thoughtPlaybackTokens.length)} / {thoughtPlaybackTokens.length}
                        </span>
                      </div>
                      <p className="text-sm leading-7 text-text-secondary/85">
                        {visibleThought}
                        {isThoughtPlaying && <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 bg-gold animate-pulse" />}
                      </p>
                    </div>
                  )}

                  {/* 最近发言气泡 */}
                  {recentSpeeches.filter((event) => event !== currentEvent).slice(0, 2).map((event, index) => (
                    <div key={`${event.agent_id || 'x'}-${index}`} className="rounded-2xl border border-line bg-white/[0.03] px-4 py-3">
                      <div className="font-hud mb-1 text-[11px] uppercase tracking-[0.2em] text-info">
                        玩家 · {event.agent_name || '玩家'}
                      </div>
                      <p className="line-clamp-2 text-sm leading-6 text-text-secondary/85">
                        {(event === currentEvent ? visibleSpeech : event.speech || event.content) || '…'}
                      </p>
                    </div>
                  ))}

                  {/* 主持人提示线 */}
                  {latestPublicSignal && (
                    <div className="flex items-start gap-2 text-sm text-text-secondary/75">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-gold" />
                      <span className="line-clamp-2">主持人：{getEventSummary(latestPublicSignal)}</span>
                    </div>
                  )}
                  </>
                  )}
                </div>

                {/* 底部操作条 */}
                <div className="relative mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-black/30 px-4 py-3">
                  <div className="flex items-center gap-2 text-xs text-text-secondary/55">
                    <span className="rounded-md border border-line bg-white/[0.04] px-2 py-1">快捷：点击左侧玩家</span>
                    <span>夺席可接管该玩家行动</span>
                    {activeModelLabel && (
                      <span className="font-hud ml-1 rounded-md border border-gold/25 bg-gold/10 px-2 py-1 text-gold/85">
                        {activeModelLabel}
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => {
                      const target = possessedAgent || currentActor || aliveAgents[0];
                      if (target) {
                        handleAgentClick(target);
                      }
                    }}
                    className="flex items-center gap-2 rounded-xl bg-gold px-5 py-2 text-sm font-bold text-[#171424] shadow-[0_0_18px_rgba(232,194,105,0.35)] transition-all hover:brightness-110"
                  >
                    夺席控制
                  </button>
                </div>
              </section>

              {/* 右栏 · 事件日志 + 统计 */}
              <aside className="hidden min-h-0 flex-col gap-4 overflow-hidden lg:flex">
                <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[1.5rem] border border-line bg-surface/40 p-4 backdrop-blur-xl">
                  {renderEventLog()}
                </div>

                <div className="shrink-0 space-y-3">
                  <div className="grid grid-cols-3 gap-2">
                    <div className="rounded-xl border border-line bg-black/30 px-2 py-3 text-center">
                      <div className="font-hud text-2xl font-black text-success">{aliveAgents.length}</div>
                      <div className="mt-1 text-[10px] text-text-secondary/55">存活</div>
                    </div>
                    <div className="rounded-xl border border-line bg-black/30 px-2 py-3 text-center">
                      <div className="font-hud text-2xl font-black text-danger">{deadAgents.length}</div>
                      <div className="mt-1 text-[10px] text-text-secondary/55">出局</div>
                    </div>
                    <div className="rounded-xl border border-line bg-black/30 px-2 py-3 text-center">
                      <div className="font-hud text-2xl font-black text-gold">{gameData.currentRound}</div>
                      <div className="mt-1 text-[10px] text-text-secondary/55">回合</div>
                    </div>
                  </div>

                  <div className="rounded-xl border border-line bg-surface/40 p-3 backdrop-blur-xl">
                    <div className="font-hud mb-2 text-[10px] uppercase tracking-[0.25em] text-text-secondary/55">
                      放逐投票 TAB VOTE
                    </div>
                    {liveVoteTally.size === 0 ? (
                      <div className="flex h-7 items-center rounded-lg bg-white/8 px-3 text-[11px] text-text-secondary/50">
                        {leadingLiveVote ? `${leadingLiveVote[0]} ${leadingLiveVote[1]} 票领先` : '本轮暂无投票'}
                      </div>
                    ) : (
                      <>
                        <div className="flex h-7 overflow-hidden rounded-lg">
                          {Array.from(liveVoteTally.entries()).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([name, count], index) => {
                            const total = Array.from(liveVoteTally.values()).reduce((sum, v) => sum + v, 0);
                            const tones = ['bg-danger/80', 'bg-gold/80', 'bg-info/80', 'bg-violet/80'];
                            return (
                              <div
                                key={name}
                                className={`${tones[index % tones.length]} flex items-center justify-center text-[10px] font-bold text-black/80`}
                                style={{ width: `${Math.max(14, (count / Math.max(1, total)) * 100)}%` }}
                                title={`${name} ${count} 票`}
                              >
                                {count}
                              </div>
                            );
                          })}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-secondary/60">
                          {Array.from(liveVoteTally.entries()).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([name, count]) => (
                            <span key={name}>{name} · {count} 票</span>
                          ))}
                        </div>
                      </>
                    )}
                  </div>

                  <div className="flex items-center justify-between rounded-xl border border-line bg-white/[0.03] px-3 py-2 text-[11px] text-text-secondary/55">
                    <span>局势压力</span>
                    <span className="font-hud text-gold">{tensionScore}%</span>
                  </div>
                </div>
              </aside>
            </div>

            {/* 移动端快捷入口 */}
            <section className="grid grid-cols-3 gap-2 rounded-[1.5rem] border border-line bg-surface/40 p-3 backdrop-blur-xl lg:hidden">
              <button
                onClick={() => setMobilePanel('players')}
                className="rounded-2xl border border-gold/25 bg-gold/10 px-3 py-3 text-left text-gold"
              >
                <Users className="mb-2 h-5 w-5" />
                <div className="text-sm font-semibold">玩家</div>
                <div className="text-[11px] text-text-secondary/45">{gameData.agents.length} 席</div>
              </button>
              <button
                onClick={() => setMobilePanel('events')}
                className="rounded-2xl border border-info/25 bg-info/10 px-3 py-3 text-left text-info"
              >
                <Activity className="mb-2 h-5 w-5" />
                <div className="text-sm font-semibold">事件</div>
                <div className="text-[11px] text-text-secondary/45">{events.length} 条</div>
              </button>
              <button
                onClick={() => {
                  setSelectedReplayGameId(gameData.gameId);
                  setShowTimelineReplay(true);
                }}
                className="rounded-2xl border border-line bg-white/[0.04] px-3 py-3 text-left text-text-secondary/80"
              >
                <History className="mb-2 h-5 w-5" />
                <div className="text-sm font-semibold">回放</div>
                <div className="text-[11px] text-text-secondary/45">时间轴</div>
              </button>
            </section>
          </div>
        )}


        {/* Game Over State */}
        {gameState === 'game_over' && gameData && gameData.winner && (
          <WerewolfGameOver
            winner={gameData.winner}
            reason={gameData.winReason || '游戏结束'}
            currentRound={gameData.currentRound}
            agents={gameData.agents}
            events={events}
            gameId={gameData.gameId}
            onReplay={handleOpenReplay}
            onRematch={handleRematch}
          />
        )}

        {/* Possession Control Modal */}
        {showPossessionControl && possessedAgent && gameData && (
          <PossessionControl
            gameId={gameData.gameId}
            possessedAgent={possessedAgent}
            allAgents={gameData.agents}
            currentPhase={gameData.phase}
            onClose={handleClosePossession}
            onActionComplete={() => {
              setSuccessMessage(`${possessedAgent.name} 的操作已提交，等待实时事件确认`);
            }}
          />
        )}

        {/* Timeline Replay Modal */}
        {showTimelineReplay && selectedReplayGameId && (
          <TimelineReplay
            gameId={selectedReplayGameId}
            onClose={handleCloseReplay}
          />
        )}

        {renderMobilePanel()}
      </div>
    </DarkMysticLayout>
  );
};

export default WerewolfMode;

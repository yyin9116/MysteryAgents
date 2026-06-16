import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Moon, Sun, MessageCircle, Vote, AlertCircle, ArrowLeft, History, Clock, RefreshCcw, Search, Trash2, Skull, Sparkles, Eye, Shield, Crosshair, Users, Activity, Brain, Target, X } from 'lucide-react';
import DarkMysticLayout from '../components/werewolf/DarkMysticLayout';
import WerewolfGameConfig from '../components/werewolf/WerewolfGameConfig';
import PossessionControl from '../components/werewolf/PossessionControl';
import WerewolfGameOver from '../components/werewolf/WerewolfGameOver';
import WerewolfCard3D from '../components/werewolf/WerewolfCard3D';
import TimelineReplay from '../components/werewolf/TimelineReplay';
import type { GameConfig } from '../components/werewolf/WerewolfGameConfig';
import type { WerewolfAgent } from '../types/werewolf';
import { deleteFinishedWerewolfReplays, deleteWerewolfReplay, downloadWerewolfReplay, listWerewolfReplays, type ReplaySummary } from '../services/werewolfReplayService';
import { useSettingsStore } from '../store/settingsStore';
import {
  createGame,
  connectGameStreamWithRetry,
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
  const [flippedCards, setFlippedCards] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string>('');
  const [successMessage, setSuccessMessage] = useState<string>('');
  const [activeModelLabel, setActiveModelLabel] = useState<string>('');
  const [tokenPlayback, setTokenPlayback] = useState({ speech: 0, thought: 0 });
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
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
      const cleanup = connectGameStreamWithRetry(
        response.game_id,
        handleGameEvent,
        5
      );
      cleanupRef.current = cleanup;
      setSelectedReplayGameId(response.game_id);
      loadReplayHistory();

      setGameState('playing');
    } catch (err: any) {
      console.error('Failed to start game:', err);
      setError(err.message || '游戏创建失败');
      setGameState('config');
    }
  };

  const handleOpenReplay = () => {
    if (gameData?.gameId) {
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
    console.log('Game event:', event);
    setEvents(prev => [...prev, event]);
    setCurrentEvent(event);

    switch (event.type) {
      case 'game_start':
        // Game started
        break;

      case 'phase_change':
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
    // In a real implementation, fetch all agent roles from backend
    // For now, we'll just mark that roles should be visible
    console.log('Revealing all roles');
  };

  const handleAgentClick = (agent: Agent) => {
    if (!agent.is_alive) return;

    setPossessedAgent(agent);
    setShowPossessionControl(true);
  };

  const handleClosePossession = () => {
    setShowPossessionControl(false);
  };

  const handleCardFlip = (agentId: string) => {
    setFlippedCards(prev => {
      const newSet = new Set(prev);
      if (newSet.has(agentId)) {
        newSet.delete(agentId);
      } else {
        newSet.add(agentId);
      }
      return newSet;
    });
  };

  const convertAgentToWerewolfAgent = (agent: Agent): WerewolfAgent => {
    return {
      id: agent.agent_id,
      name: agent.name,
      role: (agent.role || 'unknown') as any,
      isAlive: agent.is_alive,
      mbti: agent.mbti_type,
      iq: agent.iq_level as any,
    };
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

  const getPhaseColor = (phase: string) => {
    switch (normalizePhase(phase)) {
      case 'night':
        return 'text-purple-400';
      case 'dawn':
        return 'text-orange-400';
      case 'day_discussion':
        return 'text-blue-400';
      case 'day_voting':
        return 'text-red-400';
      default:
        return 'text-ww-gold';
    }
  };

  const phaseSteps = [
    { key: 'night', label: '夜晚行动', hint: '狼人/神职暗中行动', icon: Moon },
    { key: 'dawn', label: '天亮结算', hint: '公布夜间结果', icon: Sun },
    { key: 'day_discussion', label: '白天发言', hint: '逐个分析与博弈', icon: MessageCircle },
    { key: 'day_voting', label: '放逐投票', hint: '公开投票处决', icon: Vote },
    { key: 'result', label: '胜负结算', hint: '阵营胜利条件', icon: Sparkles },
  ];

  const getEventPhase = (event?: WerewolfEvent | null) => normalizePhase(event?.phase || event?.to_phase || event?.data?.to_phase || gameData?.phase);
  const currentVisualPhase = currentEvent?.type === 'elimination' || currentEvent?.type === 'game_over'
    ? 'result'
    : getEventPhase(currentEvent);

  const getPhaseAtmosphere = (phase?: string) => {
    switch (normalizePhase(phase)) {
      case 'night':
        return {
          shell: 'border-violet-400/30 bg-[radial-gradient(circle_at_20%_20%,rgba(91,33,182,0.28),transparent_34%),linear-gradient(135deg,rgba(8,6,24,0.94),rgba(15,23,42,0.82))]',
          accent: 'from-violet-300 via-fuchsia-300 to-slate-300',
          label: '夜雾潜行',
          motion: '雾线流动 / 暗杀轨迹',
        };
      case 'dawn':
        return {
          shell: 'border-amber-300/30 bg-[radial-gradient(circle_at_50%_0%,rgba(251,191,36,0.28),transparent_36%),linear-gradient(135deg,rgba(69,26,3,0.78),rgba(15,23,42,0.86))]',
          accent: 'from-amber-200 via-orange-300 to-rose-200',
          label: '晨光结算',
          motion: '日出扫光 / 伤亡公布',
        };
      case 'day_discussion':
        return {
          shell: 'border-sky-300/30 bg-[radial-gradient(circle_at_15%_80%,rgba(14,165,233,0.22),transparent_35%),linear-gradient(135deg,rgba(8,47,73,0.78),rgba(15,23,42,0.86))]',
          accent: 'from-sky-200 via-cyan-300 to-blue-300',
          label: '圆桌发言',
          motion: '声波扩散 / 视线交锋',
        };
      case 'day_voting':
        return {
          shell: 'border-orange-300/30 bg-[radial-gradient(circle_at_80%_30%,rgba(249,115,22,0.24),transparent_34%),linear-gradient(135deg,rgba(67,20,7,0.82),rgba(15,23,42,0.86))]',
          accent: 'from-orange-200 via-red-300 to-yellow-200',
          label: '票压倒计',
          motion: '投票箭线 / 压迫热浪',
        };
      case 'result':
        return {
          shell: 'border-red-300/35 bg-[radial-gradient(circle_at_50%_50%,rgba(239,68,68,0.24),transparent_36%),linear-gradient(135deg,rgba(69,10,10,0.82),rgba(15,23,42,0.9))]',
          accent: 'from-red-200 via-ww-gold to-white',
          label: '命运揭示',
          motion: '裂纹冲击 / 阵营落幕',
        };
      default:
        return {
          shell: 'border-ww-gold/25 bg-black/35',
          accent: 'from-ww-gold via-white to-ww-gold',
          label: '实时剧场',
          motion: '事件同步',
        };
    }
  };

  const atmosphere = getPhaseAtmosphere(currentVisualPhase);

  const getEventTone = (event?: WerewolfEvent | null) => {
    const type = event?.type;
    const phase = getEventPhase(event);
    if (type === 'error') return 'border-red-400/40 bg-red-500/10 text-red-100';
    if (type === 'elimination' || type === 'game_over' || type === 'death_announcement') return 'border-red-400/35 bg-red-500/10 text-red-100';
    if (type === 'agent_voting' || type === 'vote' || phase === 'day_voting') return 'border-orange-400/35 bg-orange-500/10 text-orange-100';
    if (type === 'agent_speaking' || type === 'discussion' || phase === 'day_discussion') return 'border-sky-400/35 bg-sky-500/10 text-sky-100';
    if (type === 'night_action' || phase === 'night') return 'border-violet-400/35 bg-violet-500/10 text-violet-100';
    if (phase === 'dawn') return 'border-amber-400/35 bg-amber-500/10 text-amber-100';
    return 'border-ww-gold/30 bg-ww-gold/10 text-ww-gold';
  };

  const getEventIcon = (event?: WerewolfEvent | null) => {
    const type = event?.type;
    const actionType = event?.action_type;
    if (type === 'agent_speaking' || type === 'discussion') return <MessageCircle className="w-5 h-5" />;
    if (type === 'agent_voting' || type === 'vote') return <Vote className="w-5 h-5" />;
    if (type === 'elimination' || type === 'death_announcement') return <Skull className="w-5 h-5" />;
    if (type === 'game_over') return <Sparkles className="w-5 h-5" />;
    if (type === 'error') return <AlertCircle className="w-5 h-5" />;
    if (actionType === 'seer_check') return <Eye className="w-5 h-5" />;
    if (actionType === 'guard_protect') return <Shield className="w-5 h-5" />;
    if (actionType === 'werewolf_kill') return <Crosshair className="w-5 h-5" />;
    return getPhaseIcon(getEventPhase(event)) || <Activity className="w-5 h-5" />;
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
  const currentActorId = currentEvent?.agent_id || currentEvent?.actor_id || currentEvent?.voter_id || currentEvent?.eliminated_id;
  const recentSpeeches = events
    .filter((event) => (event.type === 'agent_speaking' || event.type === 'discussion') && (event.speech || event.content))
    .slice(-3)
    .reverse();
  const recentVotes = events
    .filter((event) => (event.type === 'agent_voting' || event.type === 'vote') && (event.voted_for_name || event.target_name))
    .slice(-4)
    .reverse();
  const recentTimelineEvents = events
    .filter((event) => getEventSummary(event).trim().length > 0)
    .slice(-12)
    .reverse();

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
      return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
    }
    if (replay.winner === 'good') {
      return 'bg-sky-500/15 text-sky-300 border-sky-500/30';
    }
    if (replay.winner === 'werewolf') {
      return 'bg-rose-500/15 text-rose-300 border-rose-500/30';
    }
    return 'bg-white/10 text-white/60 border-white/10';
  };

  const renderReplayHistory = (compact = false) => (
    <div className={`${compact ? 'p-4' : 'p-8'} w-full rounded-3xl border border-white/10 bg-black/30 backdrop-blur-sm animate-slideUp`}>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className={`${compact ? 'text-xl' : 'text-2xl'} font-bold text-ww-gold`}>历史回放</h2>
          <p className="text-sm text-white/50 mt-1">已保存的狼人杀时间轴，可随时重看</p>
        </div>
        <button
          onClick={loadReplayHistory}
          className="p-2 rounded-xl border border-white/10 text-white/60 hover:text-ww-gold hover:border-ww-gold/30 transition-colors"
          title="刷新历史回放"
        >
          <RefreshCcw className={`w-4 h-4 ${replaysLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] mb-4">
        <label className="flex items-center gap-2 px-3 py-2 rounded-xl border border-white/10 bg-black/20 text-white/60">
          <Search className="w-4 h-4" />
          <input
            value={replaySearch}
            onChange={(event) => setReplaySearch(event.target.value)}
            placeholder="搜索 game_id"
            className="w-full bg-transparent outline-none text-sm text-white placeholder:text-white/25"
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
              className={`shrink-0 px-3 py-2 rounded-xl text-sm border transition-colors ${
                replayFilter === value
                  ? 'border-ww-gold/40 bg-ww-gold/10 text-ww-gold'
                  : 'border-white/10 text-white/55 hover:border-white/25'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-white/35">排序会作用于当前筛选结果</p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-white/60">
            <span>排序</span>
            <select
              value={replaySort}
              onChange={(event) => setReplaySort(event.target.value as ReplaySortOption)}
              className="rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none"
            >
              <option value="updated_desc">最近更新</option>
              <option value="started_desc">最近开始</option>
              <option value="started_asc">最早开始</option>
              <option value="events_desc">事件最多</option>
            </select>
          </label>
          <button
            onClick={handleDeleteFinishedReplays}
            className="rounded-xl border border-red-400/20 bg-red-500/10 px-3 py-2 text-sm text-red-200 transition-colors hover:border-red-400/40 hover:bg-red-500/15"
            title="清理全部已结束回放"
          >
            清理已结束
          </button>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-2 sm:gap-3">
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-3 sm:px-4">
          <div className="text-[11px] text-white/35 sm:text-xs">总数</div>
          <div className="mt-1 text-lg font-semibold text-white sm:text-xl">{replayStats.total}</div>
        </div>
        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-3 sm:px-4">
          <div className="text-[11px] text-emerald-200/70 sm:text-xs">进行中</div>
          <div className="mt-1 text-lg font-semibold text-emerald-200 sm:text-xl">{replayStats.active}</div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-3 sm:px-4">
          <div className="text-[11px] text-white/35 sm:text-xs">已结束</div>
          <div className="mt-1 text-lg font-semibold text-white sm:text-xl">{replayStats.finished}</div>
        </div>
      </div>

      {replaysLoading && replays.length === 0 ? (
        <div className="py-10 text-center text-white/50">加载历史回放中...</div>
      ) : replays.length === 0 ? (
        <div className="py-10 text-center text-white/40">
          <History className="w-10 h-10 mx-auto mb-3 opacity-60" />
          <p>{replaysTotal === 0 && replayFilter === 'all' && replaySearch.trim() === '' ? '还没有可回放的历史对局' : '没有符合筛选条件的回放'}</p>
        </div>
      ) : (
        <div className={`${compact ? 'max-h-[52vh] overflow-y-auto pr-1 scrollbar-none' : ''} space-y-3`}>
          {replays.map((replay) => (
            <div
              key={replay.game_id}
              className="w-full p-4 rounded-2xl border border-white/10 bg-white/[0.03] hover:border-ww-gold/40 hover:bg-ww-gold/5 transition-colors"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <button
                    onClick={() => handleOpenHistoricalReplay(replay.game_id)}
                    className="flex max-w-full items-center gap-2 mb-2 text-left"
                  >
                    <span className="truncate font-semibold text-white">{replay.game_id}</span>
                    <span className={`shrink-0 px-2 py-0.5 text-[11px] rounded-full border ${getReplayStatusClassName(replay)}`}>
                      {getReplayStatusLabel(replay)}
                    </span>
                  </button>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-white/55">
                    <span>事件 {replay.total_events}</span>
                    <span>{replay.player_count ? `${replay.player_count} 人局` : '人数未同步'}</span>
                    {typeof replay.alive_count === 'number' && (
                      <span>存活 {replay.alive_count}</span>
                    )}
                    <span>第 {replay.current_round} 回合</span>
                    <span>阶段 {replay.current_phase}</span>
                  </div>
                  {replay.game_over_reason && (
                    <p className="mt-2 line-clamp-2 text-sm text-white/45">
                      结局：{replay.game_over_reason}
                    </p>
                  )}
                </div>
                <div className="flex items-center justify-between gap-3 sm:items-start">
                  <div className="text-xs text-white/45 flex items-center gap-1 whitespace-nowrap">
                    <Clock className="w-3 h-3" />
                    <span title={replay.updated_at ? new Date(replay.updated_at).toLocaleString('zh-CN') : '未记录时间'}>
                      {formatRelativeTime(replay.updated_at)}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleExportReplay(replay.game_id)}
                      className="rounded-xl border border-white/10 px-2 py-1.5 text-xs text-white/45 hover:text-sky-300 hover:border-sky-400/30 transition-colors"
                      title={`导出 ${replay.game_id}`}
                    >
                      导出
                    </button>
                    <button
                      onClick={() => handleDeleteReplay(replay.game_id)}
                      className="p-2 rounded-xl border border-white/10 text-white/40 hover:text-red-300 hover:border-red-400/30 transition-colors"
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
            <div className="flex items-center justify-between pt-2 text-sm text-white/50">
              <span>
                第 {currentReplayPage} / {totalReplayPages} 页，共 {replaysTotal} 条
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setReplayPage((page) => Math.max(1, page - 1))}
                  disabled={currentReplayPage === 1}
                  className="px-3 py-1.5 rounded-lg border border-white/10 disabled:opacity-40 disabled:cursor-not-allowed hover:border-white/25 transition-colors"
                >
                  上一页
                </button>
                <button
                  onClick={() => setReplayPage((page) => Math.min(totalReplayPages, page + 1))}
                  disabled={currentReplayPage === totalReplayPages}
                  className="px-3 py-1.5 rounded-lg border border-white/10 disabled:opacity-40 disabled:cursor-not-allowed hover:border-white/25 transition-colors"
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

  const renderPlayerSeats = (compact = false) => (
    <section className={`${compact ? 'p-4' : 'p-4 md:p-5'} rounded-[1.5rem] border border-white/10 bg-black/30 backdrop-blur-xl md:rounded-[2rem]`}>
      <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className={`${compact ? 'text-lg' : 'text-xl'} font-bold text-ww-gold`}>玩家席位</h2>
          <p className="text-sm text-white/45">点击存活玩家可进入夺舍控制。</p>
        </div>
        <div className="text-xs text-white/40">存活 {aliveAgents.length} / 出局 {deadAgents.length}</div>
      </div>
      <div className={`${compact ? 'max-h-[68vh] overflow-y-auto pr-1 scrollbar-none grid-cols-2' : 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5'} grid gap-3`}>
        {gameData?.agents.map((agent) => {
          const isCurrent = currentActorId === agent.agent_id;
          return (
            <div
              key={agent.agent_id}
              className={`relative overflow-hidden rounded-2xl border p-2 transition-all md:rounded-3xl md:p-3 ${
                isCurrent
                  ? 'border-ww-gold/55 bg-ww-gold/10 shadow-[0_0_30px_rgba(255,215,0,0.16)] animate-seat-focus'
                  : agent.is_alive
                    ? 'border-white/10 bg-white/[0.03]'
                    : 'border-red-400/20 bg-red-500/10 opacity-75'
              }`}
            >
              {isCurrent && (
                <div className="absolute left-3 top-2 z-20 rounded-full border border-ww-gold/50 bg-black/80 px-2 py-0.5 text-[10px] font-semibold text-ww-gold md:left-6 md:-top-2 md:px-3 md:py-1 md:text-[11px]">
                  当前焦点
                </div>
              )}
              <div className="mx-auto flex justify-center overflow-hidden rounded-xl md:rounded-2xl">
                <WerewolfCard3D
                  agent={convertAgentToWerewolfAgent(agent)}
                  isFlipped={Boolean(agent.role) && (flippedCards.has(agent.agent_id) || !agent.is_alive)}
                  onFlip={() => {
                    if (agent.role) {
                      handleCardFlip(agent.agent_id);
                    }
                  }}
                  showAura={agent.is_alive || isCurrent}
                  size="compact"
                />
              </div>
              <div className="mt-2 flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-black/65 p-2 backdrop-blur md:rounded-2xl md:p-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-white md:text-base">{agent.name}</div>
                  <div className="text-xs text-white/45">{agent.mbti_type} / {agent.iq_level}</div>
                </div>
                <span className={`shrink-0 rounded-full border px-2 py-1 text-[10px] md:text-[11px] ${
                  agent.is_alive
                    ? 'border-emerald-400/25 bg-emerald-500/10 text-emerald-200'
                    : 'border-red-400/25 bg-red-500/10 text-red-200'
                }`}>
                  {agent.is_alive ? '在场' : agent.role_cn || '身份揭示中'}
                </span>
              </div>
              {agent.is_alive && (
                <button
                  onClick={() => handleAgentClick(agent)}
                  className="mt-2 w-full rounded-xl border border-ww-gold/35 bg-ww-gold/10 px-2 py-1.5 text-[11px] font-semibold text-ww-gold transition-colors hover:border-ww-gold/60 hover:bg-ww-gold/20 md:mt-3 md:rounded-2xl md:px-3 md:py-2 md:text-xs"
                >
                  夺舍
                </button>
              )}
              {agent.is_possessed && (
                <div className="mt-2 text-center text-xs text-ww-gold animate-pulse">
                  已夺舍
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );

  const renderEventStream = (compact = false) => (
    <section className={`${compact ? 'p-4' : 'p-5'} rounded-[2rem] border border-white/10 bg-black/30 backdrop-blur-xl`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className={`${compact ? 'text-lg' : 'text-xl'} font-bold text-ww-gold`}>标准化事件流</h2>
          <p className="text-sm text-white/45">按事件类型统一展示，避免空白日志和原始字段名。</p>
        </div>
        <span className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-white/45">
          {events.length} 条
        </span>
      </div>
      <div className={`scrollbar-none ${compact ? 'max-h-[70vh]' : 'max-h-80'} space-y-3 overflow-y-auto pr-1 md:pr-2`}>
        {recentTimelineEvents.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 text-sm text-white/45">
            暂无事件，实时流连接后会在这里逐条出现。
          </div>
        ) : recentTimelineEvents.map((event, index) => (
          <div key={`${event.type}-${index}`} className={`rounded-2xl border p-4 ${getEventTone(event)}`}>
            <div className="mb-2 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 font-semibold">
                {getEventIcon(event)}
                {getEventTitle(event)}
              </div>
              <span className="text-xs text-white/45">{getPhaseText(getEventPhase(event))}</span>
            </div>
            <p className="line-clamp-3 text-sm leading-6 text-white/65">
              {event === currentEvent && hasPlaybackContent
                ? visibleSpeech || visibleThought || '逐 token 回放中...'
                : getEventSummary(event)}
            </p>
          </div>
        ))}
      </div>
    </section>
  );

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
        <div className="flex h-full flex-col overflow-hidden rounded-[1.75rem] border border-white/10 bg-slate-950/95 shadow-2xl">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <div className="text-lg font-bold text-ww-gold">{titleMap[mobilePanel]}</div>
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
            {mobilePanel === 'players' && renderPlayerSeats(true)}
            {mobilePanel === 'events' && renderEventStream(true)}
          </div>
        </div>
      </div>
    );
  };

  return (
    <DarkMysticLayout>
      <div className="flex flex-col min-h-screen p-3 md:p-4">
        {/* Config State */}
        {gameState === 'config' && (
          <div className="flex-1 flex flex-col items-center justify-center">
            <button
              onClick={() => navigate('/')}
              className="absolute top-4 left-4 p-2 text-ww-gold/60 hover:text-ww-gold transition-colors flex items-center gap-2"
            >
              <ArrowLeft className="w-5 h-5" />
              返回
            </button>

            <div className="w-full max-w-6xl flex flex-col items-center gap-4 sm:gap-10">
              <header className="mb-1 pt-8 text-center animate-fadeIn sm:mb-12 sm:pt-0">
                <h1 className="text-4xl md:text-7xl font-bold mb-2 sm:mb-4 text-transparent bg-clip-text bg-gradient-to-b from-ww-gold to-yellow-700 tracking-[0.16em] sm:tracking-[0.2em] uppercase drop-shadow-[0_0_15px_rgba(255,215,0,0.5)]">
                  狼人杀
                </h1>
                <div className="h-1 w-24 sm:w-32 bg-ww-gold mx-auto rounded-full mb-2 sm:mb-4 opacity-50 shadow-[0_0_10px_#ffd700]"></div>
                <p className="text-ww-gold/60 tracking-[0.3em] sm:tracking-[0.5em] text-xs sm:text-sm uppercase">
                  Werewolf Game Mode
                </p>
              </header>

              {error && (
                <div className="mb-6 p-4 bg-red-500/20 border border-red-500/50 rounded-lg text-red-300 flex items-center gap-2">
                  <AlertCircle className="w-5 h-5" />
                  {error}
                </div>
              )}

              {successMessage && (
                <div className="mb-6 p-4 bg-emerald-500/15 border border-emerald-500/35 rounded-lg text-emerald-200 flex items-center gap-2">
                  <History className="w-5 h-5" />
                  {successMessage}
                </div>
              )}

              <div className="w-full grid gap-3 sm:gap-8 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)] items-start">
                <WerewolfGameConfig onStart={handleStartGame} />

                <div className="w-full lg:hidden rounded-3xl border border-ww-gold/20 bg-black/35 p-3 backdrop-blur-sm animate-slideUp">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="mb-2 flex items-center gap-2 text-ww-gold">
                        <History className="w-5 h-5" />
                        <h2 className="text-lg font-bold">历史回放</h2>
                      </div>
                      <p className="hidden text-xs leading-5 text-white/50 min-[430px]:block">回放和筛选放进独立面板。</p>
                    </div>
                    <button
                      onClick={() => setMobilePanel('history')}
                      className="shrink-0 rounded-2xl border border-ww-gold/35 bg-ww-gold/10 px-4 py-2 text-sm font-semibold text-ww-gold"
                    >
                      打开
                    </button>
                  </div>
                  <div className="mt-4 grid grid-cols-3 gap-2">
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2">
                      <div className="text-[10px] text-white/35">总数</div>
                      <div className="text-lg font-semibold text-white">{replayStats.total}</div>
                    </div>
                    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2">
                      <div className="text-[10px] text-emerald-200/65">进行中</div>
                      <div className="text-lg font-semibold text-emerald-200">{replayStats.active}</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2">
                      <div className="text-[10px] text-white/35">已结束</div>
                      <div className="text-lg font-semibold text-white">{replayStats.finished}</div>
                    </div>
                  </div>
                </div>

                <div className="hidden lg:block">
                  {renderReplayHistory()}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Loading State */}
        {gameState === 'loading' && (
          <div className="flex-1 flex flex-col items-center justify-center animate-fadeIn">
            <div className="w-16 h-16 border-4 border-ww-gold/20 border-t-ww-gold rounded-full animate-spin mb-6 shadow-[0_0_15px_rgba(255,215,0,0.3)]"></div>
            <p className="text-ww-gold tracking-[0.3em] animate-pulse">
              正在召唤 Agent 进入迷雾...
            </p>
          </div>
        )}

        {/* Playing State */}
        {gameState === 'playing' && gameData && (
          <div className="flex-1 animate-fadeIn space-y-4 md:space-y-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <button
                onClick={() => {
                  if (cleanupRef.current) cleanupRef.current();
                  navigate('/');
                }}
                className="p-2 text-ww-gold/60 hover:text-ww-gold transition-colors flex items-center gap-2"
              >
                <ArrowLeft className="w-5 h-5" />
                退出
              </button>

              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={() => {
                    if (gameData.gameId) {
                      setSelectedReplayGameId(gameData.gameId);
                    }
                    setShowTimelineReplay(true);
                  }}
                  className="p-2 text-ww-gold/60 hover:text-ww-gold transition-colors flex items-center gap-2"
                  title="查看回放"
                >
                  <History className="w-5 h-5" />
                  <span className="text-sm">回放</span>
                </button>

                <div className={`flex items-center gap-2 rounded-full border border-white/10 bg-black/30 px-4 py-2 ${getPhaseColor(gameData.phase)}`}>
                  {getPhaseIcon(gameData.phase)}
                  <span className="font-semibold">{getPhaseText(gameData.phase)}</span>
                </div>
                <div className="rounded-full border border-ww-gold/25 bg-ww-gold/10 px-4 py-2 text-ww-gold">
                  第 {gameData.currentRound} 回合
                </div>
              </div>
            </div>

            <section className="rounded-[1.5rem] md:rounded-[2rem] border border-white/10 bg-black/35 p-3 md:p-4 shadow-2xl backdrop-blur-xl">
              <div className="scrollbar-none flex gap-3 overflow-x-auto pb-1 md:grid md:grid-cols-5 md:overflow-visible md:pb-0">
                {phaseSteps.map((step, index) => {
                  const Icon = step.icon;
                  const isActive = step.key === normalizePhase(gameData.phase);
                  const isPast = phaseSteps.findIndex(item => item.key === normalizePhase(gameData.phase)) > index;
                  return (
                    <div
                      key={step.key}
                      className={`relative min-w-[9.5rem] overflow-hidden rounded-2xl border p-3 transition-all md:min-w-0 md:p-4 ${
                        isActive
                          ? 'border-ww-gold/50 bg-ww-gold/15 text-ww-gold shadow-[0_0_24px_rgba(255,215,0,0.14)] animate-phase-breathe'
                          : isPast
                            ? 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200'
                            : 'border-white/10 bg-white/[0.03] text-white/45'
                      }`}
                    >
                      {isActive && <div className="absolute inset-x-0 top-0 h-0.5 bg-ww-gold animate-pulse" />}
                      <div className="mb-3 flex items-center justify-between">
                        <Icon className="w-5 h-5" />
                        <span className="text-[11px] uppercase tracking-[0.2em]">Step {index + 1}</span>
                      </div>
                      <div className="font-semibold">{step.label}</div>
                      <div className="mt-1 text-xs opacity-70">{step.hint}</div>
                    </div>
                  );
                })}
              </div>
            </section>

            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px] 2xl:grid-cols-[minmax(0,1fr)_360px]">
              <section className={`relative overflow-hidden rounded-[1.5rem] border p-4 shadow-2xl backdrop-blur-xl animate-slideUp md:rounded-[2rem] md:p-6 ${atmosphere.shell} ${getEventTone(currentEvent)}`}>
                <div className="pointer-events-none absolute inset-0 opacity-70">
                  <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${atmosphere.accent} animate-shimmer-line`} />
                  {currentVisualPhase === 'night' && (
                    <>
                      <div className="absolute -left-24 top-10 h-40 w-[130%] rotate-[-8deg] rounded-full bg-violet-300/10 blur-3xl animate-drift-fog" />
                      <div className="absolute right-8 top-12 h-2 w-2 rounded-full bg-white/70 shadow-[0_0_24px_rgba(255,255,255,0.8)] animate-star-blink" />
                      <div className="absolute left-1/3 top-24 h-px w-32 rotate-12 bg-gradient-to-r from-transparent via-red-300/60 to-transparent animate-slash-trace" />
                    </>
                  )}
                  {currentVisualPhase === 'dawn' && (
                    <>
                      <div className="absolute -top-36 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-amber-200/20 blur-3xl animate-sunrise-glow" />
                      <div className="absolute inset-x-0 top-16 h-px bg-gradient-to-r from-transparent via-amber-100/60 to-transparent animate-light-sweep" />
                    </>
                  )}
                  {currentVisualPhase === 'day_discussion' && (
                    <>
                      <div className="absolute left-10 top-20 h-28 w-28 rounded-full border border-sky-200/20 animate-sound-ring" />
                      <div className="absolute right-14 bottom-16 h-20 w-20 rounded-full border border-cyan-200/20 animate-sound-ring [animation-delay:700ms]" />
                      <div className="absolute inset-x-10 bottom-8 h-px bg-gradient-to-r from-transparent via-sky-200/50 to-transparent animate-dialogue-scan" />
                    </>
                  )}
                  {currentVisualPhase === 'day_voting' && (
                    <>
                      <div className="absolute left-0 top-1/3 h-px w-full bg-gradient-to-r from-transparent via-orange-200/60 to-transparent animate-vote-arrow" />
                      <div className="absolute right-8 top-20 h-28 w-28 rounded-full bg-red-400/10 blur-2xl animate-heat-pulse" />
                    </>
                  )}
                  {currentVisualPhase === 'result' && (
                    <>
                      <div className="absolute left-1/2 top-1/2 h-px w-[80%] -translate-x-1/2 rotate-12 bg-red-200/40 animate-crack-flash" />
                      <div className="absolute left-1/3 top-1/3 h-px w-[45%] rotate-[-28deg] bg-ww-gold/40 animate-crack-flash [animation-delay:240ms]" />
                    </>
                  )}
                </div>
                <div className="absolute -right-20 -top-24 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
                <div className="absolute -bottom-28 left-1/4 h-64 w-64 rounded-full bg-ww-gold/10 blur-3xl" />
                <div className="relative flex flex-col gap-5 md:gap-6">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="flex items-start gap-4">
                      <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-white/15 bg-black/35 shadow-inner">
                        {getEventIcon(currentEvent)}
                      </div>
                      <div>
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1 text-xs text-white/55">
                            {getPhaseText(getEventPhase(currentEvent))}
                          </span>
                          {currentEvent?.index && currentEvent?.total && (
                            <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1 text-xs text-white/55">
                              {currentEvent.index}/{currentEvent.total}
                            </span>
                          )}
                        </div>
                        <h2 className="text-2xl font-bold tracking-tight text-white md:text-3xl">{getEventTitle(currentEvent)}</h2>
                        <div className="mt-3 flex flex-wrap gap-2 text-xs">
                          <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1 text-white/60">{atmosphere.label}</span>
                          <span className="rounded-full border border-white/10 bg-black/25 px-3 py-1 text-white/45">{atmosphere.motion}</span>
                        </div>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-black/25 px-4 py-3 text-right">
                      <div className="text-xs text-white/45">实时模型</div>
                      <div className="mt-1 text-sm font-semibold text-ww-gold">
                        {activeModelLabel || '未记录模型'}
                      </div>
                    </div>
                  </div>

                  <div className="rounded-3xl border border-white/10 bg-black/30 p-4 md:p-5">
                    {!hasPlaybackContent && (
                      <p className="text-lg leading-8 text-white/85 whitespace-pre-wrap">{getEventSummary(currentEvent)}</p>
                    )}
                    {speechPlaybackTokens.length > 0 && (
                      <div className="rounded-2xl border border-sky-400/20 bg-sky-500/10 p-4">
                        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2 text-sm font-semibold text-sky-200">
                            <MessageCircle className="w-4 h-4" />
                            逐 token 发言
                          </div>
                          <span className="rounded-full border border-sky-300/20 bg-black/25 px-3 py-1 text-[11px] text-sky-100/75">
                            {Math.min(tokenPlayback.speech, speechPlaybackTokens.length)} / {speechPlaybackTokens.length} tokens
                          </span>
                        </div>
                        <p className="min-h-20 text-base leading-7 text-white/85 whitespace-pre-wrap md:min-h-24 md:text-lg md:leading-8">
                          {visibleSpeech}
                          {isSpeechPlaying && <span className="ml-0.5 inline-block h-5 w-2 translate-y-1 bg-sky-200 animate-pulse" />}
                        </p>
                      </div>
                    )}
                    {speechPlaybackTokens.length === 0 && currentEvent?.type === 'agent_speaking' && (
                      <div className="rounded-2xl border border-sky-400/20 bg-sky-500/10 p-4">
                        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-sky-200">
                          <MessageCircle className="w-4 h-4" />
                          逐 token 发言
                        </div>
                        <div className="flex items-center gap-3 text-sm text-sky-100/80">
                          <div className="flex gap-1">
                            <span className="h-2 w-2 rounded-full bg-sky-300 animate-bounce" />
                            <span className="h-2 w-2 rounded-full bg-sky-300 animate-bounce [animation-delay:120ms]" />
                            <span className="h-2 w-2 rounded-full bg-sky-300 animate-bounce [animation-delay:240ms]" />
                          </div>
                          模型正在生成公开发言，收到内容后会逐 token 展开
                        </div>
                      </div>
                    )}
                    {thoughtPlaybackTokens.length > 0 && (
                      <div className="mt-4 rounded-2xl border border-ww-gold/20 bg-ww-gold/10 p-4">
                        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2 text-sm font-semibold text-ww-gold">
                            <Brain className="w-4 h-4" />
                            思考过程回放
                          </div>
                          <span className="rounded-full border border-ww-gold/20 bg-black/25 px-3 py-1 text-[11px] text-ww-gold/80">
                            {Math.min(tokenPlayback.thought, thoughtPlaybackTokens.length)} / {thoughtPlaybackTokens.length} tokens
                          </span>
                        </div>
                        <p className="min-h-16 text-sm leading-7 text-white/70 whitespace-pre-wrap">
                          {visibleThought}
                          {isThoughtPlaying && <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 bg-ww-gold animate-pulse" />}
                        </p>
                      </div>
                    )}
                    {hasPlaybackContent && (
                      <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-xs leading-5 text-white/45">
                        当前为前端逐 token 回放：后端收到模型完整 JSON 后立即分词播放；若后续接入真实 streaming delta，这个面板可直接显示真实到达的 token。
                      </div>
                    )}
                    {currentEvent?.suspicion && Object.keys(currentEvent.suspicion).length > 0 && (
                      <div className="mt-4">
                        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-white/70">
                          <Target className="w-4 h-4" />
                          怀疑值快照
                        </div>
                        <div className="grid gap-2 sm:grid-cols-2">
                          {Object.entries(currentEvent.suspicion).slice(0, 6).map(([agentId, score]) => {
                            const agent = gameData.agents.find(item => item.agent_id === agentId);
                            const numericScore = typeof score === 'number' ? score : Number(score) || 0;
                            return (
                              <div key={agentId} className="rounded-xl border border-white/10 bg-black/25 p-3">
                                <div className="mb-2 flex items-center justify-between text-xs">
                                  <span className="text-white/65">{agent?.name || agentId}</span>
                                  <span className="text-ww-gold">{numericScore.toFixed(1)}</span>
                                </div>
                                <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                                  <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-ww-gold to-red-400" style={{ width: `${Math.min(100, Math.max(0, numericScore * 10))}%` }} />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>

                  {!currentEvent?.speech && currentEvent?.type === 'agent_speaking' && (
                    <div className="flex items-center gap-3 text-sm text-sky-100/80">
                      <div className="flex gap-1">
                        <span className="h-2 w-2 rounded-full bg-sky-300 animate-bounce" />
                        <span className="h-2 w-2 rounded-full bg-sky-300 animate-bounce [animation-delay:120ms]" />
                        <span className="h-2 w-2 rounded-full bg-sky-300 animate-bounce [animation-delay:240ms]" />
                      </div>
                      模型正在生成这名玩家的公开发言
                    </div>
                  )}
                </div>
              </section>

              <aside className="grid gap-3 sm:grid-cols-3 xl:block xl:space-y-4">
                <div className="rounded-[1.5rem] border border-ww-gold/15 bg-black/35 p-4 backdrop-blur-xl xl:rounded-[2rem] xl:p-5">
                  <div className="mb-4 flex items-center gap-2 text-ww-gold">
                    <Users className="w-5 h-5" />
                    <h2 className="font-semibold">圆桌态势</h2>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-2xl border border-emerald-400/20 bg-emerald-500/10 p-4">
                      <div className="text-xs text-emerald-200/65">存活</div>
                      <div className="mt-1 text-3xl font-bold text-emerald-200">{aliveAgents.length}</div>
                    </div>
                    <div className="rounded-2xl border border-red-400/20 bg-red-500/10 p-4">
                      <div className="text-xs text-red-200/65">出局</div>
                      <div className="mt-1 text-3xl font-bold text-red-200">{deadAgents.length}</div>
                    </div>
                  </div>
                  <div className="mt-4 space-y-2 text-sm text-white/55">
                    <div className="flex justify-between gap-3">
                      <span>对局 ID</span>
                      <span className="font-mono text-white/75">{gameData.gameId}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span>公开阶段</span>
                      <span className={getPhaseColor(gameData.phase)}>{getPhaseText(gameData.phase)}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span>身份牌</span>
                      <span className="text-white/70">未公开，出局后揭示</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-[1.5rem] border border-sky-300/15 bg-sky-500/5 p-4 backdrop-blur-xl xl:rounded-[2rem] xl:p-5">
                  <div className="mb-4 flex items-center gap-2 text-sky-200">
                    <MessageCircle className="w-5 h-5" />
                    <h2 className="font-semibold">声纹残响</h2>
                  </div>
                  <div className="scrollbar-none space-y-3 xl:max-h-60 xl:overflow-y-auto xl:pr-1">
                    {recentSpeeches.length === 0 ? (
                      <p className="text-sm text-white/40">暂无公开发言，等待讨论阶段。</p>
                    ) : recentSpeeches.map((event, index) => (
                      <div key={`${event.agent_id || index}-${index}`} className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                        <div className="mb-1 text-sm font-semibold text-white">{event.agent_name || '玩家'}</div>
                        <p className="line-clamp-3 text-xs leading-5 text-white/55">
                          {event === currentEvent ? visibleSpeech || '逐 token 回放中...' : event.speech || event.content}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[1.5rem] border border-orange-300/15 bg-orange-500/5 p-4 backdrop-blur-xl xl:rounded-[2rem] xl:p-5">
                  <div className="mb-4 flex items-center gap-2 text-orange-200">
                    <Vote className="w-5 h-5" />
                    <h2 className="font-semibold">票压轨迹</h2>
                  </div>
                  <div className="space-y-2">
                    {recentVotes.length === 0 ? (
                      <p className="text-sm text-white/40">投票阶段尚未开始。</p>
                    ) : recentVotes.map((event, index) => (
                      <div key={`${event.agent_id || index}-vote-${index}`} className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm">
                        <span className="text-white/70">{event.agent_name || event.voter_name || '玩家'}</span>
                        <span className="text-orange-200">→ {event.voted_for_name || event.target_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </aside>
            </div>

            <section className="grid grid-cols-3 gap-2 rounded-[1.5rem] border border-white/10 bg-black/30 p-3 backdrop-blur-xl lg:hidden">
              <button
                onClick={() => setMobilePanel('players')}
                className="rounded-2xl border border-ww-gold/25 bg-ww-gold/10 px-3 py-3 text-left text-ww-gold"
              >
                <Users className="mb-2 h-5 w-5" />
                <div className="text-sm font-semibold">玩家</div>
                <div className="text-[11px] text-white/45">{gameData.agents.length} 席</div>
              </button>
              <button
                onClick={() => setMobilePanel('events')}
                className="rounded-2xl border border-sky-300/20 bg-sky-500/10 px-3 py-3 text-left text-sky-200"
              >
                <Activity className="mb-2 h-5 w-5" />
                <div className="text-sm font-semibold">事件</div>
                <div className="text-[11px] text-white/45">{events.length} 条</div>
              </button>
              <button
                onClick={() => {
                  setSelectedReplayGameId(gameData.gameId);
                  setShowTimelineReplay(true);
                }}
                className="rounded-2xl border border-white/10 bg-white/[0.04] px-3 py-3 text-left text-white/70"
              >
                <History className="mb-2 h-5 w-5" />
                <div className="text-sm font-semibold">回放</div>
                <div className="text-[11px] text-white/45">时间轴</div>
              </button>
            </section>

            <div className="hidden lg:block">
              {renderPlayerSeats()}
            </div>

            <div className="hidden lg:block">
              {renderEventStream()}
            </div>
          </div>
        )}

        {/* Game Over State */}
        {gameState === 'game_over' && gameData && gameData.winner && (
          <WerewolfGameOver
            winner={gameData.winner}
            reason={gameData.winReason || '游戏结束'}
            currentRound={gameData.currentRound}
            agents={gameData.agents}
            onReplay={handleOpenReplay}
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
              console.log('Action completed');
              // Optionally close the modal after action
              // setShowPossessionControl(false);
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

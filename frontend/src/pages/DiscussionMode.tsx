import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, Sparkles, ArrowLeft, Swords } from 'lucide-react';
import { motion } from 'framer-motion';

import { buildApiUrl } from '../services/api';
import { useSettingsStore } from '../store/settingsStore';
import { pickPreferredModelConfig } from '../lib/modelProviders';
import CommonGameSetup, { type CommonSetupState } from '../components/setup/CommonGameSetup';

interface Agent {
  id: string;
  name: string;
  mbti_type: string;
  iq_level: string;
}

interface Character {
  id: string;
  name: string;
  mbti_type: string;
  source: string;
  avatar_url: string;
}

interface Profession {
  title: string;
  description: string;
}

interface CharacterInfo {
  agent_id: string;
  agent_name: string;
  character: Character;
  profession: Profession;
}

interface Message {
  id: string;
  speaker_id: string;
  speaker_name: string;
  speaker_type: 'agent' | 'user' | 'system';
  content: string;
  thought?: string;
  agree_with?: string[];
  disagree_with?: string[];
  sentiment?: string;
  timestamp: string;
}

interface DebaterCard {
  id: string;
  name: string;
  trait: string;
  avatarChar: string;
}

type Side = 'pro' | 'con';

const SIDE_TONE: Record<Side, { text: string; border: string; bg: string; dot: string }> = {
  pro: {
    text: 'text-info',
    border: 'border-info/45',
    bg: 'bg-info/10',
    dot: 'bg-info',
  },
  con: {
    text: 'text-danger',
    border: 'border-danger/45',
    bg: 'bg-danger/10',
    dot: 'bg-danger',
  },
};

export const DiscussionMode: React.FC = () => {
  const navigate = useNavigate();
  const { modelConfigs, fetchModelConfigs } = useSettingsStore();
  const [discussionId, setDiscussionId] = useState<string | null>(null);
  const [topic, setTopic] = useState('');
  const [agentCount, setAgentCount] = useState(6);
  const [useCharacters, setUseCharacters] = useState(true);
  const [setup, setSetup] = useState<CommonSetupState | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [characters, setCharacters] = useState<CharacterInfo[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isActive, setIsActive] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isConfiguring, setIsConfiguring] = useState(true);
  const [currentThinkingAgent, setCurrentThinkingAgent] = useState<string | null>(null);
  const [userSpeech, setUserSpeech] = useState('');
  const [topicGenerating, setTopicGenerating] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [nowTick, setNowTick] = useState<number>(() => Date.now());

  const stageEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // 计时器：对垒进行时每秒刷新
  useEffect(() => {
    if (!isActive || !startedAt) return;
    const timer = window.setInterval(() => setNowTick(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [isActive, startedAt]);

  useEffect(() => {
    stageEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentThinkingAgent]);

  const postJson = async (path: string, body: unknown) => {
    const response = await fetch(buildApiUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }
    return response;
  };

  useEffect(() => {
    fetchModelConfigs().catch((err) => console.error('Failed to load model configs:', err));
  }, [fetchModelConfigs]);

  /** AI 出题：生成一个有争议性的话题，避免玩家面对空白议题无从开始 */
  const handleGenerateTopic = async () => {
    if (topicGenerating) return;
    setTopicGenerating(true);
    try {
      const preferred = setup?.selectedModel || pickPreferredModelConfig(modelConfigs);
      const res = await postJson('/api/discussion/generate-topic', {
        hint: '',
        model_config_data: preferred
          ? {
              provider: preferred.provider,
              model: setup?.globalModel || preferred.model,
              api_key: preferred.api_key || undefined,
              base_url: preferred.base_url || undefined,
            }
          : undefined,
      });
      const data = await res.json();
      if (data?.topic) setTopic(String(data.topic));
    } catch (err) {
      console.error('Failed to generate topic:', err);
      alert('话题生成失败，请稍后重试');
    } finally {
      setTopicGenerating(false);
    }
  };

  const handleCreateDiscussion = async () => {
    if (!topic.trim()) {
      alert('请先输入讨论主题');
      return;
    }

    try {
      const requestBody: Record<string, unknown> = {
        topic: topic.trim(),
        agent_count: agentCount,
        use_balanced_team: true,
        use_characters: useCharacters,
      };

      // 后端 CreateDiscussionRequest 只认 llm_config（model_config 会被静默丢弃）
      const preferred = setup?.selectedModel || pickPreferredModelConfig(modelConfigs);
      if (preferred) {
        requestBody.llm_config = {
          provider: preferred.provider || undefined,
          model: (setup?.globalModel && setup.selectedModel?.id === preferred.id ? setup.globalModel : '') || preferred.model,
          api_key: preferred.api_key || undefined,
          base_url: preferred.base_url || undefined,
        };
      }
      // 三游戏统一：主题阵容 + 智能模型分配
      if (setup?.roster) {
        requestBody.roster = setup.roster;
        requestBody.roster_work = setup.rosterWork;
      }
      if (setup?.autoAssign) {
        requestBody.auto_assign = {
          candidates: setup.autoAssign.candidates,
          disabled_models: setup.autoAssign.disabledModels,
          effort_by_role: setup.autoAssign.effortByRole,
        };
      }

      const response = await postJson('/api/discussion/create', requestBody);
      const data = await response.json();
      setDiscussionId(data.discussion_id);
      setAgents(data.agents);
      setCharacters(data.characters || []);
      setIsConfiguring(false);
    } catch (error) {
      console.error('Failed to create discussion:', error);
      alert('创建对垒失败，请检查模型配置');
    }
  };

  const handleStartDiscussion = async () => {
    if (!discussionId) return;

    try {
      await postJson('/api/discussion/start', { discussion_id: discussionId });
      setIsActive(true);
      setStartedAt(Date.now());

      const eventSource = new EventSource(buildApiUrl(`/api/discussion/stream/${discussionId}`));
      eventSourceRef.current = eventSource;

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        switch (data.type) {
          case 'agent_thinking':
            setCurrentThinkingAgent(data.agent_name);
            break;
          case 'agent_speaking':
            setCurrentThinkingAgent(null);
            setMessages((prev) => [
              ...prev,
              {
                id: `msg_${Date.now()}_${data.agent_id}`,
                speaker_id: data.agent_id,
                speaker_name: data.agent_name,
                speaker_type: 'agent',
                content: data.speech,
                thought: data.thought,
                agree_with: data.agree_with || [],
                disagree_with: data.disagree_with || [],
                sentiment: data.sentiment || 'neutral',
                timestamp: new Date().toISOString(),
              },
            ]);
            break;
          case 'discussion_end':
            setIsActive(false);
            eventSource.close();
            break;
          case 'error':
            console.error('Stream error:', data.message);
            break;
          default:
            break;
        }
      };

      eventSource.onerror = (error) => {
        console.error('EventSource error:', error);
        eventSource.close();
        setIsActive(false);
      };
    } catch (error) {
      console.error('Failed to start discussion:', error);
      alert('启动对垒失败');
    }
  };

  const handlePause = async () => {
    if (!discussionId) return;
    try {
      await postJson('/api/discussion/pause', { discussion_id: discussionId });
      setIsPaused(true);
    } catch (error) {
      console.error('Failed to pause:', error);
    }
  };

  const handleResume = async () => {
    if (!discussionId) return;
    try {
      await postJson('/api/discussion/resume', { discussion_id: discussionId });
      setIsPaused(false);
    } catch (error) {
      console.error('Failed to resume:', error);
    }
  };

  const handleEnd = async () => {
    if (!discussionId) return;
    try {
      await postJson('/api/discussion/end', { discussion_id: discussionId });
      eventSourceRef.current?.close();
      setIsActive(false);
    } catch (error) {
      console.error('Failed to end:', error);
    }
  };

  const handleUserSpeak = async (speech: string) => {
    if (!discussionId || !speech.trim()) return;

    try {
      if (isActive && !isPaused) {
        await handlePause();
      }

      const response = await postJson('/api/discussion/user-speak', {
        discussion_id: discussionId,
        speech: speech.trim(),
        mention_agents: [],
      });
      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          id: data.message_id,
          speaker_id: 'user',
          speaker_name: '你',
          speaker_type: 'user',
          content: speech.trim(),
          timestamp: data.timestamp,
        },
      ]);
      setUserSpeech('');

      setTimeout(() => {
        if (isActive) {
          handleResume();
        }
      }, 500);
    } catch (error) {
      console.error('Failed to send message:', error);
      alert('发送失败');
    }
  };

  const handleBackToHome = () => {
    eventSourceRef.current?.close();
    navigate('/');
  };

  // ---------- 擂台数据推导 ----------

  // 玩家分边：按创建顺序偶数位 → 正方，奇数位 → 反方
  const debaters = useMemo(() => {
    const charMap = new Map(characters.map((c) => [c.agent_id, c]));
    const cards: Array<DebaterCard & { side: Side }> = agents.map((agent, index) => {
      const charInfo = charMap.get(agent.id);
      return {
        id: agent.id,
        name: charInfo?.agent_name || agent.name,
        trait: charInfo ? charInfo.profession.title : `${agent.mbti_type} · ${agent.iq_level}`,
        avatarChar: (charInfo?.agent_name || agent.name || '?').slice(0, 1),
        side: index % 2 === 0 ? 'pro' : 'con',
      };
    });
    return cards;
  }, [agents, characters]);

  const proDebaters = useMemo(() => debaters.filter((d) => d.side === 'pro'), [debaters]);
  const conDebaters = useMemo(() => debaters.filter((d) => d.side === 'con'), [debaters]);

  const sideOfSpeaker = (speakerId: string): Side | null => {
    const found = debaters.find((d) => d.id === speakerId);
    return found ? found.side : null;
  };

  // 支持率：由其他玩家发言中的 agree_with / disagree_with 聚合
  const stats = useMemo(() => {
    const agree: Record<string, number> = {};
    const disagree: Record<string, number> = {};
    let totalAgree = 0;
    let totalDisagree = 0;
    for (const msg of messages) {
      for (const id of msg.agree_with || []) {
        agree[id] = (agree[id] || 0) + 1;
        totalAgree += 1;
      }
      for (const id of msg.disagree_with || []) {
        disagree[id] = (disagree[id] || 0) + 1;
        totalDisagree += 1;
      }
    }
    const supportOf = (id: string): number | null => {
      const a = agree[id] || 0;
      const d = disagree[id] || 0;
      const denom = a + d;
      if (denom === 0) return null;
      return Math.round((a / denom) * 100);
    };
    const sideShare = (side: Side): number => {
      if (totalAgree === 0) return 50;
      const ids = debaters.filter((d) => d.side === side).map((d) => d.id);
      const sideAgree = ids.reduce((sum, id) => sum + (agree[id] || 0), 0);
      return Math.round((sideAgree / totalAgree) * 100);
    };
    return { supportOf, proShare: sideShare('pro'), totalAgree };
  }, [messages, debaters]);

  const currentMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const replayMessages = useMemo(
    () => (messages.length > 1 ? messages.slice(-3, -1).reverse() : []),
    [messages]
  );
  const currentSide = currentMessage ? sideOfSpeaker(currentMessage.speaker_id) : null;
  const roundNumber = Math.max(1, Math.ceil(messages.length / Math.max(1, agentCount)));

  // 交锋焦点：最近一条带反对立场的发言
  const clashMessage = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const msg = messages[i];
      if (msg.disagree_with && msg.disagree_with.length > 0) {
        const targets = msg
          .disagree_with.map((id) => debaters.find((d) => d.id === id)?.name)
          .filter(Boolean)
          .slice(0, 2);
        if (targets.length > 0) {
          return { speaker: msg.speaker_name, targets: targets.join('、') };
        }
      }
    }
    return null;
  }, [messages, debaters]);

  const elapsedLabel = useMemo(() => {
    if (!startedAt) return '00:00';
    const seconds = Math.max(0, Math.floor((nowTick - startedAt) / 1000));
    const mm = String(Math.floor(seconds / 60)).padStart(2, '0');
    const ss = String(seconds % 60).padStart(2, '0');
    return `${mm}:${ss}`;
  }, [startedAt, nowTick]);

  const statusLabel = isActive
    ? isPaused
      ? '已暂停'
      : '进行中'
    : messages.length > 0
      ? '已结束'
      : '待开始';

  const renderDebaterColumn = (side: Side) => {
    const tone = SIDE_TONE[side];
    const list = side === 'pro' ? proDebaters : conDebaters;
    const speakingId = currentThinkingAgent ? null : currentMessage?.speaker_id;
    return (
      <aside className="flex min-h-0 flex-col gap-2.5">
        <p className={`font-hud text-[11px] uppercase tracking-[0.25em] ${tone.text}`}>
          {side === 'pro' ? '正方 PRO' : '反方 CON'} · {list.length} 名玩家
        </p>
        <div className="flex flex-col gap-3 overflow-y-auto scrollbar-none pr-0.5">
          {list.map((d) => {
            const isSpeaking = speakingId === d.id;
            const isThinking = currentThinkingAgent === d.name;
            const support = stats.supportOf(d.id);
            return (
              <div
                key={d.id}
                className={`flex items-center gap-3 rounded-[14px] border bg-surface px-3.5 py-3.5 transition-all ${
                  isSpeaking || isThinking ? tone.border : 'border-line'
                }`}
              >
                <span
                  className={`flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-full font-bold text-white ${tone.dot}`}
                >
                  {d.avatarChar}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium text-text-primary">
                    玩家 · {d.name}
                  </span>
                  <span className={`block truncate text-[11px] ${isThinking ? tone.text : 'text-text-secondary/70'}`}>
                    {d.trait}
                    {isSpeaking ? ' · 发言中' : isThinking ? ' · 思考中' : ''}
                  </span>
                </span>
                <span className={`font-hud shrink-0 text-sm font-bold ${support === null ? 'text-text-secondary/40' : tone.text}`}>
                  {support === null ? '—' : `${support}%`}
                </span>
              </div>
            );
          })}
        </div>
      </aside>
    );
  };

  if (isConfiguring) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--ds-bg-base)] p-4 text-text-primary">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="w-full max-w-xl rounded-[1.75rem] border border-line bg-surface/70 p-8 backdrop-blur-xl sm:p-10"
        >
          <div className="mb-9 text-center">
            <div className="mb-5 inline-block rounded-2xl border border-violet/35 bg-violet/12 p-3.5">
              <MessageSquare size={34} className="text-violet" />
            </div>
            <h1 className="mb-2 text-3xl font-black tracking-wide text-text-primary">辩论会 · 自由对垒</h1>
            <p className="text-sm text-text-secondary/75">设置议题与玩家数量，AI 玩家将围绕议题展开立论与驳论</p>
          </div>

          <div className="space-y-7">
            <div className="space-y-2.5">
              <label className="font-hud flex items-center justify-between px-1 text-[11px] uppercase tracking-[0.25em] text-text-secondary/60">
                <span>议题 TOPIC</span>
                <button
                  type="button"
                  onClick={handleGenerateTopic}
                  disabled={topicGenerating}
                  className="flex items-center gap-1.5 rounded-lg border border-violet/50 bg-violet/12 px-2.5 py-1 text-[11px] normal-case tracking-normal text-violet transition-colors hover:bg-violet/20 disabled:opacity-40"
                >
                  <Sparkles size={12} className={topicGenerating ? 'animate-pulse' : ''} />
                  {topicGenerating ? '生成中…' : 'AI 出题'}
                </button>
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="例如：AI 生成内容是否具有真正的创造力"
                className="w-full rounded-2xl border border-line bg-white/[0.04] px-5 py-4 text-lg text-text-primary transition-all outline-none placeholder:text-text-secondary/40 focus:border-violet/60"
              />
              <p className="px-1 text-[11px] text-text-secondary/50">
                没有思路？点「AI 出题」让模型生成一个有争议性的话题。
              </p>
            </div>

            {/* 三游戏共享：玩家数量 / 全局推理模型 / 智能分配 / 角色阵容 */}
            <CommonGameSetup
              playerCount={agentCount}
              onPlayerCountChange={setAgentCount}
              minPlayers={3}
              maxPlayers={10}
              playerLabel="玩家数量"
              showChatStyle={false}
              autoAssignTierText="按智力分档自动挑选模型：High 用最强推理，Mid 次之，Low 用轻量模型。"
              onChange={setSetup}
            />

            <div className="rounded-2xl border border-line bg-white/[0.03] p-5">
              <label className="flex cursor-pointer items-center justify-between">
                <div className="flex items-center gap-3.5">
                  <div className="rounded-xl border border-violet/30 bg-violet/12 p-2.5 text-violet">
                    <Sparkles size={20} />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-text-primary">角色扮演</div>
                    <div className="text-xs text-text-secondary/65">以历史与神话人物身份入场，自动生成职业视角</div>
                  </div>
                </div>
                <button
                  onClick={() => setUseCharacters(!useCharacters)}
                  className={`relative h-7 w-14 rounded-full transition-colors ${useCharacters ? 'bg-violet' : 'bg-white/10'}`}
                  aria-label="切换角色扮演"
                >
                  <motion.div
                    animate={{ left: useCharacters ? 32 : 4 }}
                    className="absolute top-1 h-5 w-5 rounded-full bg-white"
                  />
                </button>
              </label>
            </div>

            <div className="flex flex-col gap-3 pt-2">
              <button
                onClick={handleCreateDiscussion}
                disabled={!topic.trim()}
                className="w-full rounded-2xl bg-gold py-4 text-lg font-bold text-[#2B2836] shadow-[0_0_22px_rgba(232,194,105,0.3)] transition-all hover:shadow-[0_0_34px_rgba(232,194,105,0.45)] disabled:cursor-not-allowed disabled:opacity-45"
              >
                创建对垒
              </button>
              <button
                onClick={handleBackToHome}
                className="w-full py-3 font-medium text-text-secondary/70 transition-colors hover:text-text-primary"
              >
                返回首页
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-[var(--ds-bg-base)] text-text-primary">
      {/* 顶栏：标题组 + 阶段徽章 + 计时组（对齐设计稿 3:461） */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-line bg-surface/50 px-7 py-4 backdrop-blur-xl">
        <div className="flex min-w-0 items-center gap-4">
          <button
            onClick={handleBackToHome}
            className="rounded-xl border border-line p-2 text-gold/70 transition-colors hover:border-gold/40 hover:text-gold"
            title="退出对局"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="min-w-0">
            <h1 className="truncate text-xl font-bold text-text-primary">辩论会 · 自由对垒</h1>
            <p className="truncate text-xs text-text-secondary/60">议题：{topic}</p>
          </div>
        </div>
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2 rounded-full border border-gold/50 bg-gold/12 px-[15px] py-[7px]">
            <span className={`h-[7px] w-[7px] rounded-full ${isActive && !isPaused ? 'animate-pulse-soft bg-gold' : 'bg-gold/50'}`} />
            <span className="text-xs font-medium text-gold">第 {roundNumber} 轮 · {statusLabel}</span>
          </div>
          <div>
            <div className="font-hud text-right text-[10px] uppercase tracking-[0.25em] text-text-secondary/50">对局时长</div>
            <div className="font-hud text-2xl font-bold leading-tight text-gold">{elapsedLabel}</div>
          </div>
        </div>
      </header>

      {/* 主体：左右分边 + 中央擂台 */}
      <div className="grid min-h-0 flex-1 gap-5 overflow-y-auto p-6 lg:grid-cols-[292px_minmax(0,1fr)_292px] lg:overflow-hidden">
        {renderDebaterColumn('pro')}

        {/* 中栏 · 擂台 */}
        <section className="flex min-h-0 flex-col gap-4 lg:overflow-y-auto lg:scrollbar-none">
          {/* 当前发言大卡 */}
          <div
            className={`rounded-[20px] border bg-surface p-7 transition-colors ${
              currentSide === 'pro'
                ? 'border-info/40 shadow-[0_0_28px_rgba(92,140,240,0.18)]'
                : currentSide === 'con'
                  ? 'border-danger/40 shadow-[0_0_28px_rgba(224,107,107,0.18)]'
                  : 'border-line'
            }`}
          >
            <div className="mb-3 flex items-center justify-between gap-3">
              <span className={`font-hud text-[11px] uppercase tracking-[0.3em] ${currentSide === 'con' ? 'text-danger' : currentSide === 'pro' ? 'text-info' : 'text-text-secondary/60'}`}>
                {currentSide === 'con' ? 'CON' : currentSide === 'pro' ? 'PRO' : 'STAGE'} · #{messages.length}
              </span>
              <span className="font-hud text-[11px] text-text-secondary/50">
                {currentMessage ? new Date(currentMessage.timestamp).toLocaleTimeString('zh-CN', { hour12: false }) : '—'}
              </span>
            </div>

            {currentMessage ? (
              <>
                <p className="min-h-16 whitespace-pre-wrap text-lg leading-8 text-text-primary md:text-[19px] md:leading-9">
                  “{currentMessage.content}”
                </p>
                <div className="mt-4 flex items-center gap-2.5">
                  <span
                    className={`flex h-8 w-8 items-center justify-center rounded-full font-bold text-white ${
                      currentMessage.speaker_id === 'user' ? 'bg-gold' : currentSide === 'con' ? 'bg-danger' : 'bg-info'
                    }`}
                  >
                    {(currentMessage.speaker_name || '你').slice(0, 1)}
                  </span>
                  <span className="truncate text-[13px] font-medium text-text-primary">
                    {currentMessage.speaker_id === 'user' ? '你（主持人）' : `玩家 · ${currentMessage.speaker_name}`}
                  </span>
                  <span className="font-hud ml-auto shrink-0 text-[11px] uppercase tracking-[0.2em] text-text-secondary/50">
                    {currentSide === 'con' ? 'CON' : currentSide === 'pro' ? 'PRO' : 'HOST'} · SPEAKING
                  </span>
                </div>
              </>
            ) : currentThinkingAgent ? (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3 text-sm text-violet/85">
                  <div className="flex gap-1.5">
                    <span className="anim-thinking-dot h-2 w-2 rounded-full bg-violet" />
                    <span className="anim-thinking-dot h-2 w-2 rounded-full bg-violet [animation-delay:150ms]" />
                    <span className="anim-thinking-dot h-2 w-2 rounded-full bg-violet [animation-delay:300ms]" />
                  </div>
                  玩家 {currentThinkingAgent} 正在构思陈词…
                </div>
                <div className="flex flex-col gap-2">
                  <span className="anim-name-shimmer-dim h-3 w-11/12 rounded-full" />
                  <span className="anim-name-shimmer-dim h-3 w-2/3 rounded-full" />
                </div>
              </div>
            ) : (
              <div className="flex min-h-16 flex-col items-center justify-center gap-2 text-text-secondary/55">
                <Swords className="h-7 w-7 opacity-40" />
                <p className="text-sm">擂台已就绪，点击下方「开始对垒」进入第一轮立论</p>
              </div>
            )}

            {clashMessage && (
              <div className="mt-4 flex items-center gap-2.5 rounded-xl bg-gold/8 px-3 py-3">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-gold" />
                <span className="truncate text-xs font-medium text-gold">
                  交锋焦点：{clashMessage.speaker} 质疑 {clashMessage.targets} 的观点
                </span>
              </div>
            )}
          </div>

          {/* 观众实时倾向 */}
          <div>
            <p className="font-hud mb-2 text-[11px] uppercase tracking-[0.25em] text-text-secondary/55">
              观众实时倾向 AUDIENCE SENTIMENT
            </p>
            <div className="flex h-[22px] overflow-hidden rounded-full">
              <div className="flex items-center bg-info pl-3 transition-all duration-700" style={{ width: `${stats.proShare}%` }}>
                <span className="whitespace-nowrap text-[11px] font-medium text-white">正方 {stats.proShare}%</span>
              </div>
              <div className="flex flex-1 items-center justify-end bg-danger pr-3 transition-all duration-700">
                <span className="whitespace-nowrap text-[11px] font-medium text-white">反方 {100 - stats.proShare}%</span>
              </div>
            </div>
            <div className="mt-1.5 flex items-center justify-between text-[11px] text-text-secondary/55">
              <span>由玩家发言立场实时聚合</span>
              <span>共 {stats.totalAgree} 次表态 · 最后更新 {currentMessage ? new Date(currentMessage.timestamp).toLocaleTimeString('zh-CN', { hour12: false }) : '—'}</span>
            </div>
          </div>

          {/* 上轮回顾 */}
          {replayMessages.map((msg) => {
            const side = sideOfSpeaker(msg.speaker_id);
            const tone = side ? SIDE_TONE[side] : null;
            return (
              <div key={msg.id} className="flex flex-col gap-1.5">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium ${tone ? tone.text : 'text-text-secondary/70'}`}>
                    {msg.speaker_id === 'user' ? '你（主持人）' : `玩家 · ${msg.speaker_name}`}
                  </span>
                  <span className="font-hud text-[10px] uppercase tracking-[0.2em] text-text-secondary/45">上轮回顾</span>
                </div>
                <div className={`rounded-[14px] border px-3.5 py-3.5 ${tone ? `${tone.border} ${tone.bg}` : 'border-line bg-white/[0.03]'}`}>
                  <p className="line-clamp-3 text-[13px] leading-[22px] text-text-secondary/85">“{msg.content}”</p>
                </div>
              </div>
            );
          })}
          <div ref={stageEndRef} />

          {/* 控制条 */}
          <div className="mt-auto rounded-2xl border border-line bg-surface/60 px-4 py-3 backdrop-blur">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                {!isActive && messages.length === 0 ? (
                  <button
                    onClick={handleStartDiscussion}
                    className="flex items-center gap-2 rounded-xl bg-gold px-5 py-2 text-sm font-bold text-[#171424] shadow-[0_0_18px_rgba(232,194,105,0.35)] transition-all hover:brightness-110"
                  >
                    <Swords className="h-4 w-4" />
                    开始对垒
                  </button>
                ) : (
                  <>
                    {isPaused ? (
                      <button
                        onClick={handleResume}
                        className="rounded-xl bg-gold px-4 py-2 text-sm font-bold text-[#171424] transition-all hover:brightness-110"
                      >
                        继续
                      </button>
                    ) : (
                      <button
                        onClick={handlePause}
                        disabled={!isActive}
                        className="rounded-xl border border-line px-4 py-2 text-sm text-text-secondary/80 transition-colors hover:border-gold/40 hover:text-gold disabled:opacity-40"
                      >
                        暂停
                      </button>
                    )}
                    <button
                      onClick={handleEnd}
                      className="rounded-xl border border-danger/40 px-4 py-2 text-sm text-danger/85 transition-colors hover:bg-danger/10"
                    >
                      结束
                    </button>
                  </>
                )}
              </div>
              <div className="flex min-w-[260px] flex-1 items-center gap-2 sm:max-w-md">
                <input
                  type="text"
                  value={userSpeech}
                  onChange={(e) => setUserSpeech(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && userSpeech.trim()) {
                      handleUserSpeak(userSpeech);
                    }
                  }}
                  placeholder="以主持人身份发言…"
                  className="min-w-0 flex-1 rounded-xl border border-line bg-white/[0.04] px-3.5 py-2 text-sm text-text-primary outline-none placeholder:text-text-secondary/40 focus:border-gold/50"
                />
                <button
                  onClick={() => handleUserSpeak(userSpeech)}
                  disabled={!userSpeech.trim()}
                  className="shrink-0 rounded-xl border border-gold/40 bg-gold/10 px-4 py-2 text-sm font-medium text-gold transition-colors hover:bg-gold/20 disabled:opacity-40"
                >
                  发言
                </button>
              </div>
            </div>
          </div>
        </section>

        {renderDebaterColumn('con')}
      </div>
    </div>
  );
};

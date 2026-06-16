import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Brain,
  ChevronRight,
  CircleDot,
  Clock3,
  Globe,
  History,
  MessageSquare,
  Moon,
  Play,
  Settings,
  Shield,
  Sparkles,
} from 'lucide-react';

import GameHistoryCard from '../components/GameHistoryCard';
import ParticleBackground from '../components/ParticleBackground';
import QuickStartWizard from '../components/QuickStartWizard';
import { useGameHistory } from '../hooks/useGameHistory';
import type { GameHistoryItem } from '../hooks/useGameHistory';
import { useSettingsStore } from '../store/settingsStore';
import type { ModelConfig } from '../types/modelConfig';

type Language = 'zh' | 'en';

interface ModeCard {
  key: 'werewolf' | 'undercover' | 'discussion';
  route: '/werewolf' | '/undercover' | '/discussion';
  icon: React.ElementType;
  toneClassName: string;
  badgeClassName: string;
}

const translations = {
  zh: {
    title: 'Mystery Agents',
    eyebrow: '多智能体社交推理沙盒',
    subtitle: '让 AI 进入狼人杀、谁是卧底和开放讨论，在实时发言、投票与回放中观察推理如何形成。',
    primaryAction: '进入狼人杀',
    setupAction: '配置模型',
    quickStart: '快速开局',
    recentGames: '最近游戏',
    noHistoryTitle: '还没有游戏记录',
    noHistoryDesc: '完成一局后，回放会出现在这里。',
    systemStatus: '运行状态',
    model: '模型',
    provider: '服务商',
    configs: '配置数量',
    environment: '环境',
    localDemo: '本地演示',
    notConfigured: '未配置',
    configureHint: '先配置模型，再开始真实对局。',
    readyHint: '已读取模型配置，可以开始对局。',
    livePill: '本地实时事件',
    replayPill: '时间轴回放',
    reasoningPill: '逐 token 展示',
    modes: {
      werewolf: {
        title: '狼人杀剧场',
        desc: '夜晚行动、白天发言、票型压力和阵营结算以沉浸式舞台呈现。',
        meta: '推荐体验',
      },
      undercover: {
        title: '谁是卧底',
        desc: '围绕秘密词汇展开描述和怀疑，观察智能体如何隐藏与拆穿身份。',
        meta: '经典推理',
      },
      discussion: {
        title: '讨论模式',
        desc: '让多个角色围绕任意议题展开自由辩论，适合观察立场和人格差异。',
        meta: '开放对话',
      },
    },
  },
  en: {
    title: 'Mystery Agents',
    eyebrow: 'Multi-agent social deduction sandbox',
    subtitle: 'Put AI agents into Werewolf, Undercover, and open discussions, then inspect live speeches, votes, and replay timelines.',
    primaryAction: 'Enter Werewolf',
    setupAction: 'Configure Models',
    quickStart: 'Quick Start',
    recentGames: 'Recent Games',
    noHistoryTitle: 'No game history yet',
    noHistoryDesc: 'Finished matches and replays will appear here.',
    systemStatus: 'Run Status',
    model: 'Model',
    provider: 'Provider',
    configs: 'Configs',
    environment: 'Environment',
    localDemo: 'Local Demo',
    notConfigured: 'Not Configured',
    configureHint: 'Configure a model before running real matches.',
    readyHint: 'Model configuration is loaded. Ready to play.',
    livePill: 'Local live events',
    replayPill: 'Replay timelines',
    reasoningPill: 'Token playback',
    modes: {
      werewolf: {
        title: 'Werewolf Theater',
        desc: 'Night actions, public speeches, vote pressure, and faction endings staged as an immersive match.',
        meta: 'Recommended',
      },
      undercover: {
        title: 'Undercover',
        desc: 'Agents describe secret words, hide intent, and reason about who does not belong.',
        meta: 'Classic deduction',
      },
      discussion: {
        title: 'Discussion Mode',
        desc: 'Let multiple personas debate any topic and inspect how perspectives diverge.',
        meta: 'Open dialogue',
      },
    },
  },
} as const;

const modeCards: ModeCard[] = [
  {
    key: 'werewolf',
    route: '/werewolf',
    icon: Moon,
    toneClassName: 'border-amber-300/25 bg-[radial-gradient(circle_at_top_right,rgba(255,215,0,0.18),transparent_32%),rgba(15,23,42,0.66)]',
    badgeClassName: 'border-amber-300/30 bg-amber-300/10 text-amber-100',
  },
  {
    key: 'undercover',
    route: '/undercover',
    icon: Shield,
    toneClassName: 'border-sky-300/20 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.14),transparent_34%),rgba(15,23,42,0.58)]',
    badgeClassName: 'border-sky-300/25 bg-sky-400/10 text-sky-100',
  },
  {
    key: 'discussion',
    route: '/discussion',
    icon: MessageSquare,
    toneClassName: 'border-rose-300/20 bg-[radial-gradient(circle_at_top_right,rgba(251,113,133,0.14),transparent_34%),rgba(15,23,42,0.58)]',
    badgeClassName: 'border-rose-300/25 bg-rose-400/10 text-rose-100',
  },
];

const getPreferredConfig = (configs: ModelConfig[]) => configs[0] || null;

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { modelConfigs, fetchModelConfigs } = useSettingsStore();
  const { history, removeGame } = useGameHistory();
  const [showWizard, setShowWizard] = useState(false);
  const [lang, setLang] = useState<Language>('zh');

  React.useEffect(() => {
    fetchModelConfigs();
  }, [fetchModelConfigs]);

  const activeModelConfig = React.useMemo(() => getPreferredConfig(modelConfigs), [modelConfigs]);
  const t = translations[lang];

  const handleResume = (item: GameHistoryItem) => {
    navigate(`/${item.type}`);
  };

  const handleWizardComplete = (config: unknown) => {
    setShowWizard(false);
    navigate('/undercover', { state: { config } });
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_20%_10%,rgba(99,102,241,0.24),transparent_28%),radial-gradient(circle_at_80%_0%,rgba(255,215,0,0.12),transparent_24%),linear-gradient(135deg,#020617,#0f172a_52%,#111827)] text-text">
      <ParticleBackground />

      <main className="relative z-10 mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
        <header className="mb-10 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.06] text-ww-gold shadow-lg">
              <Brain className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-[0.22em] text-white/45">{t.eyebrow}</div>
              <div className="text-lg font-black text-white">Mystery Agents</div>
            </div>
          </div>

          <nav className="flex gap-2" aria-label={lang === 'zh' ? '首页操作' : 'Home actions'}>
            <button
              type="button"
              onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}
              className="rounded-2xl border border-white/10 bg-white/[0.05] p-3 text-white/60 transition-colors hover:border-white/20 hover:text-white focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label={lang === 'zh' ? 'Switch to English' : '切换到中文'}
            >
              <Globe size={20} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => navigate('/settings')}
              className="rounded-2xl border border-white/10 bg-white/[0.05] p-3 text-white/60 transition-colors hover:border-white/20 hover:text-white focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label={t.setupAction}
            >
              <Settings size={20} aria-hidden="true" />
            </button>
          </nav>
        </header>

        <section className="grid flex-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-6">
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.055] p-6 shadow-2xl backdrop-blur-xl sm:p-8 lg:p-10"
            >
              <div className="pointer-events-none absolute -right-20 -top-28 h-72 w-72 rounded-full bg-ww-gold/10 blur-3xl" />
              <div className="pointer-events-none absolute bottom-0 left-0 h-px w-full bg-gradient-to-r from-transparent via-ww-gold/50 to-transparent" />

              <div className="relative max-w-3xl">
                <div className="mb-5 flex flex-wrap gap-2">
                  {[t.livePill, t.replayPill, t.reasoningPill].map((pill) => (
                    <span key={pill} className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-white/60">
                      {pill}
                    </span>
                  ))}
                </div>
                <h1 className="text-4xl font-black tracking-tight text-white sm:text-6xl lg:text-7xl">
                  {t.title}
                </h1>
                <p className="mt-5 max-w-2xl text-base leading-7 text-white/65 sm:text-lg">
                  {t.subtitle}
                </p>

                <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                  <button
                    type="button"
                    onClick={() => navigate('/werewolf')}
                    className="inline-flex items-center justify-center gap-2 rounded-2xl bg-ww-gold px-5 py-3 font-bold text-slate-950 transition-transform hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-ww-gold/70"
                  >
                    <Play size={18} aria-hidden="true" />
                    {t.primaryAction}
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate('/settings')}
                    className="inline-flex items-center justify-center gap-2 rounded-2xl border border-white/12 bg-white/[0.04] px-5 py-3 font-semibold text-white/75 transition-colors hover:border-white/25 hover:text-white focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <Settings size={18} aria-hidden="true" />
                    {t.setupAction}
                  </button>
                </div>
              </div>
            </motion.div>

            <section aria-label={lang === 'zh' ? '游戏模式' : 'Game modes'} className="grid gap-4 md:grid-cols-3">
              {modeCards.map((mode) => {
                const Icon = mode.icon;
                const copy = t.modes[mode.key];
                return (
                  <motion.button
                    key={mode.key}
                    type="button"
                    whileHover={{ y: -4 }}
                    whileTap={{ scale: 0.99 }}
                    onClick={() => navigate(mode.route)}
                    className={`group flex min-h-64 flex-col items-start overflow-hidden rounded-[1.75rem] border p-5 text-left shadow-xl backdrop-blur-xl transition-colors hover:border-white/25 focus:outline-none focus:ring-2 focus:ring-primary ${mode.toneClassName}`}
                  >
                    <div className="mb-5 flex w-full items-center justify-between gap-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-black/25 text-white">
                        <Icon className="h-6 w-6" aria-hidden="true" />
                      </div>
                      <span className={`rounded-full border px-3 py-1 text-xs ${mode.badgeClassName}`}>
                        {copy.meta}
                      </span>
                    </div>
                    <h2 className="text-xl font-black text-white">{copy.title}</h2>
                    <p className="mt-3 flex-1 text-sm leading-6 text-white/58">{copy.desc}</p>
                    <div className="mt-5 flex items-center gap-2 text-sm font-semibold text-white/75 transition-colors group-hover:text-white">
                      {t.primaryAction}
                      <ChevronRight size={16} aria-hidden="true" />
                    </div>
                  </motion.button>
                );
              })}
            </section>

            <button
              type="button"
              onClick={() => setShowWizard(true)}
              className="flex w-full items-center justify-center gap-2 rounded-[1.5rem] border border-dashed border-white/14 bg-white/[0.03] px-5 py-4 font-semibold text-white/60 transition-colors hover:border-ww-gold/40 hover:text-ww-gold focus:outline-none focus:ring-2 focus:ring-ww-gold/70"
            >
              <Sparkles size={18} aria-hidden="true" />
              {t.quickStart}
            </button>
          </div>

          <aside className="space-y-4">
            <section className="rounded-[1.75rem] border border-white/10 bg-white/[0.055] p-5 backdrop-blur-xl">
              <div className="mb-4 flex items-center gap-2 font-bold text-white">
                <CircleDot size={18} className={activeModelConfig ? 'text-emerald-300' : 'text-amber-300'} aria-hidden="true" />
                {t.systemStatus}
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className={`text-sm leading-6 ${activeModelConfig ? 'text-emerald-100/75' : 'text-amber-100/75'}`}>
                  {activeModelConfig ? t.readyHint : t.configureHint}
                </p>
              </div>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-white/45">{t.model}</dt>
                  <dd className="max-w-44 truncate font-mono text-primary">{activeModelConfig ? activeModelConfig.model : t.notConfigured}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-white/45">{t.provider}</dt>
                  <dd className="text-accent">{activeModelConfig ? activeModelConfig.provider : '-'}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-white/45">{t.configs}</dt>
                  <dd className="text-sky-300">{modelConfigs.length}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-white/45">{t.environment}</dt>
                  <dd className="text-emerald-300">{t.localDemo}</dd>
                </div>
              </dl>
            </section>

            <section className="rounded-[1.75rem] border border-white/10 bg-white/[0.055] p-5 backdrop-blur-xl">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 font-bold text-white">
                  <History size={18} className="text-primary" aria-hidden="true" />
                  {t.recentGames}
                </div>
                <Clock3 size={16} className="text-white/35" aria-hidden="true" />
              </div>
              <div className="scrollbar-none max-h-[25rem] space-y-3 overflow-y-auto pr-1">
                {history.length > 0 ? (
                  history.map((item) => (
                    <GameHistoryCard key={item.id} item={item} onResume={handleResume} onRemove={removeGame} />
                  ))
                ) : (
                  <div role="status" className="rounded-2xl border border-dashed border-white/10 bg-black/20 px-4 py-8 text-center">
                    <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-2xl bg-white/[0.06] text-white/45">
                      <History size={18} aria-hidden="true" />
                    </div>
                    <h2 className="text-sm font-semibold text-white/75">{t.noHistoryTitle}</h2>
                    <p className="mt-2 text-xs leading-5 text-white/45">{t.noHistoryDesc}</p>
                  </div>
                )}
              </div>
            </section>
          </aside>
        </section>
      </main>

      <AnimatePresence>
        {showWizard && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setShowWizard(false)}
            />
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 18 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 18 }}
              className="relative w-full max-w-lg overflow-hidden rounded-3xl border border-white/10 bg-slate-950/95 shadow-2xl"
            >
              <QuickStartWizard onComplete={handleWizardComplete} onCancel={() => setShowWizard(false)} />
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

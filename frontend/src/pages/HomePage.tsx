import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Fingerprint, Globe, MessagesSquare, Moon, ScrollText, Settings, X } from 'lucide-react';

import QuickStartWizard from '../components/QuickStartWizard';
import { ThemeToggle } from '../components/ThemeToggle';
import { useGameHistory } from '../hooks/useGameHistory';
import { useI18n } from '../hooks/useI18n';
import type { GameHistoryItem } from '../hooks/useGameHistory';
import { useSettingsStore } from '../store/settingsStore';
import type { TranslationKeys } from '../utils/i18n';

/** 首页文案切片（全局词典 home 段） */
type HomeCopy = TranslationKeys['home'];

interface ModeCard {
  key: 'werewolf' | 'undercover' | 'discussion' | 'jubensha';
  route: '/werewolf' | '/undercover' | '/discussion' | '/jubensha';
  icon: React.ElementType;
  /** 图标容器色调（对齐设计稿：狼红 / 辩论紫 / 卧底橙） */
  toneText: string;
  toneBg: string;
  /** 参数行强调色：狼人杀金色，其余灰紫 */
  paramClassName: string;
}

const modeCards: ModeCard[] = [
  {
    key: 'werewolf',
    route: '/werewolf',
    icon: Moon,
    toneText: 'text-role-wolf',
    toneBg: 'bg-role-wolf/15',
    paramClassName: 'text-gold',
  },
  {
    key: 'discussion',
    route: '/discussion',
    icon: MessagesSquare,
    toneText: 'text-violet',
    toneBg: 'bg-violet/15',
    paramClassName: 'text-text-secondary/60',
  },
  {
    key: 'undercover',
    route: '/undercover',
    icon: Fingerprint,
    toneText: 'text-role-undercover',
    toneBg: 'bg-role-undercover/15',
    paramClassName: 'text-text-secondary/60',
  },
  {
    key: 'jubensha',
    route: '/jubensha',
    icon: ScrollText,
    toneText: 'text-gold',
    toneBg: 'bg-gold/15',
    paramClassName: 'text-text-secondary/60',
  },
];

const modeLabel = (type: GameHistoryItem['type'], t: HomeCopy) => {
  switch (type) {
    case 'werewolf': return t.modes.werewolf.title;
    case 'undercover': return t.modes.undercover.title;
    case 'jubensha': return t.modes.jubensha.title;
    default: return t.modes.discussion.title;
  }
};

const formatTime = (ts: number) => {
  const diff = Date.now() - ts;
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return 'NOW';
  if (minutes < 60) return `${minutes}M AGO`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}H AGO`;
  return `${Math.round(hours / 24)}D AGO`;
};

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { modelConfigs, fetchModelConfigs, setLanguage } = useSettingsStore();
  const { history, removeGame } = useGameHistory();
  const [showWizard, setShowWizard] = useState(false);
  const { t, language: lang } = useI18n();
  const home = t.home;

  React.useEffect(() => {
    fetchModelConfigs();
  }, [fetchModelConfigs]);

  const isOnline = modelConfigs.length > 0;

  const handleResume = (item: GameHistoryItem) => {
    navigate(`/${item.type}`);
  };

  const scrollToModes = () => {
    document.getElementById('mode-select')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-background text-text">
      {/* 顶栏 */}
      <header className="flex items-center justify-between px-6 py-4 sm:px-10 sm:py-[22px]">
        <div className="flex items-center gap-3">
          <Moon className="h-5 w-5 text-gold" aria-hidden="true" />
          <span className="font-hud text-[13px] tracking-[0.18em] text-gold">{home.brand}</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="mr-1 hidden items-center gap-2 sm:flex">
            <span
              className={`h-1.5 w-1.5 rounded-full ${isOnline ? 'bg-success' : 'bg-warning'}`}
              aria-hidden="true"
            />
            <span className="font-hud text-xs text-text-secondary/60">
              {isOnline ? `${home.online} · ${modelConfigs.length} CONFIGS` : home.notConfigured}
            </span>
          </div>
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setLanguage(lang === 'zh' ? 'en' : 'zh')}
            className="rounded-xl border border-white/10 bg-white/[0.04] p-2.5 text-text-secondary/70 transition-colors hover:border-white/20 hover:text-text focus:outline-none focus:ring-2 focus:ring-violet/60"
            aria-label={lang === 'zh' ? 'Switch to English' : '切换到中文'}
          >
            <Globe size={16} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => navigate('/settings')}
            className="rounded-xl border border-white/10 bg-white/[0.04] p-2.5 text-text-secondary/70 transition-colors hover:border-white/20 hover:text-text focus:outline-none focus:ring-2 focus:ring-violet/60"
            aria-label={home.setupAction}
          >
            <Settings size={16} aria-hidden="true" />
          </button>
        </div>
      </header>

      {/* 主视觉 */}
      <motion.main
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="flex flex-1 flex-col justify-center gap-[18px] px-6 py-8 sm:gap-[22px] sm:px-[60px] sm:py-[60px]"
      >
        <p className="font-hud text-[13px] tracking-[0.22em] text-violet">{home.eyebrow}</p>
        <h1 className="text-4xl font-black tracking-tight text-text-primary sm:text-7xl lg:text-[88px] lg:leading-none">
          {home.title}
        </h1>
        <p className="max-w-2xl text-base leading-7 text-text-secondary sm:text-base">{home.subtitle}</p>

        <div className="mt-2 flex flex-col gap-4 sm:flex-row">
          <button
            type="button"
            onClick={scrollToModes}
            className="rounded-xl bg-gold px-8 py-4 text-base font-medium text-[#2B2836] shadow-[0_0_28px_rgba(232,194,105,0.35)] transition-all hover:shadow-[0_0_40px_rgba(232,194,105,0.5)] active:scale-[0.98] sm:px-10"
          >
            {home.primaryAction}
          </button>
          <button
            type="button"
            onClick={() => navigate('/settings')}
            className="rounded-xl border border-white/20 bg-white/[0.06] px-8 py-4 text-base font-medium text-text-primary transition-all hover:border-white/35 hover:bg-white/[0.09] active:scale-[0.98] sm:px-9"
          >
            {home.setupAction}
          </button>
        </div>
      </motion.main>

      {/* 模式选择 */}
      <section id="mode-select" aria-label={home.modesLabel} className="scroll-mt-6 px-6 pb-9 sm:px-10">
        <p className="mb-3.5 font-hud text-[11px] tracking-[0.2em] text-text-secondary/50">{home.modesLabel}</p>
        <div className="grid gap-5 md:grid-cols-3">
          {modeCards.map((mode, index) => {
            const Icon = mode.icon;
            const copy = home.modes[mode.key];
            return (
              <motion.button
                key={mode.key}
                type="button"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08 * index, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                whileHover={{ y: -4 }}
                onClick={() => navigate(mode.route)}
                className="flex flex-col items-start gap-3.5 rounded-[20px] border border-white/10 bg-surface p-6 text-left transition-colors hover:border-violet/45 focus:outline-none focus:ring-2 focus:ring-violet/60"
              >
                <span className={`flex h-11 w-11 items-center justify-center rounded-xl ${mode.toneBg}`}>
                  <Icon className={`h-5 w-5 ${mode.toneText}`} aria-hidden="true" />
                </span>
                <h2 className="text-[22px] font-bold text-text-primary">{copy.title}</h2>
                <p className="flex-1 text-[13px] leading-[22px] text-text-secondary">{copy.desc}</p>
                <span className={`font-hud text-[11px] tracking-wider ${mode.paramClassName}`}>{copy.params}</span>
              </motion.button>
            );
          })}
        </div>
      </section>

      {/* 最近对局 */}
      <section aria-label={home.recentMatches} className="px-6 pb-7 sm:px-10">
        <p className="mb-3.5 font-hud text-[11px] tracking-[0.2em] text-text-secondary/50">{home.recentMatches}</p>
        {history.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-3">
            {history.slice(0, 3).map((item) => (
              <div
                key={item.id}
                className="group flex cursor-pointer items-center justify-between gap-3.5 rounded-[14px] border border-white/[0.08] bg-surface px-4 py-4 transition-colors hover:border-white/20"
                onClick={() => handleResume(item)}
              >
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-medium text-text-primary">
                    {modeLabel(item.type, home)} · {item.status === 'active' ? home.statusActive : home.statusDone}
                  </p>
                  <p className="mt-1 truncate text-[11px] text-text-secondary/55">
                    {item.config?.topic || item.config?.playerCount ? buildHistoryMeta(item) : ''}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className="font-hud text-[10px] text-text-secondary/50">{formatTime(item.timestamp)}</span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeGame(item.id);
                    }}
                    className="rounded-md px-1.5 py-0.5 text-[10px] text-text-secondary/40 opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
                    aria-label="remove"
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-[14px] border border-dashed border-white/10 px-4 py-6 text-center text-xs text-text-secondary/50">
            {home.noHistory}
          </div>
        )}
      </section>

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
              <QuickStartWizard onComplete={() => setShowWizard(false)} onCancel={() => setShowWizard(false)} />
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

/** 最近对局副行：话题或人数等一句概要 */
const buildHistoryMeta = (item: GameHistoryItem): string => {
  const cfg = item.config ?? {};
  if (cfg.topic) return String(cfg.topic);
  if (cfg.playerCount) return `${cfg.playerCount}P`;
  return '—';
};

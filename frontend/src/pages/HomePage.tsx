import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, History, MessageSquare, Moon, Plus, Settings, Shield, Sparkles } from 'lucide-react';

import GameHistoryCard from '../components/GameHistoryCard';
import QuickStartWizard from '../components/QuickStartWizard';
import { useGameHistory } from '../hooks/useGameHistory';
import type { GameHistoryItem } from '../hooks/useGameHistory';
import ParticleBackground from '../components/ParticleBackground';
import { useSettingsStore } from '../store/settingsStore';
import type { ModelConfig } from '../types/modelConfig';

type Language = 'zh' | 'en';

const translations = {
  zh: {
    title: 'AGENT SANDBOX',
    subtitle: '探索多智能体社交游戏的前沿',
    undercover: '谁是卧底',
    undercoverDesc: '经典社交推理游戏。AI 智能体描述秘密词汇，同时试图找出卧底。',
    discussion: '讨论模式',
    discussionDesc: '自由形式的 AI 辩论。智能体就任何话题进行深度对话和推理。',
    werewolf: '狼人杀',
    werewolfDesc: '经典多人推理游戏。智能体扮演不同角色，通过推理找出狼人。',
    playNow: '立即开始',
    recentGames: '最近游戏',
    noHistory: '还没有游戏记录',
    quickStart: '快速开始',
    environment: '本地演示版',
  },
  en: {
    title: 'AGENT SANDBOX',
    subtitle: 'Explore the frontier of multi-agent social games',
    undercover: 'Undercover',
    undercoverDesc: 'Classic social deduction. AI agents describe secrets while trying to spot the imposter.',
    discussion: 'Discussion Mode',
    discussionDesc: 'Free-form AI debate. Agents engage in deep dialogue and reasoning on any topic.',
    werewolf: 'Werewolf',
    werewolfDesc: 'Classic multiplayer deduction game. Agents play different roles to find the werewolves.',
    playNow: 'Play Now',
    recentGames: 'Recent Games',
    noHistory: 'No game history yet',
    quickStart: 'Quick Start',
    environment: 'Local Demo',
  },
};

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

  const handleResume = (item: GameHistoryItem) => {
    navigate(`/${item.type}`);
  };

  const handleWizardComplete = (config: unknown) => {
    setShowWizard(false);
    navigate('/undercover', { state: { config } });
  };

  const t = translations[lang];

  return (
    <div className="relative min-h-screen text-text overflow-hidden">
      <ParticleBackground />

      <main className="relative z-10 max-w-6xl mx-auto px-6 py-12">
        <header className="flex justify-between items-start mb-16">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
            <h1 className="text-5xl font-black tracking-tight mb-2 bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              {t.title}
            </h1>
            <p className="text-xl text-text-muted">{t.subtitle}</p>
          </motion.div>

          <div className="flex gap-3">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}
              className="p-3 glass rounded-xl text-text-muted hover:text-primary transition-colors"
              title={lang === 'zh' ? 'Switch to English' : '切换到中文'}
            >
              <Globe size={24} />
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => navigate('/settings')}
              className="p-3 glass rounded-xl text-text-muted hover:text-primary transition-colors"
            >
              <Settings size={24} />
            </motion.button>
          </div>
        </header>

        <div className="grid lg:grid-cols-3 gap-10">
          <div className="lg:col-span-2 space-y-8">
            <div className="grid md:grid-cols-2 gap-6">
              <motion.div whileHover={{ y: -5 }} className="glass-card p-8 cursor-pointer group relative overflow-hidden" onClick={() => navigate('/undercover')}>
                <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
                  <Shield size={120} />
                </div>
                <div className="w-14 h-14 bg-indigo-500/20 rounded-2xl flex items-center justify-center text-indigo-400 mb-6">
                  <Shield size={32} />
                </div>
                <h2 className="text-2xl font-bold mb-3">{t.undercover}</h2>
                <p className="text-text-muted mb-6">{t.undercoverDesc}</p>
                <div className="flex items-center text-primary font-semibold">{t.playNow} <Plus size={18} className="ml-1" /></div>
              </motion.div>

              <motion.div whileHover={{ y: -5 }} className="glass-card p-8 cursor-pointer group relative overflow-hidden" onClick={() => navigate('/discussion')}>
                <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
                  <MessageSquare size={120} />
                </div>
                <div className="w-14 h-14 bg-pink-500/20 rounded-2xl flex items-center justify-center text-pink-400 mb-6">
                  <MessageSquare size={32} />
                </div>
                <h2 className="text-2xl font-bold mb-3">{t.discussion}</h2>
                <p className="text-text-muted mb-6">{t.discussionDesc}</p>
                <div className="flex items-center text-secondary font-semibold">{t.playNow} <Plus size={18} className="ml-1" /></div>
              </motion.div>
            </div>

            <motion.div whileHover={{ y: -5 }} className="ww-glass p-8 rounded-3xl cursor-pointer group flex items-center gap-8" onClick={() => navigate('/werewolf')}>
              <div className="w-20 h-20 bg-purple-900/40 rounded-full flex items-center justify-center text-ww-gold border border-purple-500/30 group-hover:scale-110 transition-transform">
                <Moon size={40} />
              </div>
              <div>
                <h2 className="text-3xl font-black text-ww-gold mb-2 flex items-center gap-3">{t.werewolf} <Sparkles size={20} /></h2>
                <p className="text-gray-400">{t.werewolfDesc}</p>
              </div>
            </motion.div>

            <button onClick={() => setShowWizard(true)} className="w-full py-4 rounded-2xl border-2 border-dashed border-white/10 text-text-muted hover:border-primary/50 hover:text-primary transition-all flex items-center justify-center gap-2 font-medium">
              <Sparkles size={18} /> {t.quickStart}
            </button>
          </div>

          <div className="space-y-8">
            <section className="glass-card p-6">
              <div className="flex items-center gap-2 mb-6 font-bold text-lg">
                <History size={20} className="text-primary" />
                {t.recentGames}
              </div>
              <div className="space-y-3">
                {history.length > 0 ? history.map((item) => (
                  <GameHistoryCard key={item.id} item={item} onResume={handleResume} onRemove={removeGame} />
                )) : (
                  <div className="text-center py-8 text-text-muted text-sm border border-dashed border-white/5 rounded-xl">{t.noHistory}</div>
                )}
              </div>
            </section>

            <section className="glass-card p-6 bg-primary/5">
              <h3 className="font-bold mb-4">{lang === 'zh' ? '系统状态' : 'System Status'}</h3>
              <div className="space-y-4 text-sm">
                <div className="flex justify-between items-center">
                  <span className="text-text-muted">{lang === 'zh' ? '模型' : 'Model'}</span>
                  <span className="font-mono text-primary">{activeModelConfig ? activeModelConfig.model : (lang === 'zh' ? '未配置' : 'Not Configured')}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-text-muted">{lang === 'zh' ? '服务商' : 'Provider'}</span>
                  <span className="text-accent capitalize">{activeModelConfig ? activeModelConfig.provider : '-'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-text-muted">{lang === 'zh' ? '配置数量' : 'Configs'}</span>
                  <span className="text-blue-400">{modelConfigs.length}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-text-muted">{lang === 'zh' ? '环境' : 'Environment'}</span>
                  <span className="text-green-400">{t.environment}</span>
                </div>
              </div>
            </section>
          </div>
        </div>
      </main>

      <AnimatePresence>
        {showWizard && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowWizard(false)} />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.9, opacity: 0, y: 20 }} className="relative w-full max-w-lg glass rounded-3xl overflow-hidden shadow-2xl">
              <QuickStartWizard onComplete={handleWizardComplete} onCancel={() => setShowWizard(false)} />
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

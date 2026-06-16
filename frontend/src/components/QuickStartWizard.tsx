import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, ChevronLeft, Check, User, Bot, Shield } from 'lucide-react';

interface QuickStartWizardProps {
  onComplete: (config: any) => void;
  onCancel: () => void;
}

const QuickStartWizard: React.FC<QuickStartWizardProps> = ({ onComplete, onCancel }) => {
  const [step, setStep] = useState(1);
  const [config, setConfig] = useState({
    playerCount: 6,
    aiCount: 5,
    undercoverCount: 1,
    topicCategory: 'Daily Life'
  });

  const next = () => setStep(s => Math.min(s + 1, 3));
  const back = () => setStep(s => Math.max(s - 1, 1));

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-8">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 transition-colors ${
              step >= s ? 'bg-primary border-primary text-white' : 'border-white/20 text-text-muted'
            }`}>
              {step > s ? <Check size={16} /> : s}
            </div>
            {s < 3 && <div className={`w-12 h-0.5 mx-2 ${step > s ? 'bg-primary' : 'bg-white/10'}`} />}
          </div>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {step === 1 && (
          <motion.div
            key="step1"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="space-y-4"
          >
            <h3 className="text-xl font-bold">Total Players</h3>
            <p className="text-text-muted">How many people and AI are playing?</p>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="4"
                max="12"
                value={config.playerCount}
                onChange={(e) => setConfig({ ...config, playerCount: parseInt(e.target.value) })}
                className="flex-1 accent-primary"
              />
              <span className="text-2xl font-mono w-8">{config.playerCount}</span>
            </div>
          </motion.div>
        )}

        {step === 2 && (
          <motion.div
            key="step2"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="space-y-4"
          >
            <h3 className="text-xl font-bold">AI Ratio</h3>
            <p className="text-text-muted">How many of them should be AI bots?</p>
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => setConfig({ ...config, aiCount: config.playerCount - 1 })}
                className={`p-4 rounded-xl border flex flex-col items-center gap-2 ${
                  config.aiCount === config.playerCount - 1 ? 'bg-primary/20 border-primary' : 'bg-white/5 border-white/10'
                }`}
              >
                <Bot size={24} />
                <span>Full AI</span>
                <span className="text-xs opacity-60">You vs {config.playerCount - 1} Bots</span>
              </button>
              <button
                onClick={() => setConfig({ ...config, aiCount: Math.floor(config.playerCount / 2) })}
                className={`p-4 rounded-xl border flex flex-col items-center gap-2 ${
                  config.aiCount === Math.floor(config.playerCount / 2) ? 'bg-primary/20 border-primary' : 'bg-white/5 border-white/10'
                }`}
              >
                <User size={24} />
                <span>Mixed</span>
                <span className="text-xs opacity-60">Balanced Mix</span>
              </button>
            </div>
          </motion.div>
        )}

        {step === 3 && (
          <motion.div
            key="step3"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="space-y-4"
          >
            <h3 className="text-xl font-bold">Game Difficulty</h3>
            <p className="text-text-muted">Set the number of undercovers.</p>
            <div className="flex justify-center gap-4">
              {[1, 2, 3].map((n) => (
                <button
                  key={n}
                  disabled={n >= config.playerCount / 2}
                  onClick={() => setConfig({ ...config, undercoverCount: n })}
                  className={`w-12 h-12 rounded-xl border flex items-center justify-center transition-all ${
                    config.undercoverCount === n ? 'bg-secondary border-secondary text-white' : 'bg-white/5 border-white/10'
                  }`}
                >
                  <Shield size={20} className={n >= config.playerCount / 2 ? 'opacity-20' : ''} />
                  <span className="ml-1">{n}</span>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-12 flex justify-between">
        <button
          onClick={step === 1 ? onCancel : back}
          className="flex items-center gap-2 px-4 py-2 text-text-muted hover:text-text transition-colors"
        >
          {step === 1 ? 'Cancel' : <><ChevronLeft size={18} /> Back</>}
        </button>
        <button
          onClick={step === 3 ? () => onComplete(config) : next}
          className="flex items-center gap-2 px-6 py-2 bg-primary rounded-lg font-semibold hover:bg-primary-hover transition-colors"
        >
          {step === 3 ? 'Start Game' : <>Next <ChevronRight size={18} /></>}
        </button>
      </div>
    </div>
  );
};

export default QuickStartWizard;

import React from 'react';
import { motion } from 'framer-motion';
import { Zap, Users, Coffee, Skull } from 'lucide-react';

export interface GamePreset {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  config: any;
}

const PRESETS: GamePreset[] = [
  {
    id: 'quick',
    name: 'Quick Match',
    description: '4 Players, fast paced',
    icon: <Zap size={18} />,
    config: { playerCount: 4, aiCount: 3, undercoverCount: 1 }
  },
  {
    id: 'standard',
    name: 'Standard',
    description: '6 Players, balanced',
    icon: <Users size={18} />,
    config: { playerCount: 6, aiCount: 5, undercoverCount: 1 }
  },
  {
    id: 'party',
    name: 'Party Mode',
    description: '8 Players, chaotic fun',
    icon: <Coffee size={18} />,
    config: { playerCount: 8, aiCount: 7, undercoverCount: 2 }
  },
  {
    id: 'hardcore',
    name: 'Hardcore',
    description: '10 Players, 2 undercovers',
    icon: <Skull size={18} />,
    config: { playerCount: 10, aiCount: 9, undercoverCount: 2 }
  }
];

interface PresetSelectorProps {
  onSelect: (preset: GamePreset) => void;
  selectedId?: string;
}

const PresetSelector: React.FC<PresetSelectorProps> = ({ onSelect, selectedId }) => {
  return (
    <div className="grid grid-cols-2 gap-3">
      {PRESETS.map((preset) => (
        <motion.button
          key={preset.id}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => onSelect(preset)}
          className={`flex flex-col p-3 rounded-xl border text-left transition-all ${
            selectedId === preset.id
              ? 'bg-primary/20 border-primary text-primary'
              : 'bg-white/5 border-white/10 text-text-muted hover:border-white/20'
          }`}
        >
          <div className="flex items-center gap-2 mb-1">
            {preset.icon}
            <span className="font-medium text-sm">{preset.name}</span>
          </div>
          <p className="text-xs opacity-60 line-clamp-1">{preset.description}</p>
        </motion.button>
      ))}
    </div>
  );
};

export default PresetSelector;

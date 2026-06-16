import React from 'react';
import { motion } from 'framer-motion';
import { Clock, Play, Trash2, Shield, MessageSquare } from 'lucide-react';
import type { GameHistoryItem } from '../hooks/useGameHistory';

interface GameHistoryCardProps {
  item: GameHistoryItem;
  onResume: (item: GameHistoryItem) => void;
  onRemove: (id: string) => void;
}

const GameHistoryCard: React.FC<GameHistoryCardProps> = ({ item, onResume, onRemove }) => {
  const date = new Date(item.timestamp).toLocaleDateString();
  const time = new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-4 flex items-center justify-between group"
    >
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-lg ${item.type === 'undercover' ? 'bg-indigo-500/20 text-indigo-400' : 'bg-pink-500/20 text-pink-400'}`}>
          {item.type === 'undercover' ? <Shield size={20} /> : <MessageSquare size={20} />}
        </div>
        <div>
          <h4 className="font-semibold text-text capitalize">{item.type} Game</h4>
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Clock size={12} />
            <span>{date} {time}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => onResume(item)}
          className="p-2 rounded-full hover:bg-white/10 text-primary transition-colors"
          title="Resume Game"
        >
          <Play size={18} fill="currentColor" />
        </button>
        <button
          onClick={() => onRemove(item.id)}
          className="p-2 rounded-full hover:bg-red-500/10 text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
          title="Delete"
        >
          <Trash2 size={18} />
        </button>
      </div>
    </motion.div>
  );
};

export default GameHistoryCard;

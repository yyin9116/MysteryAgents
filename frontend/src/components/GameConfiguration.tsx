import React, { useState } from 'react';
import { Settings, Users, Sparkles, Play, ShieldAlert, Dice5 } from 'lucide-react';
import { gameService } from '../services/gameService';
import { useGameStore } from '../store/gameStore';
import { useSettingsStore } from '../store/settingsStore';
import { useI18n } from '../hooks/useI18n';
import PresetSelector from './PresetSelector';
import type { GamePreset } from './PresetSelector';
import { motion } from 'framer-motion';

const GameConfiguration: React.FC = () => {
    const [agentCount, setAgentCount] = useState(6);
    const [civilianWord, setCivilianWord] = useState('牛奶');
    const [undercoverWord, setUndercoverWord] = useState('豆浆');
    const [useBalancedTeam, setUseBalancedTeam] = useState(true);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedPresetId, setSelectedPresetId] = useState<string>();
    
    const setGame = useGameStore((state) => state.setGame);
    const { modelConfig } = useSettingsStore();
    const { t } = useI18n();

    const handlePresetSelect = (preset: GamePreset) => {
        setSelectedPresetId(preset.id);
        setAgentCount(preset.config.aiCount + 1);
        // Undercover count is currently handled by backend if useBalancedTeam is true
        // But we can store it if we want manual control later
    };

    const handleCreateGame = async (e: React.MouseEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        try {
            const gameConfig: any = {
                agent_count: agentCount,
                civilian_word: civilianWord,
                undercover_word: undercoverWord,
                use_balanced_team: useBalancedTeam,
            };

            if (modelConfig && modelConfig.api_key) {
                gameConfig.model_config = {
                    model: modelConfig.model,
                    api_key: modelConfig.api_key,
                    base_url: modelConfig.base_url
                };
            }

            const result = await gameService.createGame(gameConfig);
            const fullState = await gameService.getGameState(result.game_id);
            setGame(fullState);
        } catch (err: any) {
            console.error('Failed to create or start game:', err);
            setError(err.response?.data?.detail || err.message || 'An unexpected error occurred during game setup.');
        } finally {
            setLoading(false);
        }
    };

    const generateRandomWords = () => {
        const pairs = [
            ['苹果', '梨'], ['手机', '平板'], ['大海', '湖泊'], 
            ['自行车', '电动车'], ['猫', '狗'], ['教师', '教授']
        ];
        const pair = pairs[Math.floor(Math.random() * pairs.length)];
        setCivilianWord(pair[0]);
        setUndercoverWord(pair[1]);
    };

    return (
        <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-5xl mx-auto space-y-8 pb-12"
        >
            <div className="flex items-center space-x-4 mb-2">
                <div className="p-3 bg-primary/20 rounded-2xl">
                    <Settings className="w-6 h-6 text-primary" />
                </div>
                <div>
                    <h2 className="text-3xl font-bold">{t.config.title}</h2>
                    <p className="text-text-muted">{t.config.subtitle}</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Panel: Presets */}
                <div className="glass-card p-6 space-y-4">
                    <div className="flex items-center space-x-3 text-lg font-semibold">
                        <Dice5 className="w-5 h-5 text-primary" />
                        <h3>Quick Presets</h3>
                    </div>
                    <PresetSelector onSelect={handlePresetSelect} selectedId={selectedPresetId} />
                </div>

                {/* Middle Panel: Participants */}
                <div className="glass-card p-6 space-y-6">
                    <div className="flex items-center space-x-3 text-lg font-semibold">
                        <Users className="w-5 h-5 text-accent" />
                        <h3>{t.config.participants}</h3>
                    </div>

                    <div className="space-y-4">
                        <div className="space-y-2">
                            <div className="flex justify-between items-center text-sm font-medium px-1">
                                <label className="text-text-muted">{t.config.agentCount}</label>
                                <span className="text-primary font-mono">{agentCount}</span>
                            </div>
                            <input
                                type="range"
                                min="3"
                                max="10"
                                value={agentCount}
                                onChange={(e) => {
                                    setAgentCount(parseInt(e.target.value));
                                    setSelectedPresetId(undefined);
                                }}
                                className="w-full accent-primary bg-white/5 h-2 rounded-lg cursor-pointer"
                            />
                        </div>

                        <div className="flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-white/10">
                            <div>
                                <p className="font-medium text-sm">{t.config.balancedTeam}</p>
                                <p className="text-xs text-text-muted">{t.config.balancedDesc}</p>
                            </div>
                            <button
                                onClick={() => setUseBalancedTeam(!useBalancedTeam)}
                                className={`w-12 h-6 rounded-full transition-colors relative ${useBalancedTeam ? 'bg-primary' : 'bg-white/10'}`}
                            >
                                <motion.div 
                                    animate={{ left: useBalancedTeam ? 28 : 4 }}
                                    className="absolute top-1 w-4 h-4 bg-white rounded-full" 
                                />
                            </button>
                        </div>
                    </div>
                </div>

                {/* Right Panel: Words */}
                <div className="glass-card p-6 space-y-6">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3 text-lg font-semibold">
                            <Sparkles className="w-5 h-5 text-secondary" />
                            <h3>{t.config.words}</h3>
                        </div>
                        <button 
                            onClick={generateRandomWords}
                            className="p-2 hover:bg-white/5 rounded-lg text-text-muted transition-colors"
                            title="Randomize"
                        >
                            <Dice5 size={18} />
                        </button>
                    </div>

                    <div className="space-y-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-text-muted px-1">{t.config.civilianWord}</label>
                            <input
                                type="text"
                                value={civilianWord}
                                onChange={(e) => setCivilianWord(e.target.value)}
                                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-secondary/50 transition-all"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-text-muted px-1">{t.config.undercoverWord}</label>
                            <input
                                type="text"
                                value={undercoverWord}
                                onChange={(e) => setUndercoverWord(e.target.value)}
                                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-secondary/50 transition-all"
                            />
                        </div>
                    </div>
                </div>
            </div>

            {error && (
                <div className="max-w-md mx-auto p-4 bg-red-500/10 border border-red-500/20 rounded-2xl flex items-center space-x-3">
                    <ShieldAlert className="w-5 h-5 text-red-500" />
                    <p className="text-sm text-red-500 font-medium">{error}</p>
                </div>
            )}

            <div className="flex justify-center pt-8">
                <motion.button
                    whileHover={{ scale: 1.05, boxShadow: "0 0 40px rgba(99, 102, 241, 0.4)" }}
                    whileTap={{ scale: 0.95 }}
                    onClick={handleCreateGame}
                    disabled={loading}
                    className="bg-primary text-white px-16 py-4 rounded-2xl font-bold text-xl transition-all flex items-center space-x-3 disabled:opacity-50"
                >
                    {loading ? (
                        <div className="w-8 h-8 border-4 border-white/20 border-t-white rounded-full animate-spin" />
                    ) : (
                        <>
                            <Play className="w-6 h-6 fill-current" />
                            <span>{t.config.launch}</span>
                        </>
                    )}
                </motion.button>
            </div>
        </motion.div>
    );
};

export default GameConfiguration;

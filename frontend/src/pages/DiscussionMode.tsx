import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

import { CharacterCard } from '../components/CharacterCard';
import { CharacterModal } from '../components/CharacterModal';
import { FixedBottomBar } from '../components/FixedBottomBar';
import { MessageBubble } from '../components/MessageBubble';
import { useI18n } from '../hooks/useI18n';
import ParticleBackground from '../components/ParticleBackground';
import { buildApiUrl } from '../services/api';
import { useSettingsStore } from '../store/settingsStore';

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

export const DiscussionMode: React.FC = () => {
  const navigate = useNavigate();
  const { modelConfig } = useSettingsStore();
  const { t } = useI18n();
  const [discussionId, setDiscussionId] = useState<string | null>(null);
  const [topic, setTopic] = useState('');
  const [agentCount, setAgentCount] = useState(6);
  const [useCharacters, setUseCharacters] = useState(true);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [characters, setCharacters] = useState<CharacterInfo[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isActive, setIsActive] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isConfiguring, setIsConfiguring] = useState(true);
  const [currentThinkingAgent, setCurrentThinkingAgent] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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

  const handleCreateDiscussion = async () => {
    if (!topic.trim()) {
      alert(t.discussion.topicPlaceholder);
      return;
    }

    try {
      const requestBody: Record<string, unknown> = {
        topic: topic.trim(),
        agent_count: agentCount,
        use_balanced_team: true,
        use_characters: useCharacters,
      };

      if (modelConfig?.api_key) {
        requestBody.model_config = {
          model: modelConfig.model,
          api_key: modelConfig.api_key,
          base_url: modelConfig.base_url,
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
      alert(`${t.discussion.createDiscussion} failed`);
    }
  };

  const handleStartDiscussion = async () => {
    if (!discussionId) return;

    try {
      await postJson('/api/discussion/start', { discussion_id: discussionId });
      setIsActive(true);

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
      alert(`${t.discussion.startDiscussion} failed`);
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

      setTimeout(() => {
        if (isActive) {
          handleResume();
        }
      }, 500);
    } catch (error) {
      console.error('Failed to send message:', error);
      alert('Send message failed');
    }
  };

  const handleInputFocus = async (isFocused: boolean) => {
    if (isFocused && isActive && !isPaused) {
      await handlePause();
    }
  };

  const handleBackToHome = () => {
    eventSourceRef.current?.close();
    navigate('/');
  };

  if (isConfiguring) {
    return (
      <div className="min-h-screen relative flex items-center justify-center p-4">
        <ParticleBackground />
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="glass-card p-8 max-w-xl w-full border border-white/10"
        >
          <div className="text-center mb-10">
            <div className="inline-block p-4 bg-pink-500/20 rounded-3xl mb-6">
              <MessageSquare size={48} className="text-pink-400" />
            </div>
            <h1 className="text-4xl font-black bg-gradient-to-r from-pink-400 to-purple-400 bg-clip-text text-transparent mb-2">
              {t.discussion.title}
            </h1>
            <p className="text-text-muted">{t.discussion.subtitle}</p>
          </div>

          <div className="space-y-8">
            <div className="space-y-3">
              <label className="text-sm font-bold text-text-muted flex items-center gap-2 px-1">
                {t.discussion.topic.toUpperCase()}
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder={t.discussion.topicPlaceholder}
                className="w-full bg-white/5 border border-white/10 rounded-2xl px-5 py-4 focus:outline-none focus:ring-2 focus:ring-pink-500/50 transition-all text-lg"
              />
            </div>

            <div className="space-y-3">
              <label className="text-sm font-bold text-text-muted flex justify-between items-center px-1">
                <span>{t.discussion.participants.toUpperCase()}</span>
                <span className="text-pink-400 font-mono text-xl">{agentCount}</span>
              </label>
              <input
                type="range"
                min="3"
                max="10"
                value={agentCount}
                onChange={(e) => setAgentCount(parseInt(e.target.value, 10))}
                className="w-full h-2 bg-white/5 rounded-lg appearance-none cursor-pointer accent-pink-500"
              />
            </div>

            <div className="bg-white/5 rounded-3xl p-6 border border-white/10">
              <label className="flex items-center justify-between cursor-pointer">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-purple-500/20 rounded-2xl text-purple-400">
                    <Sparkles size={24} />
                  </div>
                  <div>
                    <div className="font-bold">{t.discussion.rolePlaying}</div>
                    <div className="text-xs text-text-muted">{t.discussion.rolePlayingDesc}</div>
                  </div>
                </div>
                <button
                  onClick={() => setUseCharacters(!useCharacters)}
                  className={`w-14 h-7 rounded-full transition-colors relative ${useCharacters ? 'bg-pink-500' : 'bg-white/10'}`}
                >
                  <motion.div
                    animate={{ left: useCharacters ? 32 : 4 }}
                    className="absolute top-1 w-5 h-5 bg-white rounded-full"
                  />
                </button>
              </label>
            </div>

            <div className="flex flex-col gap-4 pt-4">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleCreateDiscussion}
                disabled={!topic.trim()}
                className="w-full bg-pink-500 text-white py-4 rounded-2xl font-bold text-xl shadow-lg hover:bg-pink-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t.discussion.createDiscussion}
              </motion.button>

              <button
                onClick={handleBackToHome}
                className="w-full py-4 text-text-muted hover:text-text font-medium transition-colors"
              >
                {t.discussion.backToHome}
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gradient-to-br from-gray-50 to-blue-50">
      <div className="bg-white border-b shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <div className="p-2 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">{t.discussion.pageTitle}</h1>
              <p className="text-gray-600 text-sm flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                </svg>
                {topic}
              </p>
            </div>
          </div>
          <button
            onClick={handleBackToHome}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 font-medium transition-all flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            {t.discussion.backToHome}
          </button>
        </div>
      </div>

      <div className="bg-white border-b shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-4">
          {characters.length > 0 ? (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
                <span className="text-sm font-semibold text-gray-700">{t.discussion.lineup}</span>
                <span className="text-xs text-gray-500">{t.discussion.lineupDesc}</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {characters.map((charInfo) => (
                  <CharacterCard
                    key={charInfo.agent_id}
                    character={charInfo.character}
                    profession={charInfo.profession}
                    agentName={charInfo.agent_name}
                    onClick={() => {
                      setSelectedCharacterId(charInfo.character.id);
                      setIsModalOpen(true);
                    }}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm font-semibold text-gray-600 flex items-center gap-1">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
                {t.discussion.participantsList}
              </span>
              {agents.map((agent) => (
                <div
                  key={agent.id}
                  className="px-3 py-1.5 bg-gradient-to-r from-purple-100 to-blue-100 text-purple-800 rounded-full text-sm font-medium border border-purple-200 shadow-sm"
                >
                  {agent.name}
                  <span className="ml-1 text-xs opacity-75">({agent.mbti_type})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6 pb-32">
        <div className="max-w-5xl mx-auto">
          {messages.length === 0 && !isActive && (
            <div className="text-center mt-20">
              <div className="inline-block p-4 bg-white rounded-2xl shadow-lg mb-4">
                <svg className="w-16 h-16 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <p className="text-gray-500 text-lg font-medium">{t.discussion.emptyState}</p>
              <p className="text-gray-400 text-sm mt-2">{t.discussion.emptyStateDesc}</p>
            </div>
          )}

          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {currentThinkingAgent && (
            <div className="flex items-center gap-2 text-gray-500 italic my-4 bg-white rounded-lg px-4 py-3 shadow-sm border border-gray-100">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
              </div>
              <span className="font-medium">{currentThinkingAgent}</span>
              <span>{t.discussion.thinking}</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      <FixedBottomBar
        onStart={handleStartDiscussion}
        onPause={handlePause}
        onResume={handleResume}
        onEnd={handleEnd}
        onUserSpeak={handleUserSpeak}
        onInputFocus={handleInputFocus}
        isPaused={isPaused}
        isActive={isActive}
      />

      {selectedCharacterId && (
        <CharacterModal
          characterId={selectedCharacterId}
          profession={characters.find((c) => c.character.id === selectedCharacterId)?.profession}
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setSelectedCharacterId(null);
          }}
        />
      )}
    </div>
  );
};

import React, { useEffect, useState } from 'react';
import { buildApiUrl } from '../services/api';

interface Character {
  id: string;
  name: string;
  mbti_type: string;
  source: string;
  original_era: string;
  description: string;
  background: string;
  signature_events: string[];
  famous_quotes: string[];
  personality_traits: string[];
  speaking_style: string;
  modern_perspective: string;
  avatar_url: string;
}

interface Profession {
  title: string;
  description: string;
}

interface CharacterModalProps {
  characterId: string;
  profession?: Profession;
  isOpen: boolean;
  onClose: () => void;
}

export const CharacterModal: React.FC<CharacterModalProps> = ({
  characterId,
  profession,
  isOpen,
  onClose
}) => {
  const [character, setCharacter] = useState<Character | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && characterId) {
      fetchCharacterDetails();
    }
  }, [isOpen, characterId]);

  const fetchCharacterDetails = async () => {
    setLoading(true);
    try {
      const response = await fetch(buildApiUrl(`/api/characters/${characterId}`));
      if (!response.ok) throw new Error('Failed to fetch character');
      const data = await response.json();
      setCharacter(data);
    } catch (error) {
      console.error('Failed to fetch character details:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 backdrop-blur-sm animate-fadeIn">
      <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden animate-slideUp">
        <div className="relative bg-gradient-to-r from-purple-500 via-blue-500 to-indigo-500 p-6 text-white">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 hover:bg-white hover:bg-opacity-20 rounded-full transition-all"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          {loading ? (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-white border-t-transparent"></div>
              <p className="mt-4">加载中...</p>
            </div>
          ) : character ? (
            <div className="flex items-start gap-6">
              <div className="flex-shrink-0">
                <div className="w-24 h-24 rounded-full bg-white bg-opacity-20 backdrop-blur-sm flex items-center justify-center text-5xl font-bold shadow-xl border-4 border-white border-opacity-30">
                  {character.name.charAt(0)}
                </div>
              </div>

              <div className="flex-1">
                <h2 className="text-3xl font-bold mb-2">{character.name}</h2>
                <div className="flex flex-wrap gap-2 mb-3">
                  <span className="px-3 py-1 bg-white bg-opacity-20 backdrop-blur-sm rounded-full text-sm font-semibold border border-white border-opacity-30">
                    {character.mbti_type}
                  </span>
                  <span className="px-3 py-1 bg-white bg-opacity-20 backdrop-blur-sm rounded-full text-sm border border-white border-opacity-30">
                    {character.original_era}
                  </span>
                </div>
                <p className="text-white text-opacity-90 flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                  {character.source}
                </p>
              </div>
            </div>
          ) : null}
        </div>

        {character && (
          <div className="overflow-y-auto max-h-[calc(90vh-200px)] p-6 space-y-6">
            {profession && (
              <div className="bg-gradient-to-r from-purple-50 to-blue-50 rounded-xl p-5 border-2 border-purple-200">
                <div className="flex items-center gap-2 mb-3">
                  <div className="p-2 bg-purple-500 rounded-lg">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <h3 className="text-xl font-bold text-gray-900">现代职业</h3>
                </div>
                <p className="text-lg font-semibold text-purple-700 mb-2">{profession.title}</p>
                <p className="text-gray-700">{profession.description}</p>
              </div>
            )}

            <div>
              <h3 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
                <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
                背景故事
              </h3>
              <p className="text-gray-700 leading-relaxed">{character.background}</p>
            </div>

            {character.signature_events && character.signature_events.length > 0 && (
              <div>
                <h3 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
                  <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                  </svg>
                  标志性事件
                </h3>
                <div className="flex flex-wrap gap-2">
                  {character.signature_events.map((event, index) => (
                    <span
                      key={index}
                      className="px-3 py-1.5 bg-blue-100 text-blue-800 rounded-lg text-sm font-medium border border-blue-200"
                    >
                      {event}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {character.famous_quotes && character.famous_quotes.length > 0 && (
              <div>
                <h3 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
                  <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                  </svg>
                  名言名句
                </h3>
                <div className="space-y-2">
                  {character.famous_quotes.map((quote, index) => (
                    <div
                      key={index}
                      className="pl-4 border-l-4 border-indigo-300 py-2 italic text-gray-700"
                    >
                      "{quote}"
                    </div>
                  ))}
                </div>
              </div>
            )}

            {character.personality_traits && character.personality_traits.length > 0 && (
              <div>
                <h3 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
                  <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  性格特征
                </h3>
                <div className="flex flex-wrap gap-2">
                  {character.personality_traits.map((trait, index) => (
                    <span
                      key={index}
                      className="px-3 py-1.5 bg-purple-100 text-purple-800 rounded-full text-sm font-medium"
                    >
                      {trait}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div>
              <h3 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
                <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
                说话风格
              </h3>
              <p className="text-gray-700 bg-green-50 rounded-lg p-4 border border-green-200">
                {character.speaking_style}
              </p>
            </div>

            <div>
              <h3 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
                <svg className="w-5 h-5 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                现代视角
              </h3>
              <p className="text-gray-700 bg-orange-50 rounded-lg p-4 border border-orange-200">
                {character.modern_perspective}
              </p>
            </div>
          </div>
        )}

        <div className="border-t p-4 bg-gray-50">
          <button
            onClick={onClose}
            className="w-full bg-gradient-to-r from-purple-500 to-blue-500 text-white py-3 rounded-xl hover:from-purple-600 hover:to-blue-600 transition-all font-semibold shadow-lg hover:shadow-xl"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
};

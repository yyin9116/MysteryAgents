import React from 'react';

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

interface CharacterCardProps {
  character: Character;
  profession?: Profession;
  agentName?: string;
  onClick?: () => void;
}

export const CharacterCard: React.FC<CharacterCardProps> = ({
  character,
  profession,
  onClick
}) => {
  return (
    <div
      onClick={onClick}
      className="group relative bg-white rounded-xl shadow-md hover:shadow-xl transition-all duration-300 overflow-hidden cursor-pointer border-2 border-transparent hover:border-purple-300 transform hover:scale-105"
    >
      {/* 背景装饰 */}
      <div className="absolute inset-0 bg-gradient-to-br from-purple-50 via-blue-50 to-indigo-50 opacity-50"></div>
      
      {/* 内容区域 */}
      <div className="relative p-4">
        {/* 头像区域 */}
        <div className="flex items-start gap-3 mb-3">
          {/* 头像 */}
          <div className="relative flex-shrink-0">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-purple-400 to-blue-500 flex items-center justify-center text-white text-2xl font-bold shadow-lg">
              {character.name.charAt(0)}
            </div>
            {/* MBTI 徽章 */}
            <div className="absolute -bottom-1 -right-1 bg-white rounded-full px-2 py-0.5 text-xs font-bold text-purple-600 shadow-md border-2 border-purple-200">
              {character.mbti_type}
            </div>
          </div>

          {/* 名字和来源 */}
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-bold text-gray-900 truncate group-hover:text-purple-600 transition-colors">
              {character.name}
            </h3>
            <p className="text-xs text-gray-500 truncate flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
              {character.source}
            </p>
          </div>
        </div>

        {/* 职业信息 */}
        {profession && (
          <div className="bg-gradient-to-r from-purple-100 to-blue-100 rounded-lg p-3 border border-purple-200">
            <div className="flex items-center gap-2 mb-1">
              <svg className="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              <span className="text-sm font-bold text-purple-800">{profession.title}</span>
            </div>
            <p className="text-xs text-gray-700 line-clamp-2">
              {profession.description}
            </p>
          </div>
        )}

        {/* 查看详情提示 */}
        <div className="mt-3 flex items-center justify-center gap-1 text-xs text-purple-600 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
          <span>点击查看详情</span>
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </div>

      {/* 装饰性光效 */}
      <div className="absolute top-0 right-0 w-20 h-20 bg-gradient-to-br from-purple-300 to-blue-300 rounded-full blur-3xl opacity-0 group-hover:opacity-20 transition-opacity"></div>
    </div>
  );
};

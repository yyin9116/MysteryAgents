import React from 'react';

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

interface MessageBubbleProps {
  message: Message;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.speaker_type === 'user';
  const isSystem = message.speaker_type === 'system';

  if (isSystem) {
    return (
      <div className="my-6 text-center">
        <div className="inline-block bg-gradient-to-r from-gray-100 to-gray-200 text-gray-700 px-6 py-2 rounded-full text-sm font-medium shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`my-6 flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-3xl ${isUser ? 'ml-12' : 'mr-12'}`}>
        {/* 发言者信息 */}
        <div className={`flex items-center gap-2 mb-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
          <div className={`flex items-center gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
            {/* 头像 */}
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
              isUser 
                ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white' 
                : 'bg-gradient-to-br from-purple-500 to-pink-500 text-white'
            }`}>
              {isUser ? '你' : message.speaker_name.charAt(0)}
            </div>
            
            {/* 名字和时间 */}
            <div className={`flex items-center gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
              <span className="text-sm font-semibold text-gray-800">
                {message.speaker_name}
              </span>
              <span className="text-xs text-gray-400">
                {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
                  hour: '2-digit',
                  minute: '2-digit'
                })}
              </span>
            </div>
          </div>
        </div>

        {/* 消息气泡 */}
        <div
          className={`rounded-2xl p-5 shadow-md transition-all hover:shadow-lg ${
            isUser
              ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white'
              : 'bg-white text-gray-800 border border-gray-100'
          }`}
        >
          {/* 发言内容 */}
          <div className="text-base leading-relaxed whitespace-pre-wrap">{message.content}</div>

          {/* Agent 的额外信息 */}
          {!isUser && (
            <>
              {/* 思考过程 */}
              {message.thought && (
                <details className="mt-4 pt-4 border-t border-gray-100">
                  <summary className="text-sm text-gray-500 cursor-pointer hover:text-purple-600 transition-colors flex items-center gap-2 font-medium">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    查看思考过程
                  </summary>
                  <div className="mt-3 text-sm text-gray-600 italic bg-gray-50 rounded-lg p-3">
                    {message.thought}
                  </div>
                </details>
              )}

              {/* 同意/反对 */}
              {((message.agree_with && message.agree_with.length > 0) ||
                (message.disagree_with && message.disagree_with.length > 0)) && (
                <div className="mt-4 pt-4 border-t border-gray-100 flex flex-wrap gap-3 text-sm">
                  {message.agree_with && message.agree_with.length > 0 && (
                    <div className="flex items-center gap-2 bg-green-50 px-3 py-1.5 rounded-full">
                      <span className="text-green-600 font-medium">👍 同意</span>
                      <span className="text-gray-700">
                        {message.agree_with.join(', ')}
                      </span>
                    </div>
                  )}
                  {message.disagree_with && message.disagree_with.length > 0 && (
                    <div className="flex items-center gap-2 bg-red-50 px-3 py-1.5 rounded-full">
                      <span className="text-red-600 font-medium">👎 反对</span>
                      <span className="text-gray-700">
                        {message.disagree_with.join(', ')}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* 情绪标签 */}
              {message.sentiment && message.sentiment !== 'neutral' && (
                <div className="mt-3">
                  <span
                    className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium ${
                      message.sentiment === 'positive'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    }`}
                  >
                    {message.sentiment === 'positive' ? '😊 积极' : '😟 消极'}
                  </span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

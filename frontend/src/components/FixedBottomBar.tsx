import React, { useState } from 'react';

interface FixedBottomBarProps {
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onEnd: () => void;
  onUserSpeak: (speech: string) => void;
  onInputFocus: (isFocused: boolean) => void; // 新增：输入框焦点变化回调
  isPaused: boolean;
  isActive: boolean;
}

export const FixedBottomBar: React.FC<FixedBottomBarProps> = ({
  onStart,
  onPause,
  onResume,
  onEnd,
  onUserSpeak,
  onInputFocus,
  isPaused,
  isActive
}) => {
  const [userInput, setUserInput] = useState('');

  const handleSend = () => {
    if (userInput.trim()) {
      onUserSpeak(userInput);
      setUserInput('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFocus = () => {
    onInputFocus(true);
  };

  const handleBlur = () => {
    onInputFocus(false);
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-surface/90 backdrop-blur-xl border-t border-line shadow-2xl">
      <div className="max-w-7xl mx-auto p-4">
        {/* 控制按钮 */}
        <div className="flex gap-2 mb-3">
          {!isActive && (
            <button
              onClick={onStart}
              className="px-6 py-2.5 bg-violet text-white rounded-xl hover:brightness-110 transition-all font-semibold shadow-lg hover:shadow-xl flex items-center gap-2 transform hover:scale-105"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              开始讨论
            </button>
          )}
          {isActive && !isPaused && (
            <button
              onClick={onPause}
              className="px-6 py-2.5 bg-gold text-[#171424] rounded-xl hover:brightness-105 transition-all font-semibold shadow-lg hover:shadow-xl flex items-center gap-2 transform hover:scale-105"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              暂停
            </button>
          )}
          {isActive && isPaused && (
            <button
              onClick={onResume}
              className="px-6 py-2.5 bg-violet text-white rounded-xl hover:brightness-110 transition-all font-semibold shadow-lg hover:shadow-xl flex items-center gap-2 transform hover:scale-105"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              继续
            </button>
          )}
          {isActive && (
            <button
              onClick={onEnd}
              className="px-6 py-2.5 border border-danger/60 bg-danger/15 text-danger rounded-xl hover:bg-danger/25 transition-all font-semibold flex items-center gap-2 transform hover:scale-105"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
              </svg>
              结束讨论
            </button>
          )}
        </div>

        {/* 用户输入 */}
        <div className="flex gap-3">
          <textarea
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyPress={handleKeyPress}
            onFocus={handleFocus}
            onBlur={handleBlur}
            placeholder="输入你的观点... (按 Enter 发送，Shift+Enter 换行)"
            className="flex-1 px-4 py-3 border border-line bg-white/[0.04] rounded-xl resize-none focus:ring-2 focus:ring-violet/50 focus:border-violet/50 text-text-primary placeholder:text-text-muted/50 transition-all"
            rows={2}
          />
          <button
            onClick={handleSend}
            disabled={!userInput.trim()}
            className="px-8 py-3 bg-info text-white rounded-xl hover:brightness-110 transition-all disabled:opacity-50 disabled:cursor-not-allowed font-semibold shadow-lg hover:shadow-xl flex items-center gap-2 transform hover:scale-105 disabled:transform-none"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
            发送
          </button>
        </div>
      </div>
    </div>
  );
};

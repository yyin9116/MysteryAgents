import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useGameHistory } from './useGameHistory';

describe('useGameHistory', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('should initialize with empty history', () => {
    const { result } = renderHook(() => useGameHistory());
    expect(result.current.history).toEqual([]);
  });

  it('should save a game record', () => {
    const { result } = renderHook(() => useGameHistory());
    
    act(() => {
      result.current.saveGame({
        type: 'undercover',
        config: { players: 6 },
        status: 'active'
      });
    });

    expect(result.current.history.length).toBe(1);
    expect(result.current.history[0].type).toBe('undercover');
    expect(result.current.history[0].id).toBeDefined();
  });

  it('should limit history to 5 items', () => {
    const { result } = renderHook(() => useGameHistory());
    
    act(() => {
      for (let i = 0; i < 10; i++) {
        result.current.saveGame({
          type: 'undercover',
          config: { i },
          status: 'completed'
        });
      }
    });

    expect(result.current.history.length).toBe(5);
  });

  it('should remove a game record', () => {
    const { result } = renderHook(() => useGameHistory());
    
    act(() => {
      result.current.saveGame({
        type: 'undercover',
        config: {},
        status: 'active'
      });
    });

    const id = result.current.history[0].id;
    
    act(() => {
      result.current.removeGame(id);
    });

    expect(result.current.history).toEqual([]);
  });
});

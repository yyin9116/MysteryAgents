import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import TimelineReplay from './TimelineReplay';

const mockFetchGameReplay = vi.fn();

vi.mock('../../services/werewolfReplayService', () => ({
  fetchGameReplay: (...args: any[]) => mockFetchGameReplay(...args),
  getGameStateAtEvent: vi.fn(() => ({
    round: 3,
    phase: 'game_over',
    alive_agents: ['agent_1', 'agent_3'],
    dead_agents: ['agent_2', 'agent_4'],
    winner: 'good',
    game_over_reason: '所有狼人被淘汰',
    night_actions: [],
    votes: {},
    conversation_history: [],
  })),
  getEventColor: vi.fn(() => '#8b5cf6'),
  getEventIcon: vi.fn(() => '🏆'),
  getEventDisplayName: vi.fn(() => '游戏结束'),
  formatEventData: vi.fn(() => '好人阵营获胜'),
  calculateEventPosition: vi.fn(() => 0),
  findEventIndexFromPosition: vi.fn(() => 0),
}));

describe('TimelineReplay', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders replay summary metadata in header', async () => {
    mockFetchGameReplay.mockResolvedValue({
      game_id: 'replay_001',
      events: [
        {
          event_id: 'event_1',
          timestamp: '2026-03-22T10:00:00',
          event_type: 'game_over',
          round: 3,
          phase: 'game_over',
          data: { winner: 'good', reason: '所有狼人被淘汰' },
          game_state_snapshot: null,
        },
      ],
      total_events: 12,
      player_count: 6,
      alive_count: 2,
      current_round: 3,
      current_phase: 'game_over',
      winner: 'good',
      game_over_reason: '所有狼人被淘汰',
      started_at: '2026-03-22T09:30:00',
    });

    render(<TimelineReplay gameId="replay_001" onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('游戏回放 - replay_001')).toBeTruthy();
    });

    expect(screen.getByText('6 人局')).toBeTruthy();
    expect(screen.getByText('2 人')).toBeTruthy();
    expect(screen.getAllByText('好人阵营').length).toBeGreaterThan(0);
    expect(screen.getByText('查看完整事件详情')).toBeTruthy();
    fireEvent.click(screen.getByText('全部'));
    expect(screen.getAllByText('所有狼人被淘汰').length).toBeGreaterThan(0);
    expect(screen.getByText('夜晚行动')).toBeTruthy();
    expect(screen.getByText('天亮结算')).toBeTruthy();
    expect(screen.getByText('白天发言')).toBeTruthy();
    expect(screen.getByText('放逐投票')).toBeTruthy();
    expect(screen.getByText('结果结算')).toBeTruthy();
  });
});

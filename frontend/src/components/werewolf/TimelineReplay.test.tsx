import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import TimelineReplay from './TimelineReplay';

const mockFetchGameReplay = vi.fn();

vi.mock('../../services/werewolfReplayService', () => ({
  fetchGameReplay: (...args: any[]) => mockFetchGameReplay(...args),
  getGameStateAtEvent: vi.fn(() => ({
    round: 3,
    phase: 'game_over',
    alive_agents: [{ agent_id: 'agent_1', name: '青蒿' }, { agent_id: 'agent_3', name: '夜鸦' }],
    dead_agents: [{ agent_id: 'agent_2', name: '铁壁' }, { agent_id: 'agent_4', name: '白泽' }],
    winner: 'good',
    game_over_reason: '所有狼人被淘汰',
    night_actions: [],
    votes: {},
    conversation_history: [],
  })),
  getEventColor: vi.fn(() => '#8b5cf6'),
  getEventDisplayName: vi.fn(() => '游戏结束'),
  formatEventData: vi.fn(() => '好人阵营获胜'),
  calculateEventPosition: vi.fn(() => 0),
  findEventIndexFromPosition: vi.fn(() => 0),
  downloadWerewolfReplay: vi.fn(),
}));

describe('TimelineReplay（设计稿 3:1069 回放播放器）', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('按设计稿渲染 Header / Timeline / Controls / EventStream / State', async () => {
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
      total_events: 1,
      player_count: 6,
      alive_count: 2,
      current_round: 3,
      current_phase: 'game_over',
      winner: 'good',
      game_over_reason: '所有狼人被淘汰',
      started_at: '2026-03-22T09:30:00',
    });

    render(<TimelineReplay gameId="replay_001" onClose={vi.fn()} />);

    // Header：标题 + 胜方徽标
    await waitFor(() => {
      expect(screen.getByText('回放 · replay_001')).toBeTruthy();
    });
    expect(screen.getByText('好人阵营胜')).toBeTruthy();

    // Timeline 卡：EVENT x/y + 回合刻度
    expect(screen.getByText('EVENT 1 / 1')).toBeTruthy();
    expect(screen.getByText('R3 · 1 事件')).toBeTruthy();

    // Controls：自动播放 / 倍速 / 结束回放
    expect(screen.getByText('自动播放')).toBeTruthy();
    expect(screen.getByText('结束回放')).toBeTruthy();
    expect(screen.getByText('2x')).toBeTruthy();

    // 事件流：当前事件高亮卡
    expect(screen.getByText('1 · 游戏结束')).toBeTruthy();
    expect(screen.getByText('所有狼人被淘汰')).toBeTruthy();

    // 当前局势：席位与存活/出局统计
    expect(screen.getByText('存活 2 · 出局 2')).toBeTruthy();
    expect(screen.getByText('回合跳转 JUMP TO ROUND')).toBeTruthy();
  });

  it('点击下一步/上一步在边界禁用', async () => {
    mockFetchGameReplay.mockResolvedValue({
      game_id: 'replay_002',
      events: [
        {
          event_id: 'event_1',
          timestamp: '2026-03-22T10:00:00',
          event_type: 'game_over',
          round: 1,
          phase: 'game_over',
          data: { winner: 'good', reason: '结束' },
          game_state_snapshot: null,
        },
      ],
      total_events: 1,
      player_count: 6,
      alive_count: 6,
      current_round: 1,
      current_phase: 'game_over',
      winner: 'good',
      game_over_reason: '结束',
      started_at: '2026-03-22T09:30:00',
    });

    render(<TimelineReplay gameId="replay_002" onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('回放 · replay_002')).toBeTruthy();
    });
    const prev = (screen.getAllByText('上一步')[0].closest('button')) as HTMLButtonElement;
    const next = (screen.getAllByText('下一步')[0].closest('button')) as HTMLButtonElement;
    expect(prev.disabled).toBe(true);
    expect(next.disabled).toBe(true);
  });
});

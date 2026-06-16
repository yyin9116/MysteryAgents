import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import WerewolfMode from './WerewolfMode';

const mockCreateGame = vi.fn();
const mockConnectGameStreamWithRetry = vi.fn();
const mockListWerewolfReplays = vi.fn();
const mockDeleteWerewolfReplay = vi.fn();
const mockDeleteFinishedWerewolfReplays = vi.fn();
const mockDownloadWerewolfReplay = vi.fn();

vi.mock('lucide-react', () => ({
  Moon: () => <div data-testid="moon-icon" />,
  Sun: () => <div data-testid="sun-icon" />,
  MessageCircle: () => <div data-testid="message-icon" />,
  Vote: () => <div data-testid="vote-icon" />,
  AlertCircle: () => <div data-testid="alert-icon" />,
  ArrowLeft: () => <div data-testid="arrow-left-icon" />,
  History: () => <div data-testid="history-icon" />,
  Clock: () => <div data-testid="clock-icon" />,
  RefreshCcw: () => <div data-testid="refresh-icon" />,
  Search: () => <div data-testid="search-icon" />,
  Trash2: () => <div data-testid="trash-icon" />,
}));

vi.mock('../components/werewolf/DarkMysticLayout', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('../components/werewolf/WerewolfGameConfig', () => ({
  default: ({ onStart }: { onStart: (config: any) => void }) => (
    <button onClick={() => onStart({ playerCount: 6, model: 'glm-4-flash' })}>
      start-game
    </button>
  ),
}));

vi.mock('../components/werewolf/PossessionControl', () => ({
  default: () => <div>Possession Control</div>,
}));

vi.mock('../components/werewolf/WerewolfCard3D', () => ({
  default: ({ agent }: { agent: { name: string } }) => <div>{agent.name}</div>,
}));

vi.mock('../components/werewolf/WerewolfGameOver', () => ({
  default: ({ onReplay }: { onReplay?: () => void }) => (
    <button onClick={onReplay}>open-replay</button>
  ),
}));

vi.mock('../components/werewolf/TimelineReplay', () => ({
  default: ({ gameId }: { gameId: string }) => <div>Timeline Replay {gameId}</div>,
}));

vi.mock('../services/werewolfService', () => ({
  createGame: (...args: any[]) => mockCreateGame(...args),
  connectGameStreamWithRetry: (...args: any[]) => mockConnectGameStreamWithRetry(...args),
}));

vi.mock('../services/werewolfReplayService', () => ({
  listWerewolfReplays: (...args: any[]) => mockListWerewolfReplays(...args),
  deleteWerewolfReplay: (...args: any[]) => mockDeleteWerewolfReplay(...args),
  deleteFinishedWerewolfReplays: (...args: any[]) => mockDeleteFinishedWerewolfReplays(...args),
  downloadWerewolfReplay: (...args: any[]) => mockDownloadWerewolfReplay(...args),
}));

describe('WerewolfMode', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(Date, 'now').mockReturnValue(new Date('2026-03-22T12:00:00').getTime());
    mockListWerewolfReplays.mockResolvedValue({ replays: [], total: 0, page: 1, page_size: 5 });
    mockDeleteWerewolfReplay.mockResolvedValue(undefined);
    mockDeleteFinishedWerewolfReplays.mockResolvedValue({ deleted_count: 1 });
    mockDownloadWerewolfReplay.mockResolvedValue(undefined);
    window.confirm = vi.fn().mockReturnValue(true);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('opens timeline replay from game over overlay', async () => {
    let eventHandler: ((event: any) => void) | undefined;

    mockCreateGame.mockResolvedValue({
      game_id: 'game_123',
      player_count: 6,
      agents: [
        {
          agent_id: 'agent_1',
          name: 'Agent One',
          mbti_type: 'ENTJ',
          iq_level: 'High',
          is_alive: true,
        },
      ],
      message: 'ok',
    });

    mockConnectGameStreamWithRetry.mockImplementation((_gameId, handler) => {
      eventHandler = handler;
      return vi.fn();
    });

    render(
      <MemoryRouter>
        <WerewolfMode />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByText('start-game'));

    await waitFor(() => {
      expect(mockConnectGameStreamWithRetry).toHaveBeenCalled();
    });

    eventHandler?.({
      type: 'game_over',
      winner: 'good',
      reason: '测试结束',
    });

    expect(await screen.findByText('open-replay', {}, { timeout: 4000 })).toBeTruthy();

    fireEvent.click(screen.getByText('open-replay'));

    expect(screen.getByText('Timeline Replay game_123')).toBeTruthy();
  }, 10000);

  it('opens timeline replay from historical replay list', async () => {
    mockListWerewolfReplays.mockResolvedValue({
      replays: [{
        game_id: 'historic_game',
        total_events: 8,
        player_count: 6,
        alive_count: 2,
        current_round: 3,
        current_phase: 'game_over',
        winner: 'good',
        game_over_reason: '所有狼人被淘汰',
        updated_at: '2026-03-22T10:00:00',
      }],
      total: 1,
      page: 1,
      page_size: 5,
      stats: { total: 1, active: 0, finished: 1 },
    });

    render(
      <MemoryRouter>
        <WerewolfMode />
      </MemoryRouter>
    );

    expect(await screen.findByText('historic_game')).toBeTruthy();
    expect(screen.getByText('6 人局')).toBeTruthy();
    expect(screen.getByText('好人胜')).toBeTruthy();
    expect(screen.getByText('结局：所有狼人被淘汰')).toBeTruthy();
    expect(screen.getByText('2 小时前')).toBeTruthy();
    expect(screen.getByText('当前结果总数')).toBeTruthy();

    fireEvent.click(screen.getByText('historic_game'));

    expect(screen.getByText('Timeline Replay historic_game')).toBeTruthy();
  });

  it('filters and deletes historical replays', async () => {
    mockListWerewolfReplays
      .mockResolvedValueOnce({
        replays: [
          {
            game_id: 'active_game',
            total_events: 4,
            current_round: 2,
            current_phase: 'night',
            updated_at: '2026-03-22T10:00:00',
            is_active: true,
          },
          {
            game_id: 'finished_game',
            total_events: 9,
            current_round: 4,
            current_phase: 'game_over',
            updated_at: '2026-03-22T09:00:00',
            is_active: false,
          },
        ],
        total: 2,
        page: 1,
        page_size: 5,
        stats: { total: 2, active: 1, finished: 1 },
      })
      .mockResolvedValueOnce({
        replays: [
          {
            game_id: 'finished_game',
            total_events: 9,
            current_round: 4,
            current_phase: 'game_over',
            updated_at: '2026-03-22T09:00:00',
            is_active: false,
          },
        ],
        total: 1,
        page: 1,
        page_size: 5,
        stats: { total: 1, active: 0, finished: 1 },
      })
      .mockResolvedValueOnce({
        replays: [
          {
            game_id: 'finished_game',
            total_events: 9,
            current_round: 4,
            current_phase: 'game_over',
            updated_at: '2026-03-22T09:00:00',
            is_active: false,
          },
        ],
        total: 1,
        page: 1,
        page_size: 5,
        stats: { total: 1, active: 0, finished: 1 },
      })
      .mockResolvedValueOnce({
        replays: [
          {
            game_id: 'active_game',
            total_events: 4,
            current_round: 2,
            current_phase: 'night',
            updated_at: '2026-03-22T10:00:00',
            is_active: true,
          },
        ],
        total: 1,
        page: 1,
        page_size: 5,
        stats: { total: 1, active: 1, finished: 0 },
      });

    render(
      <MemoryRouter>
        <WerewolfMode />
      </MemoryRouter>
    );

    expect(await screen.findByText('finished_game')).toBeTruthy();

    fireEvent.click(screen.getAllByText('已结束')[0]);
    expect(screen.getByText('finished_game')).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByText('active_game')).toBeNull();
    });

    fireEvent.change(screen.getByPlaceholderText('搜索 game_id'), {
      target: { value: 'finished' },
    });
    expect(screen.getByText('finished_game')).toBeTruthy();

    const deleteButtons = screen.getAllByTitle(/删除/);
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(mockDeleteWerewolfReplay).toHaveBeenCalledWith('finished_game');
    });
    expect(screen.getByText('已删除回放 finished_game')).toBeTruthy();
  });

  it('exports replay from the history list', async () => {
    mockListWerewolfReplays.mockResolvedValue({
      replays: [{
        game_id: 'historic_game',
        total_events: 8,
        player_count: 6,
        alive_count: 2,
        current_round: 3,
        current_phase: 'game_over',
        winner: 'good',
        game_over_reason: '所有狼人被淘汰',
        updated_at: '2026-03-22T10:00:00',
      }],
      total: 1,
      page: 1,
      page_size: 5,
      stats: { total: 1, active: 0, finished: 1 },
    });

    render(
      <MemoryRouter>
        <WerewolfMode />
      </MemoryRouter>
    );

    expect(await screen.findByText('historic_game')).toBeTruthy();

    fireEvent.click(screen.getByTitle('导出 historic_game'));

    await waitFor(() => {
      expect(mockDownloadWerewolfReplay).toHaveBeenCalledWith('historic_game');
    });
    expect(screen.getByText('已导出回放 historic_game')).toBeTruthy();
  });

  it('paginates historical replays', async () => {
    mockListWerewolfReplays
      .mockResolvedValueOnce({
        replays: Array.from({ length: 5 }, (_, index) => ({
          game_id: `game_${index + 1}`,
          total_events: index + 3,
          player_count: 6,
          alive_count: Math.max(0, 6 - index),
          current_round: index + 1,
          current_phase: 'night',
          updated_at: `2026-03-22T1${index}:00:00`,
          is_active: index < 2,
        })),
        total: 6,
        page: 1,
        page_size: 5,
        stats: { total: 6, active: 2, finished: 4 },
      })
      .mockResolvedValueOnce({
        replays: [
          {
            game_id: 'game_6',
            total_events: 8,
            player_count: 6,
            alive_count: 1,
            current_round: 6,
            current_phase: 'game_over',
            winner: 'werewolf',
            game_over_reason: '狼人数量 >= 好人数量',
            updated_at: '2026-03-22T15:00:00',
            is_active: false,
          },
        ],
        total: 6,
        page: 2,
        page_size: 5,
        stats: { total: 6, active: 2, finished: 4 },
      });

    render(
      <MemoryRouter>
        <WerewolfMode />
      </MemoryRouter>
    );

    expect(await screen.findByText('第 1 / 2 页，共 6 条')).toBeTruthy();
    expect(screen.getByText('game_1')).toBeTruthy();
    expect(screen.queryByText('game_6')).toBeNull();

    fireEvent.click(screen.getByText('下一页'));

    await waitFor(() => {
      expect(screen.getByText('第 2 / 2 页，共 6 条')).toBeTruthy();
    });
    expect(screen.getByText('game_6')).toBeTruthy();
  });

  it('requests replay sorting changes from the backend', async () => {
    mockListWerewolfReplays
      .mockResolvedValueOnce({
        replays: [
          {
            game_id: 'game_recent',
            total_events: 4,
            current_round: 2,
            current_phase: 'night',
            updated_at: '2026-03-22T10:00:00',
          },
        ],
        total: 1,
        page: 1,
        page_size: 5,
        stats: { total: 1, active: 0, finished: 1 },
      })
      .mockResolvedValueOnce({
        replays: [
          {
            game_id: 'game_long',
            total_events: 15,
            current_round: 5,
            current_phase: 'game_over',
            updated_at: '2026-03-21T10:00:00',
          },
        ],
        total: 1,
        page: 1,
        page_size: 5,
        stats: { total: 1, active: 0, finished: 1 },
      });

    render(
      <MemoryRouter>
        <WerewolfMode />
      </MemoryRouter>
    );

    expect(await screen.findByText('game_recent')).toBeTruthy();
    expect(mockListWerewolfReplays).toHaveBeenLastCalledWith({
      page: 1,
      pageSize: 5,
      search: '',
      sortBy: 'updated_at',
      sortOrder: 'desc',
      status: 'all',
    });

    fireEvent.change(screen.getByDisplayValue('最近更新'), {
      target: { value: 'events_desc' },
    });

    await waitFor(() => {
      expect(screen.getByText('game_long')).toBeTruthy();
    });
    expect(mockListWerewolfReplays).toHaveBeenLastCalledWith({
      page: 1,
      pageSize: 5,
      search: '',
      sortBy: 'total_events',
      sortOrder: 'desc',
      status: 'all',
    });
  });

  it('auto refreshes replay history while staying on config screen', async () => {
    vi.useFakeTimers();

    mockListWerewolfReplays.mockResolvedValue({
      replays: [
        {
          game_id: 'active_game',
          total_events: 4,
          current_round: 2,
          current_phase: 'night',
          updated_at: '2026-03-22T10:00:00',
          is_active: true,
        },
      ],
      total: 1,
      page: 1,
      page_size: 5,
      stats: { total: 1, active: 1, finished: 0 },
    });

    render(
      <MemoryRouter>
        <WerewolfMode />
      </MemoryRouter>
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText('active_game')).toBeTruthy();
    expect(mockListWerewolfReplays).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });

    expect(mockListWerewolfReplays).toHaveBeenCalledTimes(2);
  });

  it('bulk deletes finished replays and refreshes the list', async () => {
    mockListWerewolfReplays
      .mockResolvedValueOnce({
        replays: [
          {
            game_id: 'finished_game',
            total_events: 9,
            current_round: 4,
            current_phase: 'game_over',
            updated_at: '2026-03-22T09:00:00',
            is_active: false,
          },
        ],
        total: 1,
        page: 1,
        page_size: 5,
        stats: { total: 1, active: 0, finished: 1 },
      })
      .mockResolvedValueOnce({
        replays: [],
        total: 0,
        page: 1,
        page_size: 5,
        stats: { total: 0, active: 0, finished: 0 },
      });

    render(
      <MemoryRouter>
        <WerewolfMode />
      </MemoryRouter>
    );

    expect(await screen.findByText('finished_game')).toBeTruthy();

    fireEvent.click(screen.getByText('清理已结束'));

    await waitFor(() => {
      expect(mockDeleteFinishedWerewolfReplays).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByText('还没有可回放的历史对局')).toBeTruthy();
    });
    expect(screen.getByText('已清理 1 个已结束回放')).toBeTruthy();
  });
});

import type { Agent } from './agent';

export type GamePhase = "description" | "voting" | "elimination" | "voting_complete";

export interface ConversationEntry {
    round: number;
    agent_id: string;
    type?: "description" | "vote" | "voting" | "elimination";
    content: string;
    thought?: string;
    suspicion?: Record<string, number>;
    user_controlled?: boolean;
}

export interface VoteDetail {
    voter: string;
    voted_for: string;
    confidence: number;
    thought: string;
}

export interface EliminationRecord {
    round: number;
    eliminated_id: string;
    eliminated_word: string;
    eliminated_role: "Civilian" | "Undercover";
    votes: Record<string, string[]>;
    vote_details: VoteDetail[];
}

export interface GameState {
    game_id: string;
    round: number;
    phase: GamePhase;
    agents: Agent[];
    conversation_history: ConversationEntry[];
    elimination_history: EliminationRecord[];
    game_over: boolean;
    result?: "civilians_win" | "undercover_wins";
    message?: string;
}

export interface GameConfig {
    agent_count: number;
    civilian_word: string;
    undercover_word: string;
    max_rounds: number;
    use_balanced_team: boolean;
    agents: Array<{ mbti_type: string; iq_level: string }>;
}

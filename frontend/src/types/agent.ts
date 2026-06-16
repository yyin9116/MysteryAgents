export type MBTIType =
    | "ENTJ" | "INTJ" | "INFP" | "ENFJ"
    | "INTP" | "ESTJ" | "ISFP" | "ENTP"
    | "ISFJ" | "ESFP" | "ESFJ" | "ESTP"
    | "INFJ" | "ENFP" | "ISTJ" | "ISTP";

export type IQLevel = "High" | "Mid" | "Low";

export interface VoteRecord {
    round: number;
    voted_for: string;
    confidence: number;
}

export interface Agent {
    id: string;
    mbti_type: MBTIType;
    iq_level: IQLevel;
    word?: string; // Only visible if possessed
    role?: "Civilian" | "Undercover";
    name?: string; // LLM-generated display name
    is_alive: boolean;
    is_possessed: boolean;
    suspicion_scores: Record<string, number>;
    vote_history: VoteRecord[];
    created_at: string;
}

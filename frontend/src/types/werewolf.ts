export type WerewolfRole = 'werewolf' | 'seer' | 'witch' | 'guard' | 'hunter' | 'villager' | 'unknown';

export interface WerewolfAgent {
  id: string;
  name: string;
  role: WerewolfRole;
  isAlive: boolean;
  mbti?: string;
  iq?: number;
  avatar?: string; // Optional URL for avatar image
}

export interface WerewolfCardProps {
  agent: WerewolfAgent;
  isFlipped: boolean;
  onFlip: () => void;
  className?: string;
}

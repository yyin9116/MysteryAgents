import type { MBTIType } from './agent';

export type Gender = "male" | "female" | "other";

export interface UserProfile {
    user_id: string;
    mbti_type: MBTIType;
    gender: Gender;
    birthday?: string;
    created_at: string;
}

export type IdentityMethod = "birthday" | "manual";

export interface CreateProfileRequest {
    method: IdentityMethod;
    gender: Gender;
    birthday?: string;
    mbti_type?: MBTIType;
}

export type { MBTIType };

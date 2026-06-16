import React, { useState, useEffect } from 'react';
import { User, Calendar, Brain, ArrowRight, ShieldAlert, Check } from 'lucide-react';
import { userService } from '../services/userService';
import { useUserStore } from '../store/userStore';
import type { MBTIType, IdentityMethod, Gender } from '../types/user';
import { useI18n } from '../hooks/useI18n';

const UserIdentitySetup: React.FC = () => {
    const [method, setMethod] = useState<IdentityMethod>('birthday');
    const [birthday, setBirthday] = useState('1990-01-01');
    const [mbtiType, setMbtiType] = useState<MBTIType | ''>('');
    const [mbtiList, setMbtiList] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [gender, setGender] = useState<Gender>('male');
    const setUser = useUserStore((state) => state.setUser);
    const { t } = useI18n();

    useEffect(() => {
        const fetchMBTITypes = async () => {
            try {
                const types = await userService.getMBTITypes();
                setMbtiList(types);
            } catch (err) {
                console.error('Failed to fetch MBTI types:', err);
            }
        };
        fetchMBTITypes();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        try {
            const profile = await userService.createProfile({
                method,
                gender,
                birthday: method === 'birthday' ? birthday : undefined,
                mbti_type: method === 'manual' ? (mbtiType as MBTIType) : undefined,
            });
            if (profile) {
                setUser(profile);
            } else {
                throw new Error('Failed to retrieve profile from server.');
            }
        } catch (err: any) {
            console.error('Failed to create profile:', err);
            setError(err.response?.data?.detail || err.message || 'An unexpected error occurred.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto">
            <div className="glass-dark p-8 rounded-3xl border border-white/10">
                <div className="flex items-center space-x-4 mb-8">
                    <div className="p-3 bg-accent/20 rounded-2xl">
                        <User className="w-6 h-6 text-accent" />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold">{t.identity.title}</h2>
                        <p className="text-text-muted">{t.identity.subtitle}</p>
                    </div>
                </div>

                <form onSubmit={handleSubmit} className="space-y-8">
                    {/* Gender Selection */}
                    <div className="space-y-3">
                        <label className="text-sm font-medium text-text-muted px-1">{t.identity.gender}</label>
                        <div className="grid grid-cols-3 gap-3">
                            {(['male', 'female', 'other'] as Gender[]).map((g) => (
                                <button
                                    key={g}
                                    type="button"
                                    onClick={() => setGender(g)}
                                    className={`py-3 px-2 rounded-xl border transition-all flex items-center justify-center space-x-2 text-sm font-bold ${gender === g
                                        ? 'bg-accent/20 border-accent text-accent'
                                        : 'bg-white/5 border-white/10 text-text-muted hover:bg-white/10'
                                        }`}
                                >
                                    <span className="capitalize">{t.identity[g as keyof typeof t.identity]}</span>
                                    {gender === g && <Check className="w-4 h-4 text-accent" />}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <button
                            type="button"
                            onClick={() => setMethod('birthday')}
                            className={`p-4 rounded-2xl border transition-all flex flex-col items-center space-y-2 ${method === 'birthday'
                                ? 'bg-primary/20 border-primary text-primary'
                                : 'bg-white/5 border-white/10 text-text-muted hover:bg-white/10'
                                }`}
                        >
                            <Calendar className="w-6 h-6" />
                            <span className="font-semibold">{t.identity.methodBirthday}</span>
                        </button>
                        <button
                            type="button"
                            onClick={() => setMethod('manual')}
                            className={`p-4 rounded-2xl border transition-all flex flex-col items-center space-y-2 ${method === 'manual'
                                ? 'bg-primary/20 border-primary text-primary'
                                : 'bg-white/5 border-white/10 text-text-muted hover:bg-white/10'
                                }`}
                        >
                            <Brain className="w-6 h-6" />
                            <span className="font-semibold">{t.identity.methodManual}</span>
                        </button>
                    </div>

                    {method === 'birthday' ? (
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-text-muted px-1">{t.identity.birthDate}</label>
                            <input
                                type="date"
                                value={birthday}
                                onChange={(e) => setBirthday(e.target.value)}
                                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all text-text"
                            />
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-text-muted px-1">{t.identity.mbtiType}</label>
                            <select
                                value={mbtiType}
                                onChange={(e) => setMbtiType(e.target.value as MBTIType)}
                                className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all text-text appearance-none"
                            >
                                <option value="" disabled className="bg-slate-900 text-text">{t.identity.placeholder}</option>
                                {Object.entries(mbtiList).map(([code, label]) => (
                                    <option key={code} value={code} className="bg-slate-900 text-text">
                                        {code} - {label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}

                    {error && (
                        <div className="p-4 bg-secondary/10 border border-secondary/20 rounded-2xl flex items-center space-x-3 animate-in fade-in zoom-in-95">
                            <div className="p-1.5 bg-secondary/20 rounded-lg">
                                <ShieldAlert className="w-4 h-4 text-secondary" />
                            </div>
                            <p className="text-sm text-secondary font-medium">{error}</p>
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading || (method === 'manual' && !mbtiType)}
                        className="w-full group bg-gradient-to-r from-primary to-accent hover:from-primary/90 hover:to-accent/90 text-white font-bold py-4 rounded-2xl shadow-lg shadow-primary/20 transition-all flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? (
                            <div className="w-6 h-6 border-4 border-white/20 border-t-white rounded-full animate-spin" />
                        ) : (
                            <>
                                <span>{t.identity.continue}</span>
                                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                            </>
                        )}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default UserIdentitySetup;

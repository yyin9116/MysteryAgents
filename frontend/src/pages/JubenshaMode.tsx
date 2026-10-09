/**
 * Jubensha (剧本杀) Mode page.
 * 剧本杀模式：选本 → 对局（读本/线索/讨论/投票）→ 复盘揭晓。
 * 支持围观 AI 对局与亲自参与（接管席位发言/投票）。
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle, ArrowLeft, BarChart3, BookOpen, Check, Clock, Eye, Loader2, ScrollText,
  Send, Sparkles, Trash2, Users, Vote as VoteIcon, X, Download,
} from 'lucide-react';

import CommonGameSetup, { type CommonSetupState } from '../components/setup/CommonGameSetup';
import {
  connectJubenshaStream, createJubenshaGame, deleteJubenshaGame,
  evaluateJubenshaGame, exportJubenshaReplay, getScript, improvScript,
  importScript, listScripts,
  submitJubenshaPlayerSpeech, submitJubenshaPlayerVote,
  type CreateJubenshaResponse, type EvaluationReport, type JubenshaEvent,
  type MyScript, type ScriptCharacter, type ScriptPackDetail, type ScriptSummary,
} from '../services/jubenshaService';

type PageState = 'config' | 'playing';

interface FeedItem {
  id: number;
  kind: 'phase' | 'speech' | 'vote' | 'clue' | 'system' | 'reveal' | 'error';
  actor?: string;
  text?: string;
  round?: number;
  clue?: { clue_id: string; title: string; recipients: string[]; recipientNames: string[] };
  reveal?: RevealInfo;
  elapsedMs?: number;
  playerControlled?: boolean;
}

/** 当前正在「思考中」的角色（后端占位事件驱动，真实发言到达后清除） */
interface SpeakingActor {
  name: string;
  message: string;
}

interface RevealInfo {
  winner: string;
  murderer_name?: string | null;
  correct_accusation?: boolean;
  tally?: Record<string, number>;
  case_replay?: string;
  timeline?: Array<{ time: string; event: string }>;
}

const PHASE_STEPS: Array<{ key: string; label: string }> = [
  { key: 'reading', label: '读本' },
  { key: 'clue', label: '线索' },
  { key: 'discussion', label: '讨论' },
  { key: 'vote', label: '投票' },
  { key: 'reveal', label: '复盘' },
];

const DIFFICULTY_LABEL: Record<string, string> = {
  easy: '入门', standard: '标准', hard: '烧脑',
};

const JubenshaMode: React.FC = () => {
  const navigate = useNavigate();

  const [pageState, setPageState] = useState<PageState>('config');
  const [error, setError] = useState('');

  // ---- 剧本选择 ----
  const [scripts, setScripts] = useState<ScriptSummary[]>([]);
  const [scriptsLoading, setScriptsLoading] = useState(false);
  const [selectedScriptId, setSelectedScriptId] = useState<string>('');
  const [scriptDetail, setScriptDetail] = useState<ScriptPackDetail | null>(null);
  const [importing, setImporting] = useState(false);

  // ---- AI 即兴创作 ----
  const [showImprov, setShowImprov] = useState(false);
  const [improvIdea, setImprovIdea] = useState('');
  const [improvCount, setImprovCount] = useState(6);
  const [improvBusy, setImprovBusy] = useState(false);

  // ---- 智能体评估报告 ----
  const [evaluation, setEvaluation] = useState<EvaluationReport | null>(null);
  const [evaluating, setEvaluating] = useState(false);

  // ---- 对局配置 ----
  const [playerMode, setPlayerMode] = useState<'spectate' | 'participate'>('spectate');
  // 执行框架：AgentScope（默认：ReActAgent + 原生压缩 + MsgHub 群聊）| legacy（litellm 直调回退）
  const [runtime, setRuntime] = useState<'legacy' | 'agentscope'>('agentscope');
  const [playerCharId, setPlayerCharId] = useState('');
  const [setup, setSetup] = useState<CommonSetupState | null>(null);
  const [creating, setCreating] = useState(false);
  /** 开局进入对局的过渡态：create 完成 → 首个 game_start 事件到达 */
  const [entering, setEntering] = useState(false);

  // ---- 对局运行 ----
  const [gameId, setGameId] = useState('');
  const [gameTitle, setGameTitle] = useState('');
  const [phase, setPhase] = useState('lobby');
  const [round, setRound] = useState(0);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [characters, setCharacters] = useState<Array<{ char_id: string; name: string; model_label?: string | null }>>([]);
  const [myScript, setMyScript] = useState<MyScript | null>(null);
  const [reveal, setReveal] = useState<RevealInfo | null>(null);
  const [playerInput, setPlayerInput] = useState<{ agentId: string; agentName: string; phase: string; message: string; timeout: number } | null>(null);
  const [inputDraft, setInputDraft] = useState('');
  const [voteTarget, setVoteTarget] = useState('');
  const [submitting, setSubmitting] = useState(false);
  /** 正在思考/投票中的角色（打字指示器） */
  const [speakingActor, setSpeakingActor] = useState<SpeakingActor | null>(null);

  const cleanupRef = useRef<(() => void) | null>(null);
  const feedIdRef = useRef(0);
  const lastSeqRef = useRef(0);
  const feedEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    return () => {
      cleanupRef.current?.();
    };
  }, []);

  useEffect(() => {
    if (pageState === 'config' && scripts.length === 0 && !scriptsLoading) {
      loadScripts();
    }
  }, [pageState]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [feed, speakingActor]);

  const loadScripts = async () => {
    setScriptsLoading(true);
    try {
      const items = await listScripts();
      setScripts(items);
    } catch (err: any) {
      setError(err.message || '获取剧本列表失败');
    } finally {
      setScriptsLoading(false);
    }
  };

  const selectScript = async (scriptId: string) => {
    setSelectedScriptId(scriptId);
    setScriptDetail(null);
    setPlayerCharId('');
    try {
      const detail = await getScript(scriptId);
      setScriptDetail(detail);
    } catch (err: any) {
      setError(err.message || '获取剧本详情失败');
    }
  };

  const handleImportFile = async (file: File) => {
    setImporting(true);
    setError('');
    try {
      const text = await file.text();
      const pack = JSON.parse(text);
      await importScript(pack, true);
      await loadScripts();
      await selectScript(pack.script_id);
    } catch (err: any) {
      setError(err.message || '导入剧本失败');
    } finally {
      setImporting(false);
    }
  };

  const handleImprov = async () => {
    if (!improvIdea.trim()) {
      setError('请先描述你的天马行空设定');
      return;
    }
    setImprovBusy(true);
    setError('');
    try {
      const selectedModel = setup?.selectedModel;
      const result = await improvScript(
        improvIdea.trim(),
        improvCount,
        selectedModel
          ? {
              provider: selectedModel.provider,
              model: setup?.globalModel || selectedModel.model,
              api_key: selectedModel.api_key,
              base_url: selectedModel.base_url,
            }
          : null,
      );
      setShowImprov(false);
      setImprovIdea('');
      await loadScripts();
      await selectScript(result.script.script_id);
    } catch (err: any) {
      setError(err.message || 'AI 创作失败');
    } finally {
      setImprovBusy(false);
    }
  };

  const handleEvaluate = async () => {
    if (!gameId) return;
    setEvaluating(true);
    setError('');
    try {
      const report = await evaluateJubenshaGame(gameId);
      setEvaluation(report);
    } catch (err: any) {
      setError(err.message || '生成评估报告失败');
    } finally {
      setEvaluating(false);
    }
  };

  // ---- 事件处理 ----
  const pushFeed = useCallback((item: Omit<FeedItem, 'id'>) => {
    feedIdRef.current += 1;
    setFeed((prev) => [...prev, { ...item, id: feedIdRef.current }]);
  }, []);

  const handleGameEvent = useCallback((event: JubenshaEvent & { seq?: number }) => {
    if (typeof event.seq === 'number') {
      if (event.seq <= lastSeqRef.current) return;
      lastSeqRef.current = event.seq;
    }
    switch (event.type) {
      case 'game_start':
        setGameId(event.game_id);
        setGameTitle(event.title);
        setEntering(false);
        break;
      case 'phase_change':
        setPhase(event.phase);
        if (typeof event.round === 'number') setRound(event.round);
        setSpeakingActor(null);
        pushFeed({ kind: 'phase', text: event.message });
        break;
      case 'agent_speaking':
        if (event.speech) {
          // 真实发言：清除思考指示器并进 feed
          setSpeakingActor(null);
          pushFeed({
            kind: 'speech',
            actor: event.agent_name,
            text: event.speech,
            round: event.round,
            elapsedMs: event.elapsed_ms,
            playerControlled: event.player_controlled,
          });
        } else {
          // 占位事件 → 打字指示器
          setSpeakingActor({ name: event.agent_name, message: event.message || '正在思考…' });
        }
        break;
      case 'clue_granted': {
        setSpeakingActor(null);
        const grants: any[] = event.grants || [];
        for (const g of grants) {
          pushFeed({
            kind: 'clue',
            clue: {
              clue_id: g.clue_id,
              title: g.title || '线索',
              recipients: g.recipients || [],
              recipientNames: g.recipient_names || [],
            },
            round: event.round,
          });
        }
        break;
      }
      case 'agent_voting':
        if (event.voted_for_name) {
          setSpeakingActor(null);
          pushFeed({
            kind: 'vote',
            actor: event.agent_name,
            text: `指认了 ${event.voted_for_name}`,
            playerControlled: event.player_controlled,
            elapsedMs: event.elapsed_ms,
          });
        } else {
          setSpeakingActor({ name: event.agent_name, message: event.message || '正在考虑指认对象…' });
        }
        break;
      case 'turn_error':
        setSpeakingActor(null);
        pushFeed({ kind: 'error', text: event.message || '模型调用异常，已使用兜底发言继续' });
        break;
      case 'player_input_required':
        setSpeakingActor(null);
        setPlayerInput({
          agentId: event.agent_id,
          agentName: event.agent_name,
          phase: event.phase,
          message: event.message,
          timeout: event.timeout_seconds || 240,
        });
        setInputDraft('');
        setVoteTarget('');
        break;
      case 'reveal':
        setReveal({
          winner: event.winner,
          murderer_name: event.murderer_name,
          correct_accusation: event.correct_accusation,
          tally: event.tally,
          case_replay: event.case_replay,
          timeline: event.timeline,
        });
        break;
      case 'game_over':
        setPhase('reveal');
        setSpeakingActor(null);
        setEntering(false);
        pushFeed({ kind: 'reveal', reveal: {
          winner: event.winner,
          murderer_name: event.murderer_name,
          correct_accusation: event.correct_accusation,
          tally: event.tally,
          case_replay: event.case_replay,
          timeline: event.timeline,
        } });
        setPlayerInput(null);
        break;
      case 'error':
        setSpeakingActor(null);
        setEntering(false);
        setError(event.message || '发生错误');
        pushFeed({ kind: 'error', text: event.message || '发生错误' });
        break;
    }
  }, [pushFeed]);

  const startGame = async () => {
    const selectedModel = setup?.selectedModel;
    if (!selectedScriptId) {
      setError('请先选择一个剧本');
      return;
    }
    if (!selectedModel) {
      setError('请先在「模型配置」中选择凭据配置与具体模型');
      return;
    }
    setCreating(true);
    setEntering(true);
    setError('');
    try {
      cleanupRef.current?.();
      lastSeqRef.current = 0;
      setFeed([]);
      setReveal(null);
      setMyScript(null);
      setPlayerInput(null);
      setSpeakingActor(null);
      setEvaluation(null);

      const resp: CreateJubenshaResponse = await createJubenshaGame({
        scriptId: selectedScriptId,
        model: setup?.globalModel || selectedModel.model,
        apiKey: selectedModel.api_key ?? undefined,
        baseUrl: selectedModel.base_url ?? undefined,
        provider: selectedModel.provider,
        chatStyle: setup?.chatStyle,
        runtime,
        autoAssign: setup?.autoAssign ?? undefined,
        playerMode,
        playerCharId: playerMode === 'participate' ? playerCharId : undefined,
      });

      setGameId(resp.game_id);
      setGameTitle(resp.title);
      setPhase(resp.phase);
      setCharacters(resp.characters || []);
      setMyScript(resp.my_script || null);
      setPageState('playing');

      if (resp.my_script) {
        pushFeed({
          kind: 'system',
          text: `你的角色：${resp.my_script.name} — ${resp.my_script.public_profile}`,
        });
      }
      cleanupRef.current = connectJubenshaStream(resp.game_id, handleGameEvent);
    } catch (err: any) {
      setError(err.message || '创建对局失败');
      setEntering(false);
    } finally {
      setCreating(false);
    }
  };

  const terminateGame = async () => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    if (gameId) {
      try {
        await deleteJubenshaGame(gameId);
      } catch {
        // 尽力而为
      }
    }
    setPageState('config');
    setFeed([]);
    setReveal(null);
    setMyScript(null);
    setGameId('');
    setEvaluation(null);
    lastSeqRef.current = 0;
  };

  const submitPlayerInput = async () => {
    if (!playerInput || !gameId) return;
    setSubmitting(true);
    setError('');
    try {
      if (playerInput.phase === 'vote') {
        if (!voteTarget) {
          setError('请选择指认对象');
          return;
        }
        await submitJubenshaPlayerVote(gameId, playerInput.agentId, voteTarget);
        pushFeed({ kind: 'vote', actor: playerInput.agentName, text: '（你的指认已提交）', playerControlled: true });
      } else {
        const content = inputDraft.trim();
        if (!content) {
          setError('发言内容不能为空');
          return;
        }
        await submitJubenshaPlayerSpeech(gameId, playerInput.agentId, content);
      }
      setPlayerInput(null);
      setInputDraft('');
    } catch (err: any) {
      setError(err.message || '提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  const phaseStepIndex = PHASE_STEPS.findIndex((s) => s.key === phase);

  // ==================================================================== //
  // Config 页
  // ==================================================================== //
  if (pageState === 'config') {
    return (
      <div className="min-h-screen bg-background text-text">
        <header className="flex items-center justify-between px-6 py-4 sm:px-10">
          <div className="flex items-center gap-3">
            <button
              type="button" onClick={() => navigate('/')}
              className="rounded-xl border border-white/10 bg-white/[0.04] p-2.5 text-text-secondary/70 transition-colors hover:border-white/20 hover:text-text"
              aria-label="返回首页"
            >
              <ArrowLeft size={16} />
            </button>
            <ScrollText className="h-5 w-5 text-violet" aria-hidden="true" />
            <span className="font-hud text-[13px] tracking-[0.18em] text-violet">剧本杀 · SCRIPT MODE</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button" onClick={() => setShowImprov((v) => !v)}
              className="rounded-xl border border-violet/40 bg-violet/10 px-4 py-2.5 text-xs text-violet transition-colors hover:border-violet hover:bg-violet/20"
            >
              <Sparkles size={14} className="mr-1.5 inline" /> AI 即兴创作
            </button>
            <label className="cursor-pointer rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-xs text-text-secondary transition-colors hover:border-white/20 hover:text-text">
              {importing ? <Loader2 size={14} className="mr-1.5 inline animate-spin" /> : <BookOpen size={14} className="mr-1.5 inline" />}
              导入剧本 JSON
              <input
                type="file" accept=".json" className="hidden" disabled={importing}
                onChange={(e) => e.target.files?.[0] && handleImportFile(e.target.files[0])}
              />
            </label>
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-6 pb-16">
          {error && (
            <div className="mb-5 flex items-center gap-2 rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
              <AlertCircle size={16} /> {error}
              <button type="button" onClick={() => setError('')} className="ml-auto"><X size={14} /></button>
            </div>
          )}

          {showImprov && (
            <div className="mb-6 rounded-[18px] border border-violet/30 bg-violet/[0.06] p-5">
              <h3 className="flex items-center gap-2 text-sm font-bold text-violet">
                <Sparkles size={15} /> AI 即兴剧本演绎
              </h3>
              <p className="mt-1.5 text-xs text-text-secondary/80">
                描述任何天马行空的设定——AI 将自动生成完整剧本（角色/私密剧本/任务/线索/真相），校验通过后可直接开局。
                例：「蒸汽朋克飞艇上的生日宴会，机械师离奇失踪」。
              </p>
              <textarea
                value={improvIdea}
                onChange={(e) => setImprovIdea(e.target.value)}
                rows={3}
                maxLength={600}
                placeholder="你的设定……"
                className="mt-3 w-full resize-none rounded-xl border border-white/10 bg-white/[0.04] px-3.5 py-2.5 text-sm text-text-primary placeholder:text-text-secondary/40 focus:border-violet focus:outline-none"
              />
              <div className="mt-3 flex items-center justify-between">
                <label className="flex items-center gap-2 text-xs text-text-secondary">
                  人数
                  <select
                    value={improvCount}
                    onChange={(e) => setImprovCount(Number(e.target.value))}
                    className="rounded-lg border border-white/10 bg-white/[0.04] px-2 py-1.5 text-text-primary focus:border-violet focus:outline-none"
                  >
                    {[4, 5, 6, 7, 8].map((n) => (
                      <option key={n} value={n}>{n} 人</option>
                    ))}
                  </select>
                </label>
                <button
                  type="button" onClick={handleImprov} disabled={improvBusy || !improvIdea.trim()}
                  className="rounded-xl bg-violet px-6 py-2.5 text-xs font-medium text-white transition-all hover:shadow-[0_0_20px_rgba(139,92,246,0.4)] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {improvBusy ? <Loader2 size={13} className="mr-1.5 inline animate-spin" /> : <Sparkles size={13} className="mr-1.5 inline" />}
                  {improvBusy ? '创作中（约 1-2 分钟）…' : '生成剧本'}
                </button>
              </div>
            </div>
          )}

          {/* 剧本列表 */}
          <p className="mb-3.5 font-hud text-[11px] tracking-[0.2em] text-text-secondary/50">选择剧本</p>
          {scriptsLoading ? (
            <div className="flex items-center gap-2 py-10 text-text-secondary"><Loader2 className="animate-spin" size={18} /> 加载中...</div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {scripts.map((s) => (
                <button
                  key={s.script_id} type="button" onClick={() => selectScript(s.script_id)}
                  className={`rounded-[16px] border p-5 text-left transition-all ${
                    selectedScriptId === s.script_id
                      ? 'border-violet bg-violet/10 shadow-[0_0_24px_rgba(139,92,246,0.15)]'
                      : 'border-white/10 bg-surface hover:border-violet/40'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <h3 className="text-lg font-bold text-text-primary">{s.title}</h3>
                    {s.builtin && <span className="rounded-md bg-gold/15 px-1.5 py-0.5 text-[10px] text-gold">内置</span>}
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-text-secondary">
                    <span className="inline-flex items-center gap-1"><Users size={12} /> {s.player_count} 人</span>
                    <span className="inline-flex items-center gap-1"><Clock size={12} /> 约 {s.estimated_minutes} 分钟</span>
                    <span>{DIFFICULTY_LABEL[s.difficulty] || s.difficulty}</span>
                  </div>
                  {s.tags.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {s.tags.map((t) => (
                        <span key={t} className="rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-text-secondary/80">{t}</span>
                      ))}
                    </div>
                  )}
                </button>
              ))}
              {scripts.length === 0 && (
                <div className="col-span-full rounded-[14px] border border-dashed border-white/10 px-4 py-10 text-center text-sm text-text-secondary/60">
                  暂无剧本，点击右上角「导入剧本 JSON」添加
                </div>
              )}
            </div>
          )}

          {/* 剧本详情 */}
          {scriptDetail && (
            <div className="mt-8 rounded-[18px] border border-white/10 bg-surface p-6">
              <h3 className="text-base font-bold text-text-primary">《{scriptDetail.meta.title}》角色一览</h3>
              <p className="mt-1 text-xs text-text-secondary/70">
                私密剧本与线索将在对局中按角色隔离发放；以下仅展示公开身份。
              </p>
              <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {scriptDetail.characters.map((c: ScriptCharacter) => (
                  <div key={c.char_id} className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-4">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-text-primary">{c.name}</span>
                      {c.age != null && <span className="text-[10px] text-text-secondary/50">{c.age} 岁</span>}
                    </div>
                    <p className="mt-1.5 text-xs leading-5 text-text-secondary/80">{c.public_profile}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 对局设置 */}
          <div className="mt-8 rounded-[18px] border border-white/10 bg-surface p-6">
            <h3 className="flex items-center gap-2 text-base font-bold text-text-primary"><Eye size={16} /> 参与方式</h3>
            <div className="mt-4 grid grid-cols-2 gap-3">
              {([
                { key: 'spectate', label: '围观 AI 对局', desc: '观看智能体们演完全局' },
                { key: 'participate', label: '亲自参与', desc: '接管一个角色发言与指认' },
              ] as const).map((opt) => (
                <button
                  key={opt.key} type="button" onClick={() => setPlayerMode(opt.key)}
                  className={`rounded-xl border p-3.5 text-left transition-colors ${
                    playerMode === opt.key ? 'border-violet bg-violet/10' : 'border-white/10 hover:border-white/25'
                  }`}
                >
                  <span className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
                    {playerMode === opt.key && <Check size={14} className="text-violet" />} {opt.label}
                  </span>
                  <span className="mt-1 block text-[11px] text-text-secondary/70">{opt.desc}</span>
                </button>
              ))}
            </div>
            {playerMode === 'participate' && scriptDetail && (
              <div className="mt-4">
                <label className="mb-1.5 block text-xs text-text-secondary">选择你的角色</label>
                <select
                  value={playerCharId} onChange={(e) => setPlayerCharId(e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-sm text-text-primary focus:border-violet focus:outline-none"
                >
                  <option value="">— 请选择 —</option>
                  {scriptDetail.characters.map((c) => (
                    <option key={c.char_id} value={c.char_id}>{c.name}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* 模型与讨论风格：与其他模式共享的选择（直接选具体模型）；剧本杀角色由剧本决定，隐藏角色阵容 */}
          <div className="mt-5 rounded-[18px] border border-white/10 bg-surface p-panel">
            <CommonGameSetup
              playerCount={scriptDetail?.characters.length || 5}
              onPlayerCountChange={() => {}}
              showPlayerStepper={false}
              showChatStyle
              showRoster={false}
              showPerAgentAssign={false}
              autoAssignTierText="按角色阵营分档自动挑选模型：凶手用最强推理，关键配角次之，普通角色用轻量模型。"
              onChange={setSetup}
            />
            <div className="mt-4 rounded-card bg-white/[0.04] p-card">
              <p className="mb-2.5 flex items-center gap-2 text-xs text-text-secondary">
                <Sparkles size={13} className="text-violet" />
                执行框架
              </p>
              <div className="grid grid-cols-2 gap-3">
                {([
                  { key: 'agentscope', label: 'AgentScope（默认）', desc: '常驻智能体 + MsgHub 群聊 + 原生上下文压缩' },
                  { key: 'legacy', label: '标准回退', desc: 'litellm 直调，滑动窗口 + 记忆衰减' },
                ] as const).map((opt) => (
                  <button
                    key={opt.key} type="button" onClick={() => setRuntime(opt.key)}
                    className={`rounded-xl border p-3 text-left transition-colors ${
                      runtime === opt.key ? 'border-violet bg-violet/10' : 'border-white/10 hover:border-white/25'
                    }`}
                  >
                    <span className="flex items-center gap-1.5 text-[13px] font-medium text-text-primary">
                      {runtime === opt.key && <Check size={13} className="text-violet" />} {opt.label}
                    </span>
                    <span className="mt-1 block text-[11px] leading-relaxed text-text-secondary/70">{opt.desc}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* 开始 */}
          <div className="mt-8 flex justify-center">
            <button
              type="button" onClick={startGame} disabled={creating || !selectedScriptId || !setup?.selectedModel}
              className="rounded-xl bg-violet px-10 py-3.5 text-base font-medium text-white shadow-[0_0_28px_rgba(139,92,246,0.35)] transition-all hover:shadow-[0_0_40px_rgba(139,92,246,0.5)] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {creating ? <Loader2 size={16} className="mr-2 inline animate-spin" /> : null}
              开局
            </button>
          </div>
        </main>
      </div>
    );
  }

  // ==================================================================== //
  // Playing 页
  // ==================================================================== //
  return (
    <div className="flex min-h-screen flex-col bg-background text-text">
      <header className="flex items-center justify-between border-b border-white/[0.08] px-6 py-3.5">
        <div className="flex items-center gap-3">
          <button
            type="button" onClick={terminateGame}
            className="rounded-xl border border-white/10 bg-white/[0.04] p-2.5 text-text-secondary/70 transition-colors hover:border-danger/50 hover:text-danger"
            aria-label="返回"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <h1 className="text-sm font-bold text-text-primary">《{gameTitle}》</h1>
            <p className="font-hud text-[10px] tracking-wider text-text-secondary/50">{gameId}</p>
          </div>
        </div>
        <button
          type="button" onClick={terminateGame}
          className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-2 text-xs text-danger transition-colors hover:bg-danger/20"
        >
          <Trash2 size={13} className="mr-1.5 inline" /> 终止对局
        </button>
      </header>

      {/* 阶段进度 */}
      <div className="flex items-center justify-center gap-1.5 border-b border-white/[0.08] px-6 py-3">
        {PHASE_STEPS.map((s, i) => (
          <React.Fragment key={s.key}>
            <span
              className={`rounded-full px-3 py-1 text-[11px] font-medium transition-colors ${
                i === phaseStepIndex
                  ? 'bg-violet/20 text-violet'
                  : i < phaseStepIndex || phase === 'reveal'
                    ? 'text-success/70'
                    : 'text-text-secondary/40'
              }`}
            >
              {s.label}
              {s.key === 'discussion' && i === phaseStepIndex && round > 0 ? ` · R${round}` : ''}
            </span>
            {i < PHASE_STEPS.length - 1 && <span className="h-px w-6 bg-white/10" aria-hidden="true" />}
          </React.Fragment>
        ))}
      </div>

      {error && (
        <div className="mx-6 mt-3 flex items-center gap-2 rounded-xl border border-danger/40 bg-danger/10 px-4 py-2.5 text-xs text-danger">
          <AlertCircle size={14} /> {error}
          <button type="button" onClick={() => setError('')} className="ml-auto"><X size={13} /></button>
        </div>
      )}

      {/* 进入对局的加载覆盖层：从开局点击持续到首个 game_start 事件 */}
      {entering && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-3xl border border-white/10 bg-[#14121f]/95 p-8 shadow-2xl">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-violet" />
            <h3 className="mt-4 text-center text-base font-bold text-text-primary">
              正在进入《{gameTitle || '剧本杀'}》
            </h3>
            <ul className="mt-5 space-y-2.5 text-xs text-text-secondary">
              <li className="flex items-center gap-2">
                <Check size={13} className="text-success" /> 对局已创建，角色剧本已分发
              </li>
              <li className="flex items-center gap-2">
                <Check size={13} className="text-success" /> 实时事件流已连接
              </li>
              <li className="flex items-center gap-2">
                <Loader2 size={13} className="animate-spin text-violet" />
                等待第一轮读本发言（首次模型调用可能需要十余秒）…
              </li>
            </ul>
          </div>
        </div>
      )}

      <div className="grid flex-1 gap-4 p-4 lg:grid-cols-[1fr_280px]">
        {/* 消息流 */}
        <div className="flex flex-col rounded-[16px] border border-white/[0.08] bg-surface">
          <div className="flex-1 space-y-2.5 overflow-y-auto p-4" style={{ maxHeight: 'calc(100vh - 260px)' }}>
            {feed.map((item) => {
              if (item.kind === 'phase') {
                return (
                  <div key={item.id} className="flex items-center gap-3 py-1.5">
                    <span className="h-px flex-1 bg-white/10" />
                    <span className="font-hud text-[10px] tracking-[0.18em] text-violet/80">{item.text}</span>
                    <span className="h-px flex-1 bg-white/10" />
                  </div>
                );
              }
              if (item.kind === 'clue' && item.clue) {
                const mine = myScript && item.clue.recipients.includes(myScript.char_id);
                return (
                  <div key={item.id} className={`rounded-xl border px-4 py-3 ${mine ? 'border-gold/40 bg-gold/[0.07]' : 'border-white/10 bg-white/[0.03]'}`}>
                    <p className="flex items-center gap-1.5 text-[11px] font-medium text-gold">
                      <ScrollText size={12} /> 线索 · {item.clue.title}
                    </p>
                    <p className="mt-1 text-xs text-text-secondary/80">
                      {mine ? '你获得了这条线索（内容已进入你的上下文）' : `获得线索：${item.clue.recipientNames.join('、') || '全员'}`}
                    </p>
                  </div>
                );
              }
              if (item.kind === 'vote') {
                return (
                  <div key={item.id} className="flex items-center gap-2 pl-2 text-xs text-text-secondary">
                    <VoteIcon size={13} className="text-danger/70" />
                    <span className="font-medium text-text-primary">{item.actor}</span>
                    <span>{item.text}</span>
                    {item.elapsedMs != null && item.elapsedMs > 0 && (
                      <span className="font-hud text-[9px] text-text-secondary/40">{(item.elapsedMs / 1000).toFixed(1)}s</span>
                    )}
                    {item.playerControlled && <span className="rounded bg-violet/15 px-1 text-[9px] text-violet">玩家</span>}
                  </div>
                );
              }
              if (item.kind === 'system') {
                return (
                  <div key={item.id} className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-xs text-text-secondary">
                    {item.text}
                  </div>
                );
              }
              if (item.kind === 'error') {
                return (
                  <div key={item.id} className="flex items-start gap-2 rounded-xl border border-warning/40 bg-warning/10 px-4 py-2.5 text-xs text-warning">
                    <AlertCircle size={13} className="mt-0.5 shrink-0" /> <span>{item.text}</span>
                  </div>
                );
              }
              if (item.kind === 'reveal' && item.reveal) {
                return <RevealCard key={item.id} reveal={item.reveal} />;
              }
              // speech
              return (
                <div key={item.id} className="rounded-xl bg-white/[0.05] px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-semibold text-text-primary">{item.actor}</span>
                    {item.playerControlled && <span className="rounded bg-violet/15 px-1.5 py-0.5 text-[9px] text-violet">玩家代打</span>}
                    {item.elapsedMs != null && item.elapsedMs > 0 && (
                      <span className="font-hud text-[9px] text-text-secondary/40">{(item.elapsedMs / 1000).toFixed(1)}s</span>
                    )}
                  </div>
                  <p className="mt-1.5 whitespace-pre-wrap text-[13px] leading-[22px] text-text-secondary">{item.text}</p>
                </div>
              );
            })}
            {/* 打字指示器：当前角色的模型调用进行中 */}
            {speakingActor && !playerInput && (
              <div className="rounded-xl border border-violet/25 bg-violet/[0.06] px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-semibold text-text-primary">{speakingActor.name}</span>
                  <span className="text-[11px] text-text-secondary/60">{speakingActor.message}</span>
                </div>
                <div className="mt-1.5 flex items-center gap-1">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="h-1.5 w-1.5 animate-bounce rounded-full bg-violet/70"
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </div>
              </div>
            )}
            <div ref={feedEndRef} />
          </div>

          {/* 玩家输入面板 */}
          {playerInput && phase !== 'reveal' && (
            <div className="border-t border-white/10 bg-violet/[0.06] p-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="flex items-center gap-1.5 text-xs font-medium text-violet">
                  <Send size={12} /> {playerInput.message}
                </p>
                <span className="font-hud text-[10px] text-text-secondary/50">超时 {playerInput.timeout}s 后 AI 代打</span>
              </div>
              {playerInput.phase === 'vote' ? (
                <div className="flex flex-wrap items-center gap-2">
                  {characters.filter((c) => c.char_id !== playerInput.agentId).map((c) => (
                    <button
                      key={c.char_id} type="button" onClick={() => setVoteTarget(c.char_id)}
                      className={`rounded-lg border px-3 py-1.5 text-xs transition-colors ${
                        voteTarget === c.char_id ? 'border-violet bg-violet/15 text-violet' : 'border-white/15 text-text-secondary hover:border-white/30'
                      }`}
                    >
                      {c.name}
                    </button>
                  ))}
                  <button
                    type="button" onClick={submitPlayerInput} disabled={submitting || !voteTarget}
                    className="ml-auto rounded-lg bg-violet px-4 py-1.5 text-xs text-white disabled:opacity-40"
                  >
                    指认
                  </button>
                </div>
              ) : (
                <div className="flex items-end gap-2">
                  <textarea
                    value={inputDraft} onChange={(e) => setInputDraft(e.target.value)}
                    rows={2} maxLength={500}
                    placeholder={`以「${playerInput.agentName}」的身份发言...`}
                    className="flex-1 resize-none rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary/40 focus:border-violet focus:outline-none"
                  />
                  <button
                    type="button" onClick={submitPlayerInput} disabled={submitting || !inputDraft.trim()}
                    className="rounded-xl bg-violet px-4 py-2.5 text-sm text-white disabled:opacity-40"
                  >
                    {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 侧栏：角色 + 我的剧本 */}
        <aside className="space-y-4">
          {myScript && (
            <div className="rounded-[16px] border border-gold/30 bg-gold/[0.06] p-4">
              <p className="font-hud text-[10px] tracking-wider text-gold">我的角色</p>
              <h3 className="mt-1 text-base font-bold text-text-primary">{myScript.name}</h3>
              <p className="mt-1.5 text-[11px] leading-5 text-text-secondary/80">{myScript.public_profile}</p>
              {myScript.script && (
                <details className="mt-2.5">
                  <summary className="cursor-pointer text-[11px] text-gold/80">查看我的私密剧本</summary>
                  <p className="mt-1.5 whitespace-pre-wrap text-[11px] leading-5 text-text-secondary/85">{myScript.script}</p>
                </details>
              )}
              {myScript.mission && (
                <p className="mt-2 rounded-lg bg-white/[0.05] px-2.5 py-1.5 text-[10px] leading-4 text-text-secondary/75">
                  任务：{myScript.mission}
                </p>
              )}
              {myScript.secret_knowledge.length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-[11px] text-gold/80">我知道的秘密（{myScript.secret_knowledge.length}）</summary>
                  <ul className="mt-1.5 space-y-1">
                    {myScript.secret_knowledge.map((k, i) => (
                      <li key={i} className="text-[10px] leading-4 text-text-secondary/70">· {k}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}

          <div className="rounded-[16px] border border-white/[0.08] bg-surface p-4">
            <p className="font-hud text-[10px] tracking-wider text-text-secondary/50">在场角色（{characters.length}）</p>
            <ul className="mt-2.5 space-y-2">
              {characters.map((c) => (
                <li
                  key={c.char_id}
                  title={c.model_label ? `夺舍 ${c.name}（由 ${c.model_label} 驱动）` : undefined}
                  className={`flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs ${
                    myScript?.char_id === c.char_id ? 'bg-gold/10 text-gold' : 'text-text-secondary'
                  }`}
                >
                  <span className="font-medium">{c.name}</span>
                  {playerInput?.agentId === c.char_id && (
                    <span className="animate-pulse rounded bg-violet/20 px-1.5 py-0.5 text-[9px] text-violet">发言中</span>
                  )}
                </li>
              ))}
            </ul>
          </div>

          {reveal && gameId && (
            <>
              <button
                type="button" onClick={handleEvaluate} disabled={evaluating}
                className="flex w-full items-center justify-center gap-2 rounded-[16px] border border-violet/30 bg-violet/[0.08] px-4 py-3 text-xs text-violet transition-colors hover:border-violet hover:bg-violet/15 disabled:opacity-50"
              >
                {evaluating ? <Loader2 size={13} className="animate-spin" /> : <BarChart3 size={13} />}
                {evaluating ? '评估生成中…' : evaluation ? '查看智能体评估报告' : '生成智能体评估报告'}
              </button>
              {evaluation && <EvaluationReportCard report={evaluation} />}
              <button
                type="button" onClick={() => exportJubenshaReplay(gameId)}
                className="flex w-full items-center justify-center gap-2 rounded-[16px] border border-white/10 bg-surface px-4 py-3 text-xs text-text-secondary transition-colors hover:border-violet/40 hover:text-text"
              >
                <Download size={13} /> 导出对局回放（数据集格式）
              </button>
            </>
          )}
        </aside>
      </div>
    </div>
  );
};

/** 复盘揭晓卡片 */
const RevealCard: React.FC<{ reveal: RevealInfo }> = ({ reveal }) => (
  <div className="rounded-2xl border border-gold/40 bg-gradient-to-b from-gold/[0.10] to-transparent p-5">
    <p className="font-hud text-[11px] tracking-[0.22em] text-gold">真相揭晓</p>
    <h3 className="mt-2 text-lg font-bold text-text-primary">
      {reveal.winner === 'civilian' ? '平民阵营获胜 — 真凶被指认' : '凶手阵营获胜 — 凶手逃过指认'}
    </h3>
    <p className="mt-1.5 text-sm text-text-secondary">
      真凶是 <span className="font-bold text-danger">{reveal.murderer_name || '未知'}</span>
      {reveal.tally && Object.keys(reveal.tally).length > 0 && (
        <> · 得票：{Object.entries(reveal.tally).map(([k, v]) => `${k} ${v} 票`).join('，')}</>
      )}
    </p>
    {reveal.case_replay && (
      <details className="mt-3" open>
        <summary className="cursor-pointer text-xs font-medium text-gold/80">案件复盘</summary>
        <p className="mt-2 whitespace-pre-wrap text-xs leading-6 text-text-secondary/85">{reveal.case_replay}</p>
      </details>
    )}
    {reveal.timeline && reveal.timeline.length > 0 && (
      <details className="mt-2.5">
        <summary className="cursor-pointer text-xs font-medium text-gold/80">时间线</summary>
        <ul className="mt-2 space-y-1.5">
          {reveal.timeline.map((t, i) => (
            <li key={i} className="text-[11px] leading-5 text-text-secondary/75">
              <span className="mr-2 font-hud text-gold/60">{t.time}</span>{t.event}
            </li>
          ))}
        </ul>
      </details>
    )}
  </div>
);

/** 智能体评估报告卡（MIRAGE 风格指标，面向专业用户） */
const ABILITY_LABEL: Record<string, string> = {
  rp: '角色扮演', ra: '推理分析', cc: '交流合作', do: '细节观察', ct: '思维创新',
};

const EvaluationReportCard: React.FC<{ report: EvaluationReport }> = ({ report }) => (
  <div className="rounded-[16px] border border-violet/30 bg-violet/[0.05] p-4">
    <p className="flex items-center gap-1.5 font-hud text-[10px] tracking-wider text-violet">
      <BarChart3 size={12} /> 智能体评估报告
    </p>

    {/* 全局指标 */}
    <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
      {([
        ['MRR 指认排名', report.victory_mrr != null ? report.victory_mrr.toFixed(2) : null, '真凶在得票排名中的倒数排名'],
        ['TII 信任倾向', report.tii != null ? report.tii.toFixed(0) : null, '对真凶的怀疑区分度（越高越准）'],
        ['CIC 线索利用', report.cic != null ? `${report.cic.toFixed(0)}%` : null, '发言中引用已获线索的比例'],
        ['ICI 互动密度', report.ici != null ? report.ici.toFixed(0) : null, '提问与互动频率'],
        ['SCI 剧本贴合', report.sci_avg != null ? report.sci_avg.toFixed(0) : null, '按剧本行动的程度'],
        ['综合能力', report.ability_avg_overall != null ? `${report.ability_avg_overall.toFixed(1)}/20` : null, '五维能力均值'],
      ] as Array<[string, string | null, string]>).map(([label, value, tip]) => (
        <div key={label} title={tip} className="rounded-lg bg-white/[0.04] px-2.5 py-2">
          <p className="text-text-secondary/60">{label}</p>
          <p className={`mt-0.5 font-hud text-sm font-bold ${value != null ? 'text-violet' : 'text-text-secondary/40'}`}>
            {value ?? '—'}
          </p>
        </div>
      ))}
    </div>

    {/* 每个智能体 */}
    <div className="mt-3 space-y-2">
      {report.agents.map((a) => (
        <details key={a.char_id} className="rounded-lg bg-white/[0.04] px-3 py-2">
          <summary className="cursor-pointer text-[11px] text-text-primary">
            {a.name}
            <span className={`ml-2 rounded px-1 py-0.5 text-[9px] ${a.camp === 'murderer' ? 'bg-danger/20 text-danger' : 'bg-white/10 text-text-secondary'}`}>
              {a.camp === 'murderer' ? '凶手' : '平民'}
            </span>
            {a.ability_avg != null && <span className="ml-2 text-text-secondary/70">能力 {a.ability_avg}</span>}
            {a.sci != null && <span className="ml-1.5 text-text-secondary/70">贴合 {a.sci.toFixed(0)}</span>}
          </summary>
          <div className="mt-2 space-y-1.5">
            {a.abilities && Object.entries(a.abilities).map(([k, v]) => (
              <div key={k} className="flex items-center gap-2 text-[10px]">
                <span className="w-14 text-text-secondary/70">{ABILITY_LABEL[k] || k}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                  <div className="h-full rounded-full bg-violet/70" style={{ width: `${(v / 20) * 100}%` }} />
                </div>
                <span className="w-7 text-right text-text-secondary">{v.toFixed(0)}</span>
              </div>
            ))}
            <p className="text-[10px] text-text-secondary/60">
              线索 {a.cic_detail?.clues_received ?? 0} 条 · 发言 {a.ici_detail?.speeches ?? 0} 次 · 气泡 {a.ici_detail?.bubbles ?? 0} 条
            </p>
            {a.comment && <p className="text-[10px] italic leading-4 text-text-secondary/75">「{a.comment}」</p>}
          </div>
        </details>
      ))}
    </div>

    <p className="mt-2.5 text-[10px] text-text-secondary/50">
      {!report.llm_scored && '统计指标已生成（LLM 评审不可用，五维分缺失）。'}
      指标参考 MIRAGE 基准；评估结果已写入回放，可随回放导出用于数据集扩充。
    </p>
  </div>
);

export default JubenshaMode;

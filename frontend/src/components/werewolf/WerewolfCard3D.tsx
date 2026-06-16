import React from 'react';
import { Moon, Eye, FlaskConical, Shield, Crosshair, User, Brain, Zap } from 'lucide-react';
import RoleAuraEffect from './RoleAuraEffect';
import type { WerewolfAgent, WerewolfRole } from '../../types/werewolf';
import '../../styles/card-animations.css';

interface WerewolfCard3DProps {
  agent: WerewolfAgent;
  isFlipped: boolean;
  onFlip: () => void;
  className?: string;
  showAura?: boolean;
  size?: 'full' | 'compact';
}

const ROLE_INFO: Record<WerewolfRole, { name: string; faction: string; desc: string; icon: React.ReactNode }> = {
  werewolf: {
    name: '狼人',
    faction: '狼人阵营',
    desc: '夜晚袭击一名玩家',
    icon: <Moon className="w-12 h-12 text-red-500" />
  },
  seer: {
    name: '预言家',
    faction: '好人阵营',
    desc: '夜晚查验一名玩家身份',
    icon: <Eye className="w-12 h-12 text-yellow-500" />
  },
  witch: {
    name: '女巫',
    faction: '好人阵营',
    desc: '拥有一瓶解药和一瓶毒药',
    icon: <FlaskConical className="w-12 h-12 text-purple-500" />
  },
  guard: {
    name: '守卫',
    faction: '好人阵营',
    desc: '夜晚守护一名玩家免受伤害',
    icon: <Shield className="w-12 h-12 text-blue-500" />
  },
  hunter: {
    name: '猎人',
    faction: '好人阵营',
    desc: '死亡时可开枪带走一名玩家',
    icon: <Crosshair className="w-12 h-12 text-orange-500" />
  },
  villager: {
    name: '村民',
    faction: '好人阵营',
    desc: '无特殊技能',
    icon: <User className="w-12 h-12 text-gray-400" />
  },
  unknown: {
    name: '身份未公开',
    faction: '等待揭示',
    desc: '出局、结算或回放中揭示身份',
    icon: <User className="w-12 h-12 text-slate-400" />
  }
};

const WerewolfCard3D: React.FC<WerewolfCard3DProps> = ({
  agent,
  isFlipped,
  onFlip,
  className = '',
  showAura = true,
  size = 'full'
}) => {
  const { role, isAlive, name, mbti, iq } = agent;
  const roleData = ROLE_INFO[role];
  const isCompact = size === 'compact';

  return (
    <div className={`perspective-1000 cursor-pointer ${isCompact ? 'w-full h-48 sm:h-56' : 'w-64 h-96'} ${className}`}>
      {/* Hover Wrapper */}
      <div className={`w-full h-full card-hover-wrapper ${!isAlive ? 'card-dead' : ''}`}>
        
        {/* Flip Container */}
        <div 
          className={`relative w-full h-full transition-transform duration-[600ms] transform-style-3d ${isFlipped ? 'rotate-y-180' : ''}`}
          onClick={onFlip}
        >
          {/* Aura Layer (Attached to the Flip Container so it flips with it) */}
          <RoleAuraEffect 
            role={role} 
            showAura={showAura} 
            className="rounded-xl"
          />

          {/* Front Face */}
          <div className={`absolute inset-0 backface-hidden bg-slate-800 border-2 border-slate-600 rounded-xl flex flex-col items-center justify-between shadow-xl z-10 overflow-hidden ${isCompact ? 'p-3' : 'p-6'}`}>
             {/* Background decorative elements */}
             <div className="absolute top-0 left-0 w-full h-full opacity-10 pointer-events-none">
                <div className="absolute -top-10 -right-10 w-40 h-40 bg-purple-500 rounded-full blur-3xl"></div>
                <div className="absolute -bottom-10 -left-10 w-40 h-40 bg-blue-500 rounded-full blur-3xl"></div>
             </div>

            <div className={`relative flex flex-col items-center w-full ${isCompact ? 'gap-2 mt-1' : 'gap-4 mt-4'}`}>
              <div className="relative">
                <div className={`${isCompact ? 'w-14 h-14 border-2' : 'w-24 h-24 border-4'} rounded-full bg-slate-700 flex items-center justify-center border-slate-600 shadow-lg overflow-hidden`}>
                   {agent.avatar ? (
                     <img src={agent.avatar} alt={name} className="w-full h-full object-cover" />
                   ) : (
                     <span className={`${isCompact ? 'text-xl' : 'text-3xl'} font-bold text-slate-300`}>{name.charAt(0).toUpperCase()}</span>
                   )}
                </div>
                {!isAlive && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/60 rounded-full">
                    <span className="text-red-500 font-bold transform -rotate-12 border-2 border-red-500 px-2 py-1 rounded">DEAD</span>
                  </div>
                )}
              </div>
              
              <h3 className={`${isCompact ? 'text-base' : 'text-xl'} font-bold text-white tracking-wider truncate max-w-full`}>{name}</h3>
              
              <div className="flex gap-2">
                {isAlive ? (
                   <span className={`${isCompact ? 'px-2 py-0.5 text-[10px]' : 'px-3 py-1 text-xs'} bg-green-900/50 text-green-200 font-bold rounded-full border border-green-700/50`}>
                    存活
                  </span>
                ) : (
                  <span className={`${isCompact ? 'px-2 py-0.5 text-[10px]' : 'px-3 py-1 text-xs'} bg-red-900/50 text-red-200 font-bold rounded-full border border-red-700/50`}>
                    已死亡
                  </span>
                )}
              </div>
            </div>

            <div className={`relative w-full ${isCompact ? 'space-y-1 mb-0' : 'space-y-3 mb-2'}`}>
              <div className={`flex items-center justify-between bg-slate-700/50 rounded-lg backdrop-blur-sm ${isCompact ? 'p-1.5' : 'p-2'}`}>
                <div className="flex items-center gap-2 text-slate-300">
                  <Brain size={isCompact ? 12 : 16} />
                  <span className={`${isCompact ? 'text-[10px]' : 'text-sm'} font-medium`}>MBTI</span>
                </div>
                <span className={`${isCompact ? 'text-[10px]' : 'text-sm'} font-bold text-blue-300`}>{mbti || 'Unknown'}</span>
              </div>
              
              <div className={`flex items-center justify-between bg-slate-700/50 rounded-lg backdrop-blur-sm ${isCompact ? 'p-1.5' : 'p-2'}`}>
                <div className="flex items-center gap-2 text-slate-300">
                  <Zap size={isCompact ? 12 : 16} />
                  <span className={`${isCompact ? 'text-[10px]' : 'text-sm'} font-medium`}>IQ</span>
                </div>
                <span className={`${isCompact ? 'text-[10px]' : 'text-sm'} font-bold text-purple-300`}>{iq || 'N/A'}</span>
              </div>
            </div>
          </div>

          {/* Back Face */}
          <div className={`absolute inset-0 backface-hidden rotate-y-180 bg-slate-900 border-2 border-slate-700 rounded-xl flex flex-col items-center justify-center shadow-xl z-10 overflow-hidden ${isCompact ? 'p-3' : 'p-6'}`}>
             {/* Background decorative elements */}
             <div className="absolute top-0 left-0 w-full h-full opacity-10 pointer-events-none">
                <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-56 h-56 bg-white rounded-full blur-[100px]"></div>
             </div>

            <div className={`relative transform ${isCompact ? 'mb-3 scale-75' : 'mb-6 scale-110'}`}>
              {roleData.icon}
            </div>
            
            <h2 className={`relative font-bold text-white mb-2 tracking-widest ${isCompact ? 'text-lg' : 'text-2xl'}`}>{roleData.name}</h2>
            <span className={`relative rounded-full text-xs font-bold border ${isCompact ? 'mb-3 px-3 py-0.5' : 'mb-8 px-4 py-1'} ${role === 'werewolf' ? 'bg-red-900/30 text-red-300 border-red-800' : 'bg-blue-900/30 text-blue-300 border-blue-800'}`}>
              {roleData.faction}
            </span>
            
            <div className={`relative text-center w-full bg-slate-800/50 rounded-lg backdrop-blur-sm ${isCompact ? 'p-2' : 'p-4'}`}>
              <h4 className={`text-slate-400 text-[10px] uppercase tracking-[0.2em] border-b border-slate-700 pb-1 ${isCompact ? 'mb-1 mx-3' : 'mb-2 mx-8'}`}>技能</h4>
              <p className={`text-slate-300 leading-relaxed font-light ${isCompact ? 'text-xs' : 'text-sm'}`}>
                {roleData.desc}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WerewolfCard3D;

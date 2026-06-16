import React from 'react';
import '../../styles/card-animations.css';
import type { WerewolfRole } from '../../types/werewolf';

interface RoleAuraEffectProps {
  role: WerewolfRole;
  className?: string;
  showAura?: boolean;
}

const RoleAuraEffect: React.FC<RoleAuraEffectProps> = ({ 
  role, 
  className = '',
  showAura = true 
}) => {
  const getAuraClass = (role: WerewolfRole) => {
    switch (role) {
      case 'werewolf':
        return 'aura-werewolf';
      case 'seer':
        return 'aura-seer';
      case 'witch':
        return 'aura-witch';
      case 'guard':
        return 'aura-guard';
      case 'hunter':
        return 'aura-hunter';
      case 'villager':
        return 'aura-villager';
      default:
        return '';
    }
  };

  if (!showAura) return null;

  return (
    <div 
      className={`absolute inset-0 rounded-xl pointer-events-none transition-opacity duration-300 ${getAuraClass(role)} ${className}`}
      style={{ zIndex: 0 }}
    />
  );
};

export default RoleAuraEffect;
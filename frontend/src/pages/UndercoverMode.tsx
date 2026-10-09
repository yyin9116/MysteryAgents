import React from 'react';
import Layout from '../components/Layout';
import UserIdentitySetup from '../components/UserIdentitySetup';
import { useUserStore } from '../store/userStore';
import { useGameStore } from '../store/gameStore';
import GameBoard from '../components/GameBoard';
import GameConfiguration from '../components/GameConfiguration';

export const UndercoverMode: React.FC = () => {
  const user = useUserStore((state) => state.user);
  const currentGame = useGameStore((state) => state.currentGame);

  // 对局中由 GameBoard 全屏呈现设计稿布局，不再套用旧 Layout 外壳
  if (user && currentGame) {
    return <GameBoard />;
  }

  return (
    <Layout>
      {!user ? <UserIdentitySetup /> : <GameConfiguration />}
    </Layout>
  );
};

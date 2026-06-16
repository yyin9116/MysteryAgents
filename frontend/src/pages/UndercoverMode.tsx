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

  return (
    <Layout>
      {!user ? (
        <UserIdentitySetup />
      ) : !currentGame ? (
        <GameConfiguration />
      ) : (
        <GameBoard />
      )}
    </Layout>
  );
};

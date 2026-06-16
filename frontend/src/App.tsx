import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { UndercoverMode } from './pages/UndercoverMode';
import { DiscussionMode } from './pages/DiscussionMode';
import WerewolfMode from './pages/WerewolfMode';
import { ModelConfigManager } from './components/ModelConfigManager';
import Layout from './components/Layout';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/undercover" element={<UndercoverMode />} />
        <Route path="/discussion" element={<DiscussionMode />} />
        <Route path="/werewolf" element={<WerewolfMode />} />
        <Route path="/settings" element={
          <Layout wide>
            <ModelConfigManager />
          </Layout>
        } />
      </Routes>
    </BrowserRouter>
  );
};

export default App;

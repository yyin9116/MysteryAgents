import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { UndercoverMode } from './pages/UndercoverMode';
import { DiscussionMode } from './pages/DiscussionMode';
import WerewolfMode from './pages/WerewolfMode';
import JubenshaMode from './pages/JubenshaMode';
import { ModelConfigManager } from './components/ModelConfigManager';
import { PromptManagement } from './pages/PromptManagement';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';

const App: React.FC = () => {
  return (
    <ErrorBoundary>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/undercover" element={<UndercoverMode />} />
        <Route path="/discussion" element={<DiscussionMode />} />
        <Route path="/werewolf" element={<WerewolfMode />} />
        <Route path="/jubensha" element={<JubenshaMode />} />
        <Route path="/settings" element={
          <Layout wide>
            <ModelConfigManager />
          </Layout>
        } />
        <Route path="/prompts" element={
          <Layout wide>
            <PromptManagement />
          </Layout>
        } />
      </Routes>
    </BrowserRouter>
    </ErrorBoundary>
  );
};

export default App;

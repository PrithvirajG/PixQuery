import React from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import AppShell from './components/AppShell';
import SearchView from './views/SearchView';
import PipelinesView from './views/PipelinesView';
import WorkspacesView from './views/WorkspacesView';
import WorkspaceDetailView from './views/WorkspaceDetailView';
import PipelineStatsView from './views/PipelineStatsView';
import ImageDetails from './pages/ImageDetails';
import JobsView from './views/JobsView';
import LandingPage from './pages/LandingPage';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AP } from './aperture/kit';
import { Logo } from './aperture/logo';

function Dashboard() {
  return (
    <AppShell>
      <Routes>
        <Route path="/search" element={<SearchView />} />
        <Route path="/workspaces" element={<WorkspacesView />} />
        <Route path="/workspaces/:id" element={<WorkspaceDetailView />} />
        <Route path="/workspaces/:id/pipelines/:pipelineId/stats" element={<PipelineStatsView />} />
        <Route path="/pipelines" element={<PipelinesView />} />
        <Route path="/jobs" element={<JobsView />} />
        <Route path="/image/:id" element={<ImageDetails />} />
        <Route path="*" element={<Navigate to="/search" replace />} />
      </Routes>
    </AppShell>
  );
}

function LoadingScreen() {
  return (
    <div
      className="ap-screen"
      style={{
        height: '100vh',
        background: AP.void,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
        <Logo variant="mark" size={40} />
        <span style={{ fontFamily: AP.mono, fontSize: 12, color: AP.ink3 }}>verifying session…</span>
      </div>
    </div>
  );
}

function AppContent() {
  const { user, loading } = useAuth();

  if (loading) return <LoadingScreen />;
  if (!user) return <LandingPage />;
  return <Dashboard />;
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppContent />
      </Router>
    </AuthProvider>
  );
}

export default App;

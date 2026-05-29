import React, { useState } from 'react';
import { BrowserRouter as Router, Route, Routes, Link, useLocation, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import theme from './theme';
import SearchView from './views/SearchView';
import PipelinesView from './views/PipelinesView';
import WorkspacesView from './views/WorkspacesView';
import ImageDetails from './pages/ImageDetails';
import JobsView from './views/JobsView';
import LandingPage from './pages/LandingPage';
import { AuthProvider, useAuth } from './context/AuthContext';

const NAV_LINKS = [
  {
    to: '/search',
    label: 'Search',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
  },
  {
    to: '/workspaces',
    label: 'Workspaces',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
      </svg>
    ),
  },
  {
    to: '/pipelines',
    label: 'Pipelines',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h7" />
      </svg>
    ),
  },
  {
    to: '/jobs',
    label: 'Jobs',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
];

function NavLink({ to, label, icon }) {
  const { pathname } = useLocation();
  const isActive = pathname === to || (to !== '/' && pathname.startsWith(to));
  return (
    <Link
      to={to}
      className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-200 ${
        isActive
          ? 'bg-violet-600/20 text-violet-300 border border-violet-500/30 shadow-[0_0_12px_rgba(139,92,246,0.2)]'
          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
      }`}
    >
      {icon}
      {label}
    </Link>
  );
}

function AppHeader() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl">
      <div className="mx-auto px-6 h-16 flex items-center justify-between gap-6 max-w-screen-2xl">
        {/* Logo */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-violet-600 to-blue-500 flex items-center justify-center shadow-[0_0_16px_rgba(139,92,246,0.4)]">
            <span className="text-sm font-black text-white">PQ</span>
          </div>
          <span className="text-xl font-extrabold bg-gradient-to-r from-white via-slate-100 to-violet-300 bg-clip-text text-transparent hidden sm:block">
            PixQuery
          </span>
        </div>

        {/* Nav Links */}
        <nav className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map((link) => (
            <NavLink key={link.to} {...link} />
          ))}
        </nav>

        {/* User Profile */}
        <div className="flex items-center gap-3 relative">
          <div className="hidden sm:flex flex-col items-end">
            <span className="text-xs font-bold text-slate-300">{user?.username}</span>
            <span className="text-[10px] text-slate-500 font-medium">Local Instance</span>
          </div>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="w-9 h-9 rounded-full bg-gradient-to-tr from-violet-600 to-blue-500 flex items-center justify-center text-sm font-black text-white shadow-[0_0_14px_rgba(139,92,246,0.35)] hover:shadow-[0_0_22px_rgba(139,92,246,0.5)] transition-shadow"
          >
            {user?.username?.[0]?.toUpperCase() ?? '?'}
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-12 w-48 bg-slate-900/95 border border-slate-800 rounded-2xl p-2 shadow-xl backdrop-blur-xl z-50">
              <div className="px-3 py-2 border-b border-slate-800 mb-1">
                <p className="text-xs font-bold text-slate-300">{user?.username}</p>
                <p className="text-[10px] text-slate-500">Logged in</p>
              </div>
              <button
                onClick={() => { logout(); setMenuOpen(false); }}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-semibold text-red-400 hover:bg-red-950/30 hover:text-red-300 transition-all"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Mobile Nav */}
      <div className="md:hidden flex items-center gap-1 px-4 pb-3 overflow-x-auto scrollbar-none">
        {NAV_LINKS.map((link) => (
          <NavLink key={link.to} {...link} />
        ))}
      </div>
    </header>
  );
}

function Dashboard() {
  return (
    <ThemeProvider theme={theme}>
      <div className="min-h-screen bg-slate-950 text-slate-100">
        {/* Ambient background orbs */}
        <div className="fixed top-0 left-1/4 w-[600px] h-[400px] rounded-full bg-violet-700/5 blur-[120px] pointer-events-none" />
        <div className="fixed bottom-0 right-1/4 w-[500px] h-[400px] rounded-full bg-blue-700/5 blur-[120px] pointer-events-none" />

        <AppHeader />

        <main className="relative z-10 max-w-screen-2xl mx-auto px-4 sm:px-6 py-6">
          <Routes>
            <Route path="/search" element={<SearchView />} />
            <Route path="/workspaces" element={<WorkspacesView />} />
            <Route path="/pipelines" element={<PipelinesView />} />
            <Route path="/jobs" element={<JobsView />} />
            <Route path="/image/:id" element={<ImageDetails />} />
            <Route path="*" element={<Navigate to="/search" replace />} />
          </Routes>
        </main>
      </div>
    </ThemeProvider>
  );
}

function LoadingScreen() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-5">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-violet-600 to-blue-500 flex items-center justify-center shadow-[0_0_30px_rgba(139,92,246,0.5)] animate-pulse">
          <span className="text-xl font-black text-white">PQ</span>
        </div>
        <div className="flex flex-col items-center gap-2">
          <div className="w-5 h-5 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
          <p className="text-xs text-slate-500 font-medium">Verifying session...</p>
        </div>
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

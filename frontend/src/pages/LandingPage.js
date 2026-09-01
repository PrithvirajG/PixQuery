import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { errorMessage } from '../lib/apiError';
import { Logo } from '../aperture/logo';

function LandingPage() {
  const { login, register } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [isLoginView, setIsLoginView] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const resetForm = () => {
    setUsername('');
    setPassword('');
    setConfirmPassword('');
    setError('');
  };

  const handleOpenAuth = (loginView = true) => {
    setIsLoginView(loginView);
    setShowAuthModal(true);
    resetForm();
  };

  const handleToggleView = () => {
    setIsLoginView(v => !v);
    setUsername('');
    setPassword('');
    setConfirmPassword('');
    setError('');
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (!username || !password) {
      setError('Please fill in all fields.');
      setLoading(false);
      return;
    }

    if (username.length < 3) {
      setError('Username must be at least 3 characters.');
      setLoading(false);
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      setLoading(false);
      return;
    }

    try {
      if (isLoginView) {
        await login(username, password);
      } else {
        if (password !== confirmPassword) {
          setError('Passwords do not match.');
          setLoading(false);
          return;
        }
        await register(username, password);
      }
      setShowAuthModal(false);
    } catch (err) {
      setError(errorMessage(err, 'An error occurred. Please check your credentials.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans relative overflow-hidden select-none">
      {/* Visual Ambient Background Lights */}
      <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full bg-violet-600/10 blur-[150px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[700px] h-[700px] rounded-full bg-blue-600/10 blur-[180px] pointer-events-none" />

      {/* Global Header */}
      <header className="relative z-10 container mx-auto px-6 py-5 flex items-center justify-between border-b border-slate-900/60 backdrop-blur-md">
        <Logo size={34} />
        <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-400">
          <a href="#features" className="hover:text-violet-400 transition-colors">Features</a>
          <a href="#technology" className="hover:text-violet-400 transition-colors">Technology</a>
          <a href="#privacy" className="hover:text-violet-400 transition-colors">Privacy</a>
        </nav>
        <div className="flex items-center gap-4">
          <button 
            onClick={() => handleOpenAuth(true)}
            className="text-sm font-semibold text-slate-300 hover:text-white px-4 py-2 transition-colors"
          >
            Login
          </button>
          <button 
            onClick={() => handleOpenAuth(false)}
            className="text-sm font-bold bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-500 hover:to-blue-500 text-white px-5 py-2.5 rounded-full transition-all duration-300 shadow-[0_0_20px_rgba(139,92,246,0.3)] hover:shadow-[0_0_30px_rgba(139,92,246,0.5)] border border-violet-500/20"
          >
            Sign Up Free
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <main className="relative z-10 flex-1 container mx-auto px-6 py-12 md:py-20 flex flex-col items-center text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-violet-950/40 border border-violet-800/40 text-violet-300 text-xs font-semibold uppercase tracking-wider mb-8 animate-pulse">
          ⚡ Core Local AI Organization
        </div>
        
        <h1 className="text-4xl md:text-6xl lg:text-7xl font-black tracking-tight leading-[1.1] max-w-4xl mb-6">
          Search your personal photos with{' '}
          <span className="bg-gradient-to-r from-violet-400 via-blue-400 to-cyan-300 bg-clip-text text-transparent">
            Natural Language
          </span>
        </h1>
        
        <p className="text-slate-400 text-lg md:text-xl max-w-2xl mb-12 font-medium">
          PixQuery runs fully local on your home PC. Weaviate-powered vector search, YOLO, and CLIP model pipelines catalog your memories while preserving 100% offline privacy.
        </p>

        {/* Interactive Query Mockup */}
        <div className="w-full max-w-3xl bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4 md:p-6 backdrop-blur-lg shadow-[0_20px_50px_rgba(0,0,0,0.5)] mb-20 transition-all duration-300 hover:border-slate-700/80">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-4 mb-5">
            <div className="flex gap-2">
              <span className="w-3.5 h-3.5 rounded-full bg-red-500/80" />
              <span className="w-3.5 h-3.5 rounded-full bg-yellow-500/80" />
              <span className="w-3.5 h-3.5 rounded-full bg-green-500/80" />
            </div>
            <span className="text-xs text-slate-500 font-mono">http://localhost:3000</span>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex gap-3 bg-slate-950 border border-slate-800 rounded-full px-5 py-3.5 shadow-inner items-center">
              <svg className="w-5 h-5 text-violet-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input 
                type="text" 
                readOnly 
                value="Find photos of my dog running on the beach at sunset" 
                className="bg-transparent border-none text-slate-200 outline-none text-sm font-medium w-full"
              />
              <span className="text-xs font-semibold px-3 py-1.5 rounded-full bg-violet-600 text-white shadow-[0_0_15px_rgba(139,92,246,0.4)]">
                Query AI
              </span>
            </div>

            {/* Mock Search Results */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-2">
              {[
                { label: 'Sunset, Dog', caption: 'A golden retriever running on the beach under a purple sky at dusk', score: '0.98' },
                { label: 'Sea, Retriever', caption: 'Happy dog splashing through small ocean waves during sunset', score: '0.92' },
                { label: 'Sandy Shore', caption: 'Retriever looking towards the setting sun on a wide sandy beach', score: '0.89' },
              ].map((item, idx) => (
                <div key={idx} className="bg-slate-950/80 border border-slate-800/60 rounded-xl p-4 flex flex-col text-left group hover:border-violet-500/30 transition-all duration-300 relative overflow-hidden">
                  <div className="absolute top-2 right-2 px-2 py-0.5 rounded-md bg-violet-950 text-[10px] font-bold text-violet-300 border border-violet-800/40">
                    Match: {item.score}
                  </div>
                  <div className="w-full h-28 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-center mb-3.5 relative overflow-hidden group-hover:border-violet-500/20">
                    <svg className="w-8 h-8 text-slate-700 group-hover:text-violet-500/50 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <span className="text-[10px] text-violet-400 font-extrabold uppercase tracking-widest mb-1">{item.label}</span>
                  <p className="text-xs text-slate-400 leading-relaxed font-medium">{item.caption}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Feature Grid */}
        <section id="features" className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-3 gap-6 text-left py-10">
          {[
            {
              title: 'Vector Search Pipeline',
              desc: 'Leverages CLIP embeddings stored in Weaviate for semantic search. Type conceptual descriptors instead of matching exact filenames.',
              icon: '🧬',
            },
            {
              title: 'Object & Scene Recognition',
              desc: 'Dual processing using YOLO (object bounding boxes) and BLIP models (natural captions) cataloging objects, people, and scene context.',
              icon: '👁️',
            },
            {
              title: 'Offline Local-first Privacy',
              desc: 'No external APIs or cloud leaks. Models run strictly on your CPU/GPU, ensuring complete privacy over your personal photo collection.',
              icon: '🛡️',
            },
          ].map((feat, idx) => (
            <div key={idx} className="bg-slate-900/30 border border-slate-900 hover:border-violet-500/20 p-8 rounded-2xl backdrop-blur-sm transition-all duration-300 hover:-translate-y-2 group shadow-xl">
              <div className="w-12 h-12 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center text-xl mb-6 shadow-inner group-hover:bg-violet-950/30 transition-colors">
                {feat.icon}
              </div>
              <h3 className="text-xl font-bold text-slate-100 mb-3 group-hover:text-violet-300 transition-colors">{feat.title}</h3>
              <p className="text-slate-400 text-sm leading-relaxed font-medium">{feat.desc}</p>
            </div>
          ))}
        </section>
      </main>

      {/* Interactive Glassmorphic Authentication Modal Overlay */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Modal Backdrop with Blur */}
          <div 
            onClick={() => setShowAuthModal(false)}
            className="absolute inset-0 bg-slate-950/80 backdrop-blur-md" 
          />

          {/* Modal Card */}
          <div className="relative z-10 w-full max-w-md bg-slate-900/80 border border-violet-500/20 rounded-3xl p-8 backdrop-blur-xl shadow-[0_0_50px_rgba(139,92,246,0.3)] animate-in fade-in zoom-in duration-300 text-left">
            
            {/* Close Button */}
            <button 
              onClick={() => setShowAuthModal(false)}
              className="absolute top-5 right-5 text-slate-500 hover:text-white transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <div className="text-center mb-8">
              <h2 className="text-3xl font-black bg-gradient-to-r from-white via-slate-100 to-violet-300 bg-clip-text text-transparent">
                {isLoginView ? 'Welcome Back' : 'Create Account'}
              </h2>
              <p className="text-slate-400 text-sm mt-2 font-medium">
                {isLoginView 
                  ? 'Access your secured local AI photo hub' 
                  : 'Establish a new secure vector index'}
              </p>
            </div>

            {error && (
              <div className="mb-6 p-4 rounded-xl bg-red-950/40 border border-red-900/60 text-red-400 text-xs font-semibold">
                ⚠️ {error}
              </div>
            )}

            <form onSubmit={handleAuthSubmit} className="flex flex-col gap-5">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-400">Username</label>
                <div className="flex gap-2.5 bg-slate-950 border border-slate-800 focus-within:border-violet-500/50 rounded-xl px-4 py-3 shadow-inner items-center transition-colors">
                  <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  <input 
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Enter your username"
                    className="bg-transparent border-none text-slate-200 text-sm outline-none w-full font-medium"
                    required
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-400">Password</label>
                <div className="flex gap-2.5 bg-slate-950 border border-slate-800 focus-within:border-violet-500/50 rounded-xl px-4 py-3 shadow-inner items-center transition-colors">
                  <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                  <input 
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="bg-transparent border-none text-slate-200 text-sm outline-none w-full font-medium"
                    required
                  />
                </div>
              </div>

              {!isLoginView && (
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-400">Confirm Password</label>
                  <div className="flex gap-2.5 bg-slate-950 border border-slate-800 focus-within:border-violet-500/50 rounded-xl px-4 py-3 shadow-inner items-center transition-colors">
                    <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                    <input 
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••"
                      className="bg-transparent border-none text-slate-200 text-sm outline-none w-full font-medium"
                      required
                    />
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 font-bold bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-500 hover:to-blue-500 text-white py-3.5 rounded-xl transition-all duration-300 shadow-[0_0_20px_rgba(139,92,246,0.3)] hover:shadow-[0_0_30px_rgba(139,92,246,0.5)] flex items-center justify-center"
              >
                {loading ? (
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  isLoginView ? 'Login' : 'Create Secure Index'
                )}
              </button>
            </form>

            <div className="mt-8 border-t border-slate-800/80 pt-6 text-center text-xs">
              <span className="text-slate-500 font-medium">
                {isLoginView ? "Don't have an account? " : "Already established an account? "}
              </span>
              <button 
                onClick={handleToggleView}
                className="text-violet-400 font-bold hover:text-violet-300 transition-colors"
              >
                {isLoginView ? 'Sign Up' : 'Log In'}
              </button>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}

export default LandingPage;

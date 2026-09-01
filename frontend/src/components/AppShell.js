// AppShell — Aperture global nav rail (Gallery / Control Room) + content area.
import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AP, IconSearch, IconWorkspaces, IconPipelines } from '../aperture/kit';
import { Logo } from '../aperture/logo';
import { useAuth } from '../context/AuthContext';

const NAV = [
  { group: 'Gallery', items: [{ key: 'search', label: 'Search', to: '/search', Icon: IconSearch }] },
  {
    group: 'Control Room',
    items: [
      { key: 'workspaces', label: 'Spaces', to: '/workspaces', Icon: IconWorkspaces },
      { key: 'pipelines', label: 'Pipelines', to: '/pipelines', Icon: IconPipelines },
    ],
  },
];

function NavItem({ item, active, onClick }) {
  const c = active ? AP.lumenSoft : AP.ink3;
  return (
    <button
      type="button"
      title={item.label}
      onClick={onClick}
      style={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 4,
        cursor: 'pointer',
        padding: '2px 0',
        background: 'transparent',
        border: 'none',
      }}
    >
      {active && (
        <span
          style={{
            position: 'absolute',
            left: -15,
            top: 4,
            bottom: 4,
            width: 3,
            borderRadius: 99,
            background: AP.lumenGrad,
            boxShadow: '0 0 10px rgba(124,108,247,.7)',
          }}
        />
      )}
      <span
        style={{
          width: 42,
          height: 38,
          borderRadius: 11,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: active ? AP.lumenBg : 'transparent',
          border: `1px solid ${active ? AP.lumenLine : 'transparent'}`,
          transition: 'all .14s',
        }}
      >
        <item.Icon c={c} />
      </span>
      <span style={{ fontFamily: AP.sans, fontSize: 9.5, fontWeight: 500, color: c, letterSpacing: '.01em' }}>
        {item.label}
      </span>
    </button>
  );
}

function activeKey(pathname) {
  if (pathname.startsWith('/workspaces')) return 'workspaces';
  if (pathname.startsWith('/pipelines')) return 'pipelines';
  return 'search'; // /search and /image/:id both belong to the Gallery
}

export default function AppShell({ children }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const active = activeKey(pathname);

  return (
    <div className="ap-screen" style={{ height: '100vh', display: 'flex', background: AP.void, overflow: 'hidden' }}>
      <nav
        style={{
          width: 82,
          flex: '0 0 auto',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 22,
          padding: '18px 0 16px',
          background: AP.panel,
          borderRight: `1px solid ${AP.line}`,
          zIndex: 5,
        }}
      >
        <Logo variant="mark" size={26} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18, flex: 1, paddingTop: 4 }}>
          {NAV.map((sec, i) => (
            <React.Fragment key={sec.group}>
              {i > 0 && <span style={{ width: 30, height: 1, background: AP.line2, alignSelf: 'center' }} />}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {sec.items.map((it) => (
                  <NavItem key={it.key} item={it} active={active === it.key} onClick={() => navigate(it.to)} />
                ))}
              </div>
            </React.Fragment>
          ))}
        </div>

        {/* user avatar + sign-out menu */}
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            title={user?.username}
            style={{
              width: 32,
              height: 32,
              borderRadius: 99,
              background: AP.card,
              border: `1px solid ${AP.line2}`,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontFamily: AP.sans,
              fontSize: 12,
              fontWeight: 600,
              color: AP.ink2,
              cursor: 'pointer',
            }}
          >
            {user?.username?.slice(0, 2)?.toUpperCase() ?? '?'}
          </button>
          {menuOpen && (
            <div
              style={{
                position: 'absolute',
                left: 44,
                bottom: 0,
                width: 180,
                background: AP.card,
                border: `1px solid ${AP.line2}`,
                borderRadius: 12,
                padding: 8,
                boxShadow: '0 10px 30px rgba(0,0,0,.5)',
                zIndex: 50,
              }}
            >
              <div style={{ padding: '6px 10px 9px', borderBottom: `1px solid ${AP.line}` }}>
                <div style={{ fontFamily: AP.sans, fontSize: 13, fontWeight: 600, color: AP.ink }}>
                  {user?.username}
                </div>
                <div style={{ fontFamily: AP.mono, fontSize: 10, color: AP.ink3, marginTop: 2 }}>local instance</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  logout();
                  setMenuOpen(false);
                }}
                style={{
                  width: '100%',
                  marginTop: 6,
                  padding: '8px 10px',
                  borderRadius: 8,
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontFamily: AP.sans,
                  fontSize: 13,
                  fontWeight: 500,
                  color: '#f0566b',
                  background: 'rgba(240,86,107,.08)',
                  border: '1px solid rgba(240,86,107,.25)',
                }}
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </nav>

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', background: AP.base }}>
        {children}
      </div>
    </div>
  );
}

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import './styles/globals.css';

type HealthState = 'checking' | 'online' | 'offline';
type NavKey = 'Overview' | 'Research runs' | 'Evidence graph' | 'Approvals' | 'Tool registry' | 'Settings';

interface Task {
  task_id: string;
  name: string;
  description: string;
  status: string;
  priority: string;
  created_at: string;
  updated_at: string;
}

interface AuditLog {
  event_id: string;
  action: string;
  resource_type?: string;
  status: string;
  created_at: string;
}

interface ApiState {
  tasks: Task[];
  audit: AuditLog[];
  tools: Record<string, { name?: string; description?: string; risk_level?: number; requires_approval?: boolean }>;
  tasksError: string | null;
  auditError: string | null;
  toolsError: string | null;
  loading: boolean;
}

const navItems: { label: NavKey; icon: string; count?: number }[] = [
  { label: 'Overview', icon: '◈' },
  { label: 'Research runs', icon: '⌁' },
  { label: 'Evidence graph', icon: '◎' },
  { label: 'Approvals', icon: '◫' },
];

const API_URL = process.env.REACT_APP_API_URL || '';

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { Accept: 'application/json', ...getAuthHeader() },
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error('Authentication is required for this view.');
    throw new Error(`API request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...getAuthHeader() },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null) as { message?: string; detail?: string } | null;
    throw new Error(detail?.message || detail?.detail || `API request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function formatDate(value?: string) {
  if (!value) return 'Unknown time';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function App() {
  const [activeNav, setActiveNav] = useState<NavKey>('Overview');
  const [health, setHealth] = useState<HealthState>('checking');
  const [showLogin, setShowLogin] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loggingIn, setLoggingIn] = useState(false);
  const [api, setApi] = useState<ApiState>({
    tasks: [], audit: [], tools: {}, tasksError: null, auditError: null, toolsError: null, loading: true,
  });

  const loadData = useCallback(async () => {
    setApi((current) => ({ ...current, loading: true }));
    const [tasksResult, auditResult, toolsResult] = await Promise.allSettled([
      request<Task[]>('/tasks/'),
      request<AuditLog[]>('/audit/logs?limit=20'),
      request<{ tools?: ApiState['tools'] }>('/tasks/tools/all'),
    ]);
    setApi({
      tasks: tasksResult.status === 'fulfilled' ? tasksResult.value : [],
      audit: auditResult.status === 'fulfilled' ? auditResult.value : [],
      tools: toolsResult.status === 'fulfilled' ? toolsResult.value.tools || {} : {},
      tasksError: tasksResult.status === 'rejected' ? tasksResult.reason.message : null,
      auditError: auditResult.status === 'rejected' ? auditResult.reason.message : null,
      toolsError: toolsResult.status === 'rejected' ? toolsResult.reason.message : null,
      loading: false,
    });
  }, []);

  useEffect(() => {
    request<{ status: string }>('/health')
      .then(() => setHealth('online'))
      .catch(() => setHealth('offline'));
    void loadData();
  }, [loadData]);

  const activeCount = api.tasks.filter((task) => !['completed', 'failed', 'cancelled'].includes(task.status)).length;
  const completedCount = api.tasks.filter((task) => task.status === 'completed').length;
  const approvalCount = api.tasks.filter((task) => task.status === 'waiting_approval').length;
  const healthLabel = health === 'online' ? 'API connected' : health === 'offline' ? 'API unavailable' : 'Connecting to API';
  const viewTitle = activeNav === 'Overview' ? 'Workspace overview' : activeNav;

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" /><div className="ambient ambient-two" />
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><span>V</span></div><div><strong>VTR<span>-Agent</span></strong><small>Research control plane</small></div></div>
        <div className="workspace-switcher"><div className="workspace-avatar">AI</div><div><span>Annucaps Research</span><small>Connected workspace</small></div><span className="chevron">⌄</span></div>
        <nav className="side-nav" aria-label="Main navigation">
          <p className="nav-label">Workspace</p>
          {navItems.map((item) => <NavButton key={item.label} item={item} active={activeNav} onClick={setActiveNav} approvalCount={approvalCount} />)}
          <p className="nav-label nav-label-spaced">Manage</p>
          <NavButton item={{ label: 'Tool registry', icon: '▦' }} active={activeNav} onClick={setActiveNav} approvalCount={approvalCount} />
          <NavButton item={{ label: 'Settings', icon: '⚙' }} active={activeNav} onClick={setActiveNav} approvalCount={approvalCount} />
        </nav>
        <div className="sidebar-footer">
          <div className={`system-status ${health}`}><span className="status-dot" /><div><strong>{healthLabel}</strong><small>FastAPI · v0.1.0</small></div></div>
          <button className="user-card" onClick={() => { setLoginError(null); setShowLogin(true); }}><div className="user-avatar">?</div><div><strong>{localStorage.getItem('access_token') ? 'Authenticated session' : 'Not signed in'}</strong><small>{localStorage.getItem('access_token') ? 'Token stored locally' : 'Sign in to access protected data'}</small></div></button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar"><div className="breadcrumbs"><span>Workspace</span><i>/</i><strong>{viewTitle}</strong></div><div className="topbar-actions"><button className="icon-button" aria-label="Refresh data" onClick={() => void loadData()}>↻</button><div className="topbar-divider" /><button className="avatar-button">?</button></div></header>
        <div className="content-wrap">
          {activeNav === 'Overview' && <Overview tasks={api.tasks} audit={api.audit} loading={api.loading} tasksError={api.tasksError} auditError={api.auditError} activeCount={activeCount} completedCount={completedCount} approvalCount={approvalCount} />}
          {activeNav === 'Research runs' && <TasksView tasks={api.tasks} loading={api.loading} error={api.tasksError} onRefresh={() => void loadData()} />}
          {activeNav === 'Evidence graph' && <UnavailableView title="Evidence graph" description="The backend does not currently expose an evidence graph endpoint. This view is intentionally not populated with fabricated data." />}
          {activeNav === 'Approvals' && <UnavailableView title="Approval queue" description="The approval API is not registered in the running backend. Approval counts are therefore not inferred or invented." />}
          {activeNav === 'Tool registry' && <ToolsView tools={api.tools} loading={api.loading} error={api.toolsError} />}
          {activeNav === 'Settings' && <SettingsView health={health} apiUrl={API_URL || 'CRA development proxy → http://localhost:8000'} />}
        </div>
      </main>
      {showLogin && <LoginModal loading={loggingIn} error={loginError} onClose={() => setShowLogin(false)} onSubmit={async (username, password) => {
        setLoggingIn(true);
        setLoginError(null);
        try {
          const result = await post<{ access_token: string }>('/auth/login', { username, password });
          localStorage.setItem('access_token', result.access_token);
          setShowLogin(false);
          await loadData();
        } catch (error) {
          setLoginError(error instanceof Error ? error.message : 'Login failed.');
        } finally {
          setLoggingIn(false);
        }
      }} />}
    </div>
  );
}

function NavButton({ item, active, onClick, approvalCount }: { item: { label: NavKey; icon: string; count?: number }; active: NavKey; onClick: (label: NavKey) => void; approvalCount: number }) {
  return <button className={`nav-item ${active === item.label ? 'active' : ''}`} onClick={() => onClick(item.label)}><span className="nav-icon">{item.icon}</span><span>{item.label}</span>{item.label === 'Approvals' && approvalCount > 0 && <b>{approvalCount}</b>}</button>;
}

function Overview({ tasks, audit, loading, tasksError, auditError, activeCount, completedCount, approvalCount }: { tasks: Task[]; audit: AuditLog[]; loading: boolean; tasksError: string | null; auditError: string | null; activeCount: number; completedCount: number; approvalCount: number }) {
  return <><section className="hero"><div><p className="eyebrow"><span className="eyebrow-line" /> LIVE BACKEND DATA</p><h1>Research, <em>verified.</em></h1><p className="hero-copy">This dashboard reflects the connected VTR-Agent API. Protected data remains empty until you authenticate.</p></div><button className="primary-button" onClick={() => window.location.href = 'http://localhost:8000/docs'}><span>↗</span> Open API docs</button></section>
    <section className="metric-grid">
      <Metric label="Active research runs" value={loading ? '—' : String(activeCount)} note="from /tasks/" tone="cyan" icon="⌁" />
      <Metric label="Completed runs" value={loading ? '—' : String(completedCount)} note="from /tasks/" tone="green" icon="✓" />
      <Metric label="Approval state" value={loading ? '—' : String(approvalCount)} note="waiting_approval tasks" tone="amber" icon="◫" />
      <Metric label="Audit events" value={loading ? '—' : String(audit.length)} note="latest 20 events" tone="violet" icon="◎" />
    </section>
    <section className="dashboard-grid"><Panel title="Research runs" eyebrow="TASK ENGINE"><DataState error={tasksError} loading={loading} empty="No research tasks returned by the API." hasData={tasks.length > 0}><div className="run-list">{tasks.slice(0, 5).map((task) => <TaskRow key={task.task_id} task={task} />)}</div></DataState></Panel><Panel title="Audit stream" eyebrow="AUDIT LOG"><DataState error={auditError} loading={loading} empty="No audit events returned by the API." hasData={audit.length > 0}><div className="signals-list">{audit.slice(0, 5).map((event) => <div className="signal-row" key={event.event_id}><div className={`signal-icon ${event.status === 'ok' ? 'success' : 'danger'}`}>{event.status === 'ok' ? '✓' : '!'}</div><div><strong>{event.action}</strong><span>{event.resource_type || 'system event'}</span></div><time>{formatDate(event.created_at)}</time></div>)}</div></DataState></Panel></section>
  </>;
}

function TasksView({ tasks, loading, error, onRefresh }: { tasks: Task[]; loading: boolean; error: string | null; onRefresh: () => void }) {
  return <section><ViewHeader eyebrow="TASK ENGINE" title="Research runs" action={<button className="secondary-button" onClick={onRefresh}>↻ Refresh</button>} /><Panel title="" eyebrow=""><DataState error={error} loading={loading} empty="No tasks are available. Authenticate through the API before creating or viewing protected tasks." hasData={tasks.length > 0}><div className="run-list">{tasks.map((task) => <TaskRow key={task.task_id} task={task} detailed />)}</div></DataState></Panel></section>;
}

function TaskRow({ task, detailed = false }: { task: Task; detailed?: boolean }) {
  const tone = task.status === 'completed' ? 'green' : task.status === 'waiting_approval' ? 'amber' : 'cyan';
  return <div className="run-row"><div className={`run-bullet ${tone}`} /><div className="run-main"><strong>{task.name || task.task_id}</strong><span>{detailed ? `${task.description || 'No description'} · ` : ''}{formatDate(task.updated_at || task.created_at)}</span></div><div className={`run-status ${tone}`}>{task.status}</div>{detailed && <div className="run-progress"><div className="progress-track"><div className={`progress-fill ${tone}`} style={{ width: task.status === 'completed' ? '100%' : '35%' }} /></div></div>}</div>;
}

function ToolsView({ tools, loading, error }: { tools: ApiState['tools']; loading: boolean; error: string | null }) {
  return <section><ViewHeader eyebrow="POLICY CONTROL" title="Tool registry" /><Panel title="" eyebrow=""><DataState error={error} loading={loading} empty="No tools were returned by the API." hasData={Object.keys(tools).length > 0}><div className="tool-grid">{Object.entries(tools).map(([id, tool]) => <article className="tool-card" key={id}><div className="tool-card-head"><strong>{tool.name || id}</strong><span className={`risk risk-${tool.risk_level || 0}`}>risk {tool.risk_level ?? '—'}</span></div><p>{tool.description || 'No description supplied by the API.'}</p><small>{tool.requires_approval ? 'Human approval required' : 'Policy-supervised execution'}</small></article>)}</div></DataState></Panel></section>;
}

function SettingsView({ health, apiUrl }: { health: HealthState; apiUrl: string }) {
  return <section><ViewHeader eyebrow="SYSTEM" title="Settings" /><Panel title="Connection diagnostics" eyebrow="RUNTIME"><div className="settings-list"><div><span>Backend status</span><strong className={`value-${health}`}>{health}</strong></div><div><span>API base</span><strong>{apiUrl}</strong></div><div><span>Authentication</span><strong>{localStorage.getItem('access_token') ? 'Token present' : 'Not configured'}</strong></div></div></Panel></section>;
}

function UnavailableView({ title, description }: { title: string; description: string }) {
  return <section><ViewHeader eyebrow="API CAPABILITY" title={title} /><div className="empty-state unavailable"><div className="empty-icon">◎</div><h3>Not available in this backend</h3><p>{description}</p><a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">Inspect available API routes ↗</a></div></section>;
}

function LoginModal({ loading, error, onClose, onSubmit }: { loading: boolean; error: string | null; onClose: () => void; onSubmit: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  return <div className="modal-backdrop" onClick={onClose}><motion.form className="composer-modal login-modal" initial={{ opacity: 0, y: 18, scale: .97 }} animate={{ opacity: 1, y: 0, scale: 1 }} onClick={(event) => event.stopPropagation()} onSubmit={(event) => { event.preventDefault(); void onSubmit(username, password); }}><button type="button" className="modal-close" onClick={onClose}>×</button><p className="eyebrow">AUTHENTICATED ACCESS</p><h2>Sign in to VTR-Agent</h2><p>Protected tasks, audit logs, and tool permissions are loaded from the running API after authentication.</p><label>Username<input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /></label>{error && <div className="form-error">{error}</div>}<div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-button" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'} <span>→</span></button></div></motion.form></div>;
}

function ViewHeader({ eyebrow, title, action }: { eyebrow: string; title: string; action?: React.ReactNode }) {
  return <div className="view-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1></div>{action}</div>;
}

function Panel({ title, eyebrow, children }: { title: string; eyebrow: string; children: React.ReactNode }) {
  return <motion.div className="panel content-panel" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><div className="panel-heading">{title && <div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div>}</div>{children}</motion.div>;
}

function Metric({ label, value, note, tone, icon }: { label: string; value: string; note: string; tone: string; icon: string }) {
  return <motion.article className="metric-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><div className={`metric-icon ${tone}`}>{icon}</div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className={`metric-delta ${tone}`}>{note}</div></motion.article>;
}

function DataState({ loading, error, empty, hasData, children }: { loading: boolean; error: string | null; empty: string; hasData: boolean; children: React.ReactNode }) {
  if (loading) return <div className="empty-state"><div className="spinner" /><p>Loading from backend…</p></div>;
  if (error) return <div className="empty-state error-state"><div className="empty-icon">!</div><h3>Could not load this data</h3><p>{error}</p></div>;
  return hasData ? children : <div className="empty-state"><div className="empty-icon">◌</div><p>{empty}</p></div>;
}

export default App;

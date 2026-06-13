import { lazy, Suspense, type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppErrorBoundary } from './components/AppErrorBoundary';
import { Layout } from './components/Layout';
import { Auth } from './pages/Auth';
import { getApiKey } from './api/client';

const CmoPage = lazy(() => import('./pages/CmoPage').then((m) => ({ default: m.CmoPage })));
const Stream = lazy(() => import('./pages/Stream').then((m) => ({ default: m.Stream })));
const Workspace = lazy(() => import('./pages/Workspace').then((m) => ({ default: m.Workspace })));
const WorkspaceMobile = lazy(() => import('./pages/WorkspaceMobile').then((m) => ({ default: m.WorkspaceMobile })));
const WorkspaceArtifact = lazy(() => import('./pages/WorkspaceArtifact').then((m) => ({ default: m.WorkspaceArtifact })));
const StrategyDraftPrototype = lazy(() => import('./pages/StrategyDraftPrototype').then((m) => ({ default: m.StrategyDraftPrototype })));
const GoldenGateStrategyWorkflow = lazy(() => import('./pages/GoldenGateStrategyWorkflow').then((m) => ({ default: m.GoldenGateStrategyWorkflow })));
const MotorMotoStrategyWorkflow = lazy(() => import('./pages/MotorMotoStrategyWorkflow').then((m) => ({ default: m.MotorMotoStrategyWorkflow })));
const StrategyWorkflowPage = lazy(() => import('./pages/StrategyWorkflowPage').then((m) => ({ default: m.StrategyWorkflowPage })));
const Ops = lazy(() => import('./pages/Ops').then((m) => ({ default: m.Ops })));
const Intelligence = lazy(() => import('./pages/Intelligence').then((m) => ({ default: m.Intelligence })));
const History = lazy(() => import('./pages/History').then((m) => ({ default: m.History })));
const Settings = lazy(() => import('./pages/Settings').then((m) => ({ default: m.Settings })));
const RunResult = lazy(() => import('./pages/RunResult').then((m) => ({ default: m.RunResult })));
const AdminLayout = lazy(() => import('./pages/admin/AdminLayout').then((m) => ({ default: m.AdminLayout })));
const AdminGettingStarted = lazy(() => import('./pages/admin/AdminGettingStarted').then((m) => ({ default: m.AdminGettingStarted })));
const AdminOverview = lazy(() => import('./pages/admin/AdminOverview').then((m) => ({ default: m.AdminOverview })));
const AdminRuns = lazy(() => import('./pages/admin/AdminRuns').then((m) => ({ default: m.AdminRuns })));
const AdminRunDetail = lazy(() => import('./pages/admin/AdminRunDetail').then((m) => ({ default: m.AdminRunDetail })));
const AdminWorkspace = lazy(() => import('./pages/admin/AdminWorkspace').then((m) => ({ default: m.AdminWorkspace })));
const AdminProviders = lazy(() => import('./pages/admin/AdminProviders').then((m) => ({ default: m.AdminProviders })));
const AdminModules = lazy(() => import('./pages/admin/AdminModules').then((m) => ({ default: m.AdminModules })));
const AdminAgentActivity = lazy(() => import('./pages/admin/AdminAgentActivity').then((m) => ({ default: m.AdminAgentActivity })));
const AdminCampaigns = lazy(() => import('./pages/admin/AdminCampaigns').then((m) => ({ default: m.AdminCampaigns })));
const AdminBilling = lazy(() => import('./pages/admin/AdminBilling').then((m) => ({ default: m.AdminBilling })));
const AdminOnboarding = lazy(() => import('./pages/admin/AdminOnboarding').then((m) => ({ default: m.AdminOnboarding })));
const AdminReports = lazy(() => import('./pages/admin/AdminReports').then((m) => ({ default: m.AdminReports })));
const AdminBrands = lazy(() => import('./pages/admin/AdminBrands').then((m) => ({ default: m.AdminBrands })));
const AdminBrandDetail = lazy(() => import('./pages/admin/AdminBrandDetail').then((m) => ({ default: m.AdminBrandDetail })));
const AdminClientReadiness = lazy(() => import('./pages/admin/AdminClientReadiness').then((m) => ({ default: m.AdminClientReadiness })));
const AdminCalendar = lazy(() => import('./pages/admin/AdminCalendar').then((m) => ({ default: m.AdminCalendar })));
const AdminObjectiveLoop = lazy(() => import('./pages/admin/AdminObjectiveLoop').then((m) => ({ default: m.AdminObjectiveLoop })));
const AdminLoopFlow = lazy(() => import('./pages/admin/AdminLoopFlow').then((m) => ({ default: m.AdminLoopFlow })));
const AdminCouncilSeats = lazy(() => import('./pages/admin/AdminCouncilSeats').then((m) => ({ default: m.AdminCouncilSeats })));
const AdminMemoryAudit = lazy(() => import('./pages/admin/AdminMemoryAudit').then((m) => ({ default: m.AdminMemoryAudit })));
const AdminWatchpoints = lazy(() => import('./pages/admin/AdminWatchpoints').then((m) => ({ default: m.AdminWatchpoints })));

function RouteLoading() {
  return <div style={{ minHeight: '100vh', background: '#f8f5ee' }} />;
}

function RequireAuth({ children }: { children: ReactNode }) {
  if (!getApiKey()) return <Navigate to="/auth" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AppErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<RouteLoading />}>
          <Routes>
            <Route path="/auth" element={<Auth />} />
            <Route
              path="/"
              element={
                <RequireAuth>
                  <Layout />
                </RequireAuth>
              }
            >
              <Route index element={<Navigate to="/stream" replace />} />
              <Route path="ops"          element={<Ops />} />
              <Route path="intelligence" element={<Intelligence />} />
              <Route path="workspace"    element={<><div className="desktop-only"><Workspace /></div><div className="mobile-only"><WorkspaceMobile /></div></>} />
              <Route path="workspace/artifacts/:runId" element={<WorkspaceArtifact />} />
              <Route path="history"      element={<History />} />
              <Route path="history/:runId" element={<RunResult />} />
              <Route path="settings"     element={<Settings />} />
              <Route path="stream"       element={<Stream />} />
              <Route path="cmo"          element={<CmoPage />} />
              <Route path="prototype/strategy-draft" element={<StrategyDraftPrototype />} />
              <Route path="prototype/golden-gate-plan" element={<GoldenGateStrategyWorkflow />} />
              <Route path="prototype/motormoto" element={<MotorMotoStrategyWorkflow />} />
              <Route path="strategy-workflows/:workflowId" element={<StrategyWorkflowPage />} />
            </Route>
            <Route path="admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="/admin/overview" replace />} />
              <Route path="brands"          element={<AdminBrands />} />
              <Route path="client-readiness" element={<AdminClientReadiness />} />
              <Route path="brands/:brandId" element={<AdminBrandDetail />} />
              <Route path="getting-started" element={<AdminGettingStarted />} />
              <Route path="onboarding"      element={<AdminOnboarding />} />
              <Route path="overview"        element={<AdminOverview />} />
              <Route path="reports"         element={<AdminReports />} />
              <Route path="runs"            element={<AdminRuns />} />
              <Route path="runs/:runId"     element={<AdminRunDetail />} />
              <Route path="workspace"       element={<AdminWorkspace />} />
              <Route path="campaigns"       element={<AdminCampaigns />} />
              <Route path="providers"       element={<AdminProviders />} />
              <Route path="billing"         element={<AdminBilling />} />
              <Route path="modules"         element={<AdminModules />} />
              <Route path="agent-activity"  element={<AdminAgentActivity />} />
              <Route path="connectors"      element={<AdminModules />} />
              <Route path="calendar"         element={<AdminCalendar />} />
              <Route path="objective-loop"   element={<AdminObjectiveLoop />} />
              <Route path="loop-flow"        element={<AdminLoopFlow />} />
              <Route path="council-seats"    element={<AdminCouncilSeats />} />
              <Route path="memory-audit"     element={<AdminMemoryAudit />} />
              <Route path="watchpoints"      element={<AdminWatchpoints />} />
            </Route>
            <Route path="*" element={<Navigate to="/stream" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AppErrorBoundary>
  );
}

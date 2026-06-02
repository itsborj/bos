import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { CmoPage } from './pages/CmoPage';
import { AppErrorBoundary } from './components/AppErrorBoundary';
import { Layout } from './components/Layout';
import { Auth } from './pages/Auth';
import { Stream } from './pages/Stream';
import { Workspace } from './pages/Workspace';
import { WorkspaceMobile } from './pages/WorkspaceMobile';
import { WorkspaceArtifact } from './pages/WorkspaceArtifact';
import { Ops } from './pages/Ops';
import { Intelligence } from './pages/Intelligence';
import { History } from './pages/History';
import { Settings } from './pages/Settings';
import { RunResult } from './pages/RunResult';
import { AdminLayout } from './pages/admin/AdminLayout';
import { AdminGettingStarted } from './pages/admin/AdminGettingStarted';
import { AdminOverview } from './pages/admin/AdminOverview';
import { AdminRuns } from './pages/admin/AdminRuns';
import { AdminRunDetail } from './pages/admin/AdminRunDetail';
import { AdminWorkspace } from './pages/admin/AdminWorkspace';
import { AdminProviders } from './pages/admin/AdminProviders';
import { AdminModules } from './pages/admin/AdminModules';
import { AdminAgentActivity } from './pages/admin/AdminAgentActivity';
import { AdminCampaigns } from './pages/admin/AdminCampaigns';
import { AdminBilling } from './pages/admin/AdminBilling';
import { AdminOnboarding } from './pages/admin/AdminOnboarding';
import { AdminReports } from './pages/admin/AdminReports';
import { AdminBrands } from './pages/admin/AdminBrands';
import { AdminBrandDetail } from './pages/admin/AdminBrandDetail';
import { AdminCalendar } from './pages/admin/AdminCalendar';
import { AdminObjectiveLoop } from './pages/admin/AdminObjectiveLoop';
import { AdminLoopFlow } from './pages/admin/AdminLoopFlow';
import { AdminCouncilSeats } from './pages/admin/AdminCouncilSeats';
import { AdminMemoryAudit } from './pages/admin/AdminMemoryAudit';
import { AdminWatchpoints } from './pages/admin/AdminWatchpoints';
import { getApiKey } from './api/client';

function RequireAuth({ children }: { children: React.ReactNode }) {
  if (!getApiKey()) return <Navigate to="/auth" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AppErrorBoundary>
      <BrowserRouter>
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
          </Route>
          <Route path="admin" element={<AdminLayout />}>
            <Route index element={<Navigate to="/admin/brands" replace />} />
            <Route path="brands"          element={<AdminBrands />} />
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
      </BrowserRouter>
    </AppErrorBoundary>
  );
}

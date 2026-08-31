import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { RedirectIfAuthenticated, RequireAuth } from './components/RouteGuards';

import Welcome from './pages/Welcome';
import Login from './pages/Login';
import Signup from './pages/Signup';
import NotFound from './pages/NotFound';

import Home from './pages/user/Home';
import AccessibilityMap from './pages/user/AccessibilityMap';
import Nearby from './pages/user/Nearby';
import FacilityDetail from './pages/user/FacilityDetail';
import ReportIssue from './pages/user/ReportIssue';
import ReportSubmitted from './pages/user/ReportSubmitted';
import MyReports from './pages/user/MyReports';
import ReportStatus from './pages/user/ReportStatus';
import Notifications from './pages/user/Notifications';
import Profile from './pages/user/Profile';

import Dashboard from './pages/authority/Dashboard';
import AuthorityReports from './pages/authority/Reports';
import AuthorityReportDetail from './pages/authority/ReportDetail';
import AuthorityMaintenance from './pages/authority/Maintenance';
import Analytics from './pages/authority/Analytics';

import MaintenanceTasks from './pages/maintenance/Tasks';
import MaintenanceTaskDetail from './pages/maintenance/TaskDetail';

/**
 * Route map.
 *
 * `/` `/map` `/reports` `/authority` `/maintenance` are the top-level paths
 * Vercel serves from the SPA build; everything under `/api/*` is handled by
 * the FastAPI function instead.
 */
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            {/* Public */}
            <Route
              path="/"
              element={
                <RedirectIfAuthenticated>
                  <Welcome />
                </RedirectIfAuthenticated>
              }
            />
            <Route
              path="/login"
              element={
                <RedirectIfAuthenticated>
                  <Login />
                </RedirectIfAuthenticated>
              }
            />
            <Route
              path="/signup"
              element={
                <RedirectIfAuthenticated>
                  <Signup />
                </RedirectIfAuthenticated>
              }
            />

            {/* Citizen portal */}
            <Route
              path="/home"
              element={
                <RequireAuth role="USER">
                  <Home />
                </RequireAuth>
              }
            />
            <Route
              path="/map"
              element={
                <RequireAuth role="USER">
                  <AccessibilityMap />
                </RequireAuth>
              }
            />
            <Route
              path="/nearby"
              element={
                <RequireAuth role="USER">
                  <Nearby />
                </RequireAuth>
              }
            />
            <Route
              path="/facility/:facilityId"
              element={
                <RequireAuth role="USER">
                  <FacilityDetail />
                </RequireAuth>
              }
            />
            <Route
              path="/report"
              element={
                <RequireAuth role="USER">
                  <ReportIssue />
                </RequireAuth>
              }
            />
            <Route
              path="/report/submitted"
              element={
                <RequireAuth role="USER">
                  <ReportSubmitted />
                </RequireAuth>
              }
            />
            <Route
              path="/my-reports"
              element={
                <RequireAuth role="USER">
                  <MyReports />
                </RequireAuth>
              }
            />
            {/* `/reports` is an alias so the documented top-level path works. */}
            <Route path="/reports" element={<Navigate to="/my-reports" replace />} />
            <Route
              path="/my-reports/:reportId"
              element={
                <RequireAuth role="USER">
                  <ReportStatus />
                </RequireAuth>
              }
            />
            <Route
              path="/notifications"
              element={
                <RequireAuth role="USER">
                  <Notifications />
                </RequireAuth>
              }
            />
            <Route
              path="/profile"
              element={
                <RequireAuth role="USER">
                  <Profile />
                </RequireAuth>
              }
            />

            {/* Authority portal */}
            <Route
              path="/authority"
              element={
                <RequireAuth role="AUTHORITY">
                  <Dashboard />
                </RequireAuth>
              }
            />
            <Route
              path="/authority/reports"
              element={
                <RequireAuth role="AUTHORITY">
                  <AuthorityReports />
                </RequireAuth>
              }
            />
            <Route
              path="/authority/reports/:reportId"
              element={
                <RequireAuth role="AUTHORITY">
                  <AuthorityReportDetail />
                </RequireAuth>
              }
            />
            <Route
              path="/authority/maintenance"
              element={
                <RequireAuth role="AUTHORITY">
                  <AuthorityMaintenance />
                </RequireAuth>
              }
            />
            <Route
              path="/authority/analytics"
              element={
                <RequireAuth role="AUTHORITY">
                  <Analytics />
                </RequireAuth>
              }
            />

            {/* Maintenance portal */}
            <Route
              path="/maintenance"
              element={
                <RequireAuth role="MAINTENANCE">
                  <MaintenanceTasks filter="all" />
                </RequireAuth>
              }
            />
            <Route
              path="/maintenance/active"
              element={
                <RequireAuth role="MAINTENANCE">
                  <MaintenanceTasks filter="active" />
                </RequireAuth>
              }
            />
            <Route
              path="/maintenance/completed"
              element={
                <RequireAuth role="MAINTENANCE">
                  <MaintenanceTasks filter="completed" />
                </RequireAuth>
              }
            />
            <Route
              path="/maintenance/tasks/:taskId"
              element={
                <RequireAuth role="MAINTENANCE">
                  <MaintenanceTaskDetail />
                </RequireAuth>
              }
            />

            <Route path="*" element={<NotFound />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

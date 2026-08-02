import { Navigate, createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '../components/AppLayout';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { AnalyticsPage } from '../pages/AnalyticsPage';
import { CitiesPage } from '../pages/CitiesPage';
import { DashboardPage } from '../pages/DashboardPage';
import { ForecastPage } from '../pages/ForecastPage';
import { LoginPage } from '../pages/LoginPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { OptimizationPage } from '../pages/OptimizationPage';
import { ReportsPage } from '../pages/ReportsPage';
import { SimulationPage } from '../pages/SimulationPage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: <ProtectedRoute />,
    children: [
      {
        path: '/',
        element: <AppLayout />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: 'cities', element: <CitiesPage /> },
          { path: 'forecast', element: <ForecastPage /> },
          { path: 'optimization', element: <OptimizationPage /> },
          { path: 'simulation', element: <SimulationPage /> },
          { path: 'analytics', element: <AnalyticsPage /> },
          { path: 'reports', element: <ReportsPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]);

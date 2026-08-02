import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded';
import EngineeringRoundedIcon from '@mui/icons-material/EngineeringRounded';
import InsightsRoundedIcon from '@mui/icons-material/InsightsRounded';
import HubRoundedIcon from '@mui/icons-material/HubRounded';
import MapRoundedIcon from '@mui/icons-material/MapRounded';
import ModelTrainingRoundedIcon from '@mui/icons-material/ModelTrainingRounded';
import PowerRoundedIcon from '@mui/icons-material/PowerRounded';
import SummarizeRoundedIcon from '@mui/icons-material/SummarizeRounded';
import {
  AppBar,
  Box,
  Button,
  Container,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Toolbar,
  Typography,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { apiClient } from '../lib/apiClient';
import { clearSession, updateUser } from '../store/authSlice';
import { useAppDispatch } from '../hooks/useAppDispatch';
import { useAppSelector } from '../hooks/useAppSelector';

const drawerWidth = 260;

const navItems = [
  { to: '/', label: 'National Dashboard', icon: <DashboardRoundedIcon /> },
  { to: '/cities', label: 'India Grid Map', icon: <MapRoundedIcon /> },
  { to: '/forecast', label: 'Forecasting', icon: <ModelTrainingRoundedIcon /> },
  { to: '/optimization', label: 'Optimization', icon: <HubRoundedIcon /> },
  { to: '/simulation', label: 'Simulation', icon: <PowerRoundedIcon /> },
  { to: '/analytics', label: 'Analytics', icon: <InsightsRoundedIcon /> },
  { to: '/reports', label: 'Reports', icon: <SummarizeRoundedIcon /> },
];

export function AppLayout() {
  const { user, accessToken } = useAppSelector((s) => s.auth);
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();

  const meQuery = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: apiClient.getMe,
    enabled: Boolean(accessToken && !user),
    retry: false,
  });

  useEffect(() => {
    if (meQuery.data) {
      dispatch(updateUser(meQuery.data));
    }
  }, [dispatch, meQuery.data]);

  useEffect(() => {
    if (meQuery.error) {
      dispatch(clearSession());
    }
  }, [dispatch, meQuery.error]);

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': { width: drawerWidth, boxSizing: 'border-box', p: 2 },
        }}
      >
        <Stack direction="row" spacing={1} sx={{ px: 1, py: 2, alignItems: 'center' }}>
          <EngineeringRoundedIcon color="primary" />
          <Typography variant="h6">Quantum-AI Grid Twin</Typography>
        </Stack>
        <List sx={{ mt: 2 }}>
          {navItems.map((item) => (
            <ListItemButton
              key={item.to}
              component={NavLink}
              to={item.to}
              selected={location.pathname === item.to}
              sx={{ mb: 1, borderRadius: 2 }}
            >
              <ListItemIcon sx={{ color: 'inherit', minWidth: 36 }}>{item.icon}</ListItemIcon>
              <ListItemText primary={item.label} />
            </ListItemButton>
          ))}
        </List>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1 }}>
        <AppBar position="static" color="transparent" elevation={0}>
          <Toolbar sx={{ justifyContent: 'space-between' }}>
            <Typography variant="h6">National Smart Grid Mission Console</Typography>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                {user?.full_name ?? 'Unknown User'} ({user?.role ?? '—'})
              </Typography>
              <Button
                color="inherit"
                onClick={() => {
                  dispatch(clearSession());
                  navigate('/login');
                }}
              >
                Logout
              </Button>
            </Stack>
          </Toolbar>
        </AppBar>
        <Container maxWidth="xl" sx={{ py: 3 }}>
          <Outlet />
        </Container>
      </Box>
    </Box>
  );
}

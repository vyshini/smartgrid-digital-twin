import { LockOutlined } from '@mui/icons-material';
import {
  Avatar,
  Box,
  Button,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { apiClient } from '../lib/apiClient';
import { setSession } from '../store/authSlice';
import { useAppDispatch } from '../hooks/useAppDispatch';

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { enqueueSnackbar } = useSnackbar();

  const loginMutation = useMutation({
    mutationFn: () => apiClient.login(username, password),
    onSuccess: (data) => {
      dispatch(
        setSession({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          user: data.user,
        }),
      );
      enqueueSnackbar('Authenticated successfully', { variant: 'success' });
      navigate('/');
    },
    onError: () => {
      enqueueSnackbar('Invalid credentials or unauthorized role.', { variant: 'error' });
    },
  });

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', px: 2 }}>
      <Paper
        component={motion.div}
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        sx={{ p: 4, width: '100%', maxWidth: 440 }}
      >
        <Stack spacing={2.5}>
          <Stack spacing={1} sx={{ alignItems: 'center' }}>
            <Avatar sx={{ bgcolor: 'primary.main' }}>
              <LockOutlined />
            </Avatar>
            <Typography variant="h5">Quantum-AI Grid Twin Access</Typography>
            <Typography variant="body2" color="text.secondary">
              Login with your authorized NSGM operator credentials.
            </Typography>
          </Stack>
          <TextField label="Username" value={username} onChange={(e) => setUsername(e.target.value)} fullWidth />
          <TextField
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            fullWidth
          />
          <Button
            variant="contained"
            size="large"
            disabled={loginMutation.isPending || !username || !password}
            onClick={() => loginMutation.mutate()}
          >
            {loginMutation.isPending ? 'Authenticating...' : 'Sign In'}
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}

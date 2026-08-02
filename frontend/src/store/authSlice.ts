import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { clearSessionStorage, readSession, writeSession } from '../core/tokenStorage';
import type { User } from '../core/types';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
}

const persisted = readSession();

const initialState: AuthState = {
  accessToken: persisted?.accessToken ?? null,
  refreshToken: persisted?.refreshToken ?? null,
  user: persisted?.user ?? null,
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setSession(
      state,
      action: PayloadAction<{ accessToken: string; refreshToken: string; user: User }>,
    ) {
      state.accessToken = action.payload.accessToken;
      state.refreshToken = action.payload.refreshToken;
      state.user = action.payload.user;
      writeSession(action.payload);
    },
    updateUser(state, action: PayloadAction<User>) {
      state.user = action.payload;
      if (state.accessToken && state.refreshToken) {
        writeSession({
          accessToken: state.accessToken,
          refreshToken: state.refreshToken,
          user: action.payload,
        });
      }
    },
    clearSession(state) {
      state.accessToken = null;
      state.refreshToken = null;
      state.user = null;
      clearSessionStorage();
    },
  },
});

export const { setSession, updateUser, clearSession } = authSlice.actions;
export const authReducer = authSlice.reducer;

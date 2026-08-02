import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

interface UiState {
  selectedCityId: number | null;
}

const initialState: UiState = {
  selectedCityId: null,
};

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setSelectedCityId(state, action: PayloadAction<number | null>) {
      state.selectedCityId = action.payload;
    },
  },
});

export const { setSelectedCityId } = uiSlice.actions;
export const uiReducer = uiSlice.reducer;

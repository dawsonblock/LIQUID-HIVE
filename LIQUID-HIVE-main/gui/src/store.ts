import { configureStore, createSlice, PayloadAction } from '@reduxjs/toolkit';

interface AppState {
  chatHistory: { role: 'user' | 'assistant'; content: string }[];
  approvals: { id: number; content: string }[];
  stateSummary: any;
}

const initialState: AppState = {
  chatHistory: [],
  approvals: [],
  stateSummary: null,
};

const appSlice = createSlice({
  name: 'app',
  initialState,
  reducers: {
    addChat(state, action: PayloadAction<{ role: 'user' | 'assistant'; content: string }>) {
      state.chatHistory.push(action.payload);
    },
    setApprovals(state, action: PayloadAction<{ id: number; content: string }[]>) {
      state.approvals = action.payload;
    },
    setStateSummary(state, action: PayloadAction<any>) {
      state.stateSummary = action.payload;
    },
  },
});

export const { addChat, setApprovals, setStateSummary } = appSlice.actions;

export const store = configureStore({ reducer: appSlice.reducer });
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
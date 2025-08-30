import { configureStore, createSlice } from '@reduxjs/toolkit';
const initialState = {
    chatHistory: [],
    approvals: [],
    stateSummary: null,
};
const appSlice = createSlice({
    name: 'app',
    initialState,
    reducers: {
        addChat(state, action) {
            state.chatHistory.push(action.payload);
        },
        setApprovals(state, action) {
            state.approvals = action.payload;
        },
        setStateSummary(state, action) {
            state.stateSummary = action.payload;
        },
    },
});
export const { addChat, setApprovals, setStateSummary } = appSlice.actions;
export const store = configureStore({ reducer: appSlice.reducer });

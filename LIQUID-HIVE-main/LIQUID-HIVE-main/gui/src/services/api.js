import axios from 'axios';
// Use same-origin relative paths; backend is served at same host/port.
export const api = axios.create({
    baseURL: '/',
    headers: { 'Content-Type': 'application/json' }
});
export const fetchState = () => api.get('/state').then(r => r.data);
export const postChat = (q) => api.post('/chat?q=' + encodeURIComponent(q)).then(r => r.data);
export const postVision = (form, groundingRequired) => axios.post('/vision?grounding_required=' + String(groundingRequired), form, {
    headers: { 'Content-Type': 'multipart/form-data' },
}).then(r => r.data);
export const getApprovals = () => api.get('/approvals').then(r => r.data);
export const approveProposal = (id) => api.post(`/approvals/${id}/approve`).then(r => r.data);
export const denyProposal = (id) => api.post(`/approvals/${id}/deny`).then(r => r.data);
export const getAdaptersState = () => api.get('/adapters/state').then(r => r.data);
export const promoteAdapter = (role) => api.post(`/adapters/promote/${encodeURIComponent(role)}`).then(r => r.data);
export const getGovernor = () => api.get('/config/governor').then(r => r.data);
export const setGovernor = (enabled, force_gpt4o) => api.post('/config/governor', { enabled, force_gpt4o }).then(r => r.data);
export const startTraining = () => api.post('/train').then(r => r.data);

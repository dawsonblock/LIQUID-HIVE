import axios from 'axios';

// Use /api prefix for backend routes through Vite proxy
export const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
});

export const fetchState = () => api.get('/state').then(r => r.data);
export const postChat = (q: string) => api.post('/chat?q=' + encodeURIComponent(q)).then(r => r.data);

export const postVision = (form: FormData, groundingRequired: boolean) =>
  axios.post('/api/vision?grounding_required=' + String(groundingRequired), form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);

export const getApprovals = () => api.get('/approvals').then(r => r.data);
export const approveProposal = (id: number) => api.post(`/approvals/${id}/approve`).then(r => r.data);
export const denyProposal = (id: number) => api.post(`/approvals/${id}/deny`).then(r => r.data);

export const getAdaptersState = () => api.get('/adapters/state').then(r => r.data);
export const promoteAdapter = (role: string) => api.post(`/adapters/promote/${encodeURIComponent(role)}`).then(r => r.data);

export const getGovernor = () => api.get('/config/governor').then(r => r.data);
export const setGovernor = (enabled: boolean, force_gpt4o: boolean) =>
  api.post('/config/governor', { enabled, force_gpt4o }).then(r => r.data);

export const startTraining = () => api.post('/train').then(r => r.data);

export const previewAutopromote = () => api.get('/autonomy/autopromote/preview').then(r => r.data);

// New secrets health endpoint
export const getSecretsHealth = () => api.get('/secrets/health').then(r => r.data);
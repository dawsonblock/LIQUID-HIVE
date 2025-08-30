import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { Box, Grid, Paper, Typography, List, ListItem, ListItemText, IconButton, Stack, Chip } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import { getApprovals, approveProposal, denyProposal, fetchState } from '../services/api';
const SystemPanel = () => {
    const [approvals, setApprovals] = useState([]);
    const [stateSummary, setStateSummary] = useState(null);
    useEffect(() => {
        const load = async () => {
            try {
                setApprovals(await getApprovals());
                setStateSummary(await fetchState());
            }
            catch { }
        };
        load();
        const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
        ws.onmessage = (ev) => {
            try {
                const msg = JSON.parse(ev.data);
                if (msg.type === 'state_update')
                    setStateSummary(msg.payload);
                if (msg.type === 'approvals_update')
                    setApprovals(msg.payload);
            }
            catch { }
        };
        return () => ws.close();
    }, []);
    const vitals = useMemo(() => stateSummary?.self_awareness_metrics || {}, [stateSummary]);
    return (_jsxs(Grid, { container: true, spacing: 2, children: [_jsx(Grid, { item: true, xs: 12, md: 6, children: _jsxs(Paper, { variant: "outlined", sx: { p: 2 }, children: [_jsx(Typography, { variant: "h6", children: "Core Vitals & Self\u2011Awareness (\u03A6)" }), _jsxs(Stack, { direction: "row", spacing: 2, sx: { mt: 1 }, children: [_jsx(Chip, { label: `Phi: ${vitals.phi ?? 'N/A'}`, color: "primary" }), _jsx(Chip, { label: `Memories: ${stateSummary?.memory_size ?? 'N/A'}` })] }), _jsxs(Box, { sx: { mt: 2 }, children: [_jsx(Typography, { variant: "subtitle2", children: "Operator Intent" }), _jsx(Typography, { variant: "body2", color: "text.secondary", children: stateSummary?.operator_intent ?? 'Unknown' })] })] }) }), _jsx(Grid, { item: true, xs: 12, md: 6, children: _jsxs(Paper, { variant: "outlined", sx: { p: 2 }, children: [_jsx(Typography, { variant: "h6", children: "Approval Queue" }), _jsxs(List, { children: [approvals.map((a) => (_jsx(ListItem, { secondaryAction: _jsxs(Box, { children: [_jsx(IconButton, { color: "success", onClick: async () => { await approveProposal(a.id); setApprovals(await getApprovals()); }, children: _jsx(CheckIcon, {}) }), _jsx(IconButton, { color: "error", onClick: async () => { await denyProposal(a.id); setApprovals(await getApprovals()); }, children: _jsx(CloseIcon, {}) })] }), children: _jsx(ListItemText, { primary: a.content }) }, a.id))), approvals.length === 0 && _jsx(Typography, { variant: "body2", color: "text.secondary", children: "No pending approvals." })] })] }) })] }));
};
export default SystemPanel;

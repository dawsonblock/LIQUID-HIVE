import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { Box, Button, Grid, Paper, Switch, FormControlLabel, Typography, Table, TableHead, TableRow, TableCell, TableBody, CircularProgress, Stack } from '@mui/material';
import { getAdaptersState, promoteAdapter, getGovernor, setGovernor, startTraining } from '../services/api';
const ForgePanel = () => {
    const [adapters, setAdapters] = useState({ state: {} });
    const [gov, setGov] = useState({});
    const [loadingTrain, setLoadingTrain] = useState(false);
    const [trainStatus, setTrainStatus] = useState(null);
    const refresh = async () => {
        try {
            setAdapters(await getAdaptersState());
            setGov(await getGovernor());
        }
        catch { }
    };
    useEffect(() => { refresh(); }, []);
    const onPromote = async (role) => {
        await promoteAdapter(role);
        await refresh();
    };
    const onToggleGov = async (key, value) => {
        const enabled = key === 'ENABLE_ORACLE_REFINEMENT' ? value : !!gov.ENABLE_ORACLE_REFINEMENT;
        const force = key === 'FORCE_GPT4O_ARBITER' ? value : !!gov.FORCE_GPT4O_ARBITER;
        await setGovernor(enabled, force);
        await refresh();
    };
    const onTrain = async () => {
        setLoadingTrain(true);
        setTrainStatus(null);
        const res = await startTraining();
        if (res.status === 'success')
            setTrainStatus(`New adapter at ${res.adapter_path}`);
        else
            setTrainStatus('Training error: ' + res.detail);
        setLoadingTrain(false);
        await refresh();
    };
    const rows = Object.entries(adapters.state || {});
    return (_jsxs(Grid, { container: true, spacing: 2, children: [_jsx(Grid, { item: true, xs: 12, children: _jsxs(Paper, { variant: "outlined", sx: { p: 2 }, children: [_jsxs(Stack, { direction: "row", spacing: 2, alignItems: "center", children: [_jsx(FormControlLabel, { control: _jsx(Switch, { checked: !!gov.ENABLE_ORACLE_REFINEMENT, onChange: e => onToggleGov('ENABLE_ORACLE_REFINEMENT', e.target.checked) }), label: "Enable Oracle Refinement" }), _jsx(FormControlLabel, { control: _jsx(Switch, { checked: !!gov.FORCE_GPT4O_ARBITER, onChange: e => onToggleGov('FORCE_GPT4O_ARBITER', e.target.checked) }), label: "Force GPT\u20114o Arbiter" }), _jsx(Box, { flexGrow: 1 }), _jsx(Button, { variant: "contained", color: "secondary", onClick: onTrain, disabled: loadingTrain, children: loadingTrain ? _jsxs(_Fragment, { children: [_jsx(CircularProgress, { size: 18, sx: { mr: 1 } }), "Igniting..."] }) : 'Ignite Training Cycle' })] }), trainStatus && _jsx(Typography, { variant: "body2", sx: { mt: 1 }, children: trainStatus })] }) }), _jsx(Grid, { item: true, xs: 12, children: _jsxs(Paper, { variant: "outlined", sx: { p: 2 }, children: [_jsx(Typography, { variant: "h6", sx: { mb: 1 }, children: "Adapter Deployment Manager" }), _jsxs(Table, { size: "small", children: [_jsx(TableHead, { children: _jsxs(TableRow, { children: [_jsx(TableCell, { children: "Role" }), _jsx(TableCell, { children: "Champion" }), _jsx(TableCell, { children: "Challenger" }), _jsx(TableCell, { align: "right", children: "Action" })] }) }), _jsxs(TableBody, { children: [rows.map(([role, entry]) => (_jsxs(TableRow, { children: [_jsx(TableCell, { children: role }), _jsx(TableCell, { children: entry.active || '' }), _jsx(TableCell, { children: entry.challenger || '' }), _jsx(TableCell, { align: "right", children: _jsx(Button, { variant: "outlined", size: "small", onClick: () => onPromote(role), disabled: !entry.challenger, children: "Promote to Champion" }) })] }, role))), rows.length === 0 && (_jsx(TableRow, { children: _jsx(TableCell, { colSpan: 4, children: _jsx(Typography, { variant: "body2", color: "text.secondary", children: "No adapters registered." }) }) }))] })] })] }) })] }));
};
export default ForgePanel;

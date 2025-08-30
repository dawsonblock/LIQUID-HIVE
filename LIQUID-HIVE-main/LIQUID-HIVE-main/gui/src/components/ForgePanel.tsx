import React, { useEffect, useState } from 'react';
import { Box, Button, Grid, Paper, Switch, FormControlLabel, Typography, Table, TableHead, TableRow, TableCell, TableBody, CircularProgress, Stack } from '@mui/material';
import { getAdaptersState, promoteAdapter, getGovernor, setGovernor, startTraining } from '../services/api';

const ForgePanel: React.FC = () => {
  const [adapters, setAdapters] = useState<any>({ state: {} });
  const [gov, setGov] = useState<{ ENABLE_ORACLE_REFINEMENT?: boolean; FORCE_GPT4O_ARBITER?: boolean }>({});
  const [loadingTrain, setLoadingTrain] = useState(false);
  const [trainStatus, setTrainStatus] = useState<string | null>(null);

  const refresh = async () => {
    try {
      setAdapters(await getAdaptersState());
      setGov(await getGovernor());
    } catch {}
  };

  useEffect(() => { refresh(); }, []);

  const onPromote = async (role: string) => {
    await promoteAdapter(role);
    await refresh();
  };

  const onToggleGov = async (key: 'ENABLE_ORACLE_REFINEMENT' | 'FORCE_GPT4O_ARBITER', value: boolean) => {
    const enabled = key === 'ENABLE_ORACLE_REFINEMENT' ? value : !!gov.ENABLE_ORACLE_REFINEMENT;
    const force = key === 'FORCE_GPT4O_ARBITER' ? value : !!gov.FORCE_GPT4O_ARBITER;
    await setGovernor(enabled, force);
    await refresh();
  };

  const onTrain = async () => {
    setLoadingTrain(true);
    setTrainStatus(null);
    const res = await startTraining();
    if (res.status === 'success') setTrainStatus(`New adapter at ${res.adapter_path}`);
    else setTrainStatus('Training error: ' + res.detail);
    setLoadingTrain(false);
    await refresh();
  };

  const rows = Object.entries(adapters.state || {});

  return (
    <Grid container spacing={2}>
      <Grid item xs={12}>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack direction="row" spacing={2} alignItems="center">
            <FormControlLabel control={<Switch checked={!!gov.ENABLE_ORACLE_REFINEMENT} onChange={e => onToggleGov('ENABLE_ORACLE_REFINEMENT', e.target.checked)} />} label="Enable Oracle Refinement" />
            <FormControlLabel control={<Switch checked={!!gov.FORCE_GPT4O_ARBITER} onChange={e => onToggleGov('FORCE_GPT4O_ARBITER', e.target.checked)} />} label="Force GPT‑4o Arbiter" />
            <Box flexGrow={1} />
            <Button variant="contained" color="secondary" onClick={onTrain} disabled={loadingTrain}>
              {loadingTrain ? <><CircularProgress size={18} sx={{ mr: 1 }} />Igniting...</> : 'Ignite Training Cycle'}
            </Button>
          </Stack>
          {trainStatus && <Typography variant="body2" sx={{ mt: 1 }}>{trainStatus}</Typography>}
        </Paper>
      </Grid>

      <Grid item xs={12}>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>Adapter Deployment Manager</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Role</TableCell>
                <TableCell>Champion</TableCell>
                <TableCell>Challenger</TableCell>
                <TableCell align="right">Action</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map(([role, entry]: any) => (
                <TableRow key={role}>
                  <TableCell>{role}</TableCell>
                  <TableCell>{entry.active || ''}</TableCell>
                  <TableCell>{entry.challenger || ''}</TableCell>
                  <TableCell align="right">
                    <Button variant="outlined" size="small" onClick={() => onPromote(role)} disabled={!entry.challenger}>Promote to Champion</Button>
                  </TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow><TableCell colSpan={4}><Typography variant="body2" color="text.secondary">No adapters registered.</Typography></TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>
      </Grid>
    </Grid>
  );
};

export default ForgePanel;
import React, { useEffect, useMemo, useState } from 'react';
import { Box, Grid, Paper, Typography, List, ListItem, ListItemText, IconButton, Stack, Chip, Button, Snackbar, Alert } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import { getApprovals, approveProposal, denyProposal, fetchState, previewAutopromote } from '../services/api';

const SystemPanel: React.FC = () => {
  const [approvals, setApprovals] = useState<{ id: number; content: string }[]>([]);
  const [stateSummary, setStateSummary] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [snack, setSnack] = useState<{ open: boolean; msg: string }[]> ([]);
  const [preview, setPreview] = useState<any[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        setApprovals(await getApprovals());
        setStateSummary(await fetchState());
      } catch {}
    };
    load();

    const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'state_update') setStateSummary(msg.payload);
        if (msg.type === 'approvals_update') setApprovals(msg.payload);
        if (msg.type === 'autonomy_events') {
          setEvents(msg.payload || []);
          // Show a toast for each event
          (msg.payload || []).forEach((e: any) => {
            const text = e?.message || `Auto‑promotion: role ${e?.role} → ${e?.new_active}`;
            setSnack(prev => [...prev, { open: true, msg: text }]);
          });
        }
      } catch {}
    };
    return () => ws.close();
  }, []);

  const vitals = useMemo(() => stateSummary?.self_awareness_metrics || {}, [stateSummary]);

  const handlePreview = async () => {
    try {
      const res = await previewAutopromote();
      setPreview(res?.candidates || []);
      if (!res?.candidates?.length) setSnack(prev => [...prev, { open: true, msg: 'No auto‑promotion candidates at this time.' }]);
    } catch (e) {
      setSnack(prev => [...prev, { open: true, msg: 'Preview failed.' }]);
    }
  };

  return (
    <>
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
              <Typography variant="h6">Core Vitals & Self‑Awareness (Φ)</Typography>
              <Button size="small" variant="outlined" onClick={handlePreview}>Preview Auto‑Promotions</Button>
            </Stack>
            <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
              <Chip label={`Phi: ${vitals.phi ?? 'N/A'}`} color="primary" />
              <Chip label={`Memories: ${stateSummary?.memory_size ?? 'N/A'}`} />
            </Stack>
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2">Operator Intent</Typography>
              <Typography variant="body2" color="text.secondary">{stateSummary?.operator_intent ?? 'Unknown'}</Typography>
            </Box>
            {preview.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2">Auto‑Promotion Candidates</Typography>
                <List dense>
                  {preview.map((p: any, i: number) => (
                    <ListItem key={i}>
                      <ListItemText primary={`Role ${p.role}: ${p.challenger} vs ${p.active}`} secondary={`p95 ${p.p95_c?.toFixed?.(3)}s vs ${p.p95_a?.toFixed?.(3)}s; cost ${p.cost_c?.toFixed?.(6)} vs ${p.cost_a?.toFixed?.(6)}`} />
                    </ListItem>
                  ))}
                </List>
              </Box>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="h6">Approval Queue</Typography>
            <List>
              {approvals.map((a) => (
                <ListItem key={a.id}
                  secondaryAction={
                    <Box>
                      <IconButton color="success" onClick={async () => { await approveProposal(a.id); setApprovals(await getApprovals()); }}>
                        <CheckIcon />
                      </IconButton>
                      <IconButton color="error" onClick={async () => { await denyProposal(a.id); setApprovals(await getApprovals()); }}>
                        <CloseIcon />
                      </IconButton>
                    </Box>
                  }
                >
                  <ListItemText primary={a.content} />
                </ListItem>
              ))}
              {approvals.length === 0 && <Typography variant="body2" color="text.secondary">No pending approvals.</Typography>}
            </List>
          </Paper>
        </Grid>
      </Grid>

      {snack.map((s, idx) => (
        <Snackbar key={idx} open={s.open} autoHideDuration={6000} onClose={() => setSnack(prev => prev.filter((_, i) => i !== idx))}>
          <Alert onClose={() => setSnack(prev => prev.filter((_, i) => i !== idx))} severity="info" sx={{ width: '100%' }}>
            {s.msg}
          </Alert>
        </Snackbar>
      ))}
    </>
  );
};

export default SystemPanel;
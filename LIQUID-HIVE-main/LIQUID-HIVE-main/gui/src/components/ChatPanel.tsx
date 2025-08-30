import React, { useState } from 'react';
import { Box, Paper, TextField, IconButton, Stack, Typography, Button, Switch, FormControlLabel, Grid, Accordion, AccordionSummary, AccordionDetails } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SendIcon from '@mui/icons-material/Send';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import ReactMarkdown from 'react-markdown';
import { postChat, postVision, fetchState } from '../services/api';
import { useDispatch, useSelector } from 'react-redux';
import type { RootState } from '../store';
import { addChat } from '../store';
import ContextSidebar from './ContextSidebar';

const ChatPanel: React.FC = () => {
  const [input, setInput] = useState('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [groundingRequired, setGroundingRequired] = useState(false);
  const [lastContext, setLastContext] = useState<string | undefined>();
  const [lastReasoning, setLastReasoning] = useState<string | undefined>();
  const [lastIntent, setLastIntent] = useState<string | undefined>();
  const [lastRationale, setLastRationale] = useState<string | undefined>();
  const [lastCritique, setLastCritique] = useState<string | undefined>();
  const [lastCorrection, setLastCorrection] = useState<string | undefined>();
  const dispatch = useDispatch();
  const history = useSelector((s: RootState) => s.chatHistory);

  const sendText = async () => {
    if (!input.trim()) return;
    dispatch(addChat({ role: 'user', content: input }));
    const res = await postChat(input);
    dispatch(addChat({ role: 'assistant', content: res.answer }));
    setLastContext(res.context);
    setLastReasoning(res.reasoning_strategy);
    setLastRationale(res.selector_reason);
    try { const st = await fetchState(); setLastIntent(st?.operator_intent); } catch {}
    setInput('');
  };

  const sendVision = async () => {
    if (!imageFile) return;
    const form = new FormData();
    form.append('file', imageFile);
    form.append('question', input || 'What is in this image?');
    const res = await postVision(form, groundingRequired);
    dispatch(addChat({ role: 'assistant', content: res.answer }));
    setLastCritique(res.critique);
    try { const st = await fetchState(); setLastIntent(st?.operator_intent); } catch {}
  };

  return (
    <Grid container spacing={2}>
      <Grid item xs={12} md={8}>
        <Stack spacing={2}>
          <Paper variant="outlined" sx={{ p: 2, height: 500, overflowY: 'auto', bgcolor: 'background.default' }}>
            {history.length === 0 && (
              <Typography variant="body2" color="text.secondary">Start the conversation with the Cognitive Core. Attach an image to ask visual questions.</Typography>
            )}
            {history.map((m, i) => (
              <Box key={i} sx={{ mb: 2 }}>
                <Typography variant="caption" color="text.secondary">{m.role.toUpperCase()}</Typography>
                <ReactMarkdown>{m.content}</ReactMarkdown>
                {(lastCritique || lastCorrection) && m.role === 'assistant' && (
                  <Accordion sx={{ mt: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}><Typography variant="caption">Show Reasoning</Typography></AccordionSummary>
                    <AccordionDetails>
                      {lastCritique && <><Typography variant="subtitle2">Judge Critique</Typography><Typography variant="body2" color="text.secondary">{lastCritique}</Typography></>}
                      {lastCorrection && <><Typography variant="subtitle2" sx={{ mt: 1 }}>Correction Analysis</Typography><Typography variant="body2" color="text.secondary">{lastCorrection}</Typography></>}
                    </AccordionDetails>
                  </Accordion>
                )}
              </Box>
            ))}
          </Paper>
          <Stack direction="row" spacing={1} alignItems="center">
            <TextField fullWidth size="small" placeholder="Type a message..." value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText(); } }} />
            <IconButton component="label" color={imageFile ? 'secondary' : 'default'}>
              <AttachFileIcon />
              <input type="file" hidden accept="image/*" onChange={e => setImageFile(e.target.files?.[0] || null)} />
            </IconButton>
            <IconButton color="primary" onClick={sendText}><SendIcon /></IconButton>
            <Button variant="outlined" onClick={sendVision} disabled={!imageFile}>Send Image</Button>
          </Stack>
          <FormControlLabel control={<Switch checked={groundingRequired} onChange={e => setGroundingRequired(e.target.checked)} />} label="Grounding Required" />
        </Stack>
      </Grid>
      <Grid item xs={12} md={4}>
        <ContextSidebar context={lastContext} reasoning={lastReasoning} intent={lastIntent} rationale={lastRationale} />
      </Grid>
    </Grid>
  );
};

export default ChatPanel;
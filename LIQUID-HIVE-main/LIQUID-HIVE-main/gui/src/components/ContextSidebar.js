import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Paper, Typography, List, ListItem, ListItemText } from '@mui/material';
const ContextSidebar = ({ context, reasoning, intent }) => {
    const docs = (context || '').split(/\n\n\[\d+\]/).filter(Boolean);
    return (_jsxs(Paper, { variant: "outlined", sx: { p: 2 }, children: [_jsx(Typography, { variant: "h6", children: "Context Awareness" }), _jsx(Typography, { variant: "subtitle2", sx: { mt: 1 }, children: "Operator Intent" }), _jsx(Typography, { variant: "body2", color: "text.secondary", children: intent || 'Unknown' }), _jsx(Typography, { variant: "subtitle2", sx: { mt: 2 }, children: "Reasoning Strategy" }), _jsx(Typography, { variant: "body2", color: "text.secondary", children: reasoning || 'N/A' }), _jsx(Typography, { variant: "subtitle2", sx: { mt: 2 }, children: "RAG Context" }), _jsxs(List, { dense: true, children: [docs.length === 0 && _jsx(Typography, { variant: "body2", color: "text.secondary", children: "No documents." }), docs.map((d, i) => (_jsx(ListItem, { children: _jsx(ListItemText, { primary: d.trim().slice(0, 120) + (d.length > 120 ? '…' : '') }) }, i)))] })] }));
};
export default ContextSidebar;

import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
} from '@mui/material';
import {
  ExpandMore,
  CheckCircle,
  Error as ErrorIcon,
  Psychology,
  Build,
  Layers,
} from '@mui/icons-material';

const ToolCall = ({ toolCall }) => {
  const { type, name, state, input, output } = toolCall;

  // Icon based on tool type
  const getIcon = () => {
    if (type === 'claude_api') return <Psychology fontSize="small" />;
    if (type === 'mcp_tool') return <Build fontSize="small" />;
    if (type === 'mcp_batch') return <Layers fontSize="small" />;
    return <Build fontSize="small" />;
  };

  // Color based on state
  const getStateColor = () => {
    if (state === 'completed') return 'success';
    if (state === 'running') return 'primary';
    if (state === 'failed') return 'error';
    return 'default';
  };

  // State icon
  const getStateIcon = () => {
    if (state === 'completed') return <CheckCircle fontSize="small" />;
    if (state === 'running') return <CircularProgress size={16} />;
    if (state === 'failed') return <ErrorIcon fontSize="small" />;
    return null;
  };

  // Format tool name for display
  const formatToolName = () => {
    return name
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (l) => l.toUpperCase());
  };

  return (
    <Card
      variant="outlined"
      sx={{
        mb: 1,
        borderLeft: 4,
        borderLeftColor: `${getStateColor()}.main`,
      }}
    >
      <Accordion disableGutters elevation={0}>
        <AccordionSummary expandIcon={<ExpandMore />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
            <Box sx={{ color: `${getStateColor()}.main` }}>
              {getIcon()}
            </Box>
            <Box sx={{ flexGrow: 1 }}>
              <Typography variant="body2" fontWeight={600}>
                {formatToolName()}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {type === 'claude_api' && 'Anthropic Claude API'}
                {type === 'mcp_tool' && 'MCP Tool Call'}
                {type === 'mcp_batch' && 'MCP Batch Execution'}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {getStateIcon()}
              <Chip
                label={state}
                size="small"
                color={getStateColor()}
                variant="outlined"
              />
            </Box>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          {/* Input */}
          {input && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" color="text.secondary" fontWeight={600}>
                INPUT
              </Typography>
              <Card variant="outlined" sx={{ mt: 0.5, backgroundColor: 'grey.50' }}>
                <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                  <pre style={{ margin: 0, fontSize: 12, fontFamily: 'monospace' }}>
                    {JSON.stringify(input, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            </Box>
          )}

          {/* Output */}
          {output && state === 'completed' && (
            <Box>
              <Typography variant="caption" color="text.secondary" fontWeight={600}>
                OUTPUT
              </Typography>
              <Card variant="outlined" sx={{ mt: 0.5, backgroundColor: 'success.50' }}>
                <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                  <pre style={{ margin: 0, fontSize: 12, fontFamily: 'monospace' }}>
                    {JSON.stringify(output, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            </Box>
          )}
        </AccordionDetails>
      </Accordion>
    </Card>
  );
};

export default ToolCall;

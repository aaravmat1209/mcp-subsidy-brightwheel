import React from 'react';
import {
  Box,
  Paper,
  Typography,
  LinearProgress,
  Stack,
  Chip,
  Card,
  CardContent,
  Divider,
} from '@mui/material';
import {
  Psychology,
  BuildCircle,
  Assessment,
} from '@mui/icons-material';
import ToolCall from './ToolCall';

const ReconciliationProgress = ({ progress }) => {
  const stages = [
    {
      id: 'extraction',
      label: 'AI Extraction',
      icon: <Psychology />,
      description: 'Claude multimodal reading PDFs and CSVs',
    },
    {
      id: 'reconciliation',
      label: 'Agentic Orchestration',
      icon: <BuildCircle />,
      description: 'Claude dynamically calling MCP tools',
    },
    {
      id: 'grading',
      label: 'Quality Assessment',
      icon: <Assessment />,
      description: 'Claude grader evaluating exception quality',
    },
  ];

  return (
    <Paper sx={{ p: 4 }}>
      <Typography variant="h5" gutterBottom>
        Processing Reconciliation
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Multi-agent AI system analyzing your subsidy reports
      </Typography>

      <Box sx={{ mb: 4 }}>
        <LinearProgress
          variant="determinate"
          value={progress.percent || 0}
          sx={{ height: 8, borderRadius: 4 }}
        />
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
          <Box>
            <Typography variant="body2" color="text.secondary">
              {progress.message || 'Initializing...'}
            </Typography>
            {progress.api_calls && (
              <Typography variant="caption" color="primary">
                API Calls: {progress.api_calls.done}/{progress.api_calls.total}
              </Typography>
            )}
          </Box>
          <Typography variant="body2" fontWeight={600}>
            {Math.floor(progress.percent || 0)}%
          </Typography>
        </Box>
      </Box>

      <Stack spacing={2}>
        {stages.map((stage) => {
          const isActive = progress.stage === stage.id;
          const isComplete = progress.percent >= getStageEndPercent(stage.id);

          return (
            <Card
              key={stage.id}
              variant="outlined"
              sx={{
                borderColor: isActive ? 'primary.main' : isComplete ? 'success.main' : 'divider',
                borderWidth: isActive ? 2 : 1,
                backgroundColor: isActive ? 'primary.50' : 'background.paper',
              }}
            >
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Box
                    sx={{
                      color: isActive ? 'primary.main' : isComplete ? 'success.main' : 'text.secondary',
                    }}
                  >
                    {stage.icon}
                  </Box>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography variant="subtitle1" fontWeight={600}>
                      {stage.label}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {stage.description}
                    </Typography>
                  </Box>
                  {isActive && (
                    <Chip label="Processing" color="primary" size="small" />
                  )}
                  {isComplete && (
                    <Chip label="Complete" color="success" size="small" />
                  )}
                </Box>
              </CardContent>
            </Card>
          );
        })}
      </Stack>

      {/* Tool Calls Section */}
      {progress.tool_calls && progress.tool_calls.length > 0 && (
        <>
          <Divider sx={{ my: 3 }} />
          <Typography variant="h6" gutterBottom>
            Orchestration Log
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Live view of AI and MCP tool calls
          </Typography>
          <Stack spacing={0.5}>
            {progress.tool_calls.map((toolCall, index) => (
              <ToolCall key={`${index}-${toolCall.state}-${toolCall.timestamp}`} toolCall={toolCall} />
            ))}
          </Stack>
        </>
      )}
    </Paper>
  );
};

const getStageEndPercent = (stageId) => {
  const percentages = {
    extraction: 33,
    reconciliation: 80,
    grading: 100,
  };
  return percentages[stageId] || 0;
};

export default ReconciliationProgress;

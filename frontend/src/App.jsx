import React, { useState } from 'react';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Container,
  Box,
  Typography,
  Paper,
  Stepper,
  Step,
  StepLabel,
  Button,
  Alert,
} from '@mui/material';
import {
  CloudUpload,
  Psychology,
} from '@mui/icons-material';
import FileUpload from './components/FileUpload';
import ReconciliationProgress from './components/ReconciliationProgress';
import ResultsView from './components/ResultsView';
import { uploadFile, startReconciliation, streamJobProgress } from './api/reconciliation';

// Brightwheel color scheme (based on their website)
const brightwheelTheme = createTheme({
  palette: {
    primary: {
      main: '#3B7CFF', // Brightwheel blue
      light: '#6B9FFF',
      dark: '#2457CC',
    },
    secondary: {
      main: '#FF6B6B', // Accent red for warnings
      light: '#FF9999',
      dark: '#CC5555',
    },
    success: {
      main: '#4CAF50',
    },
    warning: {
      main: '#FF9800',
    },
    error: {
      main: '#F44336',
    },
    background: {
      default: '#F5F7FA',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#2C3E50',
      secondary: '#5A6C7D',
    },
  },
  typography: {
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif',
    h4: {
      fontWeight: 700,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 8,
          padding: '10px 24px',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        },
      },
    },
  },
});

const steps = ['Upload Reports', 'AI Extraction', 'Reconciliation', 'Review Results'];

function App() {
  const [activeStep, setActiveStep] = useState(0);
  const [files, setFiles] = useState({
    kinderconnect: null,
    cacfp: null,
    roster: null,
  });
  const [fileIds, setFileIds] = useState({});
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState({});
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const handleFilesSelected = (uploadedFiles) => {
    setFiles(uploadedFiles);
    setError(null);
  };

  const handleStartReconciliation = async () => {
    if (!files.kinderconnect && !files.cacfp && !files.roster) {
      setError('Please upload at least one report file');
      return;
    }

    setProcessing(true);
    setActiveStep(1);
    setError(null);

    try {
      // Step 1: Upload files to backend
      const uploadedFileIds = {};

      for (const [workflow, file] of Object.entries(files)) {
        if (file) {
          const result = await uploadFile(file, workflow);
          uploadedFileIds[workflow] = result.file_id;
        }
      }

      setFileIds(uploadedFileIds);

      // Step 2: Start reconciliation job
      const { job_id } = await startReconciliation(uploadedFileIds);

      // Step 3: Stream progress
      streamJobProgress(
        job_id,
        (jobData) => {
          // Update progress
          setProgress({
            stage: jobData.stage,
            message: jobData.message,
            percent: jobData.progress,
            api_calls: jobData.api_calls,
            tool_calls: jobData.tool_calls || [],
          });

          // Update step based on stage
          if (jobData.stage === 'extraction') {
            setActiveStep(1);
          } else if (jobData.stage === 'reconciliation') {
            setActiveStep(2);
          } else if (jobData.stage === 'grading') {
            setActiveStep(3);
          }
        },
        (finalResults) => {
          // Complete
          setResults(finalResults);
          setActiveStep(4);
          setProcessing(false);
        },
        (err) => {
          // Error
          setError(err);
          setProcessing(false);
        }
      );
    } catch (err) {
      setError(err.message);
      setProcessing(false);
    }
  };

  const handleReset = () => {
    setActiveStep(0);
    setFiles({
      kinderconnect: null,
      cacfp: null,
      roster: null,
    });
    setFileIds({});
    setResults(null);
    setProgress({});
    setError(null);
    setProcessing(false);
  };

  return (
    <ThemeProvider theme={brightwheelTheme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', backgroundColor: 'background.default', py: 4 }}>
        {/* Header */}
        <Container maxWidth="lg">
          <Box sx={{ mb: 4, display: 'flex', alignItems: 'center', gap: 2 }}>
            <Box
              sx={{
                width: 48,
                height: 48,
                borderRadius: 2,
                backgroundColor: 'primary.main',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Psychology sx={{ color: 'white', fontSize: 28 }} />
            </Box>
            <Box>
              <Typography variant="h4" color="text.primary">
                Subsidy Reconciliation
              </Typography>
              <Typography variant="body2" color="text.secondary">
                AI-powered automation for brightwheel
              </Typography>
            </Box>
          </Box>

          {/* Stepper */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Stepper activeStep={activeStep}>
              {steps.map((label) => (
                <Step key={label}>
                  <StepLabel>{label}</StepLabel>
                </Step>
              ))}
            </Stepper>
          </Paper>

          {/* Error Alert */}
          {error && (
            <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {/* Content */}
          {activeStep === 0 && (
            <Paper sx={{ p: 4 }}>
              <Typography variant="h5" gutterBottom>
                Upload Subsidy Reports
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Upload KinderConnect attendance, CACFP meal counts, or enrollment roster CSV files
              </Typography>
              <FileUpload onFilesSelected={handleFilesSelected} />
              <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  variant="contained"
                  size="large"
                  startIcon={<CloudUpload />}
                  onClick={handleStartReconciliation}
                  disabled={!files.kinderconnect && !files.cacfp && !files.roster}
                >
                  Start Reconciliation
                </Button>
              </Box>
            </Paper>
          )}

          {(activeStep === 1 || activeStep === 2 || activeStep === 3) && (
            <ReconciliationProgress progress={progress} />
          )}

          {activeStep === 4 && results && (
            <ResultsView results={results} onReset={handleReset} />
          )}
        </Container>
      </Box>
    </ThemeProvider>
  );
}

export default App;

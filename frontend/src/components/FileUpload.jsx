import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Stack,
} from '@mui/material';
import {
  CloudUpload,
  InsertDriveFile,
  CheckCircle,
} from '@mui/icons-material';

const FileUpload = ({ onFilesSelected }) => {
  const [files, setFiles] = useState({
    kinderconnect: null,
    cacfp: null,
    roster: null,
  });

  const handleFileChange = (type) => (event) => {
    const file = event.target.files[0];
    if (file) {
      const newFiles = { ...files, [type]: file };
      setFiles(newFiles);
      onFilesSelected(newFiles);
    }
  };

  const uploadOptions = [
    {
      id: 'kinderconnect',
      label: 'KinderConnect Report',
      description: 'Attendance records (PDF)',
      accept: '.pdf',
    },
    {
      id: 'cacfp',
      label: 'CACFP Meal Count',
      description: 'Meal service records (PDF)',
      accept: '.pdf',
    },
    {
      id: 'roster',
      label: 'Enrollment Roster',
      description: 'Student roster (CSV)',
      accept: '.csv',
    },
  ];

  return (
    <Stack spacing={2}>
      {uploadOptions.map((option) => (
        <Card
          key={option.id}
          variant="outlined"
          sx={{
            borderColor: files[option.id] ? 'success.main' : 'divider',
            borderWidth: 2,
          }}
        >
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                {files[option.id] ? (
                  <CheckCircle color="success" />
                ) : (
                  <InsertDriveFile color="action" />
                )}
                <Box>
                  <Typography variant="subtitle1" fontWeight={600}>
                    {option.label}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {option.description}
                  </Typography>
                  {files[option.id] && (
                    <Chip
                      label={files[option.id].name}
                      size="small"
                      color="success"
                      variant="outlined"
                      sx={{ mt: 1 }}
                    />
                  )}
                </Box>
              </Box>
              <Button
                component="label"
                variant={files[option.id] ? 'outlined' : 'contained'}
                startIcon={<CloudUpload />}
              >
                {files[option.id] ? 'Change' : 'Upload'}
                <input
                  type="file"
                  hidden
                  accept={option.accept}
                  onChange={handleFileChange(option.id)}
                />
              </Button>
            </Box>
          </CardContent>
        </Card>
      ))}
    </Stack>
  );
};

export default FileUpload;

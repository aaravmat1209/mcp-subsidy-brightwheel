import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  Chip,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Divider,
} from '@mui/material';
import {
  CheckCircle,
  Warning,
  Error as ErrorIcon,
  Refresh,
  Download,
  Schedule,
  TrendingUp,
  BugReport,
  OpenInNew,
} from '@mui/icons-material';

const ResultsView = ({ results, onReset }) => {
  const workflows = results?.results || {};
  const kinderconnect = workflows.kinderconnect || {};
  const summary = kinderconnect.summary || {};

  // Parse exceptions from real orchestrator output
  const exceptionsList = kinderconnect.exceptions || [];
  const jiraTickets = kinderconnect.jira_tickets || [];
  const stagedActions = kinderconnect.staged_actions || [];
  const matchedCount = summary.matched_children || summary.matched || 0;
  const exceptionCount = summary.exception_children || summary.exceptions || 0;
  const totalCount = summary.total_students || summary.total || 0;
  const matchRate = matchedCount / (totalCount || 1);
  const timeSaved = summary.time_saved_hours || 0;

  return (
    <Box>
      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <CheckCircle color="success" fontSize="large" />
                <Typography variant="h4" fontWeight={700}>
                  {matchedCount}
                </Typography>
              </Box>
              <Typography variant="body1" fontWeight={600}>
                Records Matched
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {Math.floor(matchRate * 100)}% match rate
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Warning color="warning" fontSize="large" />
                <Typography variant="h4" fontWeight={700}>
                  {exceptionCount}
                </Typography>
              </Box>
              <Typography variant="body1" fontWeight={600}>
                Exceptions Found
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Requires manual review
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Schedule color="primary" fontSize="large" />
                <Typography variant="h4" fontWeight={700}>
                  {timeSaved.toFixed(1)}h
                </Typography>
              </Box>
              <Typography variant="body1" fontWeight={600}>
                Time Saved
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {Math.floor(matchRate * 100)}% automation rate
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Jira Tickets Auto-Created */}
      {jiraTickets && jiraTickets.length > 0 && (
        <Alert severity="success" icon={<BugReport />} sx={{ mb: 3 }}>
          <Typography variant="body1" fontWeight={600}>
            {jiraTickets.length} Jira {jiraTickets.length === 1 ? 'Ticket' : 'Tickets'} Auto-Created
          </Typography>
          <Typography variant="body2" sx={{ mt: 1, mb: 2 }}>
            HIGH/CRITICAL exceptions have been automatically logged to Jira for tracking and resolution.
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {jiraTickets.map((ticket, index) => (
              <Button
                key={index}
                size="small"
                variant="outlined"
                color="primary"
                endIcon={<OpenInNew />}
                href={ticket.url}
                target="_blank"
                rel="noopener noreferrer"
                sx={{ textTransform: 'none' }}
              >
                {ticket.issue_key}: {ticket.summary}
              </Button>
            ))}
          </Box>
        </Alert>
      )}

      {/* Staged Actions: System of Action */}
      {stagedActions && stagedActions.length > 0 && (
        <Paper sx={{ p: 3, mb: 3, border: '2px solid', borderColor: 'primary.main' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <CheckCircle color="primary" fontSize="large" />
            <Box>
              <Typography variant="h5" fontWeight={700}>
                System of Action: {stagedActions.length} Automated {stagedActions.length === 1 ? 'Action' : 'Actions'} Staged
              </Typography>
              <Typography variant="body2" color="text.secondary">
                AI has automatically staged Brightwheel actions based on reconciliation results. Review and approve below.
              </Typography>
            </Box>
          </Box>

          <Divider sx={{ my: 2 }} />

          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>
                    <Typography variant="subtitle2" fontWeight={600}>
                      Action Type
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="subtitle2" fontWeight={600}>
                      Student
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="subtitle2" fontWeight={600}>
                      Amount / Details
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="subtitle2" fontWeight={600}>
                      Reason
                    </Typography>
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {stagedActions.map((action, index) => {
                  const actionType = action.action_type;
                  const getActionLabel = (type) => {
                    if (type === 'log_agency_payment') return 'Log Payment';
                    if (type === 'bill_another_payer') return 'Bill Parent';
                    if (type === 'create_document_request') return 'Request Document';
                    return type;
                  };

                  const getActionColor = (type) => {
                    if (type === 'log_agency_payment') return 'success';
                    if (type === 'bill_another_payer') return 'warning';
                    if (type === 'create_document_request') return 'info';
                    return 'default';
                  };

                  return (
                    <TableRow key={index} hover>
                      <TableCell>
                        <Chip
                          label={getActionLabel(actionType)}
                          size="small"
                          color={getActionColor(actionType)}
                          sx={{ fontWeight: 600 }}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {action.student_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          ID: {action.student_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {action.amount && (
                          <Typography variant="body2" fontWeight={600}>
                            ${action.amount.toFixed(2)}
                          </Typography>
                        )}
                        {action.remaining_balance && (
                          <Typography variant="body2" fontWeight={600}>
                            ${action.remaining_balance.toFixed(2)}
                          </Typography>
                        )}
                        {action.document_type && (
                          <Typography variant="body2" fontWeight={600}>
                            {action.document_type}
                          </Typography>
                        )}
                        {action.invoice_id && (
                          <Typography variant="caption" color="text.secondary" display="block">
                            Invoice: {action.invoice_id}
                          </Typography>
                        )}
                        {action.payer_type && (
                          <Typography variant="caption" color="text.secondary" display="block">
                            To: {action.payer_type}
                          </Typography>
                        )}
                        {action.due_date && (
                          <Typography variant="caption" color="text.secondary" display="block">
                            Due: {action.due_date}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {action.reason || 'Reconciliation match - ready to log payment'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>

          <Box sx={{ mt: 3, p: 2, bgcolor: 'primary.light', borderRadius: 1 }}>
            <Typography variant="body2" color="primary.contrastText" sx={{ mb: 2 }}>
              <strong>What happens when you click "Approve All"?</strong>
            </Typography>
            <Typography variant="body2" color="primary.contrastText">
              • Payment logging: Updates Brightwheel invoices and marks them as paid by the state agency
              <br />
              • Balance transfers: Creates parent co-pay invoices for underpayment amounts
              <br />
              • Document requests: Sends email/notification to parents requesting updated eligibility letters
            </Typography>
          </Box>
        </Paper>
      )}

      {/* Exceptions Detail */}
      {exceptionsList && exceptionsList.length > 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h5" gutterBottom>
            Exceptions Requiring Attention
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            AI-detected discrepancies with actionable recommendations
          </Typography>

          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>
                    <Typography variant="subtitle2" fontWeight={600}>
                      Student
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="subtitle2" fontWeight={600}>
                      Severity
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="subtitle2" fontWeight={600}>
                      Issue
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="subtitle2" fontWeight={600}>
                      Recommended Action
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="subtitle2" fontWeight={600}>
                      Jira Ticket
                    </Typography>
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {exceptionsList.map((exception, index) => {
                  const severity = exception.severity || exception.exception_type || 'MEDIUM';
                  const issue = exception.action_required || exception.exceptions?.[0]?.reason || 'Exception found';

                  // Find matching Jira ticket for this exception
                  const matchingTicket = jiraTickets.find(t =>
                    t.summary.includes(exception.child_name)
                  );

                  // Map severity to chip color
                  const getSeverityColor = (sev) => {
                    if (sev === 'CRITICAL') return 'error';
                    if (sev === 'HIGH') return 'warning';
                    return 'default';
                  };

                  return (
                    <TableRow key={index}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {exception.child_name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={severity}
                          size="small"
                          color={getSeverityColor(severity)}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{issue}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          Review and update records manually
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {matchingTicket ? (
                          <Button
                            size="small"
                            variant="text"
                            color="primary"
                            endIcon={<OpenInNew />}
                            href={matchingTicket.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            sx={{ textTransform: 'none' }}
                          >
                            {matchingTicket.issue_key}
                          </Button>
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            -
                          </Typography>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* AI Insights */}
      {exceptionCount > 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h5" gutterBottom>
            AI-Generated Insights
          </Typography>

          {/* Pattern Analysis */}
          {exceptionsList.some(e => e.exception_type === 'MISSING_STUDENT') && (
            <Alert severity="error" icon={<ErrorIcon />} sx={{ mb: 2 }}>
              <Typography variant="body2" fontWeight={600}>
                Missing Students Detected
              </Typography>
              <Typography variant="body2" sx={{ mt: 1 }}>
                {exceptionsList.filter(e => e.exception_type === 'MISSING_STUDENT').length} students
                appear in KinderConnect but not in Brightwheel. This indicates enrollment synchronization
                issues. Verify that all KinderConnect enrollments are properly imported into Brightwheel.
              </Typography>
            </Alert>
          )}

          {exceptionsList.some(e => e.exception_type === 'TIME_MISMATCH') && (
            <Alert severity="warning" icon={<TrendingUp />}>
              <Typography variant="body2" fontWeight={600}>
                Time Discrepancies Detected
              </Typography>
              <Typography variant="body2" sx={{ mt: 1 }}>
                {exceptionsList.filter(e => e.exception_type === 'TIME_MISMATCH').length} students
                show attendance time differences. Review check-in/check-out times to ensure accurate
                subsidy billing.
              </Typography>
            </Alert>
          )}
        </Paper>
      )}

      {/* Actions */}
      <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
        <Button variant="outlined" startIcon={<Download />}>
          Export Audit Trail
        </Button>
        <Button variant="outlined" startIcon={<Refresh />} onClick={onReset}>
          Process New Reports
        </Button>
        <Button
          variant="contained"
          color="success"
          size="large"
          disabled={!stagedActions || stagedActions.length === 0}
          sx={{ fontWeight: 700 }}
        >
          {stagedActions && stagedActions.length > 0
            ? `Approve All (${stagedActions.length} ${stagedActions.length === 1 ? 'Action' : 'Actions'})`
            : 'No Actions to Approve'
          }
        </Button>
      </Box>
    </Box>
  );
};

export default ResultsView;

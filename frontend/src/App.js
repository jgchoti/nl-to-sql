import React, { useState } from 'react';
import {
    Container,
    Box,
    Typography,
    TextField,
    Button,
    Paper,
    Grid,
    Card,
    CardContent,
    Alert,
    CircularProgress,
    Chip,
    Divider
} from '@mui/material';
import {
    Send as SendIcon,
    PlayArrow as PlayIcon,
    Storage as DatabaseIcon,
    Code as CodeIcon,
    TableChart as TableIcon,
    CloudUpload as UploadIcon
} from '@mui/icons-material';
import axios from 'axios';

const API_BASE_URL = 'https://nl-to-sql-dhbf.onrender.com/api';

function App() {
    const [question, setQuestion] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isInitialized, setIsInitialized] = useState(false);
    const [databaseName, setDatabaseName] = useState('');
    const [currentResult, setCurrentResult] = useState(null);
    const [error, setError] = useState('');
    const [file, setFile] = useState(null);
    const [sessionId, setSessionId] = useState('');

    const downloadCSV = (results, databaseName = 'results') => {
        if (!results || results.length === 0) return;
        const headers = Object.keys(results[0]);

        const csvContent =
            [headers.join(',')]
                .concat(results.map(row => headers.map(h => `"${row[h]}"`).join(','))) // data rows
                .join('\n');

        // Create blob and download link
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${databaseName}_query_results.csv`;
        link.click();
    };

    const handleFileChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile) {
            const allowedExtensions = ['sqlite', 'db', 'csv'];
            const fileExtension = selectedFile.name.split('.').pop().toLowerCase();

            if (allowedExtensions.includes(fileExtension)) {
                setFile(selectedFile);
                setError('');
            } else {
                setError('Please select a valid file (.sqlite, .db, or .csv)');
                setFile(null);
            }
        }
    };

    const handleUpload = async () => {
        if (!file) {
            setError('Please select a file to upload');
            return;
        }

        try {
            setIsLoading(true);
            setError('');

            const formData = new FormData();
            formData.append('file', file);

            const response = await axios.post(`${API_BASE_URL}/upload`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });

            if (response.data.session_id) {
                setIsInitialized(true);
                setSessionId(response.data.session_id);
                setDatabaseName(file.name);
                setError('');
            } else {
                setError(response.data.error || 'Upload failed');
            }
        } catch (err) {
            setError('Failed to upload database. Please check if the backend is running.');
            console.error('Database upload error:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();


        if (!isInitialized || !sessionId) {
            setError('Please upload a database file first.');
            return;
        }

        if (!question.trim() || question.length < 10) {
            setError('Please ask a clearer question (at least 10 characters).');
            return;
        }

        try {
            setIsLoading(true);
            setError('');

            const response = await axios.post(`${API_BASE_URL}/get-query`, {
                session_id: sessionId,
                question: question.trim()
            });

            if (response.data.success) {
                setCurrentResult(response.data.result);
            } else {
                setError(response.data.error || 'Failed to process question.');
            }
        } catch (err) {
            setError('Failed to process question. Please try again.');
            console.error('Query error:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const runTestQuery = async (testQuestion) => {
        if (!isInitialized || !sessionId) {
            setError('Please upload a database file first.');
            return;
        }

        try {
            setIsLoading(true);
            setError('');

            const response = await axios.post(`${API_BASE_URL}/get-query`, {
                session_id: sessionId,
                question: testQuestion
            });

            if (response.data.success) {
                setCurrentResult(response.data.result);
                setQuestion(testQuestion);
            } else {
                setError(response.data.error || 'Failed to run test query.');
            }
        } catch (err) {
            setError('Failed to run test query. Please try again.');
            console.error('Test query error:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const renderResults = (result) => {
        if (!result) return null;

        return (
            <Card sx={{ mt: 3, mb: 3 }}>
                <CardContent>
                    <Typography variant="h6" gutterBottom>
                        Results for: {result?.question}
                    </Typography>

                    {result.sql_query && (
                        <>
                            <Typography variant="subtitle2" color="text.secondary" gutterBottom sx={{ mt: 2 }}>
                                Generated SQL Query:
                            </Typography>
                            <Paper
                                sx={{
                                    p: 2,
                                    bgcolor: 'grey.100',
                                    fontFamily: 'monospace',
                                    fontSize: '0.9rem',
                                    overflow: 'auto'
                                }}
                            >
                                {result.sql_query}
                            </Paper>
                        </>
                    )}

                    {result.results && result.results.length > 0 && (
                        <>
                            <Box display="flex" justifyContent="flex-end" mb={1}>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    onClick={() => downloadCSV(result.results, databaseName)}
                                >
                                    Download CSV
                                </Button>
                            </Box>

                            <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 2, mb: 1 }}>
                                Query Results ({result.row_count} rows):
                            </Typography>
                            <Paper sx={{ p: 2, overflow: 'auto', maxHeight: 400 }}>
                                <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse' }}>
                                    <thead>
                                        <tr>
                                            {Object.keys(result.results[0]).map((key) => (
                                                <th key={key} style={{
                                                    padding: '8px',
                                                    border: '1px solid #ddd',
                                                    textAlign: 'left',
                                                    backgroundColor: '#f5f5f5',
                                                    fontWeight: 'bold'
                                                }}>
                                                    {key}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {result.results.map((row, index) => (
                                            <tr key={index}>
                                                {Object.values(row).map((value, colIndex) => (
                                                    <td key={colIndex} style={{
                                                        padding: '8px',
                                                        border: '1px solid #ddd',
                                                        maxWidth: '200px',
                                                        overflow: 'hidden',
                                                        textOverflow: 'ellipsis'
                                                    }}>
                                                        {String(value || '')}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </Box>
                            </Paper>
                        </>
                    )}

                    {result.answer && (
                        <>
                            <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 2, mb: 1 }}>
                                AI Answer:
                            </Typography>
                            <Paper sx={{ p: 2, bgcolor: 'primary.50', border: '1px solid', borderColor: 'primary.200' }}>
                                <Typography>{result.answer}</Typography>
                            </Paper>
                        </>
                    )}
                </CardContent>
            </Card>
        );
    };

    const testQuestions = [
        "Show me all table names and their row counts",
        "What columns are available in the first table?",
        "Show me the first 5 rows of data",
        "What is the total number of records?"
    ];

    return (
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
            <Box textAlign="center" mb={4}>
                <Typography variant="h3" component="h1" gutterBottom>
                    <DatabaseIcon sx={{ fontSize: 40, mr: 2, verticalAlign: 'middle' }} />
                    SQL Assistant
                </Typography>
                <Typography variant="h6" color="text.secondary" gutterBottom>
                    Natural Language to SQL Query Converter
                </Typography>
            </Box>

            <Paper sx={{ p: 3, mb: 4 }}>
                <Typography variant="h6" gutterBottom>
                    Upload Database
                </Typography>

                {!isInitialized ? (
                    <Box>
                        <input
                            accept=".sqlite,.db,.csv"
                            style={{ display: 'none' }}
                            id="file-input"
                            type="file"
                            onChange={handleFileChange}
                        />
                        <label htmlFor="file-input">
                            <Button
                                variant="outlined"
                                component="span"
                                startIcon={<UploadIcon />}
                                sx={{ mr: 2 }}
                            >
                                Choose File
                            </Button>
                        </label>

                        {file && (
                            <Chip
                                label={file.name}
                                onDelete={() => setFile(null)}
                                sx={{ mr: 2 }}
                            />
                        )}

                        <Button
                            variant="contained"
                            onClick={handleUpload}
                            disabled={!file || isLoading}
                            startIcon={isLoading ? <CircularProgress size={20} /> : <UploadIcon />}
                        >
                            {isLoading ? 'Uploading...' : 'Upload'}
                        </Button>
                    </Box>
                ) : (
                    <Box>
                        <Alert severity="success" sx={{ mb: 2 }}>
                            Database "{databaseName}" uploaded successfully!
                        </Alert>
                        <Button
                            variant="outlined"
                            onClick={() => {
                                setIsInitialized(false);
                                setSessionId('');
                                setFile(null);
                                setCurrentResult(null);
                                setQuestion('');
                                setError('');
                            }}
                        >
                            Upload Different Database
                        </Button>
                    </Box>
                )}
            </Paper>

            <Grid container spacing={3}>
                <Grid item xs={12} md={8}>
                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Ask a Question
                        </Typography>
                        <form onSubmit={handleSubmit}>
                            <TextField
                                fullWidth
                                multiline
                                rows={3}
                                variant="outlined"
                                placeholder="Ask a question about your database (e.g., 'Show me the top 5 records by value')"
                                value={question}
                                onChange={(e) => setQuestion(e.target.value)}
                                disabled={isLoading || !isInitialized}
                                sx={{ mb: 2 }}
                            />
                            <Box display="flex" gap={2} flexWrap="wrap">
                                <Button
                                    type="submit"
                                    variant="contained"
                                    disabled={isLoading || !question.trim() || !isInitialized}
                                    startIcon={isLoading ? <CircularProgress size={20} /> : <SendIcon />}
                                >
                                    {isLoading ? 'Processing...' : 'Ask Question'}
                                </Button>

                                {!isInitialized && (
                                    <Chip
                                        label="Please upload a database first"
                                        color="warning"
                                        size="small"
                                    />
                                )}
                            </Box>
                        </form>
                    </Paper>

                    {error && (
                        <Alert severity="error" sx={{ mt: 2 }}>
                            {error}
                        </Alert>
                    )}

                    {currentResult && renderResults(currentResult)}
                </Grid>

                <Grid item xs={12} md={4}>
                    <Paper sx={{ p: 3, mb: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            <CodeIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                            How It Works
                        </Typography>
                        <Typography variant="body2" component="div" paragraph>
                            <ol style={{ paddingLeft: '20px' }}>
                                <li>Upload your database (.sqlite, .db, or .csv file)</li>
                                <li>Type your question in plain English</li>
                                <li>Our AI generates the appropriate SQL query</li>
                                <li>The query is executed against your database</li>
                                <li>Results are displayed with an AI explanation</li>
                            </ol>
                        </Typography>
                    </Paper>

                    <Paper sx={{ p: 3, mb: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            <TableIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                            Test Questions
                        </Typography>
                        <Typography variant="body2" component="div" sx={{ mb: 2 }}>
                            Try these sample questions to explore your data:
                        </Typography>

                        <Box>
                            {testQuestions.map((testQ, index) => (
                                <Button
                                    key={index}
                                    variant="outlined"
                                    size="small"
                                    onClick={() => runTestQuery(testQ)}
                                    disabled={isLoading || !isInitialized}
                                    sx={{
                                        mb: 1,
                                        mr: 1,
                                        textTransform: 'none',
                                        fontSize: '0.75rem'
                                    }}
                                >
                                    {testQ}
                                </Button>
                            ))}
                        </Box>
                    </Paper>

                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Example Questions
                        </Typography>
                        <Typography variant="body2" component="div">
                            <ul style={{ paddingLeft: '20px', fontSize: '0.85rem' }}>
                                <li>"Show me the top 10 records by value"</li>
                                <li>"What are the unique categories in the data?"</li>
                                <li>"Count records by status"</li>
                                <li>"Show records from last month"</li>
                                <li>"What is the average of numeric columns?"</li>
                            </ul>
                        </Typography>
                    </Paper>
                </Grid>
            </Grid>
        </Container>
    );
}

export default App;
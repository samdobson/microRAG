import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Upload, Send, Trash2, FileText } from 'lucide-react';

interface Document {
  id: string;
  filename: string;
  upload_date: string;
  chunk_count: number;
}

interface DebugInfo {
  context: string;
  full_prompt: string;
  relevant_chunks: Array<{
    content: string;
    metadata: any;
    score?: number;
  }>;
}

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  sources?: string[];
  debug_info?: DebugInfo;
}

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [debugMode, setDebugMode] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchDocuments();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API_URL}/documents`);
      setDocuments(response.data);
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };

  const handleFileUpload = async (file: File) => {
    if (!file.name.endsWith('.txt') && !file.name.endsWith('.md')) {
      setUploadError('Only .txt and .md files are supported');
      return;
    }

    setIsUploading(true);
    setUploadError('');
    setUploadSuccess('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setUploadSuccess(response.data.message);
      fetchDocuments();
      
      // Clear success message after 3 seconds
      setTimeout(() => setUploadSuccess(''), 3000);
    } catch (error: any) {
      setUploadError(error.response?.data?.detail || 'Error uploading file');
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileInput = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setIsDragging(false);
    
    const file = event.dataTransfer.files[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  const handleDeleteDocument = async (documentId: string) => {
    if (!window.confirm('Are you sure you want to delete this document?')) {
      return;
    }

    try {
      await axios.delete(`${API_URL}/documents/${documentId}`);
      fetchDocuments();
    } catch (error) {
      console.error('Error deleting document:', error);
    }
  };

  const handleSendMessage = async (event: React.FormEvent) => {
    event.preventDefault();
    
    if (!inputMessage.trim() || isLoading) {
      return;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: inputMessage.trim(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_URL}/chat`, {
        message: inputMessage.trim(),
        collection_id: null, // Let backend choose the collection
        debug: debugMode,
      });

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: response.data.response,
        sources: response.data.sources,
        debug_info: response.data.debug_info,
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error: any) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: error.response?.data?.detail || 'I encountered an error while processing your message.',
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container">
      <div className="header">
        <h1>microRAG</h1>
        <p>Upload documents and chat with them using AI</p>
      </div>

      <div className="main-content">
        <div className="sidebar">
          <div className="section-title">Documents</div>
          
          <div
            className={`upload-area ${isDragging ? 'dragging' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md"
              onChange={handleFileInput}
              className="file-input"
            />
            
            {isUploading ? (
              <div className="loading"></div>
            ) : (
              <>
                <Upload size={24} style={{ color: '#666', marginBottom: 8 }} />
                <div className="upload-text">
                  Drag & drop files here or click to upload
                </div>
                <button className="upload-button">Choose Files</button>
              </>
            )}
          </div>

          {uploadError && <div className="error">{uploadError}</div>}
          {uploadSuccess && <div className="success">{uploadSuccess}</div>}

          <div className="document-list">
            {documents.map((doc) => (
              <div key={doc.id} className="document-item">
                <div className="document-info">
                  <h4>
                    <FileText size={16} style={{ display: 'inline', marginRight: 4 }} />
                    {doc.filename}
                  </h4>
                  <p>{doc.chunk_count} chunks • {new Date(doc.upload_date).toLocaleDateString()}</p>
                </div>
                <button
                  onClick={() => handleDeleteDocument(doc.id)}
                  className="delete-button"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="chat-area">
          <div className="chat-messages">
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', color: '#666', marginTop: '40px' }}>
                <FileText size={48} style={{ color: '#ddd', marginBottom: 16 }} />
                <p>Upload some documents and start asking questions!</p>
              </div>
            )}
            
            {messages.map((message) => (
              <div key={message.id} className={`message ${message.type}`}>
                <div className="message-content">
                  {message.content}
                </div>
                {message.sources && message.sources.length > 0 && (
                  <div className="message-sources">
                    Sources: {message.sources.join(', ')}
                  </div>
                )}
                {message.debug_info && (
                  <details className="debug-info">
                    <summary>Debug Information</summary>
                    <div className="debug-section">
                      <h4>Retrieved Context:</h4>
                      <pre className="debug-text">{message.debug_info.context}</pre>
                    </div>
                    <div className="debug-section">
                      <h4>Full Prompt Sent to Model:</h4>
                      <pre className="debug-text">{message.debug_info.full_prompt}</pre>
                    </div>
                    <div className="debug-section">
                      <h4>Relevant Chunks:</h4>
                      {message.debug_info.relevant_chunks.map((chunk, index) => (
                        <div key={index} className="debug-chunk">
                          <div className="chunk-header">
                            <strong>Chunk {index + 1}</strong>
                            {chunk.score && <span className="chunk-score">Score: {chunk.score.toFixed(3)}</span>}
                            <div className="chunk-metadata">
                              File: {chunk.metadata.filename || 'Unknown'}
                            </div>
                          </div>
                          <pre className="chunk-content">{chunk.content}</pre>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            ))}
            
            {isLoading && (
              <div className="message assistant">
                <div className="message-content">
                  <div className="loading"></div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-area">
            <div className="chat-controls">
              <label className="debug-toggle">
                <input
                  type="checkbox"
                  checked={debugMode}
                  onChange={(e) => setDebugMode(e.target.checked)}
                />
                Debug Mode
              </label>
            </div>
            <form onSubmit={handleSendMessage} className="chat-input-form">
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder="Ask a question about your documents..."
                className="chat-input"
                disabled={isLoading || documents.length === 0}
              />
              <button
                type="submit"
                className="send-button"
                disabled={isLoading || !inputMessage.trim() || documents.length === 0}
              >
                {isLoading ? <div className="loading"></div> : <Send size={16} />}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;

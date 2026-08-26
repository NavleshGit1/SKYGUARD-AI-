import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          backgroundColor: '#08090E',
          color: '#F8FAFC',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'Inter, sans-serif',
          padding: '24px'
        }}>
          <div style={{
            maxWidth: '640px',
            width: '100%',
            backgroundColor: '#121624',
            border: '1px solid #FF0055',
            borderRadius: '16px',
            padding: '28px',
            boxShadow: '0 0 30px rgba(255, 0, 85, 0.25)'
          }}>
            <h2 style={{ color: '#FF0055', margin: '0 0 12px 0', fontSize: '20px', fontWeight: 'bold' }}>
              ⚠️ Dashboard Diagnostic Mode
            </h2>
            <p style={{ color: '#94A3B8', fontSize: '14px', margin: '0 0 16px 0' }}>
              {this.state.error && this.state.error.toString()}
            </p>
            <pre style={{
              backgroundColor: '#08090E',
              padding: '16px',
              borderRadius: '10px',
              color: '#00D2FF',
              fontSize: '12px',
              fontFamily: 'JetBrains Mono, monospace',
              overflow: 'auto',
              maxHeight: '220px',
              border: '1px solid rgba(0, 210, 255, 0.2)'
            }}>
              {this.state.errorInfo?.componentStack || 'No stack available'}
            </pre>
            <div style={{ marginTop: '20px', display: 'flex', gap: '12px' }}>
              <button
                onClick={() => window.location.reload()}
                style={{
                  backgroundColor: '#00D2FF',
                  color: '#08090E',
                  border: 'none',
                  padding: '10px 20px',
                  borderRadius: '10px',
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
              >
                Reload Dashboard
              </button>
              <button
                onClick={() => {
                  localStorage.clear();
                  window.location.reload();
                }}
                style={{
                  backgroundColor: 'rgba(255, 255, 255, 0.08)',
                  color: '#CBD5E1',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  padding: '10px 20px',
                  borderRadius: '10px',
                  fontWeight: '600',
                  cursor: 'pointer'
                }}
              >
                Clear Local Storage & Reset
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

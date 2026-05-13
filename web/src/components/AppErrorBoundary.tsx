import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export class AppErrorBoundary extends Component<Props, State> {
  state: State = {
    hasError: false,
    message: '',
  };

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      message: error.message || 'Unknown frontend error',
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('BOS frontend render error', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="auth-page">
          <div className="auth-card">
            <div className="auth-title">Frontend error</div>
            <div className="auth-sub" style={{ marginTop: 8 }}>
              The UI hit a render error. Hard refresh once. If it still fails, send this message:
            </div>
            <div
              style={{
                marginTop: 12,
                padding: '10px 12px',
                border: '1px solid #ddd',
                borderRadius: 6,
                background: '#fafafa',
                fontFamily: 'monospace',
                fontSize: 12,
                wordBreak: 'break-word',
              }}
            >
              {this.state.message}
            </div>
            <button className="btn btn-dark" style={{ width: '100%', marginTop: 14 }} onClick={() => window.location.reload()}>
              Reload BOS
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

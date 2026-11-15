import { Component } from 'react';
import { reportClientError } from '../utils/errorReporting';

/**
 * E12 — catches render errors so one broken screen doesn't blank the app.
 *
 * Props:
 *   resetKey  — when it changes (e.g. the route path) the boundary clears, so
 *               navigating away from a broken page recovers automatically.
 *   fullPage  — top-level variant (navbar may be gone): offers reload only.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
    this.reset = this.reset.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    reportClientError(error, { componentStack: info?.componentStack, source: 'boundary' });
  }

  componentDidUpdate(prevProps) {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.reset();
    }
  }

  reset() {
    this.setState({ error: null });
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    const { fullPage } = this.props;
    return (
      <div className="error-boundary" role="alert" style={{
        maxWidth: 560, margin: fullPage ? '15vh auto' : '3rem auto', padding: '1.5rem',
        background: 'var(--card-bg, #fff)', borderRadius: 12, borderLeft: '4px solid #c0392b',
        boxShadow: '0 2px 10px rgba(0,0,0,0.06)',
      }}>
        <h2 style={{ marginTop: 0 }}>Something went wrong on this page</h2>
        <p style={{ color: '#555' }}>
          The problem has been reported automatically. Your saved data is safe —
          {fullPage ? ' reloading usually fixes it.' : ' you can try again or go back to the dashboard.'}
        </p>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {!fullPage && <button className="btn btn-primary" onClick={this.reset}>Try again</button>}
          {!fullPage && <a className="btn btn-secondary" href="/">Go to dashboard</a>}
          <button className="btn btn-secondary" onClick={() => window.location.reload()}>Reload</button>
        </div>
        {import.meta.env.DEV && (
          <pre style={{ marginTop: '1rem', fontSize: '0.75rem', whiteSpace: 'pre-wrap', color: '#a33' }}>
            {String(error?.stack || error)}
          </pre>
        )}
      </div>
    );
  }
}

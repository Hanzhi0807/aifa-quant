import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}
interface State {
  hasError: boolean
  message: string
}

/** Route-level error boundary showing a friendly error page with retry. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('ErrorBoundary caught:', error, info)
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, message: '' })
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div className="glass-card p-8 text-center">
          <div className="text-2xl mb-2">⚠️</div>
          <div className="text-white font-medium mb-1">页面出错了</div>
          <div className="text-[var(--text-muted)] text-sm mb-4">{this.state.message}</div>
          <button
            onClick={this.handleRetry}
            className="px-4 py-2 bg-[var(--cyan)] text-black rounded-lg text-sm font-medium hover:opacity-90"
          >
            重试
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

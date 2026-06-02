import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-error-100 text-error-500 flex items-center justify-center mb-4 text-3xl">
            !
          </div>
          <h2 className="text-xl font-bold text-primary-900 mb-2">Une erreur est survenue</h2>
          <p className="text-primary-500 text-sm mb-4 max-w-md">{this.state.error?.message}</p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-4 py-2 rounded-xl bg-accent-500 text-white font-medium hover:bg-accent-600 transition-colors"
          >
            Réessayer
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

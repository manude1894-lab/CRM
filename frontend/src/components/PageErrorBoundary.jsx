import React from "react";
import { reportError } from "../utils/reportError";

// Keeps a crash inside one page from blanking the whole app (sidebar and header stay usable). The crash is
// reported to the support desk (review 22-11-2026); the reference lets a user quote it.
export default class PageErrorBoundary extends React.Component {
  state = { error: null, reference: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Page crashed:", error, info?.componentStack);
    reportError(this.props.where || "page", error, `${error?.stack || ""}\n${info?.componentStack || ""}`)
      .then((reference) => reference && this.setState({ reference }));
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="max-w-lg mx-auto mt-16 bg-white border border-red-100 rounded-xl p-6 text-center">
        <h2 className="text-base font-semibold text-gray-900">This page couldn't load</h2>
        <p className="text-sm text-gray-500 mt-1">Something went wrong while showing it. Other pages still work from the menu.</p>
        {this.state.reference && <p className="text-xs text-gray-600 mt-2">The support team has been told. Reference <span className="font-mono font-semibold">{this.state.reference}</span></p>}
        <p className="text-xs text-gray-500 mt-3 font-mono break-words">{String(this.state.error?.message || this.state.error)}</p>
        <button onClick={() => window.location.reload()}
          className="mt-4 px-4 py-2 text-sm text-white rounded-lg bg-brand-600 hover:bg-brand-700">
          Reload
        </button>
      </div>
    );
  }
}

import { Component, type ReactNode } from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ArticlesListPage } from "./pages/ArticlesListPage";
import { ArticleDetailPage } from "./pages/ArticleDetailPage";
import { AskAiPage } from "./pages/AskAiPage";

const queryClient = new QueryClient();

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return <p className="p-6 text-red-600">Something went wrong. Please reload the page.</p>;
    }
    return this.props.children;
  }
}

export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <nav className="border-b border-gray-200 p-4">
            <div className="mx-auto flex max-w-4xl gap-6">
              <Link to="/" className="font-semibold text-gray-900">
                Articles
              </Link>
              <Link to="/ask" className="font-semibold text-gray-900">
                Ask AI
              </Link>
            </div>
          </nav>
          <Routes>
            <Route path="/" element={<ArticlesListPage />} />
            <Route path="/articles/:id" element={<ArticleDetailPage />} />
            <Route path="/ask" element={<AskAiPage />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

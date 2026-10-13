import { Component, type ReactNode } from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ArticlesListPage } from "./pages/ArticlesListPage";
import { ArticleDetailPage } from "./pages/ArticleDetailPage";
import { AskAiPage } from "./pages/AskAiPage";

const queryClient = new QueryClient();

// -mb-4 + pb-4 pull each tab's underline down onto the nav's own bottom border,
// so the active marker reads as a bar on the nav edge rather than a floating rule.
const tabClass = ({ isActive }: { isActive: boolean }) =>
  `-mb-4 border-b-2 pb-4 font-semibold ${
    isActive
      ? "border-orange-600 text-orange-700"
      : "border-transparent text-gray-900 hover:text-orange-700"
  }`;

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
              {/* `end` is required: without it "/" prefix-matches every route and
                  the Articles tab would stay marked on /ask too. */}
              <NavLink to="/" end className={tabClass}>
                Articles
              </NavLink>
              <NavLink to="/ask" className={tabClass}>
                Ask AI
              </NavLink>
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

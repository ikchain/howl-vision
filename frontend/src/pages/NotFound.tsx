import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="min-h-screen bg-ocean-deep flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-content-muted mb-4">404</h1>
        <p className="text-content-secondary mb-6">Page not found</p>
        <Link to="/" className="text-teal-text hover:text-teal-light transition-colors">
          Go home
        </Link>
      </div>
    </div>
  );
}

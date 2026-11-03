import { NavLink } from "react-router-dom";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive
      ? "bg-accent-gold text-bg-deep"
      : "text-text-muted hover:text-text-primary hover:bg-bg-card"
  }`;

export function NavBar() {
  return (
    <header className="flex items-center justify-between px-6 py-3 border-b border-border-dim bg-bg-card">
      <div className="flex items-center gap-2 font-semibold text-text-primary">
        <span>🎲</span>
        <span>Baccarat Vector Match</span>
      </div>
      <nav className="flex gap-2">
        <NavLink to="/" end className={linkClass}>
          模擬器
        </NavLink>
        <NavLink to="/admin" end className={linkClass}>
          後台
        </NavLink>
        <NavLink to="/admin/derived" className={linkClass}>
          下三路後台
        </NavLink>
      </nav>
    </header>
  );
}

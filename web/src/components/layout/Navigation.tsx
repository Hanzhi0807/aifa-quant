import { Link, useLocation } from "react-router";
import { Github, Activity } from "lucide-react";

const navItems = [
  { label: "首页", path: "/" },
  { label: "回测 / 绩效", path: "/backtest" },
  { label: "数据中心", path: "/data" },
  { label: "选股报告", path: "/reports" },
];

export default function Navigation() {
  const location = useLocation();

  return (
    <nav className="nav-glass fixed top-0 left-0 right-0 z-50 h-[70px]">
      <div className="max-w-[1400px] mx-auto h-full flex items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2 group">
          <Activity className="w-6 h-6 text-[var(--cyan)]" />
          <span className="text-white font-bold text-xl tracking-wide">
            AifaQuant
          </span>
        </Link>

        <div className="flex items-center gap-1">
          {navItems.map((item) => {
            const isActive =
              item.path === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ${
                  isActive
                    ? "bg-white/10 text-[var(--cyan)]"
                    : "text-white/50 hover:text-white hover:bg-white/5"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>

        <a
          href="https://github.com/ivyzhi0807/aifa-quant"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-white/50 hover:text-white transition-colors duration-300"
        >
          <Github className="w-5 h-5" />
        </a>
      </div>
    </nav>
  );
}

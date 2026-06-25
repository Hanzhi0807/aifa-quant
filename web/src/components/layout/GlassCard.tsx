import type { ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
  action?: ReactNode;
}

export default function GlassCard({
  children,
  className = "",
  title,
  subtitle,
  action,
}: GlassCardProps) {
  return (
    <div className={`glass-card ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between mb-5">
          <div>
            {title && (
              <h3 className="text-base font-semibold text-white">{title}</h3>
            )}
            {subtitle && (
              <p className="text-sm text-[var(--text-muted)] mt-0.5">
                {subtitle}
              </p>
            )}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

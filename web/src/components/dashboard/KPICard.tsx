import { TrendingUp, TrendingDown, Minus, type LucideIcon } from "lucide-react";

interface KPICardProps {
  label: string;
  value: string;
  prefix?: string;
  suffix?: string;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  icon?: LucideIcon;
  variant?: "default" | "cyan" | "green" | "orange";
}

const variantColors = {
  default: "text-white",
  cyan: "text-[var(--cyan)]",
  green: "text-[var(--green)]",
  orange: "text-[var(--orange)]",
};

export default function KPICard({
  label,
  value,
  prefix = "",
  suffix = "",
  trend,
  trendValue,
  icon: Icon,
  variant = "default",
}: KPICardProps) {
  const TrendIcon =
    trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;

  return (
    <div className="glass-card animate-fade-in">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="kpi-label mb-2">{label}</p>
          <div className="flex items-baseline gap-1">
            {prefix && (
              <span className="text-lg text-[var(--text-muted)]">{prefix}</span>
            )}
            <span className={`kpi-value ${variantColors[variant]}`}>
              {value}
            </span>
            {suffix && (
              <span className="text-lg text-[var(--text-muted)]">{suffix}</span>
            )}
          </div>
          {trend && (
            <div className="flex items-center gap-1 mt-2">
              <TrendIcon
                className={`w-3.5 h-3.5 ${
                  trend === "up"
                    ? "text-[var(--green)]"
                    : trend === "down"
                    ? "text-[var(--red)]"
                    : "text-[var(--text-muted)]"
                }`}
              />
              {trendValue && (
                <span
                  className={`text-xs font-medium ${
                    trend === "up"
                      ? "text-[var(--green)]"
                      : trend === "down"
                      ? "text-[var(--red)]"
                      : "text-[var(--text-muted)]"
                  }`}
                >
                  {trendValue}
                </span>
              )}
            </div>
          )}
        </div>
        {Icon && (
          <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center">
            <Icon className="w-5 h-5 text-[var(--cyan)]" />
          </div>
        )}
      </div>
    </div>
  );
}

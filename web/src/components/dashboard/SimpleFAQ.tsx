import { Link } from "react-router";
import { ChevronDown, HelpCircle } from "lucide-react";
import { useState } from "react";
import GlassCard from "../layout/GlassCard";

interface FAQItem {
  question: string;
  answer: string;
  link?: { text: string; to: string };
}

interface SimpleFAQProps {
  items: FAQItem[];
}

export default function SimpleFAQ({ items }: SimpleFAQProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <GlassCard title="常见问题">
      <div className="space-y-1">
        {items.map((item, i) => {
          const isOpen = openIndex === i;
          return (
            <div
              key={i}
              className="rounded-xl overflow-hidden"
            >
              <button
                onClick={() => setOpenIndex(isOpen ? null : i)}
                className="w-full flex items-center gap-3 p-4 text-left hover:bg-white/[0.03] transition-colors"
              >
                <HelpCircle className="w-4 h-4 text-[var(--cyan)] flex-shrink-0" />
                <span className="flex-1 text-sm font-medium text-white">
                  {item.question}
                </span>
                <ChevronDown
                  className={`w-4 h-4 text-[var(--text-muted)] transition-transform duration-200 ${
                    isOpen ? "rotate-180" : ""
                  }`}
                />
              </button>
              {isOpen && (
                <div className="px-4 pb-4 pl-11">
                  <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                    {item.answer}
                  </p>
                  {item.link && (
                    <Link
                      to={item.link.to}
                      className="inline-block mt-2 text-xs text-[var(--cyan)] hover:underline"
                    >
                      {item.link.text} →
                    </Link>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}

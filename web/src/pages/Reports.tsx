import { Link } from "react-router";
import { ArrowLeft, FileText, Calendar } from "lucide-react";
import { trpc } from "@/providers/trpc";
import GlassCard from "@/components/layout/GlassCard";
import { useState } from "react";

function MarkdownRenderer({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: JSX.Element[] = [];

  let inTable = false;
  let tableRows: string[][] = [];

  const flushTable = () => {
    if (tableRows.length < 2) return;
    const headers = tableRows[0];
    const dataRows = tableRows.slice(1).filter(
      (r) => !r.every((cell) => /^[-|: ]+$/.test(cell))
    );
    elements.push(
      <div key={`table-${elements.length}`} className="overflow-x-auto my-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10">
              {headers.map((h, i) => (
                <th
                  key={i}
                  className="text-left text-xs text-[var(--text-muted)] font-medium uppercase tracking-wider pb-2 pr-4"
                >
                  {h.trim()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.map((row, ri) => (
              <tr key={ri} className="border-b border-white/[0.03]">
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className="py-2 pr-4 text-sm text-[var(--text-secondary)]"
                  >
                    {cell.trim()}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableRows = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("|")) {
      inTable = true;
      const cells = line.split("|").slice(1, -1);
      tableRows.push(cells);
      continue;
    }

    if (inTable) {
      flushTable();
      inTable = false;
    }

    if (line.startsWith("# ")) {
      elements.push(
        <h1 key={i} className="text-xl font-bold text-white mt-4 mb-2">
          {line.slice(2)}
        </h1>
      );
    } else if (line.startsWith("## ")) {
      elements.push(
        <h2 key={i} className="text-lg font-semibold text-white mt-6 mb-2">
          {line.slice(3)}
        </h2>
      );
    } else if (line.startsWith("**") && line.endsWith("**")) {
      elements.push(
        <p key={i} className="text-sm font-semibold text-white my-1">
          {line.replace(/\*\*/g, "")}
        </p>
      );
    } else if (line.startsWith("**")) {
      elements.push(
        <p key={i} className="text-sm text-[var(--text-secondary)] my-1">
          {line.replace(/\*\*/g, "")}
        </p>
      );
    } else if (line.startsWith("- ")) {
      elements.push(
        <li key={i} className="text-sm text-[var(--text-secondary)] ml-4 list-disc">
          {line.slice(2)}
        </li>
      );
    } else if (line.trim() === "") {
      continue;
    } else {
      elements.push(
        <p key={i} className="text-sm text-[var(--text-secondary)] my-1">
          {line}
        </p>
      );
    }
  }

  if (inTable) flushTable();

  return <div className="space-y-1">{elements}</div>;
}

export default function Reports() {
  const { data: reports, isLoading: listLoading } = trpc.reports.list.useQuery();
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const { data: reportData, isLoading: contentLoading } =
    trpc.reports.get.useQuery(
      { filename: selectedFile! },
      { enabled: !!selectedFile }
    );

  const reportList = reports || [];

  return (
    <div className="min-h-screen pt-[90px] pb-12 px-6">
      <div className="max-w-[1400px] mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4 animate-fade-in">
          <Link
            to="/"
            className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-[var(--text-secondary)]" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white">AI 选股报告</h1>
            <p className="text-sm text-[var(--text-secondary)]">
              每周自动生成的 AI 选股推理报告
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Report List */}
          <GlassCard title="历史报告" className="lg:col-span-1">
            {listLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-12 bg-white/5 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : reportList.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 gap-3">
                <FileText className="w-10 h-10 text-[var(--text-muted)]" />
                <p className="text-sm text-[var(--text-secondary)]">暂无报告</p>
                <p className="text-xs text-[var(--text-muted)] text-center">
                  运行{" "}
                  <code className="px-1.5 py-0.5 bg-white/5 rounded text-[var(--cyan)]">
                    aifa weekly-report
                  </code>{" "}
                  生成
                </p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {reportList.map((report) => (
                  <button
                    key={report.filename}
                    onClick={() => setSelectedFile(report.filename)}
                    className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors ${
                      selectedFile === report.filename
                        ? "bg-[var(--cyan)]/10 border border-[var(--cyan)]/30"
                        : "hover:bg-white/5"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-[var(--text-muted)]" />
                      <span className="text-sm text-white">{report.date}</span>
                    </div>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5 ml-6">
                      {report.title}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </GlassCard>

          {/* Report Content */}
          <GlassCard
            title={selectedFile ? "报告内容" : "选择报告"}
            className="lg:col-span-3"
          >
            {!selectedFile ? (
              <div className="h-[400px] flex flex-col items-center justify-center gap-3">
                <FileText className="w-12 h-12 text-[var(--text-muted)]" />
                <p className="text-sm text-[var(--text-secondary)]">
                  从左侧选择一份报告查看
                </p>
              </div>
            ) : contentLoading ? (
              <div className="h-[400px] flex items-center justify-center">
                <div className="w-8 h-8 border-2 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : !reportData?.content ? (
              <div className="h-[400px] flex flex-col items-center justify-center gap-3">
                <FileText className="w-12 h-12 text-[var(--text-muted)]" />
                <p className="text-sm text-[var(--text-secondary)]">
                  报告内容不可用
                </p>
              </div>
            ) : (
              <MarkdownRenderer content={reportData.content} />
            )}
          </GlassCard>
        </div>
      </div>
    </div>
  );
}

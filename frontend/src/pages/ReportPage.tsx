import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { getReport } from "@/api/analysisApi";
import ReportSummary from "@/components/ReportSummary";
import ScoreChart from "@/components/ScoreChart";
import SkillList from "@/components/SkillList";
import ProblemList from "@/components/ProblemList";
import SuggestionList from "@/components/SuggestionList";
import LoadingSpinner from "@/components/LoadingSpinner";
import ErrorAlert from "@/components/ErrorAlert";
import type { FullReport } from "@/types/analysis";

function asArray<T = any>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function num(value: any): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function text(value: any, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

export default function ReportPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<FullReport | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!taskId) return;
    setLoading(true);
    setError("");
    getReport(Number(taskId))
      .then((res) => setReport(res.data))
      .catch((e) => setError(e?.message || "报告加载失败"))
      .finally(() => setLoading(false));
  }, [taskId]);

  if (loading) return <LoadingSpinner text="正在加载报告..." />;
  if (error) return <ErrorAlert message={error} />;
  if (!report) return null;

  const summary: any = report.summary || {};
  const score: any = report.score_detail || {};
  const skill: any = report.skill_analysis || {};
  const matched = asArray<string>(skill.matched_skills);
  const missing = asArray<string>(skill.missing_skills);
  const recommended = asArray<string>(skill.recommended_skills_to_learn);
  const problems = asArray(report.resume_problems);
  const rewrites = asArray(report.rewrite_suggestions);
  const interviewQuestions = asArray(report.interview_questions);
  const nextSteps = asArray(report.next_steps);

  const scoreItems = [
    { label: "技能匹配", value: num(score.skill_score) },
    { label: "项目相关性", value: num(score.project_score) },
    { label: "语义相似度", value: num(score.semantic_score) },
    { label: "硬性要求", value: num(score.requirement_score) },
  ];

  const handleCopy = () => {
    const lines = [
      `得分：${num(summary.total_score).toFixed(1)}（${text(summary.match_level, "未评级")}）`,
      text(summary.one_sentence_conclusion, "暂无结论"),
      `已匹配：${matched.length ? matched.join("、") : "暂无"}`,
      `缺失：${missing.length ? missing.join("、") : "暂无"}`,
    ];
    navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">分析报告</h1>
          <p className="text-sm text-gray-500 mt-1">报告查看已做容错处理；导出 Word/PDF 使用中文字体模板。</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={handleCopy}
            className="px-4 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            {copied ? "已复制！" : "复制摘要"}
          </button>
          <a href={`/rewrite/${taskId}`} className="px-4 py-1.5 text-sm border border-purple-300 text-purple-700 rounded-lg hover:bg-purple-50 transition-colors">简历改写</a>
          <a href={`/interview/${taskId}`} className="px-4 py-1.5 text-sm border border-green-300 text-green-700 rounded-lg hover:bg-green-50 transition-colors">面试练习</a>
          <a href={`/api/v1/analysis/${taskId}/export/word`} className="px-4 py-1.5 text-sm border border-blue-300 text-blue-700 rounded-lg hover:bg-blue-50 transition-colors">导出 Word</a>
          <a href={`/api/v1/analysis/${taskId}/export/pdf`} target="_blank" rel="noreferrer" className="px-4 py-1.5 text-sm border border-primary-300 text-primary-700 rounded-lg hover:bg-primary-50 transition-colors">导出 PDF</a>
        </div>
      </div>

      <ReportSummary
        totalScore={num(summary.total_score)}
        matchLevel={text(summary.match_level, "未评级")}
        conclusion={text(summary.one_sentence_conclusion, "暂无结论")}
      />

      <Section title="评分明细">
        <ScoreChart scores={scoreItems} />
      </Section>

      <Section title="技能分析">
        <div className="grid md:grid-cols-2 gap-6">
          <SkillList title="已匹配技能" skills={matched} variant="matched" />
          <SkillList title="缺失技能" skills={missing} variant="missing" />
        </div>
        {recommended.length > 0 && (
          <div className="mt-4">
            <SkillList title="建议学习" skills={recommended} />
          </div>
        )}
      </Section>

      <Section title="简历问题">
        {problems.length ? <ProblemList problems={problems} /> : <EmptyText text="暂无明显问题，或当前报告未返回问题列表。" />}
      </Section>

      {rewrites.length > 0 && (
        <Section title="项目经历重写建议">
          <div className="space-y-4">
            {rewrites.map((r: any, i) => (
              <div key={i} className="bg-white border border-gray-200 rounded-lg p-4">
                <h4 className="font-medium text-gray-800 mb-2">{text(r.project_name, `项目 ${i + 1}`)}</h4>
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-xs font-semibold text-gray-500 mb-1">原文</p>
                    <p className="text-gray-600 whitespace-pre-line">{text(r.original_text, "暂无原文")}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-primary-600 mb-1">建议</p>
                    <p className="text-gray-800 whitespace-pre-line">{text(r.rewritten_text, "暂无建议")}</p>
                  </div>
                </div>
                {asArray<string>(r.missing_info_to_add).length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-semibold text-yellow-700 mb-1">需要补充</p>
                    <ul className="text-xs text-gray-600 space-y-1">
                      {asArray<string>(r.missing_info_to_add).map((m, j) => <li key={j}>+ {m}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {interviewQuestions.length > 0 && (
        <Section title="面试问题预览">
          <div className="space-y-3">
            {interviewQuestions.map((q: any, i) => (
              <div key={i} className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600 font-medium">{text(q.question_type, "question")}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700">{text(q.difficulty, "medium")}</span>
                </div>
                <p className="text-sm font-medium text-gray-800">{text(q.question, "暂无题目")}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="下一步建议">
        {nextSteps.length ? <SuggestionList title="" items={nextSteps} /> : <EmptyText text="暂无下一步建议。" />}
      </Section>
    </div>
  );
}

function EmptyText({ text }: { text: string }) {
  return <p className="text-sm text-gray-500 bg-gray-50 border border-gray-200 rounded-lg p-4">{text}</p>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-lg font-bold text-gray-800 mb-4 pb-2 border-b border-gray-200">{title}</h2>
      {children}
    </div>
  );
}

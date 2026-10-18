import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { deleteAnalysisTask, runAnalysis } from "@/api/analysisApi";
import { deleteResume, listResumes, type ResumeListItem } from "@/api/resumeApi";
import { deleteJD, listJDs, type JDListItem } from "@/api/jdApi";
import ScoreCard from "@/components/ScoreCard";
import SkillList from "@/components/SkillList";
import LoadingSpinner from "@/components/LoadingSpinner";
import ErrorAlert from "@/components/ErrorAlert";
import type { AnalysisResultData, AnalysisHistoryItem } from "@/types/analysis";
import client from "@/api/client";

export default function AnalysisPage() {
  const navigate = useNavigate();

  const [resumes, setResumes] = useState<ResumeListItem[]>([]);
  const [jds, setJds] = useState<JDListItem[]>([]);
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [selectedJdId, setSelectedJdId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [result, setResult] = useState<AnalysisResultData | null>(null);
  const [history, setHistory] = useState<AnalysisHistoryItem[]>([]);

  const refreshHistory = useCallback(async () => {
    const res: any = await client.get("/analysis/history/list");
    setHistory(res.data || []);
  }, []);

  const refreshResumes = useCallback(async () => {
    const res = await listResumes();
    const list = res.data || [];
    setResumes(list);
    setSelectedResumeId((current) => {
      const latestId = Number(localStorage.getItem("latest_resume_id") || 0);
      if (current && list.some((r) => r.id === current)) return current;
      if (latestId && list.some((r) => r.id === latestId)) return latestId;
      return list[0]?.id || null;
    });
  }, []);

  const refreshJds = useCallback(async () => {
    const res = await listJDs();
    const list = res.data || [];
    setJds(list);
    setSelectedJdId((current) => {
      const latestId = Number(localStorage.getItem("latest_jd_id") || 0);
      if (current && list.some((j) => j.id === current)) return current;
      if (latestId && list.some((j) => j.id === latestId)) return latestId;
      return list[0]?.id || null;
    });
  }, []);

  const refreshAll = useCallback(async () => {
    setError("");
    await Promise.allSettled([refreshResumes(), refreshJds(), refreshHistory()]);
  }, [refreshHistory, refreshJds, refreshResumes]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const handleRun = async () => {
    if (!selectedResumeId || !selectedJdId) {
      setError("请先选择一份简历和一个岗位");
      return;
    }
    setLoading(true);
    setError("");
    setSuccess("");
    setResult(null);
    try {
      const res = await runAnalysis({ resume_id: selectedResumeId, jd_id: selectedJdId });
      setResult(res.data);
      await refreshHistory();
    } catch (e: any) {
      setError(e.message || "分析失败");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteResume = async (resume: ResumeListItem) => {
    if (!window.confirm(`确定删除简历「${resume.filename}」吗？相关分析、改写和面试记录也会一起删除。`)) return;
    setDeleting(true);
    setError("");
    setSuccess("");
    try {
      await deleteResume(resume.id);
      if (selectedResumeId === resume.id) setSelectedResumeId(null);
      if (localStorage.getItem("latest_resume_id") === String(resume.id)) {
        localStorage.removeItem("latest_resume_id");
        localStorage.removeItem("latest_resume_filename");
      }
      setResult(null);
      await refreshAll();
      setSuccess("简历已删除，相关分析记录已清理。");
    } catch (e: any) {
      setError(e.message || "删除简历失败");
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteJd = async (jd: JDListItem) => {
    if (!window.confirm(`确定删除岗位「${jd.title || "未命名岗位"}」吗？相关分析、改写和面试记录也会一起删除。`)) return;
    setDeleting(true);
    setError("");
    setSuccess("");
    try {
      await deleteJD(jd.id);
      if (selectedJdId === jd.id) setSelectedJdId(null);
      if (localStorage.getItem("latest_jd_id") === String(jd.id)) {
        localStorage.removeItem("latest_jd_id");
        localStorage.removeItem("latest_jd_title");
      }
      setResult(null);
      await refreshAll();
      setSuccess("岗位已删除，相关分析记录已清理。");
    } catch (e: any) {
      setError(e.message || "删除岗位失败");
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteAnalysis = async (item: AnalysisHistoryItem) => {
    if (!window.confirm(`确定删除这条分析记录 #${item.task_id} 吗？对应的改写简历和面试记录也会一起删除。`)) return;
    setDeleting(true);
    setError("");
    setSuccess("");
    try {
      await deleteAnalysisTask(item.task_id);
      if (result?.task_id === item.task_id) setResult(null);
      await refreshHistory();
      setSuccess("分析记录已删除。");
    } catch (e: any) {
      setError(e.message || "删除分析记录失败");
    } finally {
      setDeleting(false);
    }
  };

  const selectedResume = resumes.find((r) => r.id === selectedResumeId);
  const selectedJd = jds.find((j) => j.id === selectedJdId);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">匹配分析</h1>
        <p className="text-sm text-gray-500 mt-1">选择简历和岗位后分析匹配度；候选区和历史记录现在支持删除清理。</p>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <PoolCard
          title="简历候选区"
          actionText="+ 上传新简历"
          onAction={() => navigate("/upload")}
          emptyText="暂无简历，请先上传"
        >
          {resumes.map((r) => (
            <div key={r.id} className={`flex items-start gap-2 rounded-lg border p-2 text-sm transition-colors ${selectedResumeId === r.id ? "border-primary-500 bg-primary-50" : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"}`}>
              <button type="button" onClick={() => setSelectedResumeId(r.id)} className="min-w-0 flex-1 text-left">
                <p className={`font-medium truncate ${selectedResumeId === r.id ? "text-primary-700" : "text-gray-900"}`}>{r.filename}</p>
                <p className="text-xs text-gray-400 truncate mt-0.5">{r.text_preview || "无预览"}</p>
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={() => handleDeleteResume(r)}
                className="shrink-0 rounded-md border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                删除
              </button>
            </div>
          ))}
        </PoolCard>

        <PoolCard
          title="岗位候选区"
          actionText="+ 导入岗位"
          onAction={() => navigate("/jd")}
          emptyText="暂无岗位，请先导入"
        >
          {jds.map((j) => (
            <div key={j.id} className={`flex items-start gap-2 rounded-lg border p-2 text-sm transition-colors ${selectedJdId === j.id ? "border-primary-500 bg-primary-50" : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"}`}>
              <button type="button" onClick={() => setSelectedJdId(j.id)} className="min-w-0 flex-1 text-left">
                <p className={`font-medium truncate ${selectedJdId === j.id ? "text-primary-700" : "text-gray-900"}`}>{j.title || "未命名岗位"}</p>
                <p className="text-xs text-gray-400 truncate mt-0.5">{j.company || "未知公司"} · {j.source}</p>
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={() => handleDeleteJd(j)}
                className="shrink-0 rounded-md border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                删除
              </button>
            </div>
          ))}
        </PoolCard>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="grid md:grid-cols-2 gap-4 mb-4">
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
            <p className="text-xs text-gray-500">已选简历</p>
            <p className="font-semibold text-gray-900 truncate text-sm">{selectedResume?.filename || "未选择"}</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
            <p className="text-xs text-gray-500">已选岗位</p>
            <p className="font-semibold text-gray-900 truncate text-sm">{selectedJd ? `${selectedJd.title}${selectedJd.company ? ` - ${selectedJd.company}` : ""}` : "未选择"}</p>
          </div>
        </div>
        <button
          onClick={handleRun}
          disabled={loading || !selectedResumeId || !selectedJdId}
          className="px-6 py-2.5 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "分析中..." : "开始分析匹配"}
        </button>
      </div>

      {loading && <LoadingSpinner text="正在调用 DeepSeek 进行匹配分析..." />}
      {error && <ErrorAlert message={error} />}
      {success && <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{success}</div>}

      {result && <AnalysisResult result={result} navigate={navigate} />}

      {history.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900">历史分析记录</h3>
            <span className="text-xs text-gray-400">可单条删除，不再一直堆积</span>
          </div>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {history.map((item) => (
              <div key={item.task_id} className="flex items-center gap-2 rounded-lg border border-gray-200 p-2">
                <button onClick={() => navigate(`/report/${item.task_id}`)} className="min-w-0 flex-1 text-left text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-900 truncate">{item.jd_title || "未命名岗位"}{item.jd_company ? ` - ${item.jd_company}` : ""}</p>
                      <p className="text-xs text-gray-400 mt-0.5">#{item.task_id} | 简历: {item.resume_filename || `#${item.resume_id}`}</p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className={`text-sm font-bold ${item.total_score >= 75 ? "text-green-600" : item.total_score >= 60 ? "text-yellow-600" : "text-red-500"}`}>{item.total_score?.toFixed(1) ?? "—"} 分</span>
                      <span className="text-xs text-gray-400">{item.match_level || ""}</span>
                    </div>
                  </div>
                </button>
                <button onClick={() => navigate(`/rewrite/${item.task_id}`)} className="px-2 py-2 text-xs text-purple-600 border border-purple-200 rounded-lg hover:bg-purple-50 transition-colors shrink-0">改写</button>
                <button onClick={() => navigate(`/interview/${item.task_id}`)} className="px-2 py-2 text-xs text-green-600 border border-green-200 rounded-lg hover:bg-green-50 transition-colors shrink-0">面试</button>
                <button onClick={() => handleDeleteAnalysis(item)} disabled={deleting} className="px-2 py-2 text-xs text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors shrink-0 disabled:opacity-50">删除</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PoolCard({ title, actionText, onAction, emptyText, children }: { title: string; actionText: string; onAction: () => void; emptyText: string; children: ReactNode }) {
  const hasChildren = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900">{title}</h3>
        <button onClick={onAction} className="text-xs text-primary-600 hover:text-primary-700">{actionText}</button>
      </div>
      {!hasChildren ? <p className="text-sm text-gray-400 py-4 text-center">{emptyText}</p> : <div className="space-y-2 max-h-56 overflow-y-auto">{children}</div>}
    </div>
  );
}

function AnalysisResult({ result, navigate }: { result: AnalysisResultData; navigate: (path: string) => void }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <ScoreCard label="总分" score={result.total_score} />
        <ScoreCard label="技能匹配" score={result.score_detail.skill_score} reason={result.score_detail.skill_reason} />
        <ScoreCard label="项目相关性" score={result.score_detail.project_score} reason={result.score_detail.project_reason} />
        <ScoreCard label="语义相关度" score={result.score_detail.semantic_score} reason={result.score_detail.semantic_reason} />
      </div>
      <AIAnalysisPanel ai={result.ai_analysis} />
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border border-gray-200 p-5"><SkillList title="已匹配技能" skills={result.matched_skills} variant="matched" /></div>
        <div className="bg-white rounded-lg border border-gray-200 p-5"><SkillList title="缺失技能" skills={result.missing_skills} variant="missing" /></div>
      </div>
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <p className="text-sm text-gray-600">发现 <span className="font-bold text-gray-800">{result.problems.length}</span> 个问题和 <span className="font-bold text-gray-800">{result.suggestions.length}</span> 条建议。</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <button onClick={() => navigate(`/report/${result.task_id}`)} className="px-6 py-2.5 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 transition-colors">查看完整报告</button>
        <button onClick={() => navigate(`/rewrite/${result.task_id}`)} className="px-6 py-2.5 bg-white border border-purple-300 text-purple-700 font-medium rounded-lg hover:bg-purple-50 transition-colors">简历改写</button>
        <button onClick={() => navigate(`/interview/${result.task_id}`)} className="px-6 py-2.5 bg-white border border-green-300 text-green-700 font-medium rounded-lg hover:bg-green-50 transition-colors">面试练习</button>
      </div>
    </div>
  );
}

function AIAnalysisPanel({ ai }: { ai: any }) {
  if (!ai) return null;
  const used = Boolean(ai.used_ai);
  return (
    <div className="bg-white rounded-lg border border-purple-200 p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">AI 深度分析</h3>
          <p className="text-xs text-gray-500 mt-1">{used ? `已调用 ${ai.provider || "LLM"} / ${ai.model || "model"}` : "当前未调用真实AI，显示规则兜底结果"}</p>
        </div>
        <span className={`text-xs px-2 py-1 rounded-full ${used ? "bg-green-50 text-green-700" : "bg-yellow-50 text-yellow-700"}`}>{used ? "AI已调用" : "规则兜底"}</span>
      </div>
      {ai.overall_conclusion && <div className="rounded-lg bg-purple-50 border border-purple-100 p-3"><p className="text-sm font-medium text-purple-900">结论</p><p className="text-sm text-purple-800 mt-1 whitespace-pre-wrap">{ai.overall_conclusion}</p></div>}
      {ai.match_positioning && <div><p className="text-sm font-semibold text-gray-800 mb-1">匹配定位</p><p className="text-sm text-gray-700 whitespace-pre-wrap">{ai.match_positioning}</p></div>}
      <div className="grid md:grid-cols-2 gap-4">
        <InfoList title="核心优势" items={ai.key_strengths} render={(x: any) => `${x.title || "优势"}：${x.evidence || ""}${x.why_relevant ? `；${x.why_relevant}` : ""}`} />
        <InfoList title="主要差距" items={ai.core_gaps} render={(x: any) => `${x.gap || "差距"}：${x.impact || ""}${x.fix_strategy ? `；建议：${x.fix_strategy}` : ""}`} />
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        <PlainList title="简历改写重点" items={ai.resume_rewrite_strategy || []} />
        <PlainList title="面试风险" items={ai.interview_risks || []} />
        <PlainList title="需提前准备" items={ai.questions_to_prepare || []} />
      </div>
      {Array.isArray(ai.action_plan) && ai.action_plan.length > 0 && <div><p className="text-sm font-semibold text-gray-800 mb-2">下一步行动</p><div className="space-y-2">{ai.action_plan.map((item: any, i: number) => <div key={i} className="text-sm border border-gray-100 rounded-lg p-3 bg-gray-50"><p className="font-medium text-gray-900">{item.priority ? `${item.priority}. ` : ""}{item.action || item.title || "行动"}</p>{(item.reason || item.expected_result) && <p className="text-gray-600 mt-1">{item.reason || ""}{item.expected_result ? ` → ${item.expected_result}` : ""}</p>}</div>)}</div></div>}
    </div>
  );
}

function InfoList({ title, items, render }: { title: string; items: any[]; render: (x: any) => string }) {
  if (!Array.isArray(items) || items.length === 0) return null;
  return <div><p className="text-sm font-semibold text-gray-800 mb-2">{title}</p><ul className="space-y-2">{items.slice(0, 6).map((item, i) => <li key={i} className="text-sm text-gray-700 bg-gray-50 rounded-lg p-2">{render(item)}</li>)}</ul></div>;
}

function PlainList({ title, items }: { title: string; items: string[] }) {
  if (!Array.isArray(items) || items.length === 0) return null;
  return <div><p className="text-sm font-semibold text-gray-800 mb-2">{title}</p><ul className="space-y-1.5">{items.slice(0, 6).map((item, i) => <li key={i} className="text-sm text-gray-700 list-disc ml-4">{item}</li>)}</ul></div>;
}

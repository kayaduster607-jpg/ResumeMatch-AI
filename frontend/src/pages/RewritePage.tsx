import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import {
  generateFullRewrite,
  getFullRewrite,
  saveEditedRewrite,
  exportFullRewritePdfUrl,
} from "@/api/analysisApi";
import type { FullRewriteData } from "@/api/analysisApi";
import LoadingSpinner from "@/components/LoadingSpinner";
import ErrorAlert from "@/components/ErrorAlert";

export default function RewritePage() {
  const { taskId } = useParams<{ taskId: string }>();
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<FullRewriteData | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editedText, setEditedText] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Load existing rewrite on mount
  useEffect(() => {
    if (!taskId) return;
    setLoading(true);
    getFullRewrite(Number(taskId))
      .then((res) => {
        if (res.success && res.data) {
          setData(res.data);
          setEditedText(res.data.full_text);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [taskId]);

  const handleGenerate = async () => {
    if (!taskId) return;
    setGenerating(true);
    setError("");
    try {
      const res = await generateFullRewrite(Number(taskId));
      if (res.success && res.data) {
        setData(res.data);
        setEditedText(res.data.full_text);
      } else {
        setError(res.message || "生成失败");
      }
    } catch (e: any) {
      setError(e.message || "生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!taskId) return;
    setSaving(true);
    try {
      await saveEditedRewrite(Number(taskId), editedText);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: any) {
      setError(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleExportPdf = () => {
    if (!taskId) return;
    window.open(exportFullRewritePdfUrl(Number(taskId)), "_blank");
  };

  const handleExportWord = () => {
    window.open(`/api/v1/analysis/${taskId}/export/word`, "_blank");
  };

  const handleExportTxt = () => {
    const text = editMode ? editedText : data?.full_text || "";
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rewritten_resume_${taskId}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <LoadingSpinner text="加载中..." />;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">简历改写</h1>
        <div className="flex gap-2">
          <Link
            to={`/report/${taskId}`}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            返回报告
          </Link>
          <Link
            to={`/interview/${taskId}`}
            className="px-3 py-1.5 text-sm border border-green-300 text-green-700 rounded-lg hover:bg-green-50"
          >
            面试练习
          </Link>
        </div>
      </div>

      {error && <ErrorAlert message={error} />}

      {/* Generate button (if no data yet) */}
      {!data && !generating && (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <div className="text-5xl mb-4">📝</div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">
            AI 简历改写
          </h2>
          <p className="text-gray-500 mb-6 max-w-md mx-auto">
            根据目标岗位 JD 智能改写简历，突出匹配技能，优化项目描述，标注待补充信息。
          </p>
          <button
            onClick={handleGenerate}
            className="px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium"
          >
            开始改写
          </button>
        </div>
      )}

      {generating && (
        <div className="text-center py-16">
          <LoadingSpinner text="AI 正在改写简历，请稍候..." />
        </div>
      )}

      {/* Rewrite result */}
      {data && (
        <>
          {/* Job target info */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-gray-800">
                目标岗位: {data.job_title}
              </h2>
              {data.target_company && (
                <span className="text-sm text-gray-500">
                  {data.target_company}
                </span>
              )}
            </div>
            {data.changes_summary && (
              <p className="text-sm text-gray-600">{data.changes_summary}</p>
            )}
            {data.highlights.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {data.highlights.map((h, i) => (
                  <span
                    key={i}
                    className="text-xs px-2 py-1 bg-primary-50 text-primary-700 rounded-full"
                  >
                    {h}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Rewrite strategy and quality gate */}
          {(data.rewrite_strategy || (data.quality_gate && data.quality_gate.length > 0)) && (
            <div className="bg-white rounded-xl border border-blue-100 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-blue-700">改写策略与质量检查</h3>
                <span className="text-xs text-gray-400">基于岗位需求 + 简历事实证据生成</span>
              </div>

              {data.rewrite_strategy && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-xs font-semibold text-gray-500 mb-1">目标岗位建模</div>
                    <div className="text-gray-800 mb-2">{data.rewrite_strategy.target_role}</div>
                    <div className="flex flex-wrap gap-1">
                      {data.rewrite_strategy.role_requirements?.slice(0, 8).map((x, i) => (
                        <span key={i} className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 rounded-full">{x}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-gray-500 mb-1">改写规则</div>
                    <ul className="text-xs text-gray-600 list-disc pl-4 space-y-1">
                      <li>{data.rewrite_strategy.project_style}</li>
                      {data.rewrite_strategy.tech_stack_rules?.slice(0, 1).map((x, i) => <li key={`t-${i}`}>{x}</li>)}
                      {data.rewrite_strategy.quantification_rules?.slice(0, 1).map((x, i) => <li key={`q-${i}`}>{x}</li>)}
                    </ul>
                  </div>
                </div>
              )}

              {data.quality_gate && data.quality_gate.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {data.quality_gate.map((g, i) => (
                    <span
                      key={i}
                      title={g.message}
                      className={`px-2 py-1 rounded-full text-xs border ${
                        g.status === "passed"
                          ? "bg-green-50 text-green-700 border-green-100"
                          : g.status === "failed"
                          ? "bg-red-50 text-red-700 border-red-100"
                          : "bg-orange-50 text-orange-700 border-orange-100"
                      }`}
                    >
                      {g.name}: {g.status === "passed" ? "通过" : g.status === "failed" ? "失败" : "需确认"}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Toolbar */}
          <div className="flex items-center justify-between">
            <div className="flex gap-2">
              <button
                onClick={() => setEditMode(!editMode)}
                className={`px-4 py-1.5 text-sm rounded-lg transition-colors ${
                  editMode
                    ? "bg-primary-600 text-white"
                    : "border border-primary-300 text-primary-700 hover:bg-primary-50"
                }`}
              >
                {editMode ? "预览模式" : "编辑模式"}
              </button>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-4 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                重新生成
              </button>
            </div>
            <div className="flex gap-2">
              {editMode && (
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-4 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                >
                  {saving ? "保存中..." : saved ? "已保存！" : "保存修改"}
                </button>
              )}
              <button
                onClick={handleExportTxt}
                className="px-4 py-1.5 text-sm border border-blue-300 text-blue-700 rounded-lg hover:bg-blue-50 transition-colors"
              >
                导出 TXT
              </button>
              <button
                onClick={handleExportPdf}
                className="px-4 py-1.5 text-sm border border-red-300 text-red-700 rounded-lg hover:bg-red-50 transition-colors"
              >
                导出 PDF
              </button>
              <button
                onClick={handleExportWord}
                className="px-4 py-1.5 text-sm border border-primary-300 text-primary-700 rounded-lg hover:bg-primary-50 transition-colors"
              >
                导出 Word
              </button>
            </div>
          </div>

          {/* Content */}
          {editMode ? (
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <textarea
                value={editedText}
                onChange={(e) => setEditedText(e.target.value)}
                className="w-full h-[600px] font-mono text-sm text-gray-800 leading-relaxed resize-none focus:outline-none"
                placeholder="编辑简历内容..."
              />
            </div>
          ) : (
            <div className="space-y-6">
              {/* Summary */}
              {data.summary && (
                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <h3 className="text-sm font-semibold text-gray-500 mb-2">
                    个人简介
                  </h3>
                  <p className="text-gray-800 leading-relaxed">
                    {data.summary}
                  </p>
                </div>
              )}

              {/* Sections */}
              {data.sections.map((sec, i) => (
                <div
                  key={i}
                  className="bg-white rounded-xl border border-gray-200 p-5"
                >
                  <h3 className="text-sm font-semibold text-primary-700 mb-3 pb-2 border-b border-gray-100">
                    {sec.title}
                  </h3>
                  <div className="text-sm text-gray-800 leading-relaxed whitespace-pre-line">
                    {sec.content}
                  </div>
                </div>
              ))}

              {/* Full text preview */}
              <div className="bg-gray-50 rounded-xl border border-gray-200 p-5">
                <h3 className="text-sm font-semibold text-gray-500 mb-3">
                  完整简历预览
                </h3>
                <pre className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap font-sans">
                  {data.full_text}
                </pre>
              </div>

              {/* Evidence Chain */}
              {data.evidence_chain && data.evidence_chain.length > 0 && (
                <div className="bg-white rounded-xl border border-green-200 p-5">
                  <h3 className="text-sm font-semibold text-green-700 mb-3 flex items-center gap-2">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    证据链（改写依据）
                  </h3>
                  <p className="text-xs text-gray-500 mb-4">
                    简历证据 = 我真的做过 | JD 证据 = 岗位需要什么（仅方向，不证明经历）
                  </p>
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {data.evidence_chain.map((item, i) => (
                      <div
                        key={i}
                        className={`border rounded-lg p-3 text-sm ${
                          item.fabrication_check === "warning" || item.risk === "high"
                            ? "border-orange-200 bg-orange-50"
                            : item.risk === "medium"
                            ? "border-yellow-100 bg-yellow-50"
                            : "border-gray-200 bg-gray-50"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <p className="text-gray-800 font-medium flex-1">
                            {item.rewritten_bullet}
                          </p>
                          {item.need_manual_confirm && (
                            <span className="shrink-0 px-1.5 py-0.5 bg-orange-100 text-orange-700 rounded text-[10px]">
                              需人工确认
                            </span>
                          )}
                        </div>

                        {/* Resume evidence */}
                        {item.resume_evidence.length > 0 && (
                          <div className="mb-2">
                            <span className="text-[10px] font-semibold text-green-600 bg-green-50 px-1.5 py-0.5 rounded">
                              简历事实证据
                            </span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {item.resume_evidence.map((ev, j) => (
                                <span
                                  key={j}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-50 border border-green-100 rounded text-xs text-gray-600"
                                >
                                  <span className="font-mono text-[10px] text-green-600">
                                    {ev.source_type.replace("resume_", "")}
                                  </span>
                                  <span className="text-gray-400">|</span>
                                  <span>{ev.field}</span>
                                  <span className="text-[10px] text-gray-400 ml-1">
                                    ({(ev.confidence * 100).toFixed(0)}%)
                                  </span>
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* JD evidence */}
                        {item.jd_evidence.length > 0 && (
                          <div className="mb-2">
                            <span className="text-[10px] font-semibold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                              JD 需求证据
                            </span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {item.jd_evidence.map((ev, j) => (
                                <span
                                  key={j}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 border border-blue-100 rounded text-xs text-gray-500"
                                >
                                  <span className="font-mono text-[10px] text-blue-500">
                                    {ev.source_type}
                                  </span>
                                  <span className="text-gray-400">|</span>
                                  <span>{ev.field}</span>
                                  <span className="text-[10px] text-gray-400 ml-1">
                                    ({(ev.confidence * 100).toFixed(0)}%)
                                  </span>
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {!item.resume_evidence.length && !item.jd_evidence.length && (
                          <p className="text-xs text-gray-400 italic">无证据来源</p>
                        )}

                        <div className="flex gap-3 text-xs mt-2 pt-2 border-t border-gray-100">
                          <span
                            className={`px-1.5 py-0.5 rounded-full ${
                              item.risk === "low"
                                ? "bg-green-100 text-green-700"
                                : item.risk === "medium"
                                ? "bg-yellow-100 text-yellow-700"
                                : "bg-red-100 text-red-700"
                            }`}
                          >
                            风险: {item.risk === "low" ? "低" : item.risk === "medium" ? "中" : "高"}
                          </span>
                          <span
                            className={`px-1.5 py-0.5 rounded-full ${
                              item.fabrication_check === "passed"
                                ? "bg-green-100 text-green-700"
                                : "bg-orange-100 text-orange-700"
                            }`}
                          >
                            编造检查: {item.fabrication_check === "passed" ? "通过" : "警告"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

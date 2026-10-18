import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import { getInterviewQuestions } from "@/api/analysisApi";
import { startInterview, chatInterview, finishInterview, type InterviewChatMessage, type InterviewStartData, type InterviewSummaryData } from "@/api/interviewApi";
import QuestionCard from "@/components/QuestionCard";
import AnswerScorePanel from "@/components/AnswerScorePanel";
import LoadingSpinner from "@/components/LoadingSpinner";
import ErrorAlert from "@/components/ErrorAlert";
import client from "@/api/client";
import type { AnalysisHistoryItem, InterviewQuestionItem } from "@/types/analysis";

export default function InterviewPage() {
  const { taskId: urlTaskId } = useParams<{ taskId: string }>();
  const [taskId, setTaskId] = useState(urlTaskId || "");
  const [useRewrittenResume, setUseRewrittenResume] = useState(true);
  const [history, setHistory] = useState<AnalysisHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [error, setError] = useState("");
  const [session, setSession] = useState<InterviewStartData | null>(null);
  const [messages, setMessages] = useState<InterviewChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [questions, setQuestions] = useState<InterviewQuestionItem[]>([]);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [round, setRound] = useState(0);
  const [finished, setFinished] = useState(false);
  const [summary, setSummary] = useState<InterviewSummaryData | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    client.get("/analysis/history/list").then((res: any) => {
      setHistory(res.data || []);
      if (!urlTaskId && res.data?.[0]?.task_id) setTaskId(String(res.data[0].task_id));
    }).catch(() => {});
  }, [urlTaskId]);

  useEffect(() => {
    if (urlTaskId) {
      setTaskId(urlTaskId);
      handleStart(Number(urlTaskId));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlTaskId]);

  const handleStart = async (id?: number) => {
    const targetId = id || Number(taskId);
    if (!targetId) {
      setError("请先选择一条分析记录。");
      return;
    }
    setLoading(true);
    setError("");
    setQuestions([]);
    setSelectedIdx(null);
    setMessages([]);
    setRound(0);
    setFinished(false);
    setSummary(null);
    try {
      const res = await startInterview({ task_id: targetId, use_rewritten_resume: useRewrittenResume });
      setSession(res.data);
      setMessages([{ role: "assistant", content: res.data.first_question }]);
      const qRes = await getInterviewQuestions(targetId);
      setQuestions(qRes.data.questions || []);
    } catch (e: any) {
      setError(e.message || "启动模拟面试失败。");
    } finally {
      setLoading(false);
    }
  };

  const handle发送 = async () => {
    const targetId = Number(taskId);
    if (!targetId || !input.trim()) return;
    const userMsg: InterviewChatMessage = { role: "user", content: input.trim() };
    const nextHistory = [...messages, userMsg];
    setMessages(nextHistory);
    setInput("");
    setChatLoading(true);
    setError("");
    try {
      const res = await chatInterview({
        task_id: targetId,
        message: userMsg.content,
        history: nextHistory.slice(-12),
        use_rewritten_resume: useRewrittenResume,
      });
      setMessages([...nextHistory, { role: "assistant", content: res.data.assistant_message }]);
      setRound((r) => r + 1);
    } catch (e: any) {
      setError(e.message || "获取面试反馈失败。");
    } finally {
      setChatLoading(false);
    }
  };

  const handleEndInterview = async () => {
    const targetId = Number(taskId);
    if (!targetId) return;
    setSummaryLoading(true);
    setError("");
    try {
      const res = await finishInterview({
        task_id: targetId,
        history: messages,
        use_rewritten_resume: useRewrittenResume,
      });
      setSummary(res.data);
      setFinished(true);
    } catch (e: any) {
      setError(e.message || "生成面试总结失败。");
    } finally {
      setSummaryLoading(false);
    }
  };

  const selected = selectedIdx !== null ? questions[selectedIdx] : null;

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">AI 模拟面试</h1>
        <p className="text-sm text-gray-500 mt-1">
          选择分析记录后开始多轮模拟面试，回答完所有问题后点击"结束面试"查看全面总结。
        </p>
      </div>

      {/* Session Setup - compact */}
      {!session && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 mb-1">分析记录</label>
              <select
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                value={taskId}
                onChange={(e) => setTaskId(e.target.value)}
              >
                <option value="">-- 请选择 --</option>
                {history.map((h) => (
                  <option key={h.task_id} value={h.task_id}>
                    #{h.task_id} | {h.jd_title}{h.jd_company ? ` - ${h.jd_company}` : ""} | {h.total_score?.toFixed(1)} 分
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={useRewrittenResume} onChange={(e) => setUseRewrittenResume(e.target.checked)} />
              使用改写简历
            </label>
            <button onClick={() => handleStart()} disabled={loading || !taskId}
              className="px-6 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50">
              {loading ? "启动中..." : "开始模拟面试"}
            </button>
          </div>
        </div>
      )}

      {loading && <LoadingSpinner />}
      {error && <ErrorAlert message={error} />}

      {/* Session active - tips bar */}
      {session && !finished && (
        <div className="flex flex-wrap gap-2 text-xs">
          {session.tips?.map((tip, i) => (
            <span key={i} className="px-2 py-1 bg-blue-50 text-blue-700 rounded-full border border-blue-200">{tip}</span>
          ))}
          {session.focus_points?.map((p, i) => (
            <span key={i} className="px-2 py-1 bg-amber-50 text-amber-700 rounded-full border border-amber-200">考察: {p}</span>
          ))}
        </div>
      )}

      {/* Main layout: chat (left) + question bank (right) */}
      {session && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Chat column - takes 2/3 */}
          <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 flex flex-col" style={{ minHeight: "70vh" }}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
              <div>
                <h2 className="font-semibold text-gray-900">
                  模拟面试：{session.jd_title}{session.company ? ` · ${session.company}` : ""}
                </h2>
                <p className="text-xs text-gray-400">
                  第 {round + 1} 轮 · {session.use_rewritten_resume ? "使用改写简历" : "使用原始简历"}
                  {session.used_ai ? " · DeepSeek 驱动" : " · 规则引擎"}
                </p>
              </div>
              <div className="flex gap-2">
                {!finished && (
                  <button onClick={handleEndInterview} disabled={summaryLoading || round < 1}
                    className="px-4 py-1.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50">
                    {summaryLoading ? "生成总结中..." : "结束面试"}
                  </button>
                )}
                <button onClick={() => handleStart()} className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">
                  重新开始
                </button>
              </div>
            </div>

            {/* Chat messages - large scrollable area */}
            {!finished ? (
              <>
                <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                  {messages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                      <div className={`max-w-[85%] px-4 py-3 rounded-xl text-sm ${
                        msg.role === "user" ? "bg-primary-600 text-white" : "bg-white border border-gray-200 text-gray-800 shadow-sm"
                      }`}>
                        <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                        {msg.role === "assistant" && i > 0 && (
                          <span className="text-[10px] text-gray-400 mt-1 block">面试官 · 第 {Math.ceil(i/2)} 题</span>
                        )}
                      </div>
                    </div>
                  ))}
                  {chatLoading && (
                    <div className="flex justify-start">
                      <div className="bg-white border border-gray-200 px-4 py-3 rounded-xl text-sm text-gray-400 animate-pulse">
                        DeepSeek 正在评估你的回答...
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>

                {/* Input area */}
                <div className="p-4 border-t border-gray-200 bg-white">
                  <div className="flex gap-2">
                    <textarea
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handle发送(); }
                      }}
                      placeholder="输入你的回答... (Enter 发送，Shift+Enter 换行)"
                      rows={3}
                      className="flex-1 border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                      disabled={chatLoading}
                    />
                    <button onClick={handle发送} disabled={chatLoading || !input.trim()}
                      className="px-8 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 self-end">
                      发送回答
                    </button>
                  </div>
                  {round >= 1 && (
                    <p className="text-xs text-gray-400 mt-1.5">
                      已回答 {round} 题 · 准备好后点击"结束面试"查看完整总结
                    </p>
                  )}
                </div>
              </>
            ) : (
              /* Summary view */
              <div className="flex-1 overflow-y-auto p-6 space-y-5">
                {summaryLoading ? (
                  <div className="flex items-center justify-center py-20"><LoadingSpinner text="正在生成面试总结..." /></div>
                ) : summary ? (
                  <>
                    <div className="text-center pb-4 border-b">
                      <h3 className="text-xl font-bold text-gray-900">面试总结</h3>
                      <p className="text-sm text-gray-500 mt-1">
                        共 {summary.total_rounds || round} 轮问答 · 综合评分 {summary.overall_score || "—"} 分
                      </p>
                    </div>
                    {summary.overall_feedback && (
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <h4 className="font-semibold text-blue-800 mb-2">总体评价</h4>
                        <p className="text-sm text-blue-700 whitespace-pre-wrap">{summary.overall_feedback}</p>
                      </div>
                    )}
                    {summary.strengths?.length > 0 && (
                      <div>
                        <h4 className="font-semibold text-green-700 mb-2">表现亮点</h4>
                        <ul className="space-y-2">{summary.strengths.map((s: string, i: number) => (
                          <li key={i} className="text-sm text-gray-700 bg-green-50 rounded-lg p-3 border border-green-100">{s}</li>
                        ))}</ul>
                      </div>
                    )}
                    {summary.weaknesses?.length > 0 && (
                      <div>
                        <h4 className="font-semibold text-red-700 mb-2">需要改进</h4>
                        <ul className="space-y-2">{summary.weaknesses.map((w: string, i: number) => (
                          <li key={i} className="text-sm text-gray-700 bg-red-50 rounded-lg p-3 border border-red-100">{w}</li>
                        ))}</ul>
                      </div>
                    )}
                    {summary.suggestions?.length > 0 && (
                      <div>
                        <h4 className="font-semibold text-primary-700 mb-2">提升建议</h4>
                        <ul className="space-y-2">{summary.suggestions.map((s: string, i: number) => (
                          <li key={i} className="text-sm text-gray-700 bg-primary-50 rounded-lg p-3 border border-primary-100">{s}</li>
                        ))}</ul>
                      </div>
                    )}
                    <div className="flex gap-3 pt-4">
                      <button onClick={() => { setFinished(false); setSummary(null); setMessages([]); handleStart(); }}
                        className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">重新练习</button>
                    </div>
                  </>
                ) : null}
              </div>
            )}
          </div>

          {/* Question bank column - 1/3 */}
          <div className="bg-white rounded-lg border border-gray-200 p-4" style={{ maxHeight: "70vh", overflowY: "auto" }}>
            <h3 className="font-semibold text-gray-900 mb-3">题库 ({questions.length})</h3>
            <p className="text-xs text-gray-500 mb-3">点击题目查看详情并练习回答</p>
            <div className="space-y-2">
              {questions.map((q, i) => (
                <div key={i}>
                  <QuestionCard question={q} selected={selectedIdx === i}
                    onSelect={() => setSelectedIdx(selectedIdx === i ? null : i)} />
                  {selectedIdx === i && selected && (
                    <AnswerScorePanel question={q.question} questionType={q.question_type} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

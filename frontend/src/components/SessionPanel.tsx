import { useEffect, useState } from "react";
import {
  SessionStatus,
  fetchSessionStatus,
  saveLoginSession,
  startLoginSession,
} from "../api";

export default function SessionPanel() {
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function refreshStatus() {
    setStatus(await fetchSessionStatus());
  }

  useEffect(() => {
    refreshStatus().catch((statusError) => {
      setError(statusError instanceof Error ? statusError.message : "读取登录态失败");
    });
  }, []);

  async function runSessionAction(action: () => Promise<SessionStatus>, successMessage: string) {
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const nextStatus = await action();
      setStatus(nextStatus);
      setMessage(successMessage);
    } catch (sessionError) {
      setError(sessionError instanceof Error ? sessionError.message : "登录态操作失败");
    } finally {
      setLoading(false);
    }
  }

  const updatedAt = status?.storage_state_updated_at
    ? new Date(status.storage_state_updated_at).toLocaleString()
    : "尚未保存";

  return (
    <section className="session-card">
      <div>
        <p className="eyebrow">登录态</p>
        <h2>{status?.has_login_state ? "已配置" : "未配置"}</h2>
        <p>
          {status?.login_in_progress
            ? "登录窗口已打开，请完成登录后点击保存。"
            : `更新时间：${updatedAt}`}
        </p>
      </div>
      <div className="session-actions">
        <button
          type="button"
          onClick={() => runSessionAction(startLoginSession, "登录窗口已打开")}
          disabled={loading || status?.login_in_progress}
        >
          重新登录
        </button>
        <button
          type="button"
          className="secondary-button"
          onClick={() => runSessionAction(saveLoginSession, "登录态已保存")}
          disabled={loading || !status?.login_in_progress}
        >
          保存登录态
        </button>
      </div>
      {message ? <p className="session-message">{message}</p> : null}
      {error ? <p className="session-error">{error}</p> : null}
    </section>
  );
}

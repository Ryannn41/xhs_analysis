import { useEffect, useState } from "react";
import {
  SessionStatus,
  fetchSessionStatus,
  getLoginScreenshotUrl,
  saveLoginSession,
  startLoginSession,
} from "../api";

export default function SessionPanel() {
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [screenshotVersion, setScreenshotVersion] = useState(Date.now());

  async function refreshStatus() {
    setStatus(await fetchSessionStatus());
  }

  useEffect(() => {
    refreshStatus().catch((statusError) => {
      setError(statusError instanceof Error ? statusError.message : "读取登录态失败");
    });
  }, []);

  useEffect(() => {
    if (!status?.login_in_progress) {
      return;
    }

    const timer = window.setInterval(() => {
      setScreenshotVersion(Date.now());
      refreshStatus().catch((statusError) => {
        setError(statusError instanceof Error ? statusError.message : "刷新登录状态失败");
      });
    }, 3000);

    return () => window.clearInterval(timer);
  }, [status?.login_in_progress]);

  async function runSessionAction(action: () => Promise<SessionStatus>, successMessage: string) {
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const nextStatus = await action();
      setStatus(nextStatus);
      setScreenshotVersion(Date.now());
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
            ? "请用小红书 App 扫描下方登录页二维码，确认登录后点击保存。"
            : `更新时间：${updatedAt}`}
        </p>
      </div>
      <div className="session-actions">
        <button
          type="button"
          onClick={() => runSessionAction(startLoginSession, "扫码登录页已生成")}
          disabled={loading || status?.login_in_progress}
        >
          重新登录
        </button>
        <button
          type="button"
          className="secondary-button"
          onClick={() => setScreenshotVersion(Date.now())}
          disabled={loading || !status?.login_in_progress}
        >
          刷新截图
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
      {status?.login_in_progress && status.login_screenshot_available ? (
        <div className="login-screenshot">
          <img src={getLoginScreenshotUrl(screenshotVersion)} alt="小红书扫码登录页截图" />
          <p>截图会自动刷新。扫码并在手机端确认后，等待页面状态变化，再点击“保存登录态”。</p>
        </div>
      ) : null}
      {message ? <p className="session-message">{message}</p> : null}
      {error ? <p className="session-error">{error}</p> : null}
    </section>
  );
}

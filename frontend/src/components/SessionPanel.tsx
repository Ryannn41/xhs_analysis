import { useEffect, useState } from "react";
import {
  SessionStatus,
  fetchSessionStatus,
  logoutSession,
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
  const currentUser = status?.current_user;
  const displayName = currentUser?.nickname || "当前登录账号";
  const avatarText = displayName.slice(0, 1).toUpperCase();
  const canLogout = Boolean(status?.has_login_state || status?.login_in_progress);

  return (
    <section className="session-card">
      <aside className="session-account-risk" role="note">
        用于登录本工具的小红书账号会因自动化访问被平台判定风险，可能导致功能受限或封号；它与下方要分析的博主账号无关。
        建议使用备用小号（例如虚拟手机号注册的账号），不要使用常用主号登录。
      </aside>
      <div className="session-main">
        {currentUser ? (
          <div className="session-avatar" aria-hidden>
            {currentUser.avatar_url ? (
              <img src={currentUser.avatar_url} alt="" />
            ) : (
              <span>{avatarText}</span>
            )}
          </div>
        ) : null}
        <div>
          <p className="eyebrow">登录态</p>
          <h2>
            {currentUser?.profile_url ? (
              <a href={currentUser.profile_url} target="_blank" rel="noreferrer">
                {displayName}
              </a>
            ) : currentUser ? (
              displayName
            ) : status?.has_login_state ? (
              "已配置"
            ) : (
              "未配置"
            )}
          </h2>
          {currentUser?.red_id ? <p>小红书号：{currentUser.red_id}</p> : null}
          <p>
            {status?.login_in_progress
              ? "登录窗口已打开，请完成登录后点击保存。"
              : `更新时间：${updatedAt}`}
          </p>
        </div>
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
        <button
          type="button"
          className="danger-button"
          onClick={() => runSessionAction(logoutSession, "已退出登录，登录态已清除")}
          disabled={loading || !canLogout}
        >
          退出登录
        </button>
      </div>
      {message ? <p className="session-message">{message}</p> : null}
      {error ? <p className="session-error">{error}</p> : null}
    </section>
  );
}

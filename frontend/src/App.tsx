import { useState } from "react";
import {
  AccountInput,
  AccountResult as AccountResultData,
  fetchAccountProfile,
} from "./api";
import AccountResult from "./components/AccountResult";
import SearchBox from "./components/SearchBox";
import SessionPanel from "./components/SessionPanel";
import { exportAccountResultsToExcel } from "./exportExcel";

interface BatchResult {
  input: AccountInput;
  result?: AccountResultData;
  error?: string;
}

interface BatchProgress {
  current: number;
  total: number;
  label: string;
}

export default function App() {
  const [results, setResults] = useState<BatchResult[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null);
  const [riskExpanded, setRiskExpanded] = useState(false);
  const [postRunBanner, setPostRunBanner] = useState<{ type: "success" | "warning"; text: string } | null>(
    null,
  );
  const successfulResults = results
    .map((item) => item.result)
    .filter((result): result is AccountResultData => Boolean(result));

  async function handleSearch(
    accounts: AccountInput[],
    startDate: string,
    endDate: string,
  ) {
    setError("");
    setPostRunBanner(null);
    setBatchProgress(null);
    setResults([]);
    setLoading(true);

    const nextResults: BatchResult[] = [];
    try {
      for (const [index, account] of accounts.entries()) {
        setBatchProgress({
          current: index + 1,
          total: accounts.length,
          label: `正在抓取 ${index + 1}/${accounts.length}：${account.name || account.id}`,
        });
        try {
          const result = await fetchAccountProfile(account.id.trim(), startDate, endDate);
          nextResults.push({ input: account, result });
        } catch (searchError) {
          nextResults.push({
            input: account,
            error: searchError instanceof Error ? searchError.message : "请求失败",
          });
        }
        setResults([...nextResults]);
      }

      const failedCount = nextResults.filter((item) => item.error).length;
      const successCount = nextResults.length - failedCount;

      if (failedCount) {
        setError(
          successCount
            ? `${failedCount} 个账号查询失败，成功结果已展示在下方。`
            : "全部账号查询失败，请检查 Excel 里的 id 或登录态。",
        );
        if (successCount > 0) {
          setPostRunBanner({
            type: "warning",
            text: `汇总：成功 ${successCount} 个，失败 ${failedCount} 个。`,
          });
        }
      } else if (nextResults.length > 0) {
        setPostRunBanner({
          type: "success",
          text: `查询完成：${nextResults.length} 个账号全部成功。`,
        });
      }
    } finally {
      setBatchProgress(null);
      setLoading(false);
    }
  }

  function scrollToTop() {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <main className="app" id="top">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Playwright 登录态自持</p>
          <h1>小红书账号分析</h1>
          <p>
            后端读取 Playwright 登录态，前端支持单个账号输入或上传 Excel 批量查询。
          </p>
        </div>
        <aside className="hero-aside" aria-label="推荐使用步骤">
          <ol className="workflow-steps">
            <li>
              <span className="step-index" aria-hidden>
                1
              </span>
              <div>
                <strong>登录态</strong>
                先完成「重新登录」并保存登录态，确保抓取可用；建议用备用小红书号登录本工具，勿用主号。
              </div>
            </li>
            <li>
              <span className="step-index" aria-hidden>
                2
              </span>
              <div>
                <strong>查询</strong>
                输入账号或上传 Excel，选择日期范围后提交。
              </div>
            </li>
            <li>
              <span className="step-index" aria-hidden>
                3
              </span>
              <div>
                <strong>结果</strong>
                查看统计与笔记列表，需要时可导出 Excel。
              </div>
            </li>
          </ol>
        </aside>
      </section>

      <SessionPanel />
      <section className="risk-notice" aria-labelledby="risk-summary">
        <div className="risk-notice-bar">
          <p className="eyebrow">使用提醒</p>
          <p className="risk-notice-summary" id="risk-summary">
            控制抓取频率，并使用备用账号登录，以降低风控与封号风险；详情可展开查看。
          </p>
          <button
            type="button"
            className="risk-toggle"
            aria-expanded={riskExpanded}
            onClick={() => setRiskExpanded((value) => !value)}
          >
            {riskExpanded ? "收起详情" : "展开详情"}
          </button>
        </div>
        {riskExpanded ? (
          <div className="risk-notice-body">
            <div>
              <p className="eyebrow">使用提醒</p>
              <h2>请控制实时抓取频率，避免触发平台风控</h2>
              <p>
                本工具会使用浏览器登录态访问账号主页和笔记详情页。短时间批量查询大量账号、
                频繁实时抓取，可能触发小红书登录验证、访问限制或数据读取失败。
                用于登录的账号也可能被反爬策略标记，存在功能受限或封号风险；登录账号与你要分析的博主账号不是一回事。
              </p>
            </div>
            <ul>
              <li>每次查询都会实时访问小红书，请根据账号数量控制执行节奏。</li>
              <li>批量账号建议分批执行，避免一次性高频抓取。</li>
              <li>出现登录墙、验证、超时或空数据时，建议暂停后再继续。</li>
              <li>
                请使用与日常工作无关的备用小红书账号（例如虚拟手机号注册的小号）登录本工具，不要用常用主号。
              </li>
            </ul>
          </div>
        ) : null}
      </section>
      <SearchBox loading={loading} onSearch={handleSearch} />
      {loading && batchProgress ? (
        <div className="progress-panel" role="status" aria-live="polite">
          <p>{batchProgress.label}</p>
          <div className="progress-bar" aria-hidden>
            <div
              className="progress-bar-fill"
              style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}
            />
          </div>
        </div>
      ) : null}
      {postRunBanner ? (
        <div
          className={postRunBanner.type === "success" ? "success-banner" : "success-banner warning-banner"}
          role="status"
        >
          <p className="batch-summary">{postRunBanner.text}</p>
        </div>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      {successfulResults.length ? (
        <div className="export-dock">
          <div className="export-dock-inner">
            <span>已生成 {successfulResults.length} 个账号的统计结果</span>
            <div className="export-dock-actions">
              <button type="button" onClick={() => exportAccountResultsToExcel(successfulResults)}>
                下载 Excel
              </button>
              <button type="button" className="back-to-top" onClick={scrollToTop}>
                回到顶部
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {results.map((item, index) =>
        item.result ? (
          <AccountResult
            key={`${item.input.id}-${index}`}
            result={item.result}
            animationDelay={`${index * 0.055}s`}
          />
        ) : (
          <section
            className="result-card result-error"
            key={`${item.input.id}-${index}`}
            style={{ animationDelay: `${index * 0.055}s` }}
          >
            <p className="eyebrow">查询失败</p>
            <h2>{item.input.name || item.input.id}</h2>
            <p>{item.error}</p>
          </section>
        ),
      )}
    </main>
  );
}

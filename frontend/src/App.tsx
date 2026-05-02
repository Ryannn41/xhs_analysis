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

export default function App() {
  const [results, setResults] = useState<BatchResult[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const successfulResults = results
    .map((item) => item.result)
    .filter((result): result is AccountResultData => Boolean(result));

  async function handleSearch(
    accounts: AccountInput[],
    refresh: boolean,
    startDate: string,
    endDate: string,
  ) {
    setError("");
    setProgress("");
    setResults([]);
    setLoading(true);

    const nextResults: BatchResult[] = [];
    try {
      for (const [index, account] of accounts.entries()) {
        setProgress(`正在抓取 ${index + 1}/${accounts.length}：${account.name || account.id}`);
        try {
          const result = await fetchAccountProfile(account.id.trim(), refresh, startDate, endDate);
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
      if (failedCount) {
        const successCount = nextResults.length - failedCount;
        setError(
          successCount
            ? `${failedCount} 个账号查询失败，成功结果已展示在下方。`
            : "全部账号查询失败，请检查 Excel 里的 id 或登录态。",
        );
      }
    } finally {
      setProgress("");
      setLoading(false);
    }
  }

  return (
    <main className="app">
      <section className="hero">
        <p className="eyebrow">Playwright 登录态自持</p>
        <h1>小红书账号分析</h1>
        <p>
          后端读取 Playwright 登录态，前端支持单个账号输入或上传 Excel 批量查询。
        </p>
      </section>

      <SessionPanel />
      <section className="risk-notice">
        <div>
          <p className="eyebrow">使用提醒</p>
          <h2>请控制实时抓取频率，避免触发平台风控</h2>
          <p>
            本工具会使用浏览器登录态访问账号主页和笔记详情页。短时间批量查询大量账号、
            频繁勾选“跳过缓存”实时抓取，可能触发小红书登录验证、访问限制或数据读取失败。
          </p>
        </div>
        <ul>
          <li>优先使用缓存；只有需要最新数据时再勾选“跳过缓存”。</li>
          <li>批量账号建议分批执行，避免一次性高频抓取。</li>
          <li>出现登录墙、验证、超时或空数据时，建议暂停后再继续。</li>
        </ul>
      </section>
      <SearchBox loading={loading} onSearch={handleSearch} />
      {progress ? <p className="progress">{progress}</p> : null}
      {error ? <p className="error">{error}</p> : null}
      {successfulResults.length ? (
        <div className="export-actions">
          <span>已生成 {successfulResults.length} 个账号的统计结果</span>
          <button type="button" onClick={() => exportAccountResultsToExcel(successfulResults)}>
            下载 Excel
          </button>
        </div>
      ) : null}
      {results.map((item, index) =>
        item.result ? (
          <AccountResult key={`${item.input.id}-${index}`} result={item.result} />
        ) : (
          <section className="result-card result-error" key={`${item.input.id}-${index}`}>
            <p className="eyebrow">查询失败</p>
            <h2>{item.input.name || item.input.id}</h2>
            <p>{item.error}</p>
          </section>
        ),
      )}
    </main>
  );
}

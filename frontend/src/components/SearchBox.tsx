import { ChangeEvent, FormEvent, useState } from "react";
import * as XLSX from "xlsx";
import { AccountInput } from "../api";

interface SearchBoxProps {
  loading: boolean;
  onSearch: (
    accounts: AccountInput[],
    startDate: string,
    endDate: string,
  ) => void;
}

function formatDateInput(date: Date) {
  return date.toISOString().slice(0, 10);
}

function defaultStartDate() {
  const date = new Date();
  date.setDate(date.getDate() - 29);
  return formatDateInput(date);
}

function readCellValue(value: unknown) {
  return value === null || value === undefined ? "" : String(value).trim();
}

function parseAccountId(value: string) {
  const profileMatch = value.match(/\/user\/profile\/([^/?#\s]+)/);
  return profileMatch ? profileMatch[1] : value;
}

export default function SearchBox({ loading, onSearch }: SearchBoxProps) {
  const [account, setAccount] = useState("");
  const [uploadedAccounts, setUploadedAccounts] = useState<AccountInput[]>([]);
  const [uploadedFileName, setUploadedFileName] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [startDate, setStartDate] = useState(defaultStartDate);
  const [endDate, setEndDate] = useState(() => formatDateInput(new Date()));

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const accounts =
      uploadedAccounts.length > 0
        ? uploadedAccounts
        : [{ name: account.trim(), id: account.trim() }];

    onSearch(accounts, startDate, endDate);
  }

  async function handleExcelUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setUploadError("");
    setUploadedAccounts([]);
    setUploadedFileName("");

    if (!file) {
      return;
    }

    try {
      const workbook = XLSX.read(await file.arrayBuffer(), { type: "array" });
      const sheetName = workbook.SheetNames[0];
      if (!sheetName) {
        throw new Error("Excel 文件没有工作表。");
      }

      const sheet = workbook.Sheets[sheetName];
      const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, {
        defval: "",
      });

      if (!rows.length) {
        throw new Error("Excel 文件没有可读取的数据。");
      }

      const accounts = rows
        .map((row) => {
          const idInput = readCellValue(row.id);
          return {
            name: readCellValue(row.name),
            id: parseAccountId(idInput),
          };
        })
        .filter((row) => row.name || row.id);

      if (!accounts.length) {
        throw new Error("Excel 需要包含 name、id 两列，且至少有一行账号。");
      }

      const missingId = accounts.find((row) => !row.id);
      if (missingId) {
        throw new Error(`账号「${missingId.name || "未命名"}」缺少 id。`);
      }

      setUploadedAccounts(accounts);
      setUploadedFileName(file.name);
      setAccount("");
      event.target.value = "";
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Excel 解析失败。");
      event.target.value = "";
    }
  }

  const isInvalidRange = Boolean(startDate && endDate && startDate > endDate);
  const hasAccountInput = Boolean(account.trim() || uploadedAccounts.length);

  return (
    <form className="search-box" onSubmit={handleSubmit}>
      <div className="search-group search-group--account">
        <p className="search-group-title">账号来源</p>
        <div className="search-main">
          <input
            type="text"
            value={account}
            onChange={(event) => {
              setAccount(event.target.value);
              if (event.target.value.trim()) {
                setUploadedAccounts([]);
                setUploadedFileName("");
              }
            }}
            placeholder="输入昵称、user_id 或小红书主页 URL"
            disabled={loading}
            aria-label="账号：昵称、user_id 或主页 URL"
          />
          <label className="upload-field">
            上传 Excel
            <input
              type="file"
              accept=".xlsx,.xls"
              onChange={handleExcelUpload}
              disabled={loading}
            />
          </label>
          {uploadedFileName ? <span className="uploaded-file">{uploadedFileName}</span> : null}
        </div>
      </div>

      <div className="search-group search-group--dates">
        <p className="search-group-title">时间范围</p>
        <label className="date-field">
          开始
          <input
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            disabled={loading}
          />
        </label>
        <label className="date-field">
          结束
          <input
            type="date"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
            disabled={loading}
          />
        </label>
      </div>

      <div className="search-group search-group--options">
        <p className="search-group-title">选项与提交</p>
        <button type="submit" disabled={loading || !hasAccountInput || isInvalidRange}>
          {loading
            ? "抓取中..."
            : uploadedAccounts.length
              ? `批量查询 ${uploadedAccounts.length} 个账号`
              : "查询账号"}
        </button>
      </div>

      {uploadedAccounts.length ? (
        <div className="upload-preview">
          <div className="upload-preview-header">
            <strong>数据预览</strong>
            <span>
              已读取 {uploadedAccounts.length} 个账号，id 列支持纯 user_id 或主页 URL。
            </span>
          </div>
          <div className="upload-preview-table">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>name</th>
                  <th>id</th>
                </tr>
              </thead>
              <tbody>
                {uploadedAccounts.map((row, index) => (
                  <tr key={`${row.id}-${index}`}>
                    <td>{index + 1}</td>
                    <td>{row.name || "-"}</td>
                    <td>{row.id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {uploadError ? <p className="form-error">{uploadError}</p> : null}
      {isInvalidRange ? <p className="form-error">开始日期不能晚于结束日期</p> : null}
    </form>
  );
}

import * as XLSX from "xlsx";
import { AccountResult } from "./api";

function formatDateForFilename(date = new Date()) {
  return date.toISOString().slice(0, 10);
}

function formatDateText(value: string) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return match ? `${match[1]}年${match[2]}月${match[3]}日` : value;
}

function accountName(result: AccountResult) {
  return result.profile.nickname || result.account.nickname || result.account.input || result.account.user_id;
}

function setColumnWidths(sheet: XLSX.WorkSheet, widths: number[]) {
  sheet["!cols"] = widths.map((wch) => ({ wch }));
}

export function exportAccountResultsToExcel(results: AccountResult[]) {
  const summaryRows = results.map((result) => ({
    账号名称: accountName(result),
    账号ID: result.account.user_id,
    小红书号: result.profile.red_id || "",
    主页链接: result.account.profile_url,
    账号粉丝量: result.stats.followers_count,
    统计开始日期: formatDateText(result.stats.period_start),
    统计结束日期: formatDateText(result.stats.period_end),
    区间帖子数: result.stats.period_note_count,
    区间点赞总量: result.stats.period_liked_total,
    区间收藏总量: result.stats.period_collected_total,
    区间评论总量: result.stats.period_comment_total,
    区间转发总量: result.stats.period_share_total,
    抓取时间: result.fetched_at,
  }));

  const noteRows = results.flatMap((result) =>
    result.notes.map((note) => ({
      账号名称: accountName(result),
      账号ID: result.account.user_id,
      小红书号: result.profile.red_id || "",
      笔记ID: note.note_id,
      标题: note.title,
      发布时间: note.time,
      笔记类型: note.type,
      笔记链接: note.url,
      点赞数: note.liked_count,
      收藏数: note.collected_count,
      评论数: note.comment_count,
      转发数: note.share_count,
      封面链接: note.cover_url,
    })),
  );

  const workbook = XLSX.utils.book_new();
  const summarySheet = XLSX.utils.json_to_sheet(summaryRows);
  const notesSheet = XLSX.utils.json_to_sheet(noteRows);

  setColumnWidths(summarySheet, [18, 28, 16, 54, 12, 14, 14, 12, 14, 14, 14, 14, 22]);
  setColumnWidths(notesSheet, [18, 28, 16, 28, 42, 20, 12, 64, 10, 10, 10, 10, 64]);

  XLSX.utils.book_append_sheet(workbook, summarySheet, "账号汇总");
  XLSX.utils.book_append_sheet(workbook, notesSheet, "笔记明细");
  XLSX.writeFile(workbook, `小红书账号统计_${formatDateForFilename()}.xlsx`);
}

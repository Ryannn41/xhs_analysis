import { useMemo, useState } from "react";
import { AccountResult as AccountResultData } from "../api";

const NOTES_PREVIEW_COUNT = 6;

interface AccountResultProps {
  result: AccountResultData;
  animationDelay?: string;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

function formatCount(value?: number) {
  return formatNumber(value ?? 0);
}

function noteCountDisplay(display: string | undefined, value: number) {
  return display || formatCount(value);
}

export default function AccountResult({ result, animationDelay }: AccountResultProps) {
  const [showAllNotes, setShowAllNotes] = useState(false);
  const { profile, notes, stats } = result;
  const displayName = profile.nickname || result.account.nickname || result.account.user_id;
  const followers =
    stats.followers_display || (stats.followers_count ? formatNumber(stats.followers_count) : "未读取");

  const statsAnchorId = useMemo(() => {
    const raw = result.account.user_id || "account";
    return `account-stats-${raw.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
  }, [result.account.user_id]);

  const visibleNotes = showAllNotes ? notes : notes.slice(0, NOTES_PREVIEW_COUNT);
  const hasMoreNotes = notes.length > NOTES_PREVIEW_COUNT;

  return (
    <section className="result-card" style={{ animationDelay }}>
      <div className="result-header">
        <div>
          <p className="eyebrow">实时抓取</p>
          <h2>{displayName}</h2>
          <p>{profile.desc || "暂无简介"}</p>
        </div>
        <a
          className="link-button"
          href={result.account.profile_url}
          target="_blank"
          rel="noreferrer"
        >
          打开主页
        </a>
      </div>

      <div className="stats-summary stats-anchor" id={statsAnchorId}>
        <div>
          <span>账号粉丝量</span>
          <strong>{followers}</strong>
        </div>
        <div>
          <span>区间点赞总量</span>
          <strong>{formatCount(stats.period_liked_total)}</strong>
        </div>
        <div>
          <span>区间收藏总量</span>
          <strong>{formatCount(stats.period_collected_total)}</strong>
        </div>
        <div>
          <span>区间评论总量</span>
          <strong>{formatCount(stats.period_comment_total)}</strong>
        </div>
        <div>
          <span>区间转发总量</span>
          <strong>{formatCount(stats.period_share_total)}</strong>
        </div>
        <div>
          <span>区间帖子数</span>
          <strong>{stats.period_note_count}</strong>
        </div>
        <div>
          <span>已扫描帖子</span>
          <strong>{stats.scanned_note_count}</strong>
        </div>
      </div>

      <div className="stats">
        <span>
          统计时间：{stats.period_start || "-"} 至 {stats.period_end || "-"}
        </span>
        {profile.red_id ? <span>小红书号：{profile.red_id}</span> : null}
        {profile.ip_location ? <span>IP：{profile.ip_location}</span> : null}
        <span>抓取时间：{result.fetched_at}</span>
      </div>

      {!stats.reached_range_start ? (
        <p className="range-warning">
          【提示】本次抓取未确认完整覆盖所选开始日期，较早帖子可能未统计到。
        </p>
      ) : null}

      {notes.length ? (
        <div className="period-notes-head">
          <h3>区间内笔记</h3>
          <a className="to-stats" href={`#${statsAnchorId}`}>
            ↑ 跳转到统计
          </a>
        </div>
      ) : null}

      <div className="period-notes">
        {visibleNotes.map((note, noteIndex) => (
          <article
            className="note-card"
            key={note.note_id}
            style={{
              animationDelay: animationDelay
                ? `calc(${animationDelay} + ${noteIndex * 0.035}s)`
                : `${noteIndex * 0.035}s`,
            }}
          >
            {note.cover_url ? (
              <img
                src={note.cover_url}
                alt={note.title?.trim() ? note.title : "笔记封面"}
              />
            ) : null}
            <p className="note-time">{note.time || "发布时间未知"}</p>
            <h3>{note.title || "无标题笔记"}</h3>
            <p>{note.desc}</p>
            <div className="note-meta">
              <span>赞 {noteCountDisplay(note.liked_count_display, note.liked_count)}</span>
              <span>藏 {noteCountDisplay(note.collected_count_display, note.collected_count)}</span>
              <span>评 {noteCountDisplay(note.comment_count_display, note.comment_count)}</span>
              <span>转 {noteCountDisplay(note.share_count_display, note.share_count)}</span>
            </div>
            {note.url ? (
              <a className="link-button" href={note.url} target="_blank" rel="noreferrer">
                查看笔记
              </a>
            ) : null}
          </article>
        ))}
        {hasMoreNotes ? (
          <div className="notes-expand-row">
            <button
              type="button"
              className="notes-expand-button"
              onClick={() => setShowAllNotes((value) => !value)}
            >
              {showAllNotes ? "收起笔记列表" : `展开全部笔记（共 ${notes.length} 条）`}
            </button>
          </div>
        ) : null}
      </div>
      {!notes.length ? (
        <p className="empty-result">【提示】所选时间段内没有可统计的帖子。</p>
      ) : null}
    </section>
  );
}

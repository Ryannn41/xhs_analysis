import { AccountResult as AccountResultData } from "../api";

interface AccountResultProps {
  result: AccountResultData;
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

export default function AccountResult({ result }: AccountResultProps) {
  const { profile, notes, stats } = result;
  const followers =
    stats.followers_display || (stats.followers_count ? formatNumber(stats.followers_count) : "-");

  return (
    <section className="result-card">
      <div className="result-header">
        <div>
          <p className="eyebrow">{result.cached ? "缓存结果" : "实时抓取"}</p>
          <h2>{profile.nickname || result.account.user_id}</h2>
          <p>{profile.desc || "暂无简介"}</p>
          {result.cached ? (
            <p className="cache-notice">当前展示的是缓存数据。如需获取实时新数据，请勾选“跳过缓存”后重新查询。</p>
          ) : null}
        </div>
        <a href={result.account.profile_url} target="_blank" rel="noreferrer">
          打开主页
        </a>
      </div>

      <div className="stats-summary">
        <div>
          <span>粉丝量</span>
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
        <span>小红书号：{profile.red_id || "-"}</span>
        <span>IP：{profile.ip_location || "-"}</span>
        <span>抓取时间：{result.fetched_at}</span>
      </div>

      {!stats.reached_range_start ? (
        <p className="range-warning">
          本次抓取未确认完整覆盖所选开始日期，较早帖子可能未统计到。
        </p>
      ) : null}

      <div className="period-notes">
        {notes.map((note) => (
          <article className="note-card" key={note.note_id}>
            {note.cover_url ? <img src={note.cover_url} alt={note.title} /> : null}
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
              <a href={note.url} target="_blank" rel="noreferrer">
                查看笔记
              </a>
            ) : null}
          </article>
        ))}
      </div>
      {!notes.length ? <p className="empty-result">所选时间段内没有可统计的帖子。</p> : null}
    </section>
  );
}

import { useEffect, useMemo, useState } from 'react';
import { marked } from 'marked';
import { api } from '../api/client';
import { formatDisplayTime } from '../lib/timezone';
import '../styles/docs.css';

marked.setOptions({ gfm: true, breaks: false });

/** 从 Markdown 提取 h2/h3 作为目录 */
function extractToc(md) {
  const items = [];
  for (const line of (md || '').split('\n')) {
    const m2 = line.match(/^## (.+)/);
    const m3 = line.match(/^### (.+)/);
    if (m2) {
      const text = m2[1].replace(/\[.*?\]\(.*?\)/g, '').trim();
      const id = slugify(text);
      items.push({ level: 2, text, id });
    } else if (m3) {
      const text = m3[1].replace(/\[.*?\]\(.*?\)/g, '').trim();
      items.push({ level: 3, text, id: slugify(text) });
    }
  }
  return items;
}

function slugify(text) {
  return String(text)
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fff]+/g, '-')
    .replace(/^-|-$/g, '');
}

/** 给渲染后的标题补 id，便于目录锚点跳转 */
function addHeadingIds(html) {
  return html.replace(/<h([23])>(.*?)<\/h\1>/g, (_, level, inner) => {
    const text = inner.replace(/<[^>]+>/g, '');
    const id = slugify(text);
    return `<h${level} id="${id}">${inner}</h${level}>`;
  });
}

export default function DocsPage({ embedded = false }) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.getUserGuide();
        if (!r.success) throw new Error(r.error || '加载失败');
        setDoc(r);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const toc = useMemo(() => extractToc(doc?.content), [doc?.content]);
  const html = useMemo(() => {
    if (!doc?.content) return '';
    return addHeadingIds(marked.parse(doc.content));
  }, [doc?.content]);

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className={`panel active docs-page${embedded ? ' docs-page-embedded' : ''}`}>
      {!embedded && (
        <div className="topbar">
          <div>
            <div className="topbar-title">使用手册</div>
            <div className="topbar-sub">
              {doc?.tagline || (doc?.updated_at ? `更新于 ${formatDisplayTime(doc.updated_at)}` : '产品说明与操作指引')}
            </div>
          </div>
        </div>
      )}
      <div className="docs-layout">
        <aside className="docs-toc">
          <div className="docs-toc-title">目录</div>
          {loading && <p className="muted">加载中…</p>}
          {error && <p className="docs-error">{error}</p>}
          <nav className="docs-toc-nav">
            {toc.map((item) => (
              <button
                key={`${item.level}-${item.text}`}
                type="button"
                className={`docs-toc-item level-${item.level}`}
                onClick={() => scrollTo(item.id)}
              >
                {item.text}
              </button>
            ))}
          </nav>
        </aside>
        <article className="docs-article prose">
          {loading && <p className="muted">正在加载文档…</p>}
          {error && !loading && <p>无法加载文档：{error}</p>}
          {!loading && !error && (
            <div className="docs-body" dangerouslySetInnerHTML={{ __html: html }} />
          )}
        </article>
      </div>
    </div>
  );
}

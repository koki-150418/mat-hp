#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MATブログ ビルドスクリプト

  HTML記事だけなら Python 3 標準ライブラリのみで動きます。
  Markdown記事（content/posts/。管理画面 /admin/ で書いた記事）がある場合は
  追加ライブラリが必要です:  pip install -r tools/requirements.txt
  （本番は GitHub Actions が push のたびに自動で実行します）

使い方:  サイトのフォルダで  python3 tools/build_blog.py

やること:
  1. 記事を集める
     - HTML記事: blog/<slug>/index.html の記事情報（post-meta）と本文（BODY）
     - Markdown記事: content/posts/<slug>/index.md（管理画面で書いた記事）
       → blog/<slug>/index.html を生成し、同じフォルダの画像を blog/<slug>/ にコピー
     - 著者: content/authors/<id>.json（記事の "author" で指定。省略時は taniguchi）
  2. 各記事ページを最新のテンプレート（ヘッダー・目次・著者・関連記事・フッター等）で作り直す
  3. blog/index.html（記事一覧）と blog/posts.json を作り直す
  4. トップページ index.html の「ブログ」欄（最新記事カード）を更新する
  5. index.html（と、あれば tokushoho.html）のヘッダー・フッターを共通テンプレートで揃える
  6. sitemap.xml を作り直す（トップ・ブログ一覧・公開中の記事。下書きは含めない）

  ※ "draft": true の記事は一覧・トップ・関連記事・sitemap に出ず、ページに noindex が付きます。
"""
import html, json, os, re, shutil, sys
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ===== サイト設定（必要に応じてここだけ変更） =====
SITE_URL   = "https://mediaiteam.com"     # 本番ドメイン（canonical / OGP に使用）
SITE_NAME  = "MEDI-AI TEAM"
LINE_URL   = "https://lin.ee/r1UDzpD"
NOINDEX    = False                         # True にすると全ブログページに noindex（公開前プレビュー用）
TOKUSHOHO_LINK = ""  # 特商法ページ公開時は ' / <a href="{root}tokushoho.html">特定商取引法に基づく表記</a>' を入れる
TOP_CARDS  = 3                             # トップページに出す最新記事の数
DEFAULT_EYECATCH = "img/blog-default.jpg"  # アイキャッチ未設定時の画像（サイトルートからのパス）
DEFAULT_AUTHOR_ID = "taniguchi"   # 記事に author が無いときの著者（content/authors/<id>.json）
# content/authors/taniguchi.json が無い場合の予備
AUTHOR = {
    "name": "谷口 総志",
    "role": "MEDI-AI TEAM 主催",
    "photo": "img/portrait-sitting.jpg",
    "link": "/#host",
    "bio": "元・臨床工学技士。長年にわたり循環器の現場に立ち、2008年からは心電図のセミナー講師として活動。"
           "出版した著書4冊はすべてAmazonランキング1位を獲得。「教える」ではなく「伸ばす」をモットーに、"
           "医療職のためのAI実践チーム「MEDI-AI TEAM」を主催している。",
}
# ================================================

E = html.escape
LINE_ATTR = f'href="{LINE_URL}" target="_blank" rel="noopener"'

def read(p):
    with open(p, encoding="utf-8") as f: return f.read()
def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f: f.write(s)

def fmt_date(d):  # 2026-10-09 -> 2026.10.09
    return d.replace("-", ".")

# ---------- 共通ヘッダー / フッター ----------
NAV = [("ホーム", "", "home"), ("MATとは", "#about", None), ("主催者", "#host", None),
       ("活動内容", "#activities", None), ("参加方法", "#entry", None), ("参加者の声", "#voices", None),
       ("ブログ", "blog/", "blog"), ("よくある質問", "#faq", None)]

def header(root, current):
    items = []
    for label, href, key in NAV:
        url = root + href if href else (root or "#top")
        cls = ' class="current"' if key and key == current else ""
        items.append(f'    <a href="{url}"{cls}>{label}</a>')
    return f'''<!-- HEADER:START (tools/build_blog.py が自動生成。直接編集しないでください) -->
<header class="site-header" id="top">
  <div class="header-top">
    <a href="{root or '#top'}" class="logo">
      <span class="logo-name">MEDI-AI TEAM</span>
      <svg class="logo-pulse" viewBox="0 0 60 14" aria-hidden="true"><path d="M0 8 H22 L25 3 L28 12 L31 1 L34 8 H60"/></svg>
      <span class="logo-sub">医療職のためのAI実践チーム</span>
    </a>
    <a {LINE_ATTR} class="header-join">公式LINE</a>
    <button class="menu-btn" aria-label="メニュー" onclick="document.body.classList.toggle('menu-open')"><span></span><span></span><span></span></button>
  </div>
  <nav class="gnav" aria-label="メインメニュー">
{chr(10).join(items)}
  </nav>
</header>
<!-- HEADER:END -->'''

def footer(root):
    r = root or "#top"
    return f'''<!-- FOOTER:START (tools/build_blog.py が自動生成。直接編集しないでください) -->
<footer class="site-footer">
  <div class="footer-cols">
    <div><p class="f-head">MEDI-AI TEAM</p><p class="f-text">医療職のためのAI実践チーム<br>主催：谷口総志</p></div>
    <div><p class="f-head">コンテンツ</p><ul><li><a href="{root}#about">MATとは</a></li><li><a href="{root}#activities">活動内容</a></li><li><a href="{root}#entry">参加方法</a></li><li><a href="{root}blog/">ブログ</a></li></ul></div>
    <div><p class="f-head">メニュー</p><ul><li><a href="{r}">ホーム</a></li><li><a href="{root}#host">主催者</a></li><li><a href="{root}#faq">よくある質問</a></li><li><a {LINE_ATTR}>公式LINE</a></li><li><a href="#">お問い合わせ</a></li></ul></div>
  </div>
  <div class="footer-bottom">
    <p><a href="#">プライバシーポリシー</a>{TOKUSHOHO_LINK.format(root=root)}</p>
    <p>© {date.today().year} MEDI-AI TEAM All Rights Reserved.</p>
  </div>
</footer>
<!-- FOOTER:END -->'''

def replace_block(s, name, new):
    pat = re.compile(rf"<!-- {name}:START.*?<!-- {name}:END -->", re.S)
    if pat.search(s):
        return pat.sub(lambda m: new, s, count=1)
    # 初回: マーカーが無ければ <header>…</header> / <footer>…</footer> を置き換える
    tag = "header" if name == "HEADER" else "footer"
    pat2 = re.compile(rf"<{tag}\b.*?</{tag}>", re.S)
    if not pat2.search(s):
        sys.exit(f"{name} が見つかりません")
    return pat2.sub(lambda m: new, s, count=1)

def head(title, desc, canonical, og_image, og_type, root, extra="", noindex=False):
    robots = '<meta name="robots" content="noindex,nofollow">\n' if (NOINDEX or noindex) else ""
    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
{robots}<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@500;600;700;800&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}style.css">
{extra}</head>'''

# ---------- 記事の読み込み ----------
META_RE = re.compile(r'<script type="application/json" id="post-meta">(.*?)</script>', re.S)
BODY_RE = re.compile(r"<!-- BODY:START -->(.*?)<!-- BODY:END -->", re.S)

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MD_DIR = os.path.join(ROOT, "content", "posts")
AUTHORS_DIR = os.path.join(ROOT, "content", "authors")

def site_path(v):
    """管理画面の画像パス（/img/x.jpg など）をサイトルートからのパス（img/x.jpg）にする"""
    v = (v or "").strip()
    return v[1:] if v.startswith("/") else v

def load_authors():
    authors = {}
    if os.path.isdir(AUTHORS_DIR):
        for fn in sorted(os.listdir(AUTHORS_DIR)):
            if not fn.endswith(".json"): continue
            aid = fn[:-5]
            try: a = json.loads(read(os.path.join(AUTHORS_DIR, fn)))
            except json.JSONDecodeError as e: sys.exit(f"content/authors/{fn} のJSONが壊れています: {e}")
            if not a.get("name"): sys.exit(f"content/authors/{fn} に name がありません")
            authors[aid] = {"name": a["name"], "role": a.get("title", ""), "photo": site_path(a.get("photo")),
                            "bio": a.get("bio", ""), "link": (a.get("link") or "").strip()}
    authors.setdefault(DEFAULT_AUTHOR_ID, AUTHOR)
    return authors

# Markdown本文から危険なタグ・属性を取り除く（外部ライター原稿の保険。レビューと併用）
def sanitize(h):
    h = re.sub(r"<(script|style|iframe|object|embed|form)\b.*?</\1\s*>", "", h, flags=re.S | re.I)
    h = re.sub(r"<(script|style|iframe|object|embed|form|input|button|link|meta)\b[^>]*>", "", h, flags=re.I)
    h = re.sub(r"""\son[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)""", "", h, flags=re.I)
    h = re.sub(r"""(href|src)\s*=\s*(["']?)\s*(javascript|vbscript|data):""", r"\1=\2#blocked:", h, flags=re.I)
    return h

JST = timezone(timedelta(hours=9))

def to_date_str(v, field, where):
    """日付を YYYY-MM-DD（日本時間）にする。管理画面の作成日時（UTC）は日本時間に直す"""
    if isinstance(v, str) and "T" in v:
        try: v = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
        except ValueError: pass
    if isinstance(v, datetime):
        if v.tzinfo is None: v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(JST).date().isoformat()
    if isinstance(v, date): return v.isoformat()
    v = str(v or "").strip()[:10]
    if v and not re.match(r"^\d{4}-\d{2}-\d{2}$", v): sys.exit(f"{where} の {field} は YYYY-MM-DD 形式にしてください: {v}")
    return v

def git_first_date(path):
    """そのファイルが最初に main に入ったコミットの日付（日本時間）。git が無ければ None"""
    import subprocess
    try:
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%cI", "--", os.path.relpath(path, ROOT)],
                             cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.split()
    except Exception:
        return None
    return to_date_str(out[-1], "date", path) if out else None

def load_md_posts():
    posts = []
    if not os.path.isdir(MD_DIR): return posts
    try:
        import markdown, yaml
    except ImportError:
        sys.exit("Markdown記事のビルドには追加ライブラリが必要です:  pip install -r tools/requirements.txt")
    for slug in sorted(os.listdir(MD_DIR)):
        d = os.path.join(MD_DIR, slug); p = os.path.join(d, "index.md")
        if not os.path.isfile(p): continue
        where = f"content/posts/{slug}/index.md"
        if not SLUG_RE.match(slug): sys.exit(f"{where}: フォルダ名（スラッグ）は半角英小文字・数字・ハイフンのみにしてください")
        src = read(p).lstrip("\ufeff")
        m = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)(.*)$", src, re.S)
        if not m: sys.exit(f"{where}: 先頭の --- で囲まれた記事情報が見つかりません")
        try: fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e: sys.exit(f"{where}: 記事情報の書式エラー: {e}")
        meta = {}
        for k in ("title", "description", "excerpt", "category", "eyecatch_alt", "author"):
            if fm.get(k) not in (None, ""): meta[k] = str(fm[k]).strip()
        meta["date"] = to_date_str(fm.get("date"), "date", where)
        if not meta["date"]: meta["date"] = git_first_date(p) or ""  # 公開日 = main に入った日（承認日）
        if not meta["date"] and re.match(r"^\d{8}", slug):  # それも無ければスラッグ（20261009-...）から
            meta["date"] = f"{slug[:4]}-{slug[4:6]}-{slug[6:8]}"
        if not meta["date"]: meta["date"] = datetime.now(JST).date().isoformat()
        if fm.get("updated"): meta["updated"] = to_date_str(fm.get("updated"), "updated", where)
        if fm.get("eyecatch"): meta["eyecatch"] = os.path.basename(site_path(str(fm["eyecatch"])))
        meta["sample"] = bool(fm.get("sample", False)); meta["draft"] = bool(fm.get("draft", False))
        meta["source"] = "markdown"
        for k in ("title", "date", "category"):
            if not meta.get(k): sys.exit(f"{where} に \"{k}\" がありません")
        if meta.get("eyecatch") and not os.path.isfile(os.path.join(d, meta["eyecatch"])):
            sys.exit(f"{where}: アイキャッチ画像 {meta['eyecatch']} が同じフォルダにありません")
        body = markdown.markdown(m.group(2), extensions=["extra", "sane_lists"], output_format="html")
        body = re.sub(r"<h1(\b[^>]*)>(.*?)</h1>", r"<h2\1>\2</h2>", body, flags=re.S)  # 本文の h1 は h2 扱い
        meta["body"] = sanitize(body)
        if not meta.get("description"):  # 概要が空なら本文の冒頭から作る
            text = re.sub(r"</(p|h[1-6]|li|blockquote|td|th)>", " ", meta["body"])
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text))).strip()
            meta["description"] = text[:110] + ("…" if len(text) > 110 else "")
        meta["md_dir"] = d
        posts.append(_finish(meta, slug))
    return posts

def _finish(meta, slug):
    meta.setdefault("updated", meta["date"])
    meta.setdefault("excerpt", meta["description"])
    meta.setdefault("draft", False)
    meta["slug"] = slug
    if "meta_json" not in meta:
        keep = {k: meta[k] for k in ("title", "description", "excerpt", "date", "updated", "category", "eyecatch",
                                     "eyecatch_alt", "author", "sample", "draft", "source") if k in meta}
        meta["meta_json"] = json.dumps(keep, ensure_ascii=False, indent=2)
    ey = meta.get("eyecatch")
    meta["eyecatch_site"] = f"blog/{slug}/{ey}" if ey else DEFAULT_EYECATCH  # サイトルートからのパス
    return meta

def load_posts():
    md_posts = load_md_posts()
    md_slugs = {p["slug"] for p in md_posts}
    posts = []
    bdir = os.path.join(ROOT, "blog")
    for slug in sorted(os.listdir(bdir)):
        p = os.path.join(bdir, slug, "index.html")
        if not os.path.isfile(p): continue
        s = read(p)
        m, b = META_RE.search(s), BODY_RE.search(s)
        if not m or not b:
            print(f"  ! スキップ（post-meta か BODY が見つかりません）: blog/{slug}/"); continue
        try: meta = json.loads(m.group(1))
        except json.JSONDecodeError as e: sys.exit(f"blog/{slug}/ の post-meta のJSONが壊れています: {e}")
        if meta.get("source") == "markdown":
            # Markdown記事から生成したページ（原稿は content/posts/）。原稿が消えていれば生成物も消す
            if slug not in md_slugs:
                shutil.rmtree(os.path.join(bdir, slug)); print(f"  - 削除（原稿なし）: blog/{slug}/")
            continue
        if slug in md_slugs:
            sys.exit(f"スラッグ \"{slug}\" が HTML記事（blog/{slug}/）と Markdown記事（content/posts/{slug}/）で重複しています")
        for k in ("title", "date", "category", "description"):
            if not meta.get(k): sys.exit(f"blog/{slug}/ の post-meta に \"{k}\" がありません")
        meta["meta_json"] = m.group(1).strip()
        meta["body"] = b.group(1).strip("\n")
        posts.append(_finish(meta, slug))
    posts += md_posts
    posts.sort(key=lambda x: (x["date"], x["slug"]), reverse=True)
    return posts

# ---------- 部品 ----------
def card(p, root):
    badge = '<span class="pc-badge">SAMPLE</span>' if p.get("sample") else ""
    return f'''    <a class="post-card" href="{root}blog/{p["slug"]}/" data-cat="{E(p["category"])}">
      <div class="pc-thumb"><img src="{root}{p["eyecatch_site"]}" alt="" loading="lazy">{badge}</div>
      <div class="pc-body">
        <p class="pc-meta"><span class="pc-cat">{E(p["category"])}</span><time datetime="{p["date"]}">{fmt_date(p["date"])}</time></p>
        <h3 class="pc-title">{E(p["title"])}</h3>
        <p class="pc-ex">{E(p["excerpt"])}</p>
      </div>
    </a>'''

def coming_soon(n):
    return "\n".join('    <div class="post-card soon"><div class="pc-thumb"></div><div class="pc-body"><p class="pc-meta"><span class="pc-cat">COMING SOON</span></p><h3 class="pc-title">記事は順次公開予定です</h3></div></div>' for _ in range(n))

def line_cta(root):
    return f'''<section class="line-cta">
  <p class="lc-small">MEDI-AI TEAM 公式LINE</p>
  <p class="lc-big">AIを、谷口総志と一緒に使い始めよう。</p>
  <p class="lc-text">参加費や申し込み方法は、公式LINEでご案内しています。</p>
  <a {LINE_ATTR} class="btn-red btn-line">公式LINEで詳しい案内を受け取る</a>
</section>'''

def slugify_id(text, used):
    base = "sec-" + str(len(used) + 1)
    used.add(base); return base

def add_ids_and_toc(body):
    used, toc = set(), []
    def rep(m):
        tag, attrs, inner = m.group(1), m.group(2) or "", m.group(3)
        idm = re.search(r'id="([^"]+)"', attrs)
        hid = idm.group(1) if idm else slugify_id(inner, used)
        if not idm: attrs += f' id="{hid}"'
        toc.append((tag, hid, re.sub(r"<[^>]+>", "", inner)))
        return f"<{tag}{attrs}>{inner}</{tag}>"
    body = re.sub(r"<(h2|h3)([^>]*)>(.*?)</\1>", rep, body, flags=re.S)
    if not toc: return body, ""
    items = "".join(f'<li class="toc-{t}"><a href="#{i}">{E(x)}</a></li>' for t, i, x in toc)
    return body, f'<nav class="toc" aria-label="目次"><p class="toc-head">目次</p><ol>{items}</ol></nav>'

# ---------- 記事ページ ----------
AUTHORS = {}

def author_box_inner(au, root, link_rel):
    img = f'      <img src="{root}{E(au["photo"])}" alt="{E(au["name"])}" loading="lazy">\n' if au.get("photo") else ""
    role = f'<span>{E(au["role"])}</span>' if au.get("role") else ""
    lk = ""
    if link_rel:
        ext = ' target="_blank" rel="noopener"' if link_rel.startswith("http") else ""
        lk = f'<a href="{E(link_rel)}" class="ab-link"{ext}>プロフィールを見る</a>'
    return f'{img}      <div><p class="ab-label">この記事を書いた人</p><p class="ab-name">{E(au["name"])}{role}</p><p class="ab-bio">{E(au.get("bio", ""))}</p>{lk}</div>'

def build_article(p, posts):
    root = "../../"
    url = f'{SITE_URL}/blog/{p["slug"]}/'
    img_abs = f'{SITE_URL}/{p["eyecatch_site"]}'
    title = f'{p["title"]}｜MATブログ｜{SITE_NAME}'
    body, toc = add_ids_and_toc(p["body"])
    aid = p.get("author") or DEFAULT_AUTHOR_ID
    if aid not in AUTHORS:  # 著者データがまだ公開されていない場合などは既定の著者で表示（ビルドは止めない）
        print(f"  ! 警告: blog/{p['slug']}/ の著者 \"{aid}\" が content/authors/ にありません → {DEFAULT_AUTHOR_ID} で表示")
        aid = DEFAULT_AUTHOR_ID
    au = AUTHORS[aid]
    link = au.get("link") or ""
    if link.startswith("/"): link_rel, link_abs = root + link[1:], SITE_URL + link
    elif link.startswith("http"): link_rel = link_abs = link
    else: link_rel = link_abs = ""
    person = {"@type": "Person", "name": au["name"].replace(" ", "")}
    if link_abs: person["url"] = link_abs
    ld = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": p["title"], "description": p["description"], "image": [img_abs],
        "datePublished": p["date"], "dateModified": p["updated"],
        "author": person,
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL + "/"},
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
    }
    bc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "ホーム", "item": SITE_URL + "/"},
        {"@type": "ListItem", "position": 2, "name": "ブログ", "item": SITE_URL + "/blog/"},
        {"@type": "ListItem", "position": 3, "name": p["title"], "item": url}]}
    extra = ('<meta property="article:published_time" content="%s">\n<meta property="article:modified_time" content="%s">\n'
             % (p["date"], p["updated"]))
    extra += '<script type="application/ld+json">%s</script>\n<script type="application/ld+json">%s</script>\n' % (
        json.dumps(ld, ensure_ascii=False), json.dumps(bc, ensure_ascii=False))
    others = [q for q in posts if q["slug"] != p["slug"] and not q["draft"]]
    rel = [q for q in others if q["category"] == p["category"]] + [q for q in others if q["category"] != p["category"]]
    rel = rel[:3]
    rel_html = "\n".join(card(q, root) for q in rel) if rel else coming_soon(3)
    sample_note = ('<p class="sample-note">この記事は、記事ページのレイアウトを確認するための<strong>サンプル記事</strong>です。本文はすべて仮の文章です。</p>'
                   if p.get("sample") else "")
    updated = (f'<span class="ah-upd">更新日 <time datetime="{p["updated"]}">{fmt_date(p["updated"])}</time></span>'
               if p["updated"] != p["date"] else "")
    return f'''{head(title, p["description"], url, img_abs, "article", root, extra, noindex=p["draft"])}
<body class="page-blog">

{header(root, "blog")}

<main class="article-wrap">
  <nav class="breadcrumb" aria-label="パンくずリスト"><a href="{root}">ホーム</a><span>›</span><a href="{root}blog/">ブログ</a><span>›</span><span aria-current="page">{E(p["title"])}</span></nav>
  <article class="article">
    <header class="article-head">
      <p class="ah-meta"><a class="pc-cat" href="{root}blog/#cat={E(p["category"])}">{E(p["category"])}</a><span>公開日 <time datetime="{p["date"]}">{fmt_date(p["date"])}</time></span>{updated}</p>
      <h1 class="article-title">{E(p["title"])}</h1>
    </header>
    <figure class="eyecatch"><img src="{root}{p["eyecatch_site"]}" alt="{E(p.get("eyecatch_alt", p["title"]))}"></figure>
    {sample_note}
    {toc}
    <div class="article-body">
<!-- BODY:START -->
{body}
<!-- BODY:END -->
    </div>
    <aside class="author-box">
{author_box_inner(au, root, link_rel)}
    </aside>
  </article>
  {line_cta(root)}
  <section class="related">
    <h2 class="h-center">関連記事</h2>
    <div class="post-grid">
{rel_html}
    </div>
    <div class="center"><a href="{root}blog/" class="btn-dark">ブログ一覧へ</a></div>
  </section>
</main>

{footer(root)}
<script type="application/json" id="post-meta">
{p["meta_json"]}
</script>
</body>
</html>
'''

# ---------- 一覧ページ ----------
def build_list(posts):
    root = "../"
    listed = [p for p in posts if not p["draft"]]
    cats = []
    for p in listed:
        if p["category"] not in cats: cats.append(p["category"])
    tags = '<button class="cat-btn is-on" data-cat="">すべて<span>%d</span></button>' % len(listed)
    tags += "".join('<button class="cat-btn" data-cat="%s">%s<span>%d</span></button>'
                    % (E(c), E(c), sum(1 for p in listed if p["category"] == c)) for c in cats)
    cards = "\n".join(card(p, root) for p in listed)
    if not listed:
        tags = ""
        cards = '    <p class="blog-empty">記事は順次公開予定です。<br>公開まで、もうしばらくお待ちください。</p>'
    elif len(listed) < 3: cards += "\n" + coming_soon(3 - len(listed))
    url = SITE_URL + "/blog/"
    desc = "医療職のためのAI実践チーム「MEDI-AI TEAM（MAT）」のブログ。AIを使い始めたい医療職のための情報を発信しています。"
    return f'''{head("MATブログ｜" + SITE_NAME, desc, url, SITE_URL + "/" + DEFAULT_EYECATCH, "website", root)}
<body class="page-blog">

{header(root, "blog")}

<main>
<section class="blog-hero">
  <p class="bh-en">MEDI-AI TEAM BLOG</p>
  <h1 class="bh-title">MATブログ</h1>
  <p class="bh-lead">AIを使ったことがない医療職が、明日から一歩を踏み出すための情報を発信していきます。<br class="pc">教わるのではなく、一緒に使う。そのためのヒントをまとめています。</p>
</section>
<section class="sec blog-list">
  {'<div class="cat-tags" role="group" aria-label="カテゴリー">' + tags + '</div>' if tags else ''}
  <div class="post-grid" id="post-grid">
{cards}
  </div>
</section>
{line_cta(root)}
</main>

{footer(root)}
<script>
(function(){{
  var btns=document.querySelectorAll('.cat-btn'), cards=document.querySelectorAll('#post-grid .post-card:not(.soon)');
  function apply(cat){{
    btns.forEach(function(b){{b.classList.toggle('is-on',b.dataset.cat===cat)}});
    cards.forEach(function(c){{c.style.display=(!cat||c.dataset.cat===cat)?'':'none'}});
  }}
  btns.forEach(function(b){{b.addEventListener('click',function(){{apply(b.dataset.cat);history.replaceState(null,'',b.dataset.cat?'#cat='+encodeURIComponent(b.dataset.cat):location.pathname)}})}});
  var m=location.hash.match(/^#cat=(.+)$/); if(m) apply(decodeURIComponent(m[1]));
}})();
</script>
</body>
</html>
'''

def main():
    AUTHORS.update(load_authors())
    posts = load_posts()
    print(f"記事数: {len(posts)}")
    for p in posts:
        out_dir = os.path.join(ROOT, "blog", p["slug"])
        if p.get("md_dir"):  # Markdown記事: 画像などを blog/<slug>/ にコピー
            os.makedirs(out_dir, exist_ok=True)
            for fn in os.listdir(p["md_dir"]):
                src = os.path.join(p["md_dir"], fn)
                if fn != "index.md" and os.path.isfile(src): shutil.copy2(src, os.path.join(out_dir, fn))
        write(os.path.join(out_dir, "index.html"), build_article(p, posts))
        print(f"  ✓ blog/{p['slug']}/  {p['date']}  {p['title']}" + ("（下書き：一覧に出ません）" if p["draft"] else ""))
    # Markdown記事から生成したフォルダは git に入れない（原稿は content/posts/。本番は Actions が生成）
    md = sorted(p["slug"] for p in posts if p.get("md_dir"))
    write(os.path.join(ROOT, "blog", ".gitignore"),
          "# 自動生成（tools/build_blog.py）: Markdown記事から作ったページ\n" + "".join(f"/{x}/\n" for x in md))
    write(os.path.join(ROOT, "blog", "index.html"), build_list(posts))
    pub = [{k: p[k] for k in ("slug", "title", "date", "updated", "category", "excerpt")} | {"url": f"blog/{p['slug']}/", "eyecatch": p["eyecatch_site"]}
           for p in posts if not p["draft"]]
    write(os.path.join(ROOT, "blog", "posts.json"), json.dumps(pub, ensure_ascii=False, indent=2) + "\n")
    print("  ✓ blog/index.html, blog/posts.json")
    # トップページ
    idx = os.path.join(ROOT, "index.html"); s = read(idx)
    latest = [p for p in posts if not p["draft"]][:TOP_CARDS]
    if latest:
        cards = "\n".join(card(p, "") for p in latest) + ("\n" + coming_soon(TOP_CARDS - len(latest)) if len(latest) < TOP_CARDS else "")
        inner = f'  <div class="post-grid">\n{cards}\n  </div>'
    else:
        inner = '  <p class="blog-empty">記事は順次公開予定です。</p>'
    block = f'<!-- BLOG-CARDS:START (自動生成) -->\n{inner}\n  <!-- BLOG-CARDS:END -->'
    if "<!-- BLOG-CARDS:START" not in s: sys.exit("index.html に BLOG-CARDS マーカーがありません")
    s = re.sub(r"<!-- BLOG-CARDS:START.*?<!-- BLOG-CARDS:END -->", lambda m: block, s, flags=re.S)
    s = replace_block(s, "HEADER", header("", "home")); s = replace_block(s, "FOOTER", footer(""))
    write(idx, s)
    print("  ✓ index.html（最新記事・ヘッダー・フッター）")
    tk = os.path.join(ROOT, "tokushoho.html")
    if os.path.isfile(tk):
        t = read(tk)
        t = replace_block(t, "HEADER", header("./", None)); t = replace_block(t, "FOOTER", footer("./"))
        write(tk, t); print("  ✓ tokushoho.html（ヘッダー・フッター）")
    # sitemap.xml
    urls = [(SITE_URL + "/", None), (SITE_URL + "/blog/", None)]
    urls += [(f"{SITE_URL}/blog/{p['slug']}/", p["updated"]) for p in posts if not p["draft"]]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u, lm in urls:
        sm += f"  <url><loc>{u}</loc>" + (f"<lastmod>{lm}</lastmod>" if lm else "") + "</url>\n"
    sm += "</urlset>\n"
    write(os.path.join(ROOT, "sitemap.xml"), sm)
    print(f"  ✓ sitemap.xml（{len(urls)} URL）")
    print("完了しました。")

if __name__ == "__main__":
    main()

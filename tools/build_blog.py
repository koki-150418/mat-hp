#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MATブログ ビルドスクリプト（Python 3 標準ライブラリのみ・追加インストール不要）

使い方:  サイトのフォルダで  python3 tools/build_blog.py

やること:
  1. blog/<slug>/index.html を全部読み、記事情報（post-meta）と本文（BODY）を取り出す
  2. 各記事ページを最新のテンプレート（ヘッダー・目次・著者・関連記事・フッター等）で作り直す
  3. blog/index.html（記事一覧）と blog/posts.json を作り直す
  4. トップページ index.html の「ブログ」欄（最新記事カード）を更新する
  5. index.html / tokushoho.html を含む全ページのヘッダー・フッターを共通テンプレートで揃える
"""
import html, json, os, re, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ===== サイト設定（必要に応じてここだけ変更） =====
SITE_URL   = "https://mediaiteam.com"     # 本番ドメイン（canonical / OGP に使用）
SITE_NAME  = "MEDI-AI TEAM"
LINE_URL   = "https://lin.ee/r1UDzpD"
NOINDEX    = True                          # プレビュー中は True。本番公開時に False にする
TOP_CARDS  = 3                             # トップページに出す最新記事の数
DEFAULT_EYECATCH = "img/blog-default.jpg"  # アイキャッチ未設定時の画像（サイトルートからのパス）
AUTHOR = {
    "name": "谷口 総志",
    "role": "MEDI-AI TEAM 主催",
    "photo": "img/portrait-sitting.jpg",
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
    <p><a href="#">プライバシーポリシー</a> / <a href="{root}tokushoho.html">特定商取引法に基づく表記</a></p>
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

def head(title, desc, canonical, og_image, og_type, root, extra=""):
    robots = '<meta name="robots" content="noindex,nofollow">\n' if NOINDEX else ""
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

def load_posts():
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
        for k in ("title", "date", "category", "description"):
            if not meta.get(k): sys.exit(f"blog/{slug}/ の post-meta に \"{k}\" がありません")
        meta.setdefault("updated", meta["date"])
        meta.setdefault("excerpt", meta["description"])
        meta.setdefault("draft", False)
        meta["slug"] = slug
        meta["meta_json"] = m.group(1).strip()
        meta["body"] = b.group(1).strip("\n")
        ey = meta.get("eyecatch")
        meta["eyecatch_site"] = f"blog/{slug}/{ey}" if ey else DEFAULT_EYECATCH  # サイトルートからのパス
        posts.append(meta)
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
def build_article(p, posts):
    root = "../../"
    url = f'{SITE_URL}/blog/{p["slug"]}/'
    img_abs = f'{SITE_URL}/{p["eyecatch_site"]}'
    title = f'{p["title"]}｜MATブログ｜{SITE_NAME}'
    body, toc = add_ids_and_toc(p["body"])
    ld = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": p["title"], "description": p["description"], "image": [img_abs],
        "datePublished": p["date"], "dateModified": p["updated"],
        "author": {"@type": "Person", "name": AUTHOR["name"].replace(" ", ""), "url": f"{SITE_URL}/#host"},
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
    return f'''{head(title, p["description"], url, img_abs, "article", root, extra)}
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
      <img src="{root}{AUTHOR["photo"]}" alt="{AUTHOR["name"]}" loading="lazy">
      <div><p class="ab-label">この記事を書いた人</p><p class="ab-name">{AUTHOR["name"]}<span>{AUTHOR["role"]}</span></p><p class="ab-bio">{AUTHOR["bio"]}</p><a href="{root}#host" class="ab-link">プロフィールを見る</a></div>
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
    if len(listed) < 3: cards += "\n" + coming_soon(3 - len(listed))
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
  <div class="cat-tags" role="group" aria-label="カテゴリー">{tags}</div>
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
    posts = load_posts()
    print(f"記事数: {len(posts)}")
    for p in posts:
        write(os.path.join(ROOT, "blog", p["slug"], "index.html"), build_article(p, posts))
        print(f"  ✓ blog/{p['slug']}/  {p['date']}  {p['title']}" + ("（下書き：一覧に出ません）" if p["draft"] else ""))
    write(os.path.join(ROOT, "blog", "index.html"), build_list(posts))
    pub = [{k: p[k] for k in ("slug", "title", "date", "updated", "category", "excerpt")} | {"url": f"blog/{p['slug']}/", "eyecatch": p["eyecatch_site"]}
           for p in posts if not p["draft"]]
    write(os.path.join(ROOT, "blog", "posts.json"), json.dumps(pub, ensure_ascii=False, indent=2) + "\n")
    print("  ✓ blog/index.html, blog/posts.json")
    # トップページ
    idx = os.path.join(ROOT, "index.html"); s = read(idx)
    latest = [p for p in posts if not p["draft"]][:TOP_CARDS]
    cards = "\n".join(card(p, "") for p in latest) + ("\n" + coming_soon(TOP_CARDS - len(latest)) if len(latest) < TOP_CARDS else "")
    block = f'<!-- BLOG-CARDS:START (自動生成) -->\n  <div class="post-grid">\n{cards}\n  </div>\n  <!-- BLOG-CARDS:END -->'
    if "<!-- BLOG-CARDS:START" not in s: sys.exit("index.html に BLOG-CARDS マーカーがありません")
    s = re.sub(r"<!-- BLOG-CARDS:START.*?<!-- BLOG-CARDS:END -->", lambda m: block, s, flags=re.S)
    s = replace_block(s, "HEADER", header("", "home")); s = replace_block(s, "FOOTER", footer(""))
    write(idx, s)
    tk = os.path.join(ROOT, "tokushoho.html"); t = read(tk)
    t = replace_block(t, "HEADER", header("./", None)); t = replace_block(t, "FOOTER", footer("./"))
    write(tk, t)
    print("  ✓ index.html（最新記事・ヘッダー・フッター）, tokushoho.html（ヘッダー・フッター）")
    print("完了しました。")

if __name__ == "__main__":
    main()

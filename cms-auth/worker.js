/**
 * MATブログ 管理画面（Decap CMS）用 GitHub ログイン中継（Cloudflare Worker）
 *
 * GitHub Pages にはサーバーが無いため、GitHub の OAuth ログインで必要な
 * 「Client Secret を使ったトークン交換」だけをこの Worker が代わりに行います。
 *
 * 必要な設定（Cloudflare の「設定 → 変数とシークレット」）:
 *   GITHUB_CLIENT_ID      … GitHub OAuth App の Client ID（テキスト）
 *   GITHUB_CLIENT_SECRET  … GitHub OAuth App の Client Secret（必ず「シークレット」で登録）
 *   ALLOWED_ORIGINS       … 任意。管理画面のURL（既定: https://mediaiteam.com,https://www.mediaiteam.com）
 *
 * エンドポイント:
 *   /auth      … Decap CMS が開くログイン窓の入口 → GitHub のログイン画面へ転送
 *   /callback  … GitHub からの戻り先（OAuth App の Authorization callback URL に登録する）
 */
const DEFAULT_ORIGINS = "https://mediaiteam.com,https://www.mediaiteam.com";
const SCOPES = new Set(["repo", "public_repo", "repo,user", "public_repo,user"]);
const STATE_COOKIE = "mat_cms_oauth_state";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/auth") return startAuth(url, env);
    if (url.pathname === "/callback") return callback(request, url, env);
    return new Response("MAT CMS auth proxy is running.", { headers: { "content-type": "text/plain; charset=utf-8" } });
  },
};

function startAuth(url, env) {
  if (!env.GITHUB_CLIENT_ID || !env.GITHUB_CLIENT_SECRET) return page(env, "error", { message: "Worker に GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET が設定されていません" });
  const provider = url.searchParams.get("provider") || "github";
  if (provider !== "github") return page(env, "error", { message: "provider は github のみ対応しています" });
  const scope = SCOPES.has(url.searchParams.get("scope")) ? url.searchParams.get("scope") : "repo";
  const state = crypto.randomUUID().replace(/-/g, "") + crypto.randomUUID().replace(/-/g, "");
  const gh = new URL("https://github.com/login/oauth/authorize");
  gh.searchParams.set("client_id", env.GITHUB_CLIENT_ID);
  gh.searchParams.set("redirect_uri", `${url.origin}/callback`);
  gh.searchParams.set("scope", scope);
  gh.searchParams.set("state", state);
  return new Response(null, {
    status: 302,
    headers: {
      location: gh.toString(),
      "set-cookie": `${STATE_COOKIE}=${state}; Path=/; Max-Age=600; HttpOnly; Secure; SameSite=Lax`,
      "cache-control": "no-store",
    },
  });
}

async function callback(request, url, env) {
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const cookie = (request.headers.get("cookie") || "").split(/;\s*/).find((c) => c.startsWith(STATE_COOKIE + "="));
  const saved = cookie ? cookie.slice(STATE_COOKIE.length + 1) : "";
  if (url.searchParams.get("error")) return page(env, "error", { message: url.searchParams.get("error_description") || url.searchParams.get("error") });
  if (!code || !state || !saved || state !== saved) return page(env, "error", { message: "ログインの確認に失敗しました。もう一度お試しください（state 不一致）" });

  const res = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json", "user-agent": "mat-cms-auth" },
    body: JSON.stringify({ client_id: env.GITHUB_CLIENT_ID, client_secret: env.GITHUB_CLIENT_SECRET, code, redirect_uri: `${url.origin}/callback` }),
  });
  let data = {};
  try { data = await res.json(); } catch (_) { /* noop */ }
  if (!res.ok || !data.access_token) return page(env, "error", { message: data.error_description || data.error || "トークンを取得できませんでした" });
  return page(env, "success", { token: data.access_token, provider: "github" });
}

// Decap CMS のログイン窓（ポップアップ）とのやり取り
//  1) この窓 → 管理画面に "authorizing:github" を送る
//  2) 管理画面が同じ文字列を返してくる（その送り主の origin を確認）
//  3) 許可された origin にだけ "authorization:github:success:{...}" を送る
function page(env, status, content) {
  const allowed = (env.ALLOWED_ORIGINS || DEFAULT_ORIGINS).split(",").map((s) => s.trim()).filter(Boolean);
  const msg = `authorization:github:${status}:${JSON.stringify(content)}`;
  const js = `(function(){
  var allowed=${JSON.stringify(allowed)}, msg=${JSON.stringify(msg)};
  function receive(e){
    if(allowed.indexOf(e.origin)===-1) return;
    window.removeEventListener("message",receive,false);
    window.opener.postMessage(msg,e.origin);
    setTimeout(function(){window.close()},500);
  }
  if(!window.opener){document.getElementById("m").textContent="この画面は管理画面から開いてください。";return;}
  window.addEventListener("message",receive,false);
  window.opener.postMessage("authorizing:github","*");
})();`.replace(/</g, "\\u003c");
  const text = status === "success" ? "ログインしました。この画面は自動で閉じます。" : "ログインに失敗しました: " + (content.message || "");
  const body = `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="robots" content="noindex"><title>MAT CMS ログイン</title></head>
<body style="font-family:sans-serif;padding:24px"><p id="m">${escapeHtml(text)}</p><script>${js}</script></body></html>`;
  return new Response(body, {
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "set-cookie": `${STATE_COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`,
    },
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

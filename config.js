/* =========================================================
   MAT サイト設定（料金・人数はここだけを書き換えてください）
   ---------------------------------------------------------
   MAT_PRICE   : 現在の月額料金（円・数字のみ）。ページ内の料金表示はすべてこの値から自動で入ります。
   MAT_MEMBERS : 現在のおおよその参加人数（表示用の文字列）。
   ========================================================= */
const MAT_PRICE   = 1980;
const MAT_MEMBERS = "約30名";

document.addEventListener("DOMContentLoaded", () => {
  const yen = MAT_PRICE.toLocaleString("ja-JP");
  document.querySelectorAll("[data-mat-price]").forEach(el => el.textContent = yen);
  document.querySelectorAll("[data-mat-members]").forEach(el => el.textContent = MAT_MEMBERS);
});

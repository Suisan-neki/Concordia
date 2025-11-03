# Concordia Invariants（検証可能性のための前提）

本ドキュメントは、イベント連鎖・署名・時刻に関する“壊してはいけない約束事”と、その検証方法を簡潔に示す。

## 1. 連鎖（Merkle-like Chain）
- ハッシュ対象: `{session_id, actor_id, actor_type, act_type, payload, artifact_hash, created_at}`（signatureは除外）。
- 計算式: `curr_hash = SHA256(canonical(envelope) || prev_hash_bytes)`（最初のprevはNone）。
- 不変条件:
  - `prev_hash` は直前イベントの `curr_hash` と一致する。
  - `created_at` はセッション内で単調非減少。
- 検証: `scripts/verify_chain.py` が再計算し、上記2点を警告する。

## 2. 署名（不可否認）
- 対象Act: `agree/reagree/revoke`（現行）。
- 署名対象（現行）: `{session_id, actor_id, actor_type, act_type, payload, artifact_hash}`。
- 既知の限界: `prev_hash/created_at` を含まないため、チェーンコンテキスト/時刻はチェーンとTSAで補う。
- 移行方針（提案）: `content_hash = SHA256(canonical(event_without_signature))` を作成し、`sign(content_hash || prev_hash)` へ。

## 3. 時刻（TSA/アンカー）
- 現行: RFC3161スタブ（`tsa_token`）。
- 提案: Roughtime/OTSで日次ルートに時刻アンカー（`anchor-day` CLI）。

## 4. アクセス制御（ポリシーの態度）
- PoC: `policy.is_allowed(context, action, resource_owner)` は例示実装（正解ではない）。
- 原則: purpose/ttl/scope を最小に。ABACは一解。Macaroonsで目的限定の可視性を担保。

## 5. Capsule（封）
- 定義（現行）: セッションの「鎖の先端（last_curr_hash）」「件数」「時刻範囲」「tsa_token」をJSONでまとめる。
- 生成: `scripts/seal_session.py --session-id <id>`。
- 目的: 検証者が“何を・いつまでに・どこまで一致すべきか”を手元で再現できる。

## 6. 既知のギャップ
- 家族/病院方針/文化の影響は脅威モデルに追補が必要（docs/INHERENT_THREATS.md に節を追加予定）。
- Two‑Lane 構成のデモは Consent Lab を拡張して汎用ロール/質問雛形を追加予定。


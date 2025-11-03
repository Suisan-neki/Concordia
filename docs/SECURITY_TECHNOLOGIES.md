# 尖った技術カタログ（意図と便益を丁寧に）

この文書は「なぜその技術が必要か」「誰にどう嬉しいか」「何を最初に作るか」を、院内ステークホルダーにも伝わる言葉でまとめ直したものです。UIやABACは最小限にし、暗号・鎖・時刻・秘匿集計といった“裏側の信頼”を主役に据えます。

- ゴール: 説明→再確認→再説明→合意/保留→再閲覧の一連の行動を、改ざん不能かつ“圧力ゼロ”で可視化する。
- 優先: ①鎖の完全性 ②署名/時刻の裏付け ③秘匿集計によるテレメトリ。
- 省略: リッチなUIや重厚なABACは後回し。閲覧は最小限、権限は軽量トークンで代替。

---

## 1) Ledger + Merkle を強化する（BLAKE3／MMR／外部アンカー）

目的
- “記録が動かない”ことを技術で示し、疑いと不安を下げる。

何をする
- ハッシュ方式を二重化: 既存の SHA‑256 に加え BLAKE3 を併記（将来互換を確保）。
- 形を最適化: 追記に強い Merkle Mountain Range(MMR)で日次ルートを作る。
- 外部アンカー: 日次ルートを OpenTimestamps 等に時刻アンカー（オフライン時はキュー）。

どう嬉しいか
- 医師: 「あとでログを改ざんしたのでは？」という疑いを受けにくくなる（脅威1）。
- 患者: 自分の選択が後から書き換えられない安心（脅威2・3）。

実装イメージ
- カノニカルJSON（キー順固定/UTC/小数秒）。signature と curr_hash はハッシュ対象外。
- CLI を用意: `verify-session`（再計算検証）、`anchor-day`（日次ルート作成とアンカー）。

注意点
- 仕様（ハッシュ順序・対象）を文書に固定。将来変更は並行運用で移行。

現行仕様（PoC/実装に即した詳細）
- アルゴリズム: SHA‑256 単独（BLAKE3/MMRは計画中）。
- チェーンハッシュ対象（イベント包絡）: 下記フィールドをカノニカル化して `prev_hash` と連結。
  - `session_id: str`
  - `actor_id: str`
  - `actor_type: str`（Enum の `.value`、例: `"doctor"`）
  - `act_type: str`（例: `"agree"`）
  - `payload: object`（任意JSON）
  - `artifact_hash: str | null`
  - `signature: str | null`（署名原文のBase64。存在してもハッシュ対象に含む）
  - `created_at: str`（UTC ISO8601）
- カノニカル化: Python `json.dumps(..., sort_keys=True, separators=(",", ":"))` を使用（空白なし・キー順固定）。
- ダイジェスト計算: `SHA256(canonical_bytes(event_envelope) || prev_hash_bytes)` → `curr_hash (hex)`。
- 保存: `UnderstandingEvent.prev_hash`/`curr_hash` にHEXで格納。
- 検証CLI: `scripts/verify_chain.py --session-id <id>` が同一手順で再計算し、差分を報告。

検証手順（擬似コード）
```
prev = None
for e in events_sorted_by_created_at:
  env = {
    "session_id": e.session_id,
    "actor_id": e.actor_id,
    "actor_type": e.actor_type.value,
    "act_type": e.act_type.value,
    "payload": e.payload,
    "artifact_hash": e.artifact_hash,
    "signature": e.signature,
    "created_at": e.created_at.isoformat(),
  }
  expected = SHA256(canonical(env) || hex_to_bytes(prev))
  assert e.prev_hash == prev
  assert e.curr_hash == expected
  prev = e.curr_hash
```

失敗モードと対処
- created_at を書き換えるとチェーンが崩れる → UTC固定・サーバ生成で回避（現行はサーバ側で付与）。
- イベントの順序入れ替え → `prev_hash` 不一致で検出。
- `payload` 局所改ざん → `curr_hash` 再計算で不一致検出。

将来拡張（計画）
- BLAKE3 併記: `curr_hash_sha256` と `curr_hash_b3` の二系統を保存。
- MMR（日次ルート）: 1日の末尾に `day_root` を生成し、外部アンカーへ提出。
- 外部アンカー: OTS/Roughtime。オフライン時はキューし、接続回復時に一括送信。

---

## 2) 署名と時刻の裏付け（Roughtime／二重署名／FROSTは将来）

目的
- 「誰が・いつ・どの操作を選んだか」を機械的に裏付け、強制の疑念を減らす。

何をする
- 時刻証明を軽量化: Roughtime や OpenTimestamps を採用（RFC3161に縛られない）。
- 体験を先に再現: 医師端末署名 + サーバ署名を併記し、2‑of‑2 的な性質をデモ。
- 将来の拡張: 本格的な閾値署名（FROST）は後段で検討（まずはスタブ設計）。

どう嬉しいか
- 医師: 「サーバが勝手に押したのでは？」という疑念を避けやすい（脅威1・4）。
- 患者: 「自分がこの時に選んだ」事実が時刻と共に残る（脅威2）。

実装イメージ
- 署名対象ダイジェスト: イベント本体 + `prev_hash`（順序を仕様化）。
- 失敗は明示的に拒否。鍵はPoCではファイル/DB、後でHSMへ移行可能に。

現行仕様（署名ベリファイの詳細）
- 署名要求の対象Act: `agree`/`reagree`/`revoke`。
- 公開鍵登録: `ActorKey(actor_id, public_key_hex)` としてDBに保存（Ed25519 Raw 32B をHEX）。
- 署名データ（クライアントが署名するメッセージ）
  - カノニカルJSON: `{session_id, actor_id, actor_type, act_type, payload, artifact_hash}`
  - 署名アルゴリズム: Ed25519（メッセージ＝上記カノニカルバイト列）。
  - エンコード: 署名は Base64（現行実装ではDBにそのまま格納、名前は `signature_hex` だがBase64）。
- ベリファイ: ルーターが公開鍵で検証し、OKならイベントを追記。失敗時は 400。
- 時刻証明: `infra/tsa.request_timestamp()` はRFC3161スタブ（`{digest, timestamp}`）を記録（将来Roughtime/OTSに置換）。

注意（設計上の補足）
- 現行の署名は `prev_hash`/`created_at` を直接は含めない（チェーンがそれを保護）。
- 将来案: `sign(curr_hash_bytes)` へ移行、もしくは「二者署名（端末＋サーバ）」で合意フリーズ力を強化。

---

## 3) Telemetry を“責めない数字”に（2サーバ秘匿集計／DP／ZPI）

目的
- 指標がプレッシャーにならないよう、個票を見せず“集計だけ”を安全に扱う。

何をする
- 2サーバの加法秘密分散でカウントを合成し、合計だけ復元（個人は不可視）。
- 差分プライバシ（DP）で微小ノイズを加え、再識別を防止（設定でON/OFF）。
- Zero Pressure Index(ZPI) をルールベースで算出（LLMなしで成立）。

どう嬉しいか
- 医師: 「数字で責められている感」を避けられる（脅威4）。
- 患者: 質問行動が個人に紐づかず安心（脅威2・3）。

実装イメージ
- 特徴量: clarify / re_explain / re_view / 合意までの時間間隔 / シグナル多様性 / 主導度。
- 重み・閾値は設定ファイルで調整可能（`.env`/`pyproject.toml`）。

現行仕様（PoCの算出ロジック）
- 入力: セッション内の UnderstandingEvent 群。
- 指標: clarify_request_rate, re_explain_rate, post_view_rate, pending_rate, revoke_rate。
- スコア式: `positive = 0.4*clarify + 0.35*post_view + 0.25*re_explain`、`penalties = 0.2*pending + 0.1*revoke`、`score = positive - penalties`。
- ゾーン決定: `score >= 0.15 → Calm`、`>= -0.05 → Observe`、それ以外は `Focus`。
- 実装: `concordia/app/services/telemetry.py`（定数はPoC、責めない表現で提示）。

将来仕様（秘匿集計の方針）
- 2サーバ加法秘密分散: 各側が `x = r` と `y = value - r` を保持し、合算のみ復元。
- 差分プライバシ: 予算 `ε` を設定し、カウントにラプラス/ガウシアンノイズを注入（集計時）。
- 出力は“提案文”のみ。ランキング/分位表示は行わない。

---

## 4) 権限は“軽く確実に”（Macaroons）。ABACは当面スキップ

目的
- 「見せすぎない透明性」を軽量に実現し、運用コストを上げない。

何をする
- Macaroons のケイブアット（条件）で `purpose=care`, `ttl`, `scope=session` を付与。
- ロールは doctor/patient の2つに限定。監査・教育は将来オプション。

どう嬉しいか
- 医師: 必要な相手だけに閲覧を渡せる（脅威3）。
- 患者: 最小開示で安心、期限も明確。

実装イメージ
- 失効/スコープ検証を共通ユーティリティに集約。ZCAP‑LD 等は研究枠に。

現行仕様（最小ABAC）
- ポリシー: `policy.is_allowed(PolicyContext(subject_id, role), action, resource_owner)`。
- 許可例: 患者は `submit_clarify/revisit/send_signal` 自己操作、`view_timeline` は自分のセッションのみ閲覧可。医師はフルアクセス（PoC）。
- ファイル: `concordia/app/domain/policy.py`。

将来仕様（Macaroons設計）
- Caveats: `purpose`, `ttl`, `scope=session:<id>`, `role=doctor|patient`。
- 付与/検証: 署名鍵管理をユーティリティに集約。失効リストと短TTLで運用。
- 表示: 目的と有効期限をUIで明示し、“見せすぎない透明性”を担保。

---

## 5) 検証が主役の最小UI（とCLI）

目的
- “裏側の信頼”をそのまま見せる。UIは少なく、検証を前面に。

何をする
- 画面は患者タイムラインと医師集計のみ。チェーン検証やアンカー状態をピル表示。
- CLI（`dialog_cli`/`doctor_summary`）でいつでも同じ情報を確認可能。

どう嬉しいか
- 医師: 複雑UIに時間を取られず、肝心の信頼状態だけを即確認。
- 患者: 比較やランキングがなく、数字に追われない（脅威4）。

実装イメージ
- UIは増やさない方針。検証と状態表示に絞る。

CLI/検証導線（現行）
- チェーン検証: `python scripts/verify_chain.py --session-id <id>`。
- 医師要約: `python scripts/doctor_summary.py --doctor-id <id>`（責めない要約）。
- 疑似対話: `python scripts/dialog_cli.py`（イベント投入の最小体験）。

データ形式の参照実装
- カノニカル化: `concordia/app/domain/merkle.py: canonical_bytes`
- チェーン計算: `concordia/app/domain/merkle.py: compute_chain_hash`
- 追記処理: `concordia/app/services/ledger.py: LedgerService.append`
- 署名検証: `concordia/app/routers/events.py: _verify_signature_input`


---

## 技術→便益→内在的脅威の対応

- 二重ハッシュ+MMR+アンカー → 「記録は動かない」 → 疑われる恐れ/切り取り拡散（脅威1,3）
- Roughtime+二重署名 → 「押させられていない」 → 強制/時刻疑義（脅威1,2,4）
- 2サーバ集計+DP → 「誰も責められない」 → 数値が圧力になる（脅威4）
- Macaroons → 「見せすぎない透明性」 → 過剰監視（脅威3）
- 最小UI/CLI → 「比較を煽らない」 → 可視化が圧力化（脅威4）

---

## 実装順（現実的なロードマップ）

1. Ledger拡張: BLAKE3併記・MMR日次ルート・`anchor-day`/`verify-session` CLI
2. 署名/時刻: Roughtimeスタブ・2署名併記（FROSTは後段）
3. Telemetry: ZPI実装・2サーバ加法分散・DPノイズ（フラグ）
4. 権限: Macaroons閲覧トークン（2ロール固定）
5. 最小UI: 検証ピル/状態表示、CLI整備

各ステップは「医師/患者にとって何が安心になるか」を説明文とともにデモ可能にする。

---

## Consent Lab（URL共有プレイグラウンド）

目的
- 汎用版 Concordia を最小操作で体験し、裏側の検証可能性を直感で理解してもらう。

何をする
- 2ロール（Initiator/Responder）が Clarify・Ask later・Agree/Decline・Re-Explain を交わす。
- すべての行動は UnderstandingEvent として記録、Merkle 連鎖と Telemetry が即時反映。
- 画面: `/lab` 一覧 → セッション作成 → `/lab/{session_id}/play` で操作。
  - セキュリティ技術カード（鎖どめ/時刻証明/二者署名/目的限定/匿名Clarify/Defer/Forget/選択的可視化）をドラッグ＆ドロップで内在的脅威スロット（権威圧/時間圧/監視圧/不可逆性/情報非対称）に適用し、痕跡として記録。

どう嬉しいか
- 非医療者にも「改ざん不能な痕跡」と「責めない指標」を短時間で理解してもらえる。
- 医療以外のドメイン（教育/契約/運用レビュー）での再利用性を示せる。

導線
- `docs/CONSENT_LAB.md` に起動手順・ルール・拡張の余地を記載。

## 電子カルテ（EHR）と Concordia の役割分担、そして“改訂”の考え方

結論から言うと、Concordia は電子カルテの置き換えではありません。目的は「説明・理解・合意に関する行動の透明化」であり、診療記録（所見・処方・検査結果）そのものは既存のEHRの責務です。

1) 役割分担
- EHR（電子カルテ）: 医療行為の事実（所見、診断、処方、指示）、法的記録。編集は院内規程に従う。
- Concordia: 対話の軌跡（present/clarify/re_explain/agree/review など）と、その完全性検証（チェーン/署名/時刻）。

2) 改訂は“追記”で扱う（書き換え≠悪ではないが、痕跡は残す）
- 追加・補足は `ANNOTATE`（追記）として、対象イベントIDと差分を記録。
- 誤りの訂正は `AMEND`、重大な意義がある場合は双方署名を推奨。
- 効力を否認する場合は `RETRACT`（履歴は残す）。
- 個人情報を将来不可読にしたいケースは `FORGET`（暗号封筒＋鍵破棄＝クリプトシュレッディングの方針）。
- いずれも「元を消す」のでなく「後から来たイベント」で上書きの意味合いを表現し、チェーンに連結する。

3) 現場の“その場完結”運用
- 多くのセッションは当日で完結する想定。再閲覧は既定OFF、要望時に有効化。
- 合意後は要点サマリ（要約とハッシュ）のみ発行。詳細ログは院内に保管。
- Telemetry は当日の行動中心（clarify率、説明→合意までの時間、シグナル多様性）で評価し、数値ではなく穏やかなメッセージで返す。

4) これがなぜ“内在的脅威”を和らげるか
- 医師: 「間違えたら終わり」ではなく、後から追記/訂正できる前提で臨める（脅威1・4）。
- 患者: その場で完結しても、必要時に再確認や追記ができる“選択肢”が担保される（脅威2）。
- 監査: 改訂も追記として鎖に残るため、透明性は維持される（脅威3）。

注: 上記の `ANNOTATE/AMEND/RETRACT/FORGET` は将来の ActType 拡張候補です。導入時は署名要否と表示の合成ルール（実効ビュー）を合わせて仕様化します。

# Concordia — 小さな合意から大きな合意へ（思索中）

タグライン: 医療では「理解の痕跡」をどう残すか — 圧力なく、改ざん不能に、手元で検証可能に

— 本ポスターは研究・設計の思索段階を共有します（実装は一部試作）。点数評価・強制導線・証拠化の自己目的化は採りません。

## 1) 合意のスケール → 医療の文脈
- 合意は「同意書」ではなく、説明→質問→再説明→保留→再閲覧という“理解行動”の往復に本質がある。
- 医療で求められるもの: 自己決定（Voluntariness）/ 説明責任（Informedness）/ 法規・訴訟対応（Verifiability）/ 多職種連携（Boundedness）。
- 役割分担: EHR=医療行為の記録 / Concordia=“理解行動”の検証可能な痕跡。
 - 図1（合意のスケール）: `docs/poster_assets/diagram1_scale.svg`

## 2) 内在的脅威（定義）
- 医師の恐れ（疑われる不安）/ 患者の閉塞（言えない）/ 第三者の過剰監視 / システムの圧力化。
 - 図2（EHRとConcordiaの役割）: `docs/poster_assets/diagram2_roles.svg`

## 3) 技術の役割（目的 → 効き目 → 採用理由）
- Merkle連鎖 +（将来）外部アンカー: 記録は動かない → 疑いを下げる → 手元で再計算でき軽量。
- Ed25519署名 +（将来）二者署名/時刻（Roughtime/OTS）: 押させられていない → 不可否認 → 高速・実装簡潔。
- 目的限定可視性（軽量ABAC → Macaroons）: 見せすぎない透明性 → 主体性を守る → caveatで purpose/ttl/scope。
- 秘匿集計 + DP: “責めない数”のみ提示 → 比較で煽らない → 2サーバ加法分散で個票不可視。
- 最小UI + CLI: 検証を主役に → スコア/ランキングを避ける → タイムラインに検証ピル、CLIでも同一確認。
 - 図3（脅威→技術→効き目の対応）: `docs/poster_assets/diagram3_mapping.svg`

## 4) ZPA（Zero Pressure Agreement）定義
- Voluntariness（合意/保留/撤回が対等）
- Informedness（説明/質問/再説明の痕跡）
- Boundedness（目的/範囲/期間/開示先の明示）
- Revocability（ANNOTATE/AMEND/RETRACT/FORGETの運用）
- Verifiability（署名/時刻/ハッシュの手元検証）

## 5) 2月の到達点（見せ方）
- チェーン検証: `scripts/verify_chain.py` で改ざん検出を実演。
- 署名/時刻: 合意系Actに端末署名必須 + TSAスタブ（Roughtime計画）。
- アンカー: `anchor-day` CLI（MMR/OTSは実験的）。
- 可視性: 最小ABAC + Macaroons v0（purpose/ttl/scope）。
- テレメトリ: Calm/Observe/Focus の穏やかなメッセージ。
- LLM: “提案のみ”の要点サマリ（モデル置換可能）。
 - 図4（タイムラインと鎖どめ/アンカー）: `docs/poster_assets/diagram4_chain.svg`
 - 図5（“責めない数”の処理経路）: `docs/poster_assets/diagram5_telemetry.svg`

## 6) 差別化（EHR / マイナポータル / Concordia）
- 主目的: EHR=医療行為 / マイナポ=交付・照会 / Concordia=“理解行動”の検証痕跡。
- 記録単位: 文書/項目 / 交付トランザクション / UnderstandingEvent（present/clarify/re_explain/agree/re_view）。
- 検証可能性: システム監査中心 / 手元でハッシュ・署名・時刻の再計算。
- 圧力への態度: 非対象（副作用） / Zero Pressure（責めない数・目的限定可視性）。

## 7) 前史 → 転換（要旨）
- 2024/9: 「患者情報共有システム」でRSA/AES/WebAuthn/RBAC/ABAC/監査連鎖を実装。
- 限界: 外部脅威対策だけでは“内在的脅威”を中和できない。合意は「はい/いいえ」ではなく“理解行動”。

## 8) 想定質問（即答）
- なぜブロックチェーンではない？ → PoCは手元検証・運用軽量を優先。外部性はOTS等で担保。
- なぜEd25519？ → 高速・鍵が小さい・実装簡潔。将来は二者署名併記。
- DPは必要？ → 個票を見せない前提でも再識別の懸念がある。目的に応じトグル。
- なぜスコアなし？ → スコアは圧力化しやすい。穏やかな提案文で代替。

## 9) 体験/検証（誰でも）
- 起動: `uvicorn concordia.app.main:app --reload`
- 体験: `http://localhost:8000/lab`
- 検証: `python scripts/verify_chain.py --session-id <id>`

## 10) 運用原則（負荷を増やさない）
- 一意に決まる場合は簡素に済ませる（既定・自動化・短導線）。
- ガードレールは目的に紐づく最小限（purpose/ttl/scope）。曖昧なときだけエスカレーション。
- 合意系Actのみ署名必須・その他は軽量運用。UIは“検証状態”の提示に限定。

## 11) 病院外の適用（独立枠）
- 契約レビュー、説明会/保護者会、授業の理解確認、運用レビュー、製品同意など。
- 同じイベント語彙（present/clarify/re_explain/agree/re_view）で“理解行動”を鎖どめ。
- Two‑Laneの汎用レイヤ（`concordia/`）をそのまま利用。ドメイン固有は薄いアダプタで対応。

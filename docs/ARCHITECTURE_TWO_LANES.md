# 二本立てアーキテクチャ（汎用ツール × 医療アプリ）

リポジトリの構成を「汎用（ドメイン非依存）」「医療（ドメイン特化）」の二本立てで扱えるように整理する提案です。

---

## 1. レイヤー構造

- 汎用レイヤー（Generic Layer）
  - パス: `concordia/`
  - 目的: 合意/説明/理解の“痕跡”を耐改ざんで記録・検証する最小キット。
  - 主要要素:
    - `SessionCapsule`（チェーン化・シール・検証）
    - 将来: 軽量署名ヘルパ、日次アンカーCLI、Macaroonsトークン

- 医療レイヤー（Medical Layer）
  - パス: `SecHack365_project/`
  - 目的: 診察室での電子カルテの情報共有を実現するアプリ本体。
  - 既存要素:
    - フロント: `src/pages/PatientDisplayPage.tsx` ほか
    - バック: `info_sharing_system/app/app.py`、`core/*`（認証/暗号/監査）

---

## 2. 境界の考え方

- 汎用は「イベント→連鎖→検証」のみ（UI/規約/業務ロジックは持たない）。
- 医療は UI と業務導線に集中し、痕跡の保存/検証は Concordia に委譲。
- 双方は JSON で疎結合（capusle の import/export）。

---

## 3. 既存コードとの関係

- いまはコア機能が `SecHack365_project/core/` に存在。
- 直ちに大規模リファクタは行わず、まずは Concordia を独立パッケージとして追加（本PR）。
- 必要に応じて、医療アプリから Concordia を呼び出す小さなアダプタを足していく（段階移行）。

---

## 4. 連携の最小例

- 医療アプリの診察終了時に：
  1) `SessionCapsule(session_id, subject_id)` を生成
  2) 主要イベント（診断確定、説明提示、質問、最終確認）を `append()`
  3) `seal(attestation={"server_sig": "..."})`
  4) `to_json()` を `audit.log` と別ファイルに保存

- 後日検証は：
  - `SessionCapsule.from_dict(...)` → `verify()` の戻り値で検証

---

## 5. 展示・資料の導線

- README（ルート）で二本立ての全体像に言及し、詳細は本ドキュメントへリンク。
- 医療READMEでは「Concordia を使って合意痕跡を自動生成」の一文を追加。
- セキュリティ技術文書から Concordia（汎用）を参照し、医療外利用の可能性を示す。


# Concordia アーキテクチャ設計 ver.0.1

README の思想（Zero Pressure / Comprehension Ledger / Merkle Integrity / Selective Visibility）を、実装可能な技術スタックへ落とし込むための初期設計メモ。  
Python を中心としたミニマル構成を前提に、まずは Docker Compose 上で動かし、院内閉域 Kubernetes へ発展させるロードマップを描く。

---

## 1. レイヤ構成

| レイヤ | 役割 | 主要技術 |
|--------|------|-----------|
| **L0: Delivery / UI** | 患者・医師の双方向ビュー。Zero Pressure Interaction を体現。 | FastAPI Templates, Jinja2, HTMX, TailwindCSS |
| **L1: API / Application** | REST + SSE/WebSocket で理解行動を処理。 | FastAPI (ASGI), Pydantic v2, Uvicorn |
| **L2: Domain Services** | Ledger, 署名、ABAC、Merkle チェーン等のユースケースロジック。 | cryptography (Ed25519/ECDSA), oso or pycasbin, custom services |
| **L3: Infrastructure** | DB、キュー、TSA、監査ログストア。 | PostgreSQL + SQLAlchemy 2.0 / SQLModel, Alembic, Celery/RQ(+Redis), immudb or Merkle chain in Postgres |

---

## 2. コンポーネント詳細

### 2.1 API / Application 層
- **FastAPI** によるモノリシック API。診療セッション単位でエンドポイントを整理（`/sessions/{id}/acts`, `/sessions/{id}/signatures` など）。
- **Pydantic v2** でスキーマ定義し、UI・API・ドキュメント生成 (Swagger + Redoc) を自動化。
- **HTMX + SSE** で署名待ち・再確認リクエストを低フリクションに更新。ASGI ミドルウェアで ABAC/監査を差し込む。

### 2.2 認証・署名
- WebAuthn 依存を避け、院内アカウントで管理する **Ed25519 キーペア** とワンタイムコード（TOTP/PIN）を組み合わせた “1 タップ相当” の UX を設計する。医師・患者ともにモバイル/端末内で秘密鍵を保管し、署名要求時は PIN + ボタン操作で完結させる。
- トランザクション署名には **cryptography** を用い、Ed25519 を標準・一部医療機関要求で ECDSA カーブへ切替可能にする。鍵配布は院内 CA またはハードウェアトークン（FIDO 互換でなくても可）で実施。
- 署名結果は `SignatureRecord` として Comprehension Ledger に格納し、不可否認性を担保。鍵更新・紛失時のローテーションプロトコルを Celery タスクで補助する。

### 2.3 Comprehension Ledger
- **理解行動 (Understanding Act)** を最小単位としたトランザクションテーブル。構造例:
  ```text
  understanding_act(id, session_id, actor_type, act_type, payload_json, created_at, signature_id, merkle_node_id)
  ```
- `act_type` は閲覧、再確認リクエスト（`clarify_request`）、説明確認、署名など。`payload_json` に UI 文脈・質問文・選択肢等を保存。再確認リクエストは「もう少し噛み砕いてほしい」といった安心のための問い直しを意味し、押せなかった事実もイベント化する。
- 挿入時に Merkle ノードへリンクし、不可逆チェーンを更新。

### 2.4 Merkle Integrity Chain / 監査ログ
- Option A: **自前 Merkle チェーン** を PostgreSQL 内で構築（`merkle_node(id, act_id, hash, prev_hash)`）。`hash = H(act_hash || prev_hash)`。
- Option B: **immudb** を別 Pod として連携し、Ledger ハッシュを定期コミット。PoC では Option A を優先、将来的に immudb へ移行。
- 監査参照用に Celery タスクで日次スナップショット＋チェーンルートを別媒体へ保全（WORM 相当）。

### 2.5 ABAC / Selective Visibility
- **oso** もしくは **pycasbin** をポリシーエンジンとして組み込み。診療・教育・監査の 3 コンテキストでポリシーセットを分離。
- 属性例: `role`（doctor/patient/auditor）、`purpose`（care/audit/education）、`sensitivity_level`（PHI/aggregated/metadata）。
- FastAPI の依存注入で `policy_enforcer` を呼び、レスポンスフィルタでマスキング or 非開示を実行。

### 2.6 タスク / 署名時刻保証
- **Celery**（または軽量に RQ）で非同期タスクを管理。ブローカーは Redis、結果バックエンドは PostgreSQL。
- 用途:
  1. RFC3161 TSA 連携（`rfc3161-client`）で日次チェーンルートにタイムスタンプを押印。
  2. 理解行動の集計・UX フィードバック生成。
  3. 署名期限や再説明リマインダーのスケジューリング。
- 院内 TSA が無い場合は内部 Ed25519 TSA を暫定実装し、閉域運用内でチェーンルートを保護。

- ### 2.7 UI ミニマム構成
- **患者ビュー**: セッション進行、説明ステップ、「再確認リクエスト（Clarify）」ボタン、PIN + ボタンで Ed25519 署名。HTMX でステップ遷移。
- **医師ビュー**: 説明スクリプト、患者の理解行動ログ、再説明ワークフロー。Tailwind で共通スタイル。
- **監査ビュー**: メタデータとハッシュのみ参照、内容本体はポリシーに応じてマスク。

---

## 3. データフロー（ハイレベル）

1. 医師がセッションを開始 (`POST /sessions`) → ABAC により権限チェック → Ledger へ「説明開始」イベントを記録。
2. 患者が UI でステップを閲覧 → `GET /sessions/{id}/steps` → 閲覧イベントを Ledger に書込。
3. 再確認リクエストや確認操作は HTMX で API 呼出し、即座に Ledger へ `understanding_act` を追加。
4. 署名ステップでは WebAuthn 認証 → `SignatureRecord` 作成 → Ledger トランザクションとハッシュチェーン更新。
5. Celery が一定周期で最新ノードを取り出し、Merkle ルートを TSA/immudb へコミット。
6. 監査リクエストは ABAC ポリシー評価後、必要最低限のデータのみ返却。

---

## 4. スキーマ / モジュール初期案

```text
app/
├── main.py                 # FastAPI エントリポイント
├── deps.py                 # 依存注入（DB, ABAC, Ledger 等）
├── api/
│   ├── sessions.py         # セッション CRUD + ステップ管理
│   ├── acts.py             # 理解行動 API
│   ├── signatures.py       # WebAuthn チャレンジ/レスポンス
│   └── audit.py            # 監査用エンドポイント
├── services/
│   ├── ledger.py           # Ledger 書込・検証
│   ├── merkle.py           # ハッシュチェーン管理
│   ├── abac.py             # oso/pycasbin ラッパー
│   └── tsa.py              # RFC3161 or 内部TSA
├── models/
│   ├── db.py               # SQLModel / SQLAlchemy 宣言
│   └── schemas.py          # Pydantic モデル
├── tasks/
│   └── worker.py           # Celery / RQ 設定
└── templates/              # Jinja2 + HTMX ビュー
```

DB は `sessions`, `participants`, `understanding_acts`, `signature_records`, `merkle_nodes`, `audit_snapshots`, `abac_attributes` などに分割。Alembic でマイグレーション管理し、監査用メタをペイロードと分離して WORM 性を確保する。

---

## 5. デプロイ戦略

1. **Dev/PoC**: Docker Compose（FastAPI, Postgres, Redis, immudb optional, Celery worker, Flower）。
2. **Staging**: 院内閉域 Kubernetes。Helm or Kustomize で Pod/Secret を管理。Hardware Security Module との連携を検討。
3. **Ops**: GitOps（Flux/ArgoCD）でポリシー変更も含めてトレーサブルに。監査ログは院内 WORM ストレージへ同期。

---

## 6. ゼロプレッシャー実装上の工夫

- UI は常に「選択肢 + 再考ボタン」を提示し、API レイヤで `act_type=reconsider` を記録。
- セッション終了後も一定時間は「再確認リクエスト」チャンネルを維持し、理解行動として記録。
- Ledger へは「押さなかった記録」も追加（例: 署名を保留した行為を明示）。
- ABAC で患者が自分のログを再確認できる権限を持ち、心理的安全を補強。
- **最短 UI フロー（Zero Pressure）**  
  1. 医師ビューから資料提示 → 資料 Artifact の SHA-256 を固定し `act_type=present` として記録。  
  2. 患者ビューで要約を確認し、`OK` / `不明` いずれも `act_type=ack_summary` としてイベント化。  
  3. Clarify モーダルで再確認メッセージを1タップ送信、「あとで聞く」ボタンも常設 (`act_type=clarify_request` / `act_type=ask_later`)。  
  4. 「同意」か「保留」を明示。PIN+Ed25519 署名が成功すると `act_type=agree`、保留は `act_type=pending` として鎖に載せるだけ。  
  5. 後日、患者ポータルで再閲覧→同意/撤回を `act_type=reagree` / `act_type=revoke` として追加。  
  → すべての選択が理解行動イベントとなり、強制でなく選択であることをチェーンが証明する。

### 6.1 再確認リクエストを後押しする UI 施策

- **常設 Clarify ボタン**: 説明の各ステップ下部に「もう少し噛み砕いて」「例を追加して」などプリセットを用意。1タップで `act_type=clarify_request` が送信され、文章入力の負担を取り除く。  
- **あとで聞くリマインダ**: `act_type=ask_later` を押した段階で、患者ポータルに軽い ToDo を表示し、後日でも気兼ねなく質問できる。タップすると再確認用フォームに遷移。  
- **匿名モード**: 同じセッション内でも、質問内容は UI 上では匿名表示され、医師には「Clarify #3」として届く。心理的な遠慮を減らし、“誰が聞いたか”を気にせず送れる。  
- **安心メッセージ**: Clarify を送信した直後に「問い合わせが記録されました。説明者に圧はかかりません」と表示し、ボタンを押したこと自体が歓迎される雰囲気を作る。  
- **音声・スタンプ入力**: 長文入力が難しい人のため、音声メモやスタンプ（「もっとゆっくり」「図で見たい」など）でも `clarify_request` を作れるようにする。  
- **後追い再確認**: セッション終了後もチャット風 UI で Clarify を送れるチャンネルを24時間開放。送れなかった確認を後から埋められる。  

技術的には、これらを `act_type=clarify_request / ask_later` のバリエーションとして扱い、payload にプリセット種別や音声ハッシュを格納するだけで実現できる。

### 6.2 診察室外への延長と医師負担の軽減

人は即座に合理的な判断を下しにくいため、説明と理解のプロセスを診察室外へ延長し「落ち着いて再確認できる」場を用意する。ただし医師が後から電子カルテを漁り直す負担を増やさない設計とする。

- **自動コンテキスト添付**: Clarify が届くと、システムが該当資料のハッシュと説明ステップ番号を自動で紐づけ、医師は電子カルテを開かずに内容を把握できる。  
- **スレッド化された後追いチャンネル**: 診察終了後も 24 時間はチャット風スレッドを維持し、患者は落ち着いたタイミングで再確認を送れる。医師には1日1回のサマリ通知のみ送り、リアルタイム対応を求めない。  
- **テンプレ回答支援**: よくある Clarify にはテンプレート回答やリンクを添えられるようにし、1クリックで返信→ Ledger に `act_type=re_explain` を記録。  
- **カルテ参照の最小化**: Concordia 側で必要なドキュメントスナップショットを保持し、電子カルテを都度開かなくても説明内容が再現できるようにする（診療情報そのものは参照権限内でサマリ化）。  
- **時間配分の見える化**: 後追い Clarify が多い場合は、次回診察の説明順や資料を自動提案し、医師の準備工数を減らす。  

これにより、患者は冷静な環境で判断でき、医師は“あとから電子カルテを掘り返す”負担なくフォローできる。

### 6.3 シンプルな芯を守る方針

侵襲度の高い処置（例: 抜歯以上の手術）を想定していても、Concordia のフローは「説明 → 再確認リクエスト → 同意/保留 → 後日フォロー」という最小構成を維持する。挑戦的な機能（匿名 Clarify、音声入力等）は拡張ポイントとして残し、PoC では常設 Clarify ボタンと 24h フォローのみを実装し、現場のフィードバックを見ながら追加する。複雑化を避け、Zero Pressure の体験を壊さないことを最優先とする。機能よりも、理解行動の完全なトレーサビリティ（署名＋Merkle＋Telemetry）と改ざん耐性に重心を置く。

---

## 7. 今後の設計タスク

1. 理解行動カテゴリと UI ステップのマッピングを詳細化し、Pydantic モデルへ落とし込み。
2. Merkle ノード計算コストと DB インデックス戦略を検証。
3. ABAC ポリシー言語（oso vs casbin）を PoC で比較し、医療部門が編集しやすい DSL を決定。
4. WebAuthn の代替として、PIN + Ed25519 署名の UX を詳細化し、鍵登録/ローテーションフローを設計。
5. 監査フォレンジック UI で `view → ask → re_explain → agree → re_view → revoke` タイムラインと Merkle ハッシュ検証デモを構築。
6. Celery/Redis の冗長化と TSA 連携の SLA を定義。

この設計を起点に、機能仕様（章6）・セキュリティ設計（章7）・UX設計（章8）を README の将来セクションとして拡張していく。監査デモでは curr_hash からの改ざん検知と ABAC による最小開示（質問テキストをマスクしメタのみ提示）を “見せ場” とする。

---

## 8. 旧院内PHRとのスコープ差分

| 項目 | 旧: 患者情報共有システム（院内PHR） | 新: Concordia（理解の痕跡基盤） |
|------|------------------------------------|--------------------------------|
| 目的 | 診療情報を共有して同意を取る | 同意の有無ではなく理解のプロセスを記録 |
| 価値の置き所 | データ共有の便利さ・説明責任 | 心理的安全と透明性の両立（Zero Pressure） |
| 中核データ | 診療データ本体＋同意フラグ | 理解行動トランザクション（閲覧/質問/再説明/再同意） |
| システム統合 | EHR/マイナポータル等と前提連携 | 必要最小限の参照のみ、院内完結で成立 |
| 成果物 | データが見える・同意が残る | 改ざん不能な理解の痕跡（Merkleログ＋署名） |
| 脅威モデル | 外部攻撃＋一般的内部不正 | Fear/Defensiveness/Misinterpretation など内在的脅威 |
| 成功指標 | 同意取得率・閲覧率 | 再確認リクエスト率・再説明率・後日の再閲覧率（圧力ゼロの指標） |

主語を「データを配る」から「対話の痕跡を刻む」に転換し、外部統合負荷を外したことで監査基盤（暗号・ログ・ABAC）へ集中できる。

---

## 9. セキュリティと思想に集中できる理由

1. **スコープ縮小**: EHR/マイナポの双方向連携は参照 or モックに限定し、個人情報スナップショットも最小化。法務・PII コストを抑えて監査ログ/UX に投資。
2. **セキュリティの核へ集中**:  
   - 不可否認性 … Ed25519 署名 + RFC3161（もしくは院内 TSA）。  
   - 改ざん検知 … Merkle チェーン + WORM ストレージ。  
   - 最小開示 … ABAC による用途別ビュー。  
   - 内在的脅威対応 … Zero Pressure UI で段階的同意・再同意・撤回を担保。
3. **思索と設計の接続**: KPI を安心指標（再確認リクエスト率等）に置き、ログを評価ではなく学習素材として扱う。

---

## 10. 技術選定（PoC〜院内検証の現実解）

- **フロント**: Next.js + TypeScript（医師/患者ビューを動的切替、段階的同意 UI）。  
- **バックエンド**: FastAPI または NestJS。JSON API + 署名/ログ発行器を実装しやすい。PoC では FastAPI を優先。  
- **認証/認可**:  
  - Ed25519/PIN 署名ワークフロー（必要なら WebAuthn/FIDO2 も選択肢）。  
  - OIDC (Keycloak) で `doctor/patient/auditor` ロール管理。  
  - ABAC: OPA or Casbin（Python では pycasbin を採用予定）。  
- **監査ログ/改ざん耐性**: immudb or 自前 Merkle + S3 互換 WORM（KMS 付き）。  
- **タイムスタンプ**: PoC では院内 NTP + 署名トークン、本番は RFC3161 TSP/HSM。  
- **DB**: PostgreSQL（JSONB + 行レベル暗号）。  
- **デプロイ**: Docker Compose → 院内 k8s（GitOps 管理）。  
- **鍵管理**: サーバ鍵は HSM/CloudHSM（PoC は YubiHSM/SoftHSM）、ローテ情報を Merkle ルートに記録。

ログ仕様は `event = {actor, role, action, resource, payload_hash, prev_hash, ts, sig}`。payload は別保管し、チェーンはメタのみを扱う。

---

## 11. データモデルの最小セット

- `understanding_events`: 理解行動（view/ask/re_explain/agree/revoke 等）。  
- `sessions`: 患者端末と医師端末のセッション紐づけ。  
- `audit_chain`: `prev_hash`, `curr_hash`, `root_id`, `sig`, `ts`。  
- `policies`: ABAC 属性とビューのマスキングルール。  
- `artifacts`: 提示資料のハッシュ（診療データは参照/モック）。  

---

## 12. MVP フェーズの切り分け

1. 段階的同意 UI（説明 → 要約確認 → 質問 → 同意/保留 → 後日再同意）。  
2. 理解行動トランザクションを Merkle ログに積み、日次スナップショット。  
3. Ed25519 署名 + 簡易 TSA（院内時刻トークン）。  
4. ABAC ビュー：診療用/監査用で項目マスク。  
5. 指標ダッシュボード：再確認リクエスト率・再閲覧率・保留率を可視化。  

ここまでで「圧力ゼロ × 改ざん不能な理解の痕跡」を実証でき、思想とセキュリティの芯を提示できる。Stretch には ZKP による説明証明や差分プライバシ集計を検討。

---

## 13. リスクと先回り施策

- **“監視っぽい”拒否感**: 文言は「共通アーカイブ」へ統一し、患者 UI に「後から何度でも見返せます」を常時表示。  
- **端末なりすまし**: 患者端末ペアリング（QR/NFC）＋ PIN/署名を組み合わせる。  
- **法的有効性**: Concordia はプロセス証跡であり既存同意書の補完と位置づけ、置換しない。  

---

## 14. 設計の芯（まとめ）

Concordia は「情報を配る」から「理解の痕跡を刻む」へ主語を転換したことで、外部統合の重さを排し、暗号・ログ・ABAC・Zero Pressure UI といったセキュリティ/思想の核に集中できる。  
このフォーカスが不可否認性・改ざん耐性・最小開示と、内在的脅威に向き合う心理設計を同時に深掘りする道を開く。

---

## 15. 詳細設計テンプレート

この節は PoC フェーズの詳細設計書をそのまま書き起こせるテンプレ。各項目を埋めながらドキュメント化する。

### 15.1 アーキテクチャ図（テキスト表現）

```
[Patient UI (Next.js)] --JSON/HTMX--> [FastAPI Gateway] --gRPC/Service--> [Ledger Service]
                                         |                         |
                                         |--> [ABAC Policy Engine] |
                                         |--> [Signature Service]--+--> [Ed25519 Vault/HSM]
                                         |--> [Audit Chain Service]--> [PostgreSQL + immudb]
                                         |--> [Task Queue]---------+--> [Celery/Redis/TSA]
                                         +--> [View Renderer] (Jinja2/Tailwind)
```

### 15.2 シーケンス（Zero Pressure 最短フロー）

1. 医師が資料を提示 → `POST /sessions/{id}/artifacts` （artifact hash 固定）。  
2. 患者ビューが要約を取得 → `GET /sessions/{id}/summary` → `PATCH /acts/{id}` (`act=view_summary/status=ok|unknown`)。  
3. 再確認リクエストモーダル → `POST /sessions/{id}/clarify`（`act=clarify_request`）。「あとで」→ `act=ask_later`。  
4. 同意/保留 → `POST /sessions/{id}/consent`（`act=agree` or `act=pending`, payload に署名/TOTP）。  
5. 後日再同意 → `POST /sessions/{id}/reauthorize`（`act=reagree` or `act=revoke`）。  
6. 各 API ハンドラが `LedgerService.append()` を呼び、`audit_chain` へ Merkle ノードを追加。  
7. Celery タスクが日次で `curr_hash` を TSA/immudb へコミット。

### 15.3 API スキーマ雛形

```yaml
POST /sessions/{session_id}/acts
request:
  actor_id: string
  actor_role: doctor|patient|auditor
  act_type: view|clarify_request|ask_later|re_explain|agree|pending|revoke
  payload:
    summary_status?: ok|unknown
    clarify_note?: string
    signature?: base64
    artifact_hash?: sha256
response:
  act_id: uuid
  merkle_hash: hex
  timestamp: RFC3339
```

同様に `/signatures/challenge`, `/consent`, `/audit/timeline` などを定義し、Payload は `domain/schemas.py` にマッピングする。

### 15.4 ログ仕様テンプレ

| フィールド | 型 | 説明 |
|------------|----|------|
| `event_id` | UUID | Ledger の主キー |
| `session_id` | UUID | 患者-医師セッション |
| `actor` | string | user id |
| `role` | enum | doctor/patient/auditor |
| `action` | enum | view / ask / re_explain / agree / pending / re_view / revoke |
| `resource` | string | artifact id / consent id |
| `payload_hash` | SHA256 | マスク対象データのハッシュ |
| `prev_hash` | SHA256 | 直前 Merkle ノード |
| `curr_hash` | SHA256 | 現ノード |
| `sig` | base64 | Ed25519 署名 |
| `ts` | RFC3339 | タイムスタンプ |

payload 本体は `storage.py`（S3/WORM）に格納し、ABAC でマスキングする。

### 15.5 監査フォレンジック UI

- タイムラインビュー: `view → ask → re_explain → agree → re_view → revoke` を一列で表示。  
- ハッシュ検証: 任意イベントから `curr_hash` を再計算し、画面上で一致/不一致を提示。  
- ABAC: 監査ロールはメタのみ表示、質問文などの機微は `***` でマスク。  
- エクスポート: ルートハッシュ + 署名済みタイムスタンプを PDF/CSV で出力。

### 15.6 KPI / ダッシュボード

- `clarify_request_rate = (#act=clarify_request + #act=ask_later) / total_sessions`  
- `re_explain_rate`, `post_view_rate`, `pending_rate`, `revocation_rate`.  
- Zero Pressure 指標は「安心ゾーン（Calm / Observe / Focus）」として表示し、上がった/下がったという競争感を生まないようにする。

---

## 16. Zero Pressure Telemetry（安心指標の実装）

「監査者がいなくても、患者・医師自らが“圧力を感じなかった”ことを確かめられる」ための仕組み。Merle チェーンや署名よりも“心理メトリクス”を前面に出し、Concordia の価値を一目で伝える。

### 16.1 指標セット

| 指標 | 計算式 | 解釈 |
|------|--------|------|
| 再確認リクエスト率 (`clarify_request_rate`) | `(act=clarify_request + act=ask_later) / sessions` | 高いほど問い直しがしやすい |
| 再説明率 (`re_explain_rate`) | `(act=re_explain) / sessions` | 医師が追加説明を促進できている |
| 保留率 (`pending_rate`) | `(act=pending) / consent_attempts` | 圧力が低い（即決を強いていない） |
| 再閲覧率 (`post_view_rate`) | `(act=re_view) / sessions` | 後日見返せる安心感 |
| 撤回率 (`revocation_rate`) | `(act=revoke) / sessions` | 正当な撤回が機能している |

これらは理解イベントそのものから導出され、マーケ指標ではなく心理的安全の可視化として扱う。

### 16.2 パイプライン

1. `understanding_events` テーブルに `act_type` と `actor_type` を刻む。  
2. Celery タスク `calculate_zero_pressure_metrics` が 15 分ごとに最新イベントを集計。  
3. 結果を `metrics_snapshot(date, clarify_request_rate, ...)` に保存し、Merle チェーンにも集計値ハッシュを記録。  
4. Next.js ダッシュボードが `/metrics/zero-pressure` でチャート表示。  
5. PDF/画像としてエクスポート可能にし、院内掲示や説明資料に流用。

### 16.3 UI モック（テキスト）

```
Zero Pressure Dashboard
-----------------------
Clarify requests   ██████  “十分に問い直せています”
Re-explain events  ████    “追加説明が活発です”
Pending decisions  ██      “即決を避けた割合”
Post-view events   ██████  “後日フォローが続いています”
Revoke events      █      “正当な撤回が機能中”

Comfort Zone: Calm (今週は選択肢が豊富な空気)
Next check-in: optional – 見ないを選べます
```

トレンド矢印や色ではなく「ゾーン名（Calm / Observe / Focus）」で今の空気を伝え、数値競争を避ける。スクリーンショット1枚でコンセプトが伝わるようにする。

### 16.4 技術的ポイント

- 集計は SQL (window function) で即算出できるため、PoC では DB 集約 + Celery で十分。  
- イベントストリームを Kafka へ拡張すれば、リアルタイムに WebSocket でダッシュボード更新も可能。  
- 指標自体も Merkle チェーンにハッシュを残すことで、後から「このグラフは改ざんされていない」証明ができる。  
- 指標は 0〜1 のスコアではなく、「Calm（安心に富む）」「Observe（様子を見る）」「Focus（再設計を検討）」の3ゾーンに分類する。基準は過去4週平均との乖離やメタデータ補正を用いて柔らかく判定する。  
- ゾーンが Focus に入った場合のみ通知（Slack/Webhook）を送り、誰かを責めるのではなく UI/プロセス改善の対話を始めるトリガにする。

### 16.5 PoC TODO

1. `metrics_snapshot` テーブルと Celery タスクを実装。  
2. FastAPI で `/metrics/zero-pressure` API を用意し、Next.js でチャート描画。  
3. Clarify/再閲覧/再説明/保留のバランスから「安心ゾーン（Calm/Observe/Focus）」を判定するロジックを定義（例: ベースラインとの乖離 + メタデータ補正）。  
4. 指標差分を Merkle チェーンに刻み、`verify-metrics` CLI を提供。  
5. 毎週の PDF レポートを自動生成し、スクリーンショットベースのデモ資料を準備。

### 16.6 公平性と適用範囲

- **評価ではなく自己レビュー用途**: ダッシュボードは施設全体の空気を示す集計のみを共有し、個別セッションは本人が任意で振り返る形にする。医師をランキングしたり、特定患者の挙動を晒したりしない。  
- **メタデータ補正**: 患者状態や説明ボリュームといったメタ情報で正規化し、極端なケースは「参考値」として集計から除外。想定と異なるデータは UI/コンテンツ改善検討のトリガに用いる。  
- **トレンド比較**: 絶対値ではなく、自分の過去や施設平均との乖離を見せることで “圧力” を下げる。  
- **適用範囲**: 安全指標は原則院内向け（医師・患者の自己レビュー）に限定し、外部公開や他業種展開はアイデア段階に留める。必要なら別プロジェクトとして切り出す。  
- **公開ポリシー**: 指標を院内でどう共有するか（部署・閲覧権限）を事前に定め、閲覧者ごとに表示粒度を切り替える。  

こうした設計により、「安心の指標」が誰かへの負担や監視にならず、院内で心理的安全を自律的に確認する仕組みとして機能する。

### 16.7 Zero Pressure 可視化 UX ガイドライン

- **見ない権利の確保**: 指標は自動ポップアップさせず、ユーザーが見たいタイミングで開ける。通知も opt-in にして「今は見ない」を選べる。  
- **緩衝メッセージ**: ダッシュボードを開いた直後に「これは改善のヒントです」「個人評価ではありません」と明記し、心理的安全を補強。色は柔らかいパレットで統一。  
- **文脈付き表示**: 数値だけでなく自動コメントを生成（例: 「再確認リクエストが減っています。先週導入した説明順の影響かもしれません」）。原因探索のヒントを添えて不安を和らげる。  
- **肯定的トーン**: プラスの変化は「問い直しがしやすくなっています」と称賛し、マイナス方向も「改善余地があります」という言い方に留める。  
- **個別セッションは自己レビュー専用**: 施設共有は集計のみ。個人の詳細ログは本人が任意で閲覧し、メモも残せる（見る/見ないを選択できる）。  
- **時間差表示**: セッション終了直後は指標を表示せず、クールダウン後に「このセッションを振り返りますか？」と穏やかに問う。  

これらの UI ルールを実装上の acceptance criteria として設け、ゼロプレッシャーの理念がデータ可視化でも守られるようにする。

---

## 17. STRIDE × 内在的脅威マッピング

心理的安全を揺らす要因を STRIDE 観点で再整理し、Zero Pressure のテクニカルコントロールに紐づける。

| STRIDE | 内在的脅威としての表れ | Concordia の対策 |
|--------|------------------------|-------------------|
| Spoofing | 「本当にこの医師の説明？」という不安、第三者操作への警戒。 | Ed25519 署名＋PIN/TOTP で操作主体を証明し、患者も Ledger 上で自分のイベントを確認可能。 |
| Tampering | 記録が書き換わる恐れから問い直しを控える。 | Merkle チェーン＋TSA/immudb で改ざん不能を示し、UI でもチェーン状態を可視化。 |
| Repudiation | 「後で責められるのでは」という防衛感情。 | 理解行動（保留・再確認含む）を不可否認トレースとして残し、ログが自分を守るメッセージを常に提示。 |
| Information Disclosure | 質問内容が監査者に晒される恐れ、監視への抵抗。 | Selective Visibility：本人のみフル閲覧、第三者はメタのみ。アクセス履歴も Ledger 化。 |
| Denial of Service | Clarify 窓口が閉じる・時間切れになる不安。 | Clarify ボタン常設、24h チャネル、「あとで聞く」イベントで質問権を奪われない設計。 |
| Elevation of Privilege | 上位者が勝手にログを評価に使うのではという警戒。 | ABAC + アクセスログをチェーンに刻み、誰がいつ閲覧したかを本人が確認できる。 |

技術要素（署名・Merkle・ABAC・Telemetry）を「心理的 STRIDE」の対策として説明することで、内在的脅威を中和する設計思想を共有する。

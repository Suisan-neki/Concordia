# Concordia 技術用語解説

## 目次
1. [合意ログの鎖（Comprehension Ledger + Merkle Chain）](#合意ログの鎖)
2. [署名/TSA スタブ](#署名tsa-スタブ)
3. [Telemetry ゾーン](#telemetry-ゾーン)
4. [ABAC/アクセスログ](#abacアクセスログ)
5. [簡易 UI](#簡易-ui)

---

## 合意ログの鎖

**Comprehension Ledger（理解台帳）** と **Merkle Integrity Chain（メルクル完全性チェーン）** の組み合わせ。

### 技術概要

**1. Comprehension Ledger（理解台帳）**
- **目的**: 患者と医師の「理解行動」を不可逆的に記録
- **最小単位**: 理解行動（Understanding Act）＝閲覧、質問、再確認リクエスト、署名など
- **データ構造**: 
  ```python
  UnderstandingEvent {
    session_id: str,    # 診療セッションID
    actor_id: str,      # 行動した人（患者/医師）
    act_type: enum,     # 行動タイプ（VIEW, ASK, RE_EXPLAIN等）
    payload: dict,      # 具体的な行動内容
    prev_hash: str,     # 直前のイベントのハッシュ
    curr_hash: str,     # このイベントのハッシュ
    signature: str      # 署名
  }
  ```
- **特徴**: 追記のみ（append-only）、改ざん不可能

**2. Merkle Integrity Chain（メルクル完全性チェーン）**
- **目的**: 改ざんを検知するためのハッシュチェーン構造
- **仕組み**: 各イベントのハッシュが直前のイベントのハッシュを含むため、1つでも改ざんすると全チェーンが破綻
- **ハッシュ計算式**: 
  ```python
  curr_hash = SHA256(
    session_id + actor_id + act_type + 
    payload + artifact_hash + 
    signature + created_at + prev_hash
  )
  ```
- **実装例**:
```python:concordia/app/services/ledger.py
class LedgerService:
    def append(self, event_in: UnderstandingEventCreate) -> UnderstandingEvent:
        prev_hash = self._latest_hash()  # 直前のハッシュを取得
        event.curr_hash = compute_chain_hash(
            {
                "session_id": event.session_id,
                "actor_id": event.actor_id,
                "act_type": event.act_type,
                "payload": event.payload,
                "created_at": event.created_at.isoformat(),
            },
            prev_hash,  # チェーンとして繋げる
        )
        self.session.add(event)
        return event
```

### 実用例

患者が説明文書を閲覧すると：
1. `UnderstandingEvent`が生成される
2. 前回のイベントのハッシュ（`prev_hash`）を含めて、新しいハッシュ（`curr_hash`）を計算
3. チェーン上に追加され、改ざん不可能な鎖として保存される

---

## 署名/TSA スタブ

**Ed25519 デジタル署名** と **TSA (Time Stamp Authority) スタブ** の組み合わせ。

### 技術概要

**1. Ed25519 デジタル署名**
- **目的**: 誰が、いつ、何に同意したかを証明（不可否認性）
- **アルゴリズム**: Ed25519（楕円曲線暗号）
- **仕組み**:
  - 患者/医師それぞれが秘密鍵を持ち、トランザクションに署名
  - 公開鍵で検証できる
- **実装例**:
```python:concordia/app/domain/sign.py
def generate_keypair() -> Tuple[bytes, bytes]:
    """Ed25519キーペアを生成"""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return (private_key.private_bytes, public_key.public_bytes)
```

**2. TSA スタブ（Time Stamp Authority スタブ）**
- **目的**: 「いつ」起こったかという時刻の証明
- **本来の仕組み**: RFC3161プロトコルで外部TSAサーバーにタイムスタンプを取得
- **スタブ（現状）**: 本番環境のTSAサーバーがない場合の暫定実装
- **実装例**:
```python:concordia/app/infra/tsa.py
def request_timestamp(digest: bytes) -> dict:
    """TSA スタブ: 本番では RFC3161 クライアントに置き換える"""
    return {
        "digest": digest.hex(),
        "timestamp": datetime.utcnow().isoformat()
    }
```
- **本番実装**: 院内のTSAサーバーと連携してRFC3161タイムスタンプを取得

### 実用例

患者が同意ボタンを押すと：
1. 秘密鍵でトランザクションに署名
2. TSAスタブ（または本番TSA）で時刻証明
3. 署名とタイムスタンプがLedgerに保存される
4. 後から「本人がこの時刻に同意した」ことが証明できる

---

## Telemetry ゾーン

**Zero Pressure 指標を可視化し、「安心ゾーン」を判定する仕組み。**

### 技術概要

**目的**: 患者・医師が「圧力を感じなかった」ことを測る心理メトリクス

**指標セット**:
| 指標 | 計算式 | 意味 |
|------|--------|------|
| 再確認リクエスト率 | `(clarify_request + ask_later) / 総イベント数` | 質問しやすさの指標 |
| 再説明率 | `re_explain / 総イベント数` | 説明が理解されていない度合い |
| 再閲覧率 | `re_view / 総イベント数` | 後から確認しやすい度合い |
| 保留率 | `pending / 総イベント数` | 即決できない安全さ |
| 取り消し率 | `revoke / 総イベント数` | 後戻りできる安心感 |

**安心ゾーン（Comfort Zone）判定**:
```python:concordia/app/domain/models.py
class ComfortZone(str, Enum):
    CALM = "calm"      # 落ち着いて理解できている
    OBSERVE = "observe"  # 観察が必要
    FOCUS = "focus"   # 集中して理解しようとしている
```

**実装例**:
```python:concordia/app/services/telemetry.py
class TelemetryService:
    def snapshot_for_session(self, session_id: str) -> MetricsSnapshot:
        events = self.session.exec(...)
        total_events = max(len(events), 1)
        
        clarify = self._count(events, {ActType.CLARIFY_REQUEST})
        re_explain = self._count(events, {ActType.RE_EXPLAIN})
        post_view = self._count(events, {ActType.RE_VIEW})
        
        # 率を計算してZone判定
        zone = self._zone_from_rates(
            clarify / total_events,
            post_view / total_events,
            re_explain / total_events,
            ...
        )
        
        return MetricsSnapshot(
            session_id=session_id,
            clarify_request_rate=clarify / total_events,
            comfort_zone=zone,  # CALM / OBSERVE / FOCUS
            ...
        )
```

### 実用例

診療セッションが終了すると：
1. 全イベントから各種指標を算出
2. 「安心ゾーン（Comfort Zone）」を判定
3. スナップショットとして保存
4. ダッシュボードで可視化

**解釈**:
- **CALM**: 良好。患者が落ち着いて理解できている
- **OBSERVE**: 注意。何か気になることがあるかも
- **FOCUS**: 集中。患者が一生懸命理解しようとしている（圧力なしの証拠）

---

## ABAC/アクセスログ

**Attribute-Based Access Control（属性ベースアクセス制御）** とアクセスログ。

### 技術概要

**ABAC（Attribute-Based Access Control）**
- **目的**: 誰が、何を、どのような目的で見るかを属性で制御
- **従来のACLとの違い**: 単純な権限リストではなく、複数の属性（役割、目的、機密度など）で柔軟に制御
- **属性例**:
```python:concordia/app/domain/policy.py
@dataclass
class PolicyContext:
    subject_id: str     # 誰
    role: str           # 医師/患者/監査者
    purpose: str        # 診療/教育/監査
    sensitivity: str    # 標準/機密/PHI（個人情報）
```
- **ポリシー例**:
  - 医師（role=doctor）+ 診療目的（purpose=care）→ 詳細データ閲覧可
  - 監査者（role=auditor）+ 監査目的（purpose=audit）→ マスキングされたデータのみ閲覧可
  - 患者（role=patient）+ 自分のデータ → 完全閲覧可

**アクセスログ**
- **目的**: 誰が何を見たかの記録（監査証跡）
- **記録内容**: アクセス時刻、ユーザーID、役割、閲覧したリソース、ポリシー評価結果

**実装例**:
```python:concordia/app/services/abac.py
class ABACService:
    def evaluate_access(self, context: PolicyContext, resource: str) -> bool:
        """ABACポリシーを評価"""
        if context.role == "doctor" and context.purpose == "care":
            return True  # 医師は診療目的で全データ閲覧可能
        elif context.role == "auditor" and context.purpose == "audit":
            return context.sensitivity != "PHI"  # 監査者は個人情報以外は閲覧可
        # ...
```

### 実用例

監査者が診療ログを見ようとすると：
1. ABACポリシーが評価される
2. 役割=監査者、目的=監査 → メタデータとハッシュのみ表示
3. 機密情報（患者名、質問内容など）は `***` でマスキング
4. アクセスログに「いつ、誰が、何を見たか」が記録される

---

## 簡易 UI

**HTMX + FastAPI Templates + TailwindCSS** による最小限のUI。

### 技術概要

**構成要素**:
1. **FastAPI Templates (Jinja2)**: サーバーサイドレンダリング
2. **HTMX**: ページ遷移なしで動的にUI更新
3. **TailwindCSS**: 最小限のスタイリング

**UI構成**:
- **患者ビュー**: 診療セッションの進行、説明ステップ、「再確認リクエスト」ボタン、PIN+ボタンで署名
- **医師ビュー**: 説明スクリプト、患者の理解行動ログ、再説明ワークフロー
- **監査ビュー**: メタデータとハッシュのみ表示、機密情報はマスキング

**実装例**:
```html:concordia/app/templates/timeline.html
<!-- HTMXでイベントを動的に追加 -->
<div hx-get="/api/sessions/{{ session_id }}/events"
     hx-trigger="every 2s"
     hx-swap="innerHTML">
  <!-- イベント一覧 -->
</div>

<!-- 再確認リクエストボタン -->
<button hx-post="/api/sessions/{{ session_id }}/acts"
        hx-vals='{"act_type": "CLARIFY_REQUEST"}'>
  もう少し詳しく教えてください
</button>
```

### 実用例

患者が「説明をもう一度読みたい」とクリックすると：
1. HTMXがバックグラウンドでAPIを呼び出す
2. `RE_VIEW`イベントがLedgerに追加される
3. UIが自動的に更新される（ページリロード不要）
4. 医師のビューにも「患者が再閲覧した」ことが表示される

---

## まとめ

| 用語 | 技術 | 役割 |
|------|------|------|
| **合意ログの鎖** | Ledger + Merkle Chain | 理解行動を改ざん不可能な鎖として保存 |
| **署名/TSA** | Ed25519 + RFC3161 | 誰が何に同意したかを証明、時刻証明 |
| **Telemetryゾーン** | メトリクス集計 + Comfort Zone判定 | 患者が圧力を感じていないかを測る |
| **ABAC/アクセスログ** | ポリシーエンジン + 監査ログ | 誰が何を見るかを属性で制御、全記録 |
| **簡易UI** | HTMX + Jinja2 | 最小限のUIで圧力ゼロ体験を実現 |

すべての機能が連携して、**「説明と理解のプロセスを圧力なく記録する」** ことを実現しています。


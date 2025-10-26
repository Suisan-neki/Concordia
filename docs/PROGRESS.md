# Concordia Progress Log

開発開始から今日（2025-10-26）までの主要な進捗を記録する。

## 2025-10-24 — 仕様固めとドキュメント整備
- 初期の仕様ドラフトと用語整理を開始し、読者（院内ステークホルダー＋エンジニア）向けの narrative を README に集約（README.md）。
- Terminology/合意ニュアンスを整理し、合意の再定義を文書化（docs/TERMINOLOGY.md）。

## 2025-10-25 — バックエンド基盤構築
- FastAPI/SQLModel ベースの API スケルトンを整備し、Zero Pressure の理解行動（`present/clarify_request/re_explain/agree/...`）を Enum 化（concordia/app/domain/models.py）。
- セッション・イベント・メトリクスのルーターを実装し、タイムライン HTML を追加（concordia/app/routers/{events,sessions,view,metrics}.py, concordia/app/templates/timeline.html）。
- TelemetryService で Calm/Observe/Focus ゾーン計算を実装し、最初の pytest を導入（concordia/app/services/telemetry.py, concordia/tests/test_telemetry.py）。
- Dockerfile / docker-compose により Postgres + Redis + API のローカル実行環境を整え、README にセットアップ手順を追記（Dockerfile, docker-compose.yml, README.md）。

## 2025-10-26 — セキュリティ要素と CLI ツール整備
- 署名鍵管理・イベント署名検証・Merkle チェーン計算を追加し、イベント署名テストを作成（concordia/app/domain/sign.py, concordia/app/tests/test_events_signature.py 等）。
- Metrics/Audit/View ルーターを拡充し、ABAC サービスのポリシー評価を簡素化（concordia/app/domain/policy.py, concordia/app/routers/audit.py）。
- Zero Pressure UI の文脈を README に反映し、医療以外の応用（営業・不動産など）への示唆と「ボタン案」「ゲーム的フィードバック案」を追記（README.md）。
- CLI 群を追加：疑似対話入力（scripts/dialog_cli.py）、医師メトリクス要約（scripts/doctor_summary.py）、デモデータ投入（scripts/seed_demo.py）。PostgreSQL の `acttype` enum を自動拡張する仕組みを DB 層＆CLI 双方に実装（concordia/app/infra/db.py, scripts/dialog_cli.py）。
- **LLM 評価機能を追加**: 行動指標だけでは測れない「理解の質」を LLM で評価する仕組みを導入（concordia/app/services/llm_assessment.py, ComprehensionAssessment モデル）。会話履歴から理解度（HIGH/MODERATE/LOW）・信頼度・懸念点を自動判定し、Zero Pressure 指標と合わせて使うことで、最終的な合意の妥当性を技術的に担保できる設計とした。現時点ではモック実装、本番では OpenAI / Anthropic / 院内 LLM API に接続予定。
- 進行中のタスクとして signal 系 ActType の API テスト追加、README の用語統一、CLI のイベント分類ロジック強化が残件。

---

次の更新時は、テレメトリ指標の評価ロジック検証・CLI のアドバイス機能・Zero Pressure 体験の説明キャプチャなどを追記予定。必要に応じて日付ごとに本ファイルへ追記する。株式会社内共有や院内ステークホルダー向けブリーフィング資料にも転用可能な粒度を意識する。 

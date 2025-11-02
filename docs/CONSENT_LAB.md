# Consent Lab（公開URLで共有できる最小プレイグラウンド）

合意とは何か。「小さな合意」と「大きな合意」の違い、そして内在的脅威を、勝敗や点数なしで体験・議論するためのミニアプリです。

## 起動

Docker が使えない/使いたくない場合は SQLite でそのまま起動できます。

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
export DATABASE_URL=sqlite:///./concordia.db  # Windows: set DATABASE_URL=sqlite:///./concordia.db
uvicorn concordia.app.main:app --reload
```

- 一覧: http://localhost:8000/lab
- セッション作成は一覧から「開始」を押すだけ。作成後は Responder で参加できます。
- 共有用URLはプレイ画面上部の「URLを共有」でコピーできます。

## ルール（最小）

- 役割: Initiator / Responder
- 行動（Responder）: Clarify / Ask later / Agree / Decline / Re-View
- 行動（Initiator）: Re-Explain（言い換え）
- すべての行動はイベントとして鎖どめされます（タイムラインは「📜 Timeline」から閲覧）。
- 右上の Zone バッジ（Calm/Observe/Focus）は Telemetry をもとに2秒ごとに更新されます。

### 脅威 ←→ 技術カード（ドラッグ＆ドロップ）

- 画面下部のカード（鎖どめ / 外部時刻証明 / 二者署名 / 目的限定トークン / 匿名Clarify / Defer / Forget / 選択的可視化）を、内在的脅威スロット（権威圧 / 時間圧 / 監視圧 / 不可逆性 / 情報非対称）へドラッグ＆ドロップ。
- ドロップすると「MITIGATE」イベントとして鎖に追記され、後から何をどう配慮したかを検証できます。

## 収集・記録

- DBには UnderstandingEvent が追記され、前のハッシュと結合して改ざん検知が可能です。
- 署名や外部アンカーはオプション（初期は無効）。

## シナリオ（非医療・例）

- グループ写真の公開（小さな合意／公開範囲／可逆性）
- 画面共有の一時許可（小さな合意／時間／可視性）
- 行動ログの継続収集（大きな合意／長期／撤回困難）

## 注意

- スコアや勝敗はありません。演出は最小です。
- 目的は議論の発端を作ることです。「合意しない自由」「保留する自由」も同じ重みで扱います。

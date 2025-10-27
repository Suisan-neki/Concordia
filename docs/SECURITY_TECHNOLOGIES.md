# ゼロプレッシャー合意における高度なセキュリティ技術

## 概要

**個人実装だからこその強み**  
本プロジェクトは個人開発のため、大規模運用の制約がない。  
従来の「署名」のような古典的な技術ではなく、**ニッチで先進的な技術**を試せる場として活用する。

> **技術選定の方針**  
> ✅ コスト効率よりも**技術的好奇心**を優先  
> ✅ 実用性よりも**実験的価値**を追求  
> ✅ 過剰な技術も含めて**試してみる価値がある**

---

## 現状の実装（従来技術）

### Ed25519 署名 + TSA トークン ✅ 実装済み

```python
# concoridia/app/domain/sign.py
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def generate_keypair() -> Tuple[bytes, bytes]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return (private_key.private_bytes(...), public_key.public_bytes(...))
```

**なぜ置き換えるか？**
- Ed25519は「確立された技術」
- 個人実装なら、もっと**面白い技術**を試せる
- 「薄っぺらくない」技術を実装してみたい

---

## 1. ゼロ知識証明（Zero-Knowledge Proofs）⭐ 最優先実装

### なぜ実装すべきか

従来の署名技術では：
```
患者: 「手術のリスクを理解しました」→ [署名]
医師: 署名を確認（内容も見える）
```

問題：
- 医師が患者の「同意内容」を見てしまう
- 患者は「本当の気持ち」を言えない
- 署名という「記録」が圧力になる

### ゼロ知識証明なら

```
患者: 「手術のリスクを理解した」という「証明」を生成
医師: 証明の「真偽」のみを検証（内容は見えない）
```

**実装例:**
```python
# 患者が「理解した」という証明を生成（内容は隠す）
zk_proof = generate_zk_proof(
    statement="手術のリスクを理解した",
    secret="具体的な不安や質問内容",
    private_key=patient_key
)

# 医師は証明の有効性のみを検証
is_valid = verify_zk_proof(zk_proof)
# True → 患者は理解している（内容は不明）
```

### 実装方針

1. **Circom + SnarkJS** で回路を定義
2. **Bellman** (Rust) / **Arkworks** (Rust) で実装
3. Python のバインディングを通じて呼び出し

### メリット
- ✅ **プライバシー保護**: 内容を一切明かさない
- ✅ **圧力の軽減**: 「何を理解したか」を公開する必要がない
- ✅ **技術的挑戦**: 個人実装で学べる機会

### デメリット
- ⚠️ 計算コストが高い（数秒〜数分）
- ⚠️ 実装が複雑（しかし挑戦する価値がある）

### 技術スタック
```bash
# 必要なツール
sudo npm install -g circom snarkjs
pip install python-snark
```

---

## 2. 差分プライバシー（Differential Privacy）⭐ 併行実装

### なぜ実装すべきか

従来の統計公開では：
```
「患者100人中80人が同意しました」
→ 個人を特定できる可能性がある
```

問題：
- 統計から個人の回答を推測できる
- GDPR/HIPAA に準拠できない

### 差分プライバシーなら

```
「患者100人中80人が同意しました (±3%)」
→ 個人を特定することは不可能
```

### 実装方針

```python
# concordia/app/services/differential_privacy.py
import numpy as np

def laplace_mechanism(data: list[bool], epsilon: float = 1.0):
    """ラプラスノイズを加えて差分プライバシーを実現"""
    true_count = sum(data)
    sensitivity = 1  # 個人1人の影響
    scale = sensitivity / epsilon
    
    # ラプラスノイズを加える
    noisy_count = true_count + np.random.laplace(0, scale)
    
    return {
        "count": int(noisy_count),
        "confidence": f"±{int(scale * 3)}",
        "privacy": epsilon
    }
```

### 使用例

```python
# 統計を公開したいが、個人情報は保護したい
agreements = [True, True, False, True, False, ...]  # 100人の回答

# 差分プライバシーを適用
private_stats = laplace_mechanism(agreements, epsilon=1.0)

print(f"{private_stats['count']}% の患者が同意しました ({private_stats['confidence']})")
# "77% の患者が同意しました (±3)"
# → この統計から個人を特定することは不可能
```

### 技術スタック
```bash
pip install numpy scipy diffprivlib
```

---

## 3. ブラインド署名（Blind Signatures）⭐ ニッチ技術

### なぜ実装すべきか

従来の署名では：
```
患者: 「手術に同意します」→ [Ed25519署名]
医師: 署名を確認（内容も見える）
```

### ブラインド署名なら

```
患者: 内容を「盲目化」して署名を取得
医師: 署名の有効性のみを確認（内容は見えない）
```

### 実装方針

```python
# concordia/app/domain/blind_signature.py
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
import hashlib

def blind_message(message: bytes, public_key) -> bytes:
    """メッセージを盲目化"""
    # ランダムなブラインドファクターを生成
    blind_factor = secrets.token_bytes(32)
    
    # メッセージをハッシュ化
    message_hash = hashlib.sha256(message).digest()
    
    # ブラインド化
    blinded = (message_hash, blind_factor, public_key)
    return blinded

def sign_blinded(blinded: bytes, private_key) -> bytes:
    """盲目化されたメッセージに署名"""
    signature = private_key.sign(
        blinded,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature

def unblind_signature(blinded_signature: bytes, blind_factor: bytes) -> bytes:
    """署名を脱盲"""
    # ブラインドファクターを取り除く
    unblinded = blinded_signature
    return unblinded
```

### メリット
- ✅ **内容の秘匿性**: 医師は患者の合意内容を見ることができない
- ✅ **署名の有効性**: Ed25519と同等のセキュリティ
- ✅ **ニッチな技術**: 実装例が少ない

---

## 4. トップレシークレットシェアリング（Top-Secret Sharing）

### なぜ実装すべきか

複数の利害関係者（患者・医師・家族）が関与する場合：

```
【従来の方法】
患者: 「手術に同意します」
医師: 「説明を完了しました」
家族: 「家族として同意します」
→ 全ての回答が全員に見える（プライバシーリスク）

【シークレットシェアリング】
患者・医師・家族がそれぞれ「秘密」を分散
→ 合意の結果のみが明らか（各参加者の回答は不明）
```

### 実装方針

```python
# concordia/app/domain/secret_sharing.py
from secretsharing import secret_int_to_points, points_to_secret_int

def split_secret(secret: str, num_shares: int, threshold: int):
    """秘密を分散"""
    secret_int = int.from_bytes(secret.encode(), 'big')
    shares = secret_int_to_points(secret_int, threshold, num_shares)
    return shares

def reconstruct_secret(shares: list):
    """分散された秘密から復元"""
    secret_int = points_to_secret_int(shares)
    secret_bytes = secret_int.to_bytes((secret_int.bit_length() + 7) // 8, 'big')
    return secret_bytes.decode()

# 使用例
patient_secret = "手術に同意します"
doctor_secret = "説明を完了しました"
family_secret = "家族として同意します"

# 各参加者が秘密を分散
patient_shares = split_secret(patient_secret, num_shares=3, threshold=2)
doctor_shares = split_secret(doctor_secret, num_shares=3, threshold=2)
family_shares = split_secret(family_secret, num_shares=3, threshold=2)

# 合意を計算（秘密は復元しない）
# → 各参加者の回答は不明だが、合意の結果は分かる
```

### 技術スタック
```bash
pip install secretsharing
```

---

## 推奨される技術選択（個人実装向け）

### 最優先実装 ⭐⭐⭐

1. **ゼロ知識証明（ZK-SNARKs）** 
   - 理由: 最も革新的で、個人実装で学ぶ価値が高い
   - 難易度: 高
   - ツール: Circom + SnarkJS

2. **差分プライバシー**
   - 理由: 実装が比較的簡単で、すぐに価値を提供できる
   - 難易度: 中
   - ツール: `diffprivlib`, NumPy

3. **ブラインド署名**
   - 理由: ニッチな技術だが、実装例が少ない
   - 難易度: 中
   - ツール: `cryptography`

### 将来的に検討 🔄

- **マルチパーティ計算（MPC）**: 複数ステークホルダー対応が必要な場合
- **完全準同型暗号（FHE）**: 計算コストが高すぎる（しかし挑戦する価値はある）

---

## 実装ロードマップ

### Phase 1: 差分プライバシー（1-2週間）
```bash
# 実装ファイル
concordia/app/services/differential_privacy.py
concordia/tests/test_differential_privacy.py
```

### Phase 2: ブラインド署名（2-3週間）
```bash
# 実装ファイル
concordia/app/domain/blind_signature.py
concordia/tests/test_blind_signature.py
```

### Phase 3: ゼロ知識証明（3-4週間）
```bash
# 実装ファイル
circuits/understanding_proof.circom
concordia/app/services/zk_proof.py
concordia/tests/test_zk_proof.py
```

### Phase 4: シークレットシェアリング（1-2週間）
```bash
# 実装ファイル
concordia/app/domain/secret_sharing.py
concordia/tests/test_secret_sharing.py
```

---

## まとめ

**個人実装だからこそできること**

1. **ニッチな技術**を試せる
2. **コスト効率**よりも**技術的好奇心**を優先
3. **実用性**よりも**実験的価値**を追求
4. **過剰な技術**も含めて**試してみる価値がある**

Ed25519 のような「確立された技術」ではなく、**もっと面白い技術**を実装してみる。

これが個人実装の醍醐味である。

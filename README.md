# 音声文字起こしツール（Whisper）

MacBook Pro M4で.m4aファイル（iPhoneのボイスメモ）をOpenAI Whisperで文字起こしするPythonプログラムです。

## 特徴

- iPhoneのボイスメモ（.m4a形式）に対応
- OpenAI Whisperによる高精度な日本語文字起こし
- 3時間以上の長時間音声にも対応
- M4チップ（MPS）で高速処理
- 自動的に音声をチャンクに分割して処理
- 処理結果をテキストファイルで保存
- **NEW!** フォルダ監視機能（新しいファイルが追加されたら自動的に文字起こし）

## 必要要件

- MacBook Pro M4（またはApple Silicon Mac）
- Python 3.8以上
- ffmpeg

## セットアップ

### 1. ffmpegのインストール

```bash
brew install ffmpeg
```

### 2. 必要なPythonライブラリのインストール

```bash
pip install -r requirements.txt
```

初回実行時にWhisperモデルが自動的にダウンロードされます。

## 使い方

### 方法1: 統合版 自動文字起こしシステム（おすすめ！）⭐️ NEW!

**単一ファイルで完結する自動文字起こしシステムです。**

1. プログラムを起動

```bash
python transcribe_auto.py
```

2. `input`フォルダに.m4aファイルをドラッグ＆ドロップ

3. 自動的に文字起こしが開始され、`output`フォルダに結果が保存されます

4. 停止するには `Ctrl+C` を押す

**メリット:**
- 単一ファイルで全機能を実現（依存関係なし）
- ファイルを追加するだけで自動処理
- ずっと動かしておける
- 複数のファイルを順番に処理できる
- 詳細な日本語コメント付きで理解しやすい

---

### 方法2: フォルダ監視モード（従来版）

**新しいファイルが追加されたら自動的に文字起こしを開始します。**

1. プログラムを起動

```bash
python monitor.py
```

2. `input`フォルダに.m4aファイルをドラッグ＆ドロップ

3. 自動的に文字起こしが開始され、`output`フォルダに結果が保存されます

4. 停止するには `Ctrl+C` を押す

**メリット:**
- ファイルを追加するだけで自動処理
- ずっと動かしておける
- 複数のファイルを順番に処理できる

---

### 方法3: バッチ処理モード（従来の方法）

**inputフォルダにあるすべての.m4aファイルを一度に処理します。**

1. `input`フォルダに.m4aファイルを配置

2. スクリプトを実行

```bash
python transcribe.py
```

3. `output`フォルダに文字起こし結果が保存されます

**メリット:**
- 一度に複数ファイルを処理
- シンプルで分かりやすい

---

### オプション

#### モデルサイズの指定

精度と速度のバランスを調整できます：

**統合版 自動文字起こしシステム:**
```bash
# より速く処理（精度は少し落ちる）
python transcribe_auto.py --model tiny

# 標準（デフォルト）
python transcribe_auto.py --model base

# より高精度（処理時間は長くなる）
python transcribe_auto.py --model medium
```

**フォルダ監視モード（従来版）:**
```bash
# より速く処理（精度は少し落ちる）
python monitor.py --model tiny

# 標準（デフォルト）
python monitor.py --model base

# より高精度（処理時間は長くなる）
python monitor.py --model medium
```

**バッチ処理モード:**
```bash
# より速く処理（精度は少し落ちる）
python transcribe.py --model tiny

# 標準（デフォルト）
python transcribe.py --model base

# より高精度（処理時間は長くなる）
python transcribe.py --model medium
```

モデルサイズ一覧：
- `tiny`: 最速（精度：低）
- `base`: 標準（バランス型）⭐️ デフォルト
- `small`: 高精度（やや遅い）
- `medium`: より高精度（遅い）
- `large`: 最高精度（非常に遅い）

#### 言語の指定

デフォルトは日本語ですが、他の言語も指定できます：

**統合版 自動文字起こしシステム:**
```bash
# 英語
python transcribe_auto.py --language en

# 中国語
python transcribe_auto.py --language zh
```

**フォルダ監視モード（従来版）:**
```bash
# 英語
python monitor.py --language en

# 中国語
python monitor.py --language zh
```

**バッチ処理モード:**
```bash
# 英語
python transcribe.py --language en

# 中国語
python transcribe.py --language zh
```

## ディレクトリ構造

```
TranscriptionSummarizer/
├── input/              # ここに.m4aファイルを配置
├── output/             # 文字起こし結果が保存される
├── transcribe_auto.py  # 統合版 自動文字起こしシステム（NEW!）⭐️
├── monitor.py          # フォルダ監視スクリプト（従来版）
├── transcribe.py       # バッチ処理スクリプト
├── requirements.txt    # 必要なライブラリ
└── README.md          # このファイル
```

## 出力ファイル形式

文字起こし結果は以下の形式で保存されます：

ファイル名: `元のファイル名_YYYYMMDD_HHMMSS.txt`

```
# 文字起こし結果
元ファイル: example.m4a
作成日時: 2024-03-15 10:30:45

============================================================

[文字起こしされたテキストがここに表示されます]
```

## パフォーマンス

- M4チップのMPS（Metal Performance Shaders）を自動的に使用
- 10分ごとにチャンク分割してメモリ効率を最適化
- 3時間以上の長時間音声でも安定して処理可能

### 処理時間の目安（M4チップ使用時）

| モデル | 1時間の音声 |
|--------|-------------|
| tiny   | 約2-3分     |
| base   | 約5-7分     |
| small  | 約10-15分   |
| medium | 約20-30分   |

※実際の処理時間は音声の内容や品質によって変動します

## トラブルシューティング

### エラー: "No .m4a files found"

- `input`フォルダに.m4aファイルが配置されているか確認してください

### エラー: "ffmpeg not found"

- ffmpegがインストールされているか確認：`brew install ffmpeg`

### メモリ不足エラー

- より小さいモデル（`tiny`や`base`）を使用してください
- 音声ファイルが非常に長い場合は、事前に分割することをお勧めします

### MPSが使えない場合

- 自動的にCPUモードに切り替わります
- M1/M2/M3/M4チップでMacOS 12.3以降であればMPSが利用可能です

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 謝辞

- [OpenAI Whisper](https://github.com/openai/whisper) - 音声認識モデル
- [PyDub](https://github.com/jiaaro/pydub) - 音声処理ライブラリ

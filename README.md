# 音声文字起こしツール（Whisper）

MacBook Pro M4で.m4aファイル（iPhoneのボイスメモ）をOpenAI Whisperで文字起こしするPythonプログラムです。

## 特徴

- iPhoneのボイスメモ（.m4a形式）に対応
- OpenAI Whisperによる高精度な日本語文字起こし
- 3時間以上の長時間音声にも対応
- M4チップ（MPS）で高速処理
- 自動的に音声をチャンクに分割して処理
- 処理結果をテキストファイルで保存

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

### 基本的な使い方

1. `input`フォルダに.m4aファイルを配置

2. スクリプトを実行

```bash
python transcribe.py
```

3. `output`フォルダに文字起こし結果が保存されます

### オプション

#### モデルサイズの指定

精度と速度のバランスを調整できます：

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
├── transcribe.py       # メインスクリプト
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

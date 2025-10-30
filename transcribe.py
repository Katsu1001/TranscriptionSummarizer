#!/usr/bin/env python3
"""
M4A音声ファイルをWhisperで文字起こしするスクリプト

【このプログラムの役割】
音声ファイル（.m4a形式）を読み込んで、AIが自動的に文字に変換します。

【特徴】
- MacBook Pro M4で高速処理できるように最適化
- 3時間以上の長時間音声にも対応
- 10分ごとに分割して処理するため、メモリに優しい
"""

# ============================================================
# 必要なライブラリをインポート（読み込む）
# ============================================================

import os                          # ファイルやフォルダの操作に使う
import sys                         # プログラムの終了などに使う
import argparse                    # コマンドライン引数（オプション）を扱う
from pathlib import Path           # ファイルパスを扱いやすくする
from datetime import datetime      # 日付と時刻を扱う
import whisper                     # OpenAIのWhisper（音声認識AI）
from pydub import AudioSegment     # 音声ファイルを分割・変換する
import torch                       # AIの計算に使う（PyTorch）

# ============================================================
# 設定（定数）
# ============================================================

INPUT_DIR = "input"       # 音声ファイルを入れるフォルダ
OUTPUT_DIR = "output"     # 文字起こし結果を保存するフォルダ
CHUNK_LENGTH_MS = 10 * 60 * 1000  # 10分ごとに分割（1000ミリ秒 = 1秒）
                                   # なぜ分割？→ 長い音声を一度に処理すると
                                   #             メモリ（RAM）が足りなくなるため


def setup_directories():
    """
    入力・出力フォルダを作成する関数

    【やること】
    - inputフォルダがなければ作る
    - outputフォルダがなければ作る
    - すでにあれば何もしない（exist_ok=True）
    """
    Path(INPUT_DIR).mkdir(exist_ok=True)   # inputフォルダを作成
    Path(OUTPUT_DIR).mkdir(exist_ok=True)  # outputフォルダを作成


def get_m4a_files():
    """
    inputフォルダから.m4aファイルを探す関数

    【やること】
    - inputフォルダの中を見る
    - 拡張子が.m4aのファイルをすべて探す
    - ファイル名順に並べて返す

    【戻り値】
    見つかった.m4aファイルのリスト（例: [audio1.m4a, audio2.m4a]）
    """
    input_path = Path(INPUT_DIR)                 # inputフォルダのパス
    m4a_files = list(input_path.glob("*.m4a"))  # *.m4a = すべての.m4aファイル
    return sorted(m4a_files)                     # 名前順に並べて返す


def convert_audio_to_chunks(audio_path, chunk_length_ms=CHUNK_LENGTH_MS):
    """
    音声ファイルを小さな塊（チャンク）に分割する関数

    【なぜ分割するの？】
    長い音声を一度に処理すると、メモリ（RAM）が足りなくなる可能性があります。
    例えば、3時間の音声を10分ずつに分割すれば、メモリを節約できます。

    【引数】
        audio_path: 音声ファイルのパス（例: input/meeting.m4a）
        chunk_length_ms: 1つのチャンクの長さ（ミリ秒）
                        デフォルトは10分 = 600,000ミリ秒

    【戻り値】
        分割された音声データのリスト（例: [0-10分, 10-20分, 20-30分, ...]）
    """
    print(f"音声ファイルを読み込み中: {audio_path.name}")
    # m4a形式の音声ファイルを読み込む
    audio = AudioSegment.from_file(str(audio_path), format="m4a")

    # 音声の長さを計算
    duration_ms = len(audio)            # ミリ秒単位で長さを取得
    duration_min = duration_ms / 1000 / 60  # 分に変換（÷1000で秒、÷60で分）
    print(f"音声の長さ: {duration_min:.1f}分")

    # ============================================================
    # 音声をチャンク（塊）に分割
    # ============================================================
    chunks = []  # 分割した音声を入れるリスト

    # 例: 30分の音声を10分ごとに分割
    #     i = 0, 600000, 1200000 のように進む
    for i in range(0, duration_ms, chunk_length_ms):
        # i から i+chunk_length_ms までの部分を切り出す
        # 例: audio[0:600000] → 最初の10分
        chunk = audio[i:i + chunk_length_ms]
        chunks.append(chunk)  # リストに追加

    print(f"{len(chunks)}個のチャンクに分割しました")
    return chunks


def transcribe_audio(audio_path, model_name="base", language="ja"):
    """
    音声ファイルを文字起こしする関数（このプログラムのメイン処理）

    【やること】
    1. AIモデル（Whisper）を読み込む
    2. 音声を10分ごとに分割
    3. それぞれの塊を文字起こし
    4. 全部つなげて返す

    【引数】
        audio_path: 音声ファイルのパス（例: input/lecture.m4a）
        model_name: Whisperモデル名
                   - tiny: 一番速いけど精度低め
                   - base: バランス型（おすすめ）
                   - small: やや高精度
                   - medium: 高精度だけど遅い
                   - large: 最高精度だけどとても遅い
        language: 言語コード（ja=日本語、en=英語）

    【戻り値】
        文字起こし結果のテキスト（全文）
    """
    print(f"\n{'='*60}")
    print(f"文字起こし開始: {audio_path.name}")
    print(f"{'='*60}")

    # ============================================================
    # どのデバイス（処理装置）で計算するか決める
    # ============================================================

    # M4チップ（Apple Silicon）が使えるかチェック
    if torch.backends.mps.is_available():
        device = "mps"  # MPS = Metal Performance Shaders（Appleの高速計算）
        print("M4チップ（MPS）を使用して高速処理します")
    # NVIDIA GPUが使えるかチェック
    elif torch.cuda.is_available():
        device = "cuda"  # CUDA = NVIDIAのGPU計算
        print("CUDA（GPU）を使用します")
    # どちらも使えない場合はCPU
    else:
        device = "cpu"
        print("CPUを使用します")

    # ============================================================
    # Whisper（AI音声認識モデル）を読み込む
    # ============================================================

    print(f"Whisperモデル（{model_name}）を読み込み中...")
    model = whisper.load_model(model_name, device=device)

    # ============================================================
    # 音声をチャンク（塊）に分割
    # ============================================================

    chunks = convert_audio_to_chunks(audio_path)

    # ============================================================
    # 一時ファイル用のフォルダを作成
    # ============================================================
    # なぜ必要？→ Whisperは音声ファイルを読み込む必要があるため、
    #           メモリ上の音声データを一度ファイルとして保存する

    temp_dir = Path("temp")               # tempフォルダ
    temp_dir.mkdir(exist_ok=True)         # なければ作成

    all_transcriptions = []  # 文字起こし結果を入れるリスト

    # ============================================================
    # 各チャンクを文字起こし（ここが一番重要！）
    # ============================================================

    # enumerate() は番号付きで繰り返す
    # 例: [(0, chunk1), (1, chunk2), (2, chunk3)]
    for idx, chunk in enumerate(chunks):
        print(f"\nチャンク {idx + 1}/{len(chunks)} を処理中...")

        # ------------------------------------------------------------
        # 1. チャンクを一時ファイルとして保存
        # ------------------------------------------------------------
        temp_file = temp_dir / f"temp_chunk_{idx}.wav"  # 一時ファイル名
        chunk.export(str(temp_file), format="wav")      # wav形式で保存

        # ------------------------------------------------------------
        # 2. Whisperで文字起こし実行
        # ------------------------------------------------------------
        result = model.transcribe(
            str(temp_file),      # 音声ファイルのパス
            language=language,   # 言語（日本語なら "ja"）
            verbose=False        # 詳細なログを表示しない
        )

        # 文字起こし結果を追加
        # result["text"] に文字起こしされたテキストが入っている
        all_transcriptions.append(result["text"])

        # ------------------------------------------------------------
        # 3. 一時ファイルを削除（もう使わないので）
        # ------------------------------------------------------------
        temp_file.unlink()  # ファイルを削除

        # ------------------------------------------------------------
        # 4. 進捗を表示
        # ------------------------------------------------------------
        progress = (idx + 1) / len(chunks) * 100  # パーセントを計算
        print(f"進捗: {progress:.1f}%")

    # ============================================================
    # 一時フォルダを削除（空になったので）
    # ============================================================

    try:
        temp_dir.rmdir()  # 空のフォルダを削除
    except:
        pass  # エラーが出ても無視（残っててもOK）

    # ============================================================
    # 全てのテキストを1つにつなげる
    # ============================================================
    # 例: ["こんにちは", "今日は"] → "こんにちは\n今日は"

    full_transcription = "\n".join(all_transcriptions)

    print(f"\n文字起こし完了!")
    print(f"文字数: {len(full_transcription)}文字")

    return full_transcription


def save_transcription(text, original_filename, output_dir=OUTPUT_DIR):
    """
    文字起こし結果をテキストファイルに保存する関数

    【やること】
    1. 元のファイル名から新しいファイル名を作る
    2. 日付と時刻を追加（同じ名前でも上書きされないように）
    3. テキストファイルに保存

    【引数】
        text: 文字起こし結果のテキスト（全文）
        original_filename: 元の音声ファイル名（例: "meeting.m4a"）
        output_dir: 保存先フォルダ（デフォルト: "output"）

    【戻り値】
        保存したファイルのパス（例: output/meeting_20250130_153000.txt）
    """

    # ============================================================
    # 出力ファイル名を生成
    # ============================================================

    # .stem = 拡張子を除いたファイル名
    # 例: "meeting.m4a" → "meeting"
    base_name = Path(original_filename).stem

    # 現在の日付と時刻を取得（例: "20250130_153000"）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ファイル名を組み立てる
    # 例: "meeting_20250130_153000.txt"
    output_filename = f"{base_name}_{timestamp}.txt"
    output_path = Path(output_dir) / output_filename  # フルパス

    # ============================================================
    # テキストファイルに保存
    # ============================================================

    # "w" = 書き込みモード、encoding="utf-8" = 日本語対応
    with open(output_path, "w", encoding="utf-8") as f:
        # ヘッダー情報を書き込む
        f.write(f"# 文字起こし結果\n")
        f.write(f"元ファイル: {original_filename}\n")
        f.write(f"作成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"\n{'='*60}\n\n")

        # 文字起こし結果を書き込む
        f.write(text)

    print(f"\n結果を保存しました: {output_path}")
    return output_path


def main():
    """
    メイン関数（プログラムが起動したら最初に実行される）

    【やること】
    1. コマンドライン引数を読み込む（--model, --languageなど）
    2. input/outputフォルダを作成
    3. inputフォルダから.m4aファイルを探す
    4. 見つかったファイルを全て文字起こし
    5. 結果をoutputフォルダに保存
    """

    # ============================================================
    # コマンドライン引数の設定
    # ============================================================

    parser = argparse.ArgumentParser(
        description="M4A音声ファイルをWhisperで文字起こしします"
    )

    # --model オプション（どのAIモデルを使うか）
    parser.add_argument(
        "--model",
        type=str,
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisperモデルのサイズ (デフォルト: base)"
    )

    # --language オプション（何語か）
    parser.add_argument(
        "--language",
        type=str,
        default="ja",
        help="言語コード (デフォルト: ja)"
    )

    # コマンドライン引数を解析（読み込む）
    args = parser.parse_args()

    # ============================================================
    # 初期セットアップ
    # ============================================================

    # input/outputフォルダを作成（なければ）
    setup_directories()

    # inputフォルダから.m4aファイルを取得
    m4a_files = get_m4a_files()

    # ファイルが1つも見つからなかったらエラー
    if not m4a_files:
        print(f"エラー: {INPUT_DIR}ディレクトリに.m4aファイルが見つかりません")
        print(f"{INPUT_DIR}ディレクトリに音声ファイルを配置してください")
        sys.exit(1)  # プログラムを終了（1 = エラーで終了）

    # 見つかったファイルを表示
    print(f"\n{len(m4a_files)}個の音声ファイルが見つかりました")
    for file in m4a_files:
        print(f"  - {file.name}")

    # ============================================================
    # 各ファイルを文字起こし
    # ============================================================

    for audio_file in m4a_files:
        try:
            # 文字起こし実行
            transcription = transcribe_audio(
                audio_file,
                model_name=args.model,
                language=args.language
            )

            # 結果をテキストファイルに保存
            save_transcription(transcription, audio_file.name)

        except Exception as e:
            # エラーが起きても次のファイルに進む
            print(f"\nエラーが発生しました: {audio_file.name}")
            print(f"エラー内容: {str(e)}")
            continue  # 次のファイルへ

    # ============================================================
    # 完了メッセージ
    # ============================================================

    print(f"\n{'='*60}")
    print("全ての処理が完了しました！")
    print(f"{'='*60}")


# ============================================================
# プログラムのエントリーポイント（スタート地点）
# ============================================================

if __name__ == "__main__":
    """
    このファイルが直接実行されたときだけ main() を実行する

    【なぜ必要？】
    他のプログラムから import されたときは main() を実行したくないため。
    例: monitor.py から import するときは、関数だけ使いたい。
    """
    main()

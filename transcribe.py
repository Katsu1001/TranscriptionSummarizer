#!/usr/bin/env python3
"""
M4A音声ファイルをWhisperで文字起こしするスクリプト

MacBook Pro M4で高速処理できるように最適化されています。
3時間以上の長時間音声にも対応しています。
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
import whisper
from pydub import AudioSegment
import torch

# 定数
INPUT_DIR = "input"
OUTPUT_DIR = "output"
CHUNK_LENGTH_MS = 10 * 60 * 1000  # 10分ごとに分割（メモリ効率のため）


def setup_directories():
    """入力・出力ディレクトリの確認"""
    Path(INPUT_DIR).mkdir(exist_ok=True)
    Path(OUTPUT_DIR).mkdir(exist_ok=True)


def get_m4a_files():
    """inputディレクトリから.m4aファイルを取得"""
    input_path = Path(INPUT_DIR)
    m4a_files = list(input_path.glob("*.m4a"))
    return sorted(m4a_files)


def convert_audio_to_chunks(audio_path, chunk_length_ms=CHUNK_LENGTH_MS):
    """
    音声ファイルをチャンクに分割

    Args:
        audio_path: 音声ファイルのパス
        chunk_length_ms: チャンクの長さ（ミリ秒）

    Returns:
        チャンクのリスト（AudioSegmentオブジェクト）
    """
    print(f"音声ファイルを読み込み中: {audio_path.name}")
    audio = AudioSegment.from_file(str(audio_path), format="m4a")

    duration_ms = len(audio)
    duration_min = duration_ms / 1000 / 60
    print(f"音声の長さ: {duration_min:.1f}分")

    # チャンクに分割
    chunks = []
    for i in range(0, duration_ms, chunk_length_ms):
        chunk = audio[i:i + chunk_length_ms]
        chunks.append(chunk)

    print(f"{len(chunks)}個のチャンクに分割しました")
    return chunks


def transcribe_audio(audio_path, model_name="base", language="ja"):
    """
    音声ファイルを文字起こし

    Args:
        audio_path: 音声ファイルのパス
        model_name: Whisperモデル名 (tiny, base, small, medium, large)
        language: 言語コード

    Returns:
        文字起こし結果のテキスト
    """
    print(f"\n{'='*60}")
    print(f"文字起こし開始: {audio_path.name}")
    print(f"{'='*60}")

    # デバイスの確認（M4の場合はMPSを使用）
    if torch.backends.mps.is_available():
        device = "mps"
        print("M4チップ（MPS）を使用して高速処理します")
    elif torch.cuda.is_available():
        device = "cuda"
        print("CUDA（GPU）を使用します")
    else:
        device = "cpu"
        print("CPUを使用します")

    # Whisperモデルの読み込み
    print(f"Whisperモデル（{model_name}）を読み込み中...")
    model = whisper.load_model(model_name, device=device)

    # 音声をチャンクに分割
    chunks = convert_audio_to_chunks(audio_path)

    # 一時ファイル用のディレクトリ
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)

    all_transcriptions = []

    # 各チャンクを文字起こし
    for idx, chunk in enumerate(chunks):
        print(f"\nチャンク {idx + 1}/{len(chunks)} を処理中...")

        # 一時ファイルに保存
        temp_file = temp_dir / f"temp_chunk_{idx}.wav"
        chunk.export(str(temp_file), format="wav")

        # 文字起こし
        result = model.transcribe(
            str(temp_file),
            language=language,
            verbose=False
        )

        all_transcriptions.append(result["text"])

        # 一時ファイルを削除
        temp_file.unlink()

        # 進捗表示
        progress = (idx + 1) / len(chunks) * 100
        print(f"進捗: {progress:.1f}%")

    # 一時ディレクトリを削除
    try:
        temp_dir.rmdir()
    except:
        pass

    # 全てのテキストを結合
    full_transcription = "\n".join(all_transcriptions)

    print(f"\n文字起こし完了!")
    print(f"文字数: {len(full_transcription)}文字")

    return full_transcription


def save_transcription(text, original_filename, output_dir=OUTPUT_DIR):
    """
    文字起こし結果をテキストファイルに保存

    Args:
        text: 文字起こし結果のテキスト
        original_filename: 元の音声ファイル名
        output_dir: 出力ディレクトリ

    Returns:
        保存したファイルのパス
    """
    # 出力ファイル名を生成
    base_name = Path(original_filename).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{base_name}_{timestamp}.txt"
    output_path = Path(output_dir) / output_filename

    # テキストファイルに保存
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# 文字起こし結果\n")
        f.write(f"元ファイル: {original_filename}\n")
        f.write(f"作成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"\n{'='*60}\n\n")
        f.write(text)

    print(f"\n結果を保存しました: {output_path}")
    return output_path


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="M4A音声ファイルをWhisperで文字起こしします"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisperモデルのサイズ (デフォルト: base)"
    )
    parser.add_argument(
        "--language",
        type=str,
        default="ja",
        help="言語コード (デフォルト: ja)"
    )

    args = parser.parse_args()

    # ディレクトリのセットアップ
    setup_directories()

    # .m4aファイルを取得
    m4a_files = get_m4a_files()

    if not m4a_files:
        print(f"エラー: {INPUT_DIR}ディレクトリに.m4aファイルが見つかりません")
        print(f"{INPUT_DIR}ディレクトリに音声ファイルを配置してください")
        sys.exit(1)

    print(f"\n{len(m4a_files)}個の音声ファイルが見つかりました")
    for file in m4a_files:
        print(f"  - {file.name}")

    # 各ファイルを処理
    for audio_file in m4a_files:
        try:
            # 文字起こし
            transcription = transcribe_audio(
                audio_file,
                model_name=args.model,
                language=args.language
            )

            # 結果を保存
            save_transcription(transcription, audio_file.name)

        except Exception as e:
            print(f"\nエラーが発生しました: {audio_file.name}")
            print(f"エラー内容: {str(e)}")
            continue

    print(f"\n{'='*60}")
    print("全ての処理が完了しました！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

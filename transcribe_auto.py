#!/usr/bin/env python3
"""
Whisper自動文字起こしシステム

【このプログラムの役割】
inputフォルダを監視して、新しい.m4aファイルが追加されたら自動的に文字起こしします。
MacBook Pro M4で高速に動作するように最適化されています。

【特徴】
- フォルダ監視による完全自動化（Watchdog使用）
- 3時間以上の長時間音声にも対応（10分ごとに分割処理）
- 重複処理防止
- ファイル転送完了待機（AirDropやコピー中の問題に対応）
- 詳細なエラーハンドリング

【使い方】
1. python transcribe_auto.py を実行
2. input/ フォルダに .m4a ファイルを追加
3. 自動的に文字起こしが開始され、output/ フォルダに結果が保存される
4. 停止するには Ctrl+C を押す
"""

# ============================================================
# 必要なライブラリをインポート（読み込む）
# ============================================================

import os                          # ファイル・フォルダ操作に使う
import sys                         # プログラムの終了などに使う
import time                        # 時間を扱う（待機など）
import signal                      # Ctrl+Cを検知するために使う
import argparse                    # コマンドライン引数を扱う
from pathlib import Path           # ファイルパスを扱いやすくする
from datetime import datetime      # 日付と時刻を扱う

# Whisper（OpenAIの音声認識AI）
import whisper

# 音声ファイルの分割・変換
from pydub import AudioSegment

# AI計算用ライブラリ（PyTorch）
import torch

# フォルダ監視用ライブラリ（Watchdog）
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# ============================================================
# 設定（定数）
# ============================================================

INPUT_DIR = "input"                    # 監視するフォルダ（ここに音声ファイルを入れる）
OUTPUT_DIR = "output"                  # 結果を保存するフォルダ
CHUNK_LENGTH_MS = 10 * 60 * 1000      # 10分ごとに分割（1000ミリ秒 = 1秒）
                                       # なぜ分割？→ 長い音声を一度に処理すると
                                       #             メモリ（RAM）が足りなくなるため


# ============================================================
# ユーティリティ関数（補助的な処理）
# ============================================================

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
    print(f"   音声ファイルを読み込み中: {audio_path.name}")
    # m4a形式の音声ファイルを読み込む
    audio = AudioSegment.from_file(str(audio_path), format="m4a")

    # 音声の長さを計算
    duration_ms = len(audio)            # ミリ秒単位で長さを取得
    duration_min = duration_ms / 1000 / 60  # 分に変換（÷1000で秒、÷60で分）
    print(f"   音声の長さ: {duration_min:.1f}分")

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

    print(f"   {len(chunks)}個のチャンクに分割しました")
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

    # ============================================================
    # どのデバイス（処理装置）で計算するか決める
    # ============================================================

    # M4チップ（Apple Silicon）が使えるかチェック
    if torch.backends.mps.is_available():
        device = "mps"  # MPS = Metal Performance Shaders（Appleの高速計算）
        print(f"   M4チップ（MPS）を使用して高速処理します")
    # NVIDIA GPUが使えるかチェック
    elif torch.cuda.is_available():
        device = "cuda"  # CUDA = NVIDIAのGPU計算
        print(f"   CUDA（GPU）を使用します")
    # どちらも使えない場合はCPU
    else:
        device = "cpu"
        print(f"   CPUを使用します")

    # ============================================================
    # Whisper（AI音声認識モデル）を読み込む
    # ============================================================

    print(f"   Whisperモデル（{model_name}）を読み込み中...")
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

    print()
    # enumerate() は番号付きで繰り返す
    # 例: [(0, chunk1), (1, chunk2), (2, chunk3)]
    for idx, chunk in enumerate(chunks):
        print(f"   チャンク {idx + 1}/{len(chunks)} を処理中...")

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
        print(f"   進捗: {progress:.1f}%")

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

    print(f"   文字起こし完了!")
    print(f"   文字数: {len(full_transcription)}文字")

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

    return output_path


# ============================================================
# フォルダ監視のためのクラス（設計図）
# ============================================================

class AudioFileHandler(FileSystemEventHandler):
    """
    音声ファイルの追加を検知して、自動的に文字起こしを実行するクラス

    【クラスとは】
    複数の機能（関数）をまとめたもの。料理のレシピ集のようなもの。
    このクラスは「新しいファイルが追加されたら文字起こしする」というレシピ。
    """

    def __init__(self, model_name="base", language="ja"):
        """
        初期設定（このクラスを使い始めるときに最初に実行される）

        引数（材料）:
            model_name: Whisperのモデル名（精度と速度のバランス）
            language: 言語（日本語は "ja"）
        """
        super().__init__()  # 親クラスの初期化（おまじない）
        self.model_name = model_name    # モデル名を保存
        self.language = language        # 言語を保存
        self.processing_files = set()   # 現在処理中のファイルを記録（重複防止）

    def on_created(self, event):
        """
        新しいファイルが作成されたときに自動的に呼ばれる関数

        【イベントとは】
        「何かが起きたとき」のこと。この関数は「ファイルが作られたとき」に
        自動的に実行される。

        引数:
            event: 何が起きたかの情報（ファイル名など）
        """

        # フォルダは無視する（ファイルだけを処理したい）
        if event.is_directory:
            return

        # 追加されたファイルのパスを取得
        file_path = Path(event.src_path)

        # .m4aファイルかどうかチェック
        # （.suffixはファイルの拡張子を取得する。例: "audio.m4a" → ".m4a"）
        if file_path.suffix.lower() != ".m4a":
            return  # .m4aでなければ何もしない

        # すでに処理中のファイルは無視する（二重処理を防ぐ）
        if str(file_path) in self.processing_files:
            return

        # ファイルが完全にコピーされるまで少し待つ
        # （大きなファイルはコピーに時間がかかるため）
        print(f"\n🔍 新しいファイルを検出: {file_path.name}")
        print("   ファイルのコピーが完了するまで待機中...")
        time.sleep(2)  # 2秒待つ

        # ファイルが完全にコピーされたか確認
        if not self._wait_for_file_ready(file_path):
            print(f"⚠️  ファイルの準備ができませんでした: {file_path.name}")
            return

        # 文字起こしを開始
        self._process_audio_file(file_path)

    def _wait_for_file_ready(self, file_path, max_wait=30):
        """
        ファイルが完全にコピーされるまで待つ関数

        【なぜ必要？】
        大きなファイルは、inputフォルダにコピーするのに時間がかかる。
        コピー中に文字起こしを始めると失敗するので、完全にコピーされるまで待つ。

        引数:
            file_path: チェックするファイルのパス
            max_wait: 最大で何秒待つか（デフォルト30秒）

        戻り値:
            True: ファイルの準備ができた
            False: タイムアウト（時間切れ）
        """
        start_time = time.time()  # 開始時刻を記録
        last_size = -1            # 前回のファイルサイズ（最初は-1）
        stable_count = 0          # ファイルサイズが変わらなかった回数

        while True:
            # 時間切れチェック
            if time.time() - start_time > max_wait:
                return False  # 30秒経っても準備できなかったら諦める

            # ファイルが存在するかチェック
            if not file_path.exists():
                time.sleep(0.5)  # 0.5秒待って再チェック
                continue

            try:
                # 現在のファイルサイズを取得
                current_size = file_path.stat().st_size

                # ファイルサイズが変わっていないかチェック
                if current_size == last_size:
                    stable_count += 1  # 変わっていない → カウントアップ
                    # 3回連続で同じサイズなら、コピー完了と判断
                    if stable_count >= 3:
                        return True
                else:
                    # サイズが変わった → まだコピー中
                    stable_count = 0
                    last_size = current_size

                time.sleep(0.5)  # 0.5秒待って再チェック

            except Exception as e:
                # エラーが起きたら0.5秒待って再チェック
                time.sleep(0.5)
                continue

    def _process_audio_file(self, file_path):
        """
        音声ファイルを文字起こしする関数

        引数:
            file_path: 文字起こしする音声ファイルのパス
        """
        # 処理中リストに追加（二重処理を防ぐ）
        self.processing_files.add(str(file_path))

        try:
            print()
            print("=" * 60)
            print(f"処理開始: {file_path.name}")
            print("=" * 60)

            # 文字起こし実行
            print("🎤 文字起こし中... （数分かかる場合があります）")
            transcription = transcribe_audio(
                file_path,
                model_name=self.model_name,
                language=self.language
            )

            # 結果をテキストファイルに保存
            output_path = save_transcription(transcription, file_path.name)

            print()
            print(f"✅ 完了: {output_path.name}")
            print("=" * 60)
            print()
            print("👀 次のファイルを待っています...")

        except Exception as e:
            # エラーが起きたときの処理
            print()
            print(f"❌ エラーが発生しました: {file_path.name}")
            print(f"エラー内容: {str(e)}")
            print()
            print("👀 次のファイルを待っています...")

        finally:
            # 処理が終わったら処理中リストから削除
            # （finally は、エラーが起きても必ず実行される）
            self.processing_files.discard(str(file_path))


# ============================================================
# プログラムを終了するための処理
# ============================================================

# プログラムを綺麗に終了させるための変数
should_exit = False


def signal_handler(sig, frame):
    """
    Ctrl+C が押されたときに呼ばれる関数

    【シグナルとは】
    プログラムへの特別な合図。Ctrl+Cを押すと「SIGINT」という
    シグナルがプログラムに送られる。

    引数:
        sig: シグナルの種類
        frame: 現在のプログラムの状態（使わない）
    """
    global should_exit  # グローバル変数（プログラム全体で使える変数）

    print()
    print()
    print("=" * 70)
    print("⏹️  停止信号を受信しました (Ctrl+C)")
    print("=" * 70)
    print("プログラムを終了しています...")
    print()

    should_exit = True  # 終了フラグを立てる


# ============================================================
# メイン処理（プログラムの本体）
# ============================================================

def main():
    """
    メイン関数（プログラムが起動したら最初に実行される）
    """

    # ============================================================
    # コマンドライン引数の設定
    # ============================================================
    # （プログラム実行時にオプションを指定できるようにする）

    parser = argparse.ArgumentParser(
        description="🎤 Whisper自動文字起こしシステム\n"
                    "inputフォルダを監視して、新しい.m4aファイルを自動的に文字起こしします",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # --model オプション（モデルの種類を選べる）
    parser.add_argument(
        "--model",
        type=str,
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisperモデルのサイズ (デフォルト: base)\n"
             "tiny: 一番速いけど精度低め\n"
             "base: バランス型（推奨）\n"
             "small: やや高精度\n"
             "medium: 高精度だけど遅い\n"
             "large: 最高精度だけどとても遅い"
    )

    # --language オプション（言語を選べる）
    parser.add_argument(
        "--language",
        type=str,
        default="ja",
        help="言語コード (デフォルト: ja)\n"
             "ja: 日本語\n"
             "en: 英語\n"
             "など"
    )

    # コマンドライン引数を解析（読み込む）
    args = parser.parse_args()

    # ============================================================
    # 初期セットアップ
    # ============================================================

    # input/output フォルダを作成（なければ）
    setup_directories()

    # 絶対パスを取得（フルパスで表示する）
    input_abs_path = Path(INPUT_DIR).resolve()
    output_abs_path = Path(OUTPUT_DIR).resolve()

    # 起動メッセージを表示
    print()
    print("=" * 70)
    print("🎤 Whisper自動文字起こしシステムを起動しました")
    print("=" * 70)
    print(f"📁 監視フォルダ: {input_abs_path}")
    print(f"📝 出力フォルダ: {output_abs_path}")
    print(f"🤖 使用モデル: {args.model}")
    print(f"🌏 言語: {args.language}")
    print()
    print("💡 使い方:")
    print(f"   1. {INPUT_DIR}/ フォルダに .m4a ファイルを追加してください")
    print("   2. 自動的に文字起こしが始まります")
    print("   3. 結果は output/ フォルダに保存されます")
    print()
    print("⏸️  停止するには Ctrl+C を押してください")
    print("=" * 70)
    print()

    # Ctrl+C を押したときの処理を登録
    signal.signal(signal.SIGINT, signal_handler)

    # ============================================================
    # フォルダ監視の開始
    # ============================================================

    # イベントハンドラー（ファイル追加を検知する係）を作成
    event_handler = AudioFileHandler(
        model_name=args.model,
        language=args.language
    )

    # オブザーバー（フォルダを監視する係）を作成
    observer = Observer()

    # どのフォルダを監視するか設定
    # recursive=False → サブフォルダは監視しない
    observer.schedule(event_handler, INPUT_DIR, recursive=False)

    # 監視を開始
    observer.start()
    print("👀 監視を開始しました... 新しいファイルを待っています")
    print()

    try:
        # メインループ（ずっと動き続ける部分）
        while not should_exit:
            time.sleep(1)  # 1秒ごとにチェック

    except KeyboardInterrupt:
        # Ctrl+C が押された場合
        pass

    finally:
        # プログラム終了時の処理
        print("フォルダ監視を停止しています...")
        observer.stop()      # 監視を停止
        observer.join()      # 監視スレッドの終了を待つ

        print()
        print("=" * 70)
        print("👋 プログラムを終了しました")
        print("=" * 70)
        print()


# ============================================================
# プログラムのエントリーポイント（スタート地点）
# ============================================================

if __name__ == "__main__":
    """
    このファイルが直接実行されたときだけ main() を実行する

    【なぜ必要？】
    他のプログラムからimportされたときは実行されないようにするため。
    """
    main()

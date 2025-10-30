#!/usr/bin/env python3
"""
フォルダ監視プログラム

このプログラムは、inputフォルダをずっと見張り続けて、
新しい音声ファイル（.m4a）が追加されたら自動的に文字起こしを始めます。

使い方：
  python monitor.py

停止方法：
  Ctrl+C を押す
"""

# ============================================================
# 必要なライブラリをインポート（読み込む）
# ============================================================

import os                          # ファイル操作に使う
import sys                         # プログラムの終了などに使う
import time                        # 時間を扱う（待機など）
import signal                      # Ctrl+Cを検知するために使う
import argparse                    # コマンドライン引数を扱う
from pathlib import Path           # ファイルパスを扱いやすくする
from datetime import datetime      # 日付と時刻を扱う
from watchdog.observers import Observer          # フォルダを監視する機能
from watchdog.events import FileSystemEventHandler  # ファイルの変更を検知する機能

# 文字起こし機能を別のファイル（transcribe.py）から読み込む
from transcribe import transcribe_audio, save_transcription, setup_directories


# ============================================================
# 設定（ここで監視するフォルダなどを決める）
# ============================================================

INPUT_DIR = "input"       # 監視するフォルダ（ここに音声ファイルを入れる）
OUTPUT_DIR = "output"     # 結果を保存するフォルダ


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

        print("=" * 70)
        print("📁 フォルダ監視プログラムが起動しました！")
        print("=" * 70)
        print(f"監視フォルダ: {INPUT_DIR}/")
        print(f"結果保存先: {OUTPUT_DIR}/")
        print(f"使用モデル: {model_name}")
        print(f"言語: {language}")
        print()
        print("💡 使い方:")
        print(f"   1. {INPUT_DIR}/ フォルダに .m4a ファイルを入れてください")
        print("   2. 自動的に文字起こしが始まります")
        print("   3. 停止するには Ctrl+C を押してください")
        print()
        print("👀 監視を開始しました... 新しいファイルを待っています")
        print("=" * 70)
        print()

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
        print(f"🔍 新しいファイルを検出: {file_path.name}")
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
            print("🎤 文字起こしを開始します")
            print(f"📄 ファイル: {file_path.name}")
            print()

            # transcribe.pyの関数を使って文字起こし実行
            transcription = transcribe_audio(
                file_path,
                model_name=self.model_name,
                language=self.language
            )

            # 結果をテキストファイルに保存
            output_path = save_transcription(transcription, file_path.name)

            print()
            print("✅ 文字起こしが完了しました！")
            print(f"📝 保存先: {output_path}")
            print()
            print("👀 次のファイルを待っています...")
            print()

        except Exception as e:
            # エラーが起きたときの処理
            print()
            print(f"❌ エラーが発生しました: {file_path.name}")
            print(f"エラー内容: {str(e)}")
            print()
            print("👀 次のファイルを待っています...")
            print()

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
        description="inputフォルダを監視して、新しい音声ファイルを自動的に文字起こしします"
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

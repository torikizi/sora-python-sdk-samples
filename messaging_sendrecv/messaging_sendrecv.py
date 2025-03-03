# Sora のデータチャネル機能を使ってメッセージを送受信するサンプルスクリプト。
#
# コマンドライン引数で指定されたデータチャネル JSON (e.g, `[{"label": "#foo", "direction": "recvonly"}, {"label": "#bar", "direction": "sendonly"}]`) に従って、メッセージの送信および受信を行う。
#
# 具体的には、
# - `direction` が `recvonly` または `sendrecv` のデータチャネルに対して、メッセージを受信したら標準出力に出力する
# - `direction` が `sendonly` または `sendrecv` のデータチャネルに対して、1 秒ごとに自動生成したメッセージを送信する
#
# 実行例:
# $ rye run python messaging_sendrecv/messaging_sendrecv.py --signaling-url ws://localhost:5000/signaling --channel-id sora --data-channels '[{"label": "#foo", "direction":"sendrecv"}, {"label":"#bar", "direction": "recvonly"}]'
import argparse
import json
import os
import random
import time

from sora_sdk import Sora


class MessagingSendrecv:
    def __init__(self, signaling_url, channel_id, data_channels, metadata):
        self.sora = Sora()
        self.connection = self.sora.create_connection(
            signaling_url=signaling_url,
            role="sendrecv",
            channel_id=channel_id,
            metadata=metadata,
            audio=False,
            video=False,
            data_channels=data_channels,
            data_channel_signaling=True,
        )

        self.sender_id = random.randint(1, 10000)
        self.data_channels = data_channels
        self.shutdown = False
        self.sendable_data_channels = set()
        self.connection.on_data_channel = self.on_data_channel
        self.connection.on_message = self.on_message
        self.connection.on_disconnect = self.on_disconnect

    def on_disconnect(self, error_code, message):
        print(f"Sora から切断されました: error_code='{error_code}' message='{message}'")
        self.shutdown = True

    def on_message(self, label, data):
        print(f"メッセージを受信しました: label={label}, data={data}")

    def on_data_channel(self, label):
        for data_channel in self.data_channels:
            if data_channel["label"] != label:
                continue

            if data_channel["direction"] in ["sendrecv", "sendonly"]:
                self.sendable_data_channels.add(label)
                break

    def run(self):
        # Sora に接続する
        self.connection.connect()
        try:
            # 一秒毎に sendonly ないし sendrecv のラベルにメッセージを送信する
            i = 0
            while not self.shutdown:
                if i % 100 == 0:
                    for label in self.sendable_data_channels:
                        data = f"sender={self.sender_id}, no={i // 100}".encode(
                            "utf-8")
                        self.connection.send_data_channel(label, data)
                        print(f"メッセージを送信しました: label={label}, data={data}")

                time.sleep(0.01)
                i += 1
        except KeyboardInterrupt:
            pass
        finally:
            # Sora から切断する（すでに切断済みの場合には無視される）
            self.connection.disconnect()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # 必須引数（環境変数からも指定可能）
    default_signaling_url = os.getenv("SORA_SIGNALING_URL")
    parser.add_argument("--signaling-url", default=default_signaling_url,
                        required=not default_signaling_url, help="シグナリング URL")
    default_channel_id = os.getenv("SORA_CHANNEL_ID")
    parser.add_argument("--channel-id", default=default_channel_id,
                        required=not default_channel_id, help="チャネルID")
    default_ddata_channels = os.getenv("SORA_DATA_CHANNELS")
    parser.add_argument("--data-channels", default=default_ddata_channels, required=not default_ddata_channels,
                        help="使用するデータチャネルを JSON で指定する (例: '[{\"label\": \"#spam\", \"direction\": \"sendrecv\"}]')")

    # オプション引数
    parser.add_argument(
        "--metadata", default=os.getenv("SORA_METADATA"), help="メタデータ JSON")
    args = parser.parse_args()

    metadata = None
    if args.metadata:
        metadata = json.loads(args.metadata)

    messaging_sendrecv = MessagingSendrecv(args.signaling_url,
                                           args.channel_id,
                                           json.loads(args.data_channels),
                                           metadata)
    messaging_sendrecv.run()

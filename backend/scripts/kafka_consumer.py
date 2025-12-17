from kafka import KafkaConsumer
import json
import argparse

bootstrap_servers = ["8.147.106.108:10092"]

parser = argparse.ArgumentParser()
parser.add_argument(
    "--from-beginning",
    action="store_true",
    help="忽略已提交 offset，从最早的消息开始消费（本次运行会重新消费历史消息）",
)
args = parser.parse_args()

consumer = KafkaConsumer(
    "website-analytics",
    bootstrap_servers=bootstrap_servers,
    security_protocol="SASL_PLAINTEXT",
    sasl_mechanism="SCRAM-SHA-512",
    sasl_plain_username="user1",
    sasl_plain_password="ad*ttGEei@Q03nY",
    auto_offset_reset="earliest",
    enable_auto_commit=True,
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    group_id="python-array-demo-group",
)

if args.from_beginning:
    # auto_offset_reset 只在“没有已提交 offset”的情况下生效；
    # 若同一个 group 之前消费过，需要显式把 position 拉回到起始位置。
    consumer.poll(timeout_ms=1000)
    assigned = consumer.assignment()
    if assigned:
        consumer.seek_to_beginning(*assigned)

print("开始消费消息...")

for msg in consumer:
    print(f"offset={msg.offset}")
    print("消息内容：", msg.value)  # msg.value 直接变成数组对象
    print("-" * 40)

import sys
from pathlib import Path

# 将项目 core 目录加入 path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from kafka import KafkaConsumer
import json
import argparse
from website_analytics.settings import get_settings

# 解析命令行参数
parser = argparse.ArgumentParser(description="Kafka 消费者脚本")
parser.add_argument(
    "--topic",
    required=True,
    help="要消费的 Kafka topic 名称",
)
parser.add_argument(
    "--group-id",
    help="消费者组 ID（可选，默认使用 .env 中的 KAFKA_GROUP_ID；想从头消费可指定新的 group-id）",
)

# 无参数时显示帮助
if len(sys.argv) == 1:
    parser.print_help()
    sys.exit(0)

args = parser.parse_args()

# 从 .env 读取配置
settings = get_settings()

consumer = KafkaConsumer(
    args.topic,
    bootstrap_servers=[settings.kafka_bootstrap_servers],
    security_protocol="SASL_PLAINTEXT",
    sasl_mechanism="SCRAM-SHA-512",
    sasl_plain_username=settings.kafka_sasl_username,
    sasl_plain_password=settings.kafka_sasl_password,
    auto_offset_reset="earliest",
    enable_auto_commit=True,
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    group_id=args.group_id or settings.kafka_group_id,
)

print(f"消费 topic: {args.topic}, group: {args.group_id or settings.kafka_group_id}")
print("开始消费消息...")

for msg in consumer:
    print(f"offset={msg.offset}")
    print("消息内容：", msg.value)
    print("-" * 40)

#!/usr/bin/env python3
"""将 JSONL 文件中的任务数据转为 Kafka 消息发送。

支持两种任务类型：
- subscription: 需要 url, account, password 三个字段
- evidence: 只需要 url 字段，不允许 account 和 password 字段
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kafka import KafkaProducer

# 确保可以导入 website_analytics
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

from website_analytics.settings import get_settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  uv run python %(prog)s data.jsonl --type subscription
  uv run python %(prog)s data.jsonl --type evidence
  uv run python %(prog)s data.jsonl --type subscription --batch-size 100
""",
    )
    parser.add_argument(
        "file",
        type=Path,
        nargs="?",
        help="要导入的 JSONL 数据文件路径",
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=["subscription", "evidence"],
        required=True,
        help="任务类型: subscription (需要 url/account/password) 或 evidence (只需要 url)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="每批发送的消息数量（默认 50）",
    )
    # 如果没有提供任何参数（除了脚本名），显示帮助信息
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    args = parser.parse_args()
    if args.file is None:
        parser.print_help()
        sys.exit(0)
    return args


def load_records(data_path: Path):
    """从 JSONL 文件加载记录"""
    if not data_path.exists():
        raise FileNotFoundError(f"文件不存在: {data_path}")

    with data_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                yield payload
            except json.JSONDecodeError as exc:
                print(f"⚠️  第 {line_no} 行 JSON 解析失败: {exc}")
                continue


def create_producer(settings) -> KafkaProducer:
    """创建 Kafka producer"""
    return KafkaProducer(
        bootstrap_servers=[settings.kafka_bootstrap_servers],
        security_protocol="SASL_PLAINTEXT",
        sasl_mechanism="SCRAM-SHA-512",
        sasl_plain_username=settings.kafka_sasl_username,
        sasl_plain_password=settings.kafka_sasl_password,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def main() -> None:
    args = parse_args()
    settings = get_settings()

    producer = create_producer(settings)
    topic = settings.kafka_topic_task

    sent = 0
    failed = 0
    batch = []

    try:
        print(f"📤 开始读取文件: {args.file} (任务类型: {args.type})")
        print(f"📡 目标 Topic: {topic}")
        print()

        for record in load_records(args.file):
            # 根据任务类型验证字段
            is_valid = False
            if args.type == "subscription":
                # Subscription: 必须有 url, account, password
                if all(k in record for k in ["url", "account", "password"]):
                    is_valid = True
            elif args.type == "evidence":
                # Evidence: 必须有 url，且不能有 account 和 password
                if "url" in record and "account" not in record and "password" not in record:
                    is_valid = True

            if not is_valid:
                print(f"⚠️  跳过无效记录: {record}")
                failed += 1
                continue

            batch.append(record)

            # 批量发送
            if len(batch) >= args.batch_size:
                try:
                    producer.send(topic, value=batch)
                    producer.flush()
                    sent += len(batch)
                    print(f"✓ 已发送 {sent} 条消息")
                    batch = []
                except Exception as exc:
                    print(f"❌ 发送失败: {exc}")
                    failed += len(batch)
                    batch = []

        # 发送剩余消息
        if batch:
            try:
                producer.send(topic, value=batch)
                producer.flush()
                sent += len(batch)
                print(f"✓ 已发送 {sent} 条消息（最后一批）")
            except Exception as exc:
                print(f"❌ 发送最后一批失败: {exc}")
                failed += len(batch)

    finally:
        producer.close()

    print()
    print(f"📊 发送完成：成功 {sent} 条，失败 {failed} 条")


if __name__ == "__main__":
    main()


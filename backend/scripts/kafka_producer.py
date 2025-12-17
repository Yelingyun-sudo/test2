from kafka import KafkaProducer
import json

bootstrap_servers = ["8.147.106.108:10092"]

producer = KafkaProducer(
    bootstrap_servers=bootstrap_servers,
    security_protocol="SASL_PLAINTEXT",
    sasl_mechanism="SCRAM-SHA-512",
    sasl_plain_username="user1",
    sasl_plain_password="ad*ttGEei@Q03nY",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

topic = "website-analytics"

print("开始发送消息到 Kafka...")

# 你需要的格式：数组包对象
data_to_send = [
    {
        "url": "https://example.com",
        "account": "my_account",
        "password": "my_password"
    }
]

producer.send(topic, value=data_to_send)
producer.flush()

print("发送成功：")
print(data_to_send)


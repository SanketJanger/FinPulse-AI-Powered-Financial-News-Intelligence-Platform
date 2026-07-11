#!/usr/bin/env bash
# Phase 1: bring up Kafka + Redis, verify health, create topics.
set -euo pipefail

echo "==> Starting infrastructure (Kafka, Redis, Kafka UI)..."
docker compose up -d kafka redis kafka-ui

echo "==> Waiting for Kafka to be healthy..."
until docker exec finpulse-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; do
  printf '.'
  sleep 2
done
echo " Kafka is up."

echo "==> Creating topics (raw-news, processed-news, alerts)..."
docker exec finpulse-kafka /opt/kafka/bin/kafka-topics.sh --create --if-not-exists \
  --bootstrap-server localhost:9092 --topic raw-news --partitions 3 --replication-factor 1
docker exec finpulse-kafka /opt/kafka/bin/kafka-topics.sh --create --if-not-exists \
  --bootstrap-server localhost:9092 --topic processed-news --partitions 3 --replication-factor 1
docker exec finpulse-kafka /opt/kafka/bin/kafka-topics.sh --create --if-not-exists \
  --bootstrap-server localhost:9092 --topic alerts --partitions 1 --replication-factor 1

echo "==> Topics:"
docker exec finpulse-kafka /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

echo "==> Checking Redis..."
docker exec finpulse-redis redis-cli ping

echo ""
echo "✅ Infra is up."
echo "   Kafka UI:      http://localhost:8080"
echo "   Redis:         localhost:6379"
echo "   Kafka broker:  localhost:9094 (external)"

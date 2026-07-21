# 日志收集系统配置

## 概述

本系统使用 structlog 输出 JSON 格式结构化日志，stdout 输出适合容器化环境。本文档描述如何对接 Loki + Promtail（推荐）或 ELK Stack 进行日志收集、存储和查询。

## 日志格式

应用日志为 JSON 格式，典型日志条目：

```json
{
  "timestamp": "2025-01-15T10:30:00.000Z",
  "level": "info",
  "event": "pipeline_started",
  "pipeline_id": "abc-123",
  "user_id": "admin",
  "request_id": "req-456",
  "message": "Pipeline execution started"
}
```

关键字段说明：
- `level`：日志级别（debug/info/warning/error）
- `event`：结构化事件名（如 pipeline_started, auth_login, http_request）
- `request_id`：请求追踪 ID（关联同一请求的所有日志）
- `pipeline_id`：Pipeline 任务 ID（关联同一任务的所有日志）

## 方案一：Loki + Promtail（推荐）

Loki 是轻量级日志聚合系统，与 Prometheus 共享存储后端，资源占用低。

### docker-compose.loki.yml

```yaml
version: "3.9"

services:
  loki:
    image: grafana/loki:2.9.0
    ports:
      - "3100:3100"
    volumes:
      - loki-data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M

  promtail:
    image: grafana/promtail:2.9.0
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./deploy/promtail-config.yml:/etc/promtail/config.yml:ro
    command: -config.file=/etc/promtail/config.yml
    restart: unless-stopped
    depends_on:
      - loki

  grafana:
    image: grafana/grafana:10.3.0
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
    restart: unless-stopped
    depends_on:
      - loki

volumes:
  loki-data:
  grafana-data:
```

### deploy/promtail-config.yml

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  # 收集 Docker 容器日志
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      # 提取容器名作为标签
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: container_name
      # 提取镜像名
      - source_labels: ['__meta_docker_container_label_com_docker_compose_service']
        target_label: service
    # 仅收集 ai-test-system 相关容器
    pipeline_stages:
      - docker:
      # 解析 JSON 日志
      - json:
          expressions:
            level: level
            event: event
            request_id: request_id
            pipeline_id: pipeline_id
      # 添加提取的字段为 Loki 标签
      - labels:
          level:
          event:
```

### 启动方式

```bash
# 启动应用 + 日志收集
docker-compose -f docker-compose.yml -f docker-compose.loki.yml up -d

# 访问 Grafana
# http://localhost:3000 (admin/admin)
# 添加 Loki 数据源 → http://loki:3100
```

### Grafana 查询示例

```logql
# 查看所有错误日志
{service="app"} |= "error"

# 查看特定 Pipeline 的日志
{service="app", pipeline_id="abc-123"}

# 查看认证相关日志
{service="app", event=~"auth_.*"}

# 统计过去 1 小时的错误数
sum(count_over_time({service="app", level="error"}[1h]))
```

## 方案二：ELK Stack

适用于已有 ELK 基础设施的团队。

### docker-compose.elk.yml

```yaml
version: "3.9"

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - es-data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    restart: unless-stopped

  logstash:
    image: docker.elastic.co/logstash/logstash:8.12.0
    volumes:
      - ./deploy/logstash.conf:/usr/share/logstash/pipeline/logstash.conf:ro
    ports:
      - "5044:5044"
    depends_on:
      - elasticsearch
    restart: unless-stopped

  kibana:
    image: docker.elastic.co/kibana/kibana:8.12.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch
    restart: unless-stopped

volumes:
  es-data:
```

### deploy/logstash.conf

```
input {
  tcp {
    port => 5044
    codec => json
  }
}

filter {
  if [level] {
    mutate {
      add_field => { "application" => "ai-test-system" }
    }
    date {
      match => ["timestamp", "ISO8601"]
      target => "@timestamp"
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "ai-test-system-%{+YYYY.MM.dd}"
  }
}
```

### 应用日志输出到 Logstash

在 `docker-compose.yml` 中为 app 服务添加 Logstash 日志驱动：

```yaml
services:
  app:
    logging:
      driver: syslog
      options:
        syslog-address: "tcp://localhost:5044"
        tag: "ai-test-system"
```

## 日志告警配置

### Loki Ruler 告警规则

```yaml
# deploy/loki-alerts.yml
groups:
  - name: ai-test-system
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate({service="app", level="error"}[5m])) > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate in ai-test-system"
          description: "More than 5 errors per second in the last 5 minutes"

      - alert: AuthFailures
        expr: |
          sum(rate({service="app", event="auth_login_failed"}[10m])) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High authentication failure rate"
          description: "More than 10 auth failures per second"
```

## 日志保留策略

| 环境 | 保留时长 | 存储 | 说明 |
|------|----------|------|------|
| 开发 | 7 天 | Loki 本地 | 快速排查 |
| 预发 | 30 天 | Loki + S3 | 回溯测试问题 |
| 生产 | 90 天 | Loki + S3 | 合规要求 |

Loki 配置 S3 长期存储：

```yaml
# loki-config.yml
storage_config:
  aws:
    s3: s3://ak:sk@us-east-1/loki-bucket
    bucketnames: loki-bucket
compactor:
  working_directory: /loki/compactor
  shared_store: s3
  retention_enabled: true
  retention_delete_delay: 2h
limits_config:
  retention_period: 2160h  # 90 天
```

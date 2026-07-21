# 告警系统部署指南

本文档说明如何为 ai-test-system 搭建完整的 Prometheus + AlertManager + 钉钉告警链路。

## 架构

```
ai-test-system:8080/metrics  ──scrape──►  Prometheus  ──fire──►  AlertManager  ──webhook──►  钉钉/邮件
```

## 1. 确认指标端点可用

应用必须安装可选依赖 `prometheus-fastapi-instrumentator`：

```bash
uv sync --extra production --extra web
# 或
pip install prometheus-fastapi-instrumentator

# 验证端点
curl http://localhost:8080/metrics | head -20
```

应看到 `http_requests_total`、`llm_request_duration_seconds` 等指标。

## 2. 部署 Prometheus

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/rules/alerts.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  - job_name: 'ai-test-system'
    metrics_path: /metrics
    static_configs:
      - targets: ['host.docker.internal:8080']  # 或实际服务地址
        labels:
          env: 'production'
```

将 `deploy/alerts.yml` 复制到 Prometheus 的 rules 目录。

## 3. 部署 AlertManager

```bash
# 复制配置模板
cp deploy/alertmanager.example.yml deploy/alertmanager.yml
# 编辑填入真实钉钉 webhook 接收地址
```

## 4. 部署钉钉 Webhook 适配器

推荐 [timonwong/prometheus-webhook-dingtalk](https://github.com/timonwong/prometheus-webhook-dingtalk)：

```bash
# 启动（端口 8060）
prometheus-webhook-dingtalk \
  --ding.profile="ai-test-system=https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN" \
  --ding.profile="critical=https://oapi.dingtalk.com/robot/send?access_token=CRITICAL_TOKEN" \
  --ding.profile="warning=https://oapi.dingtalk.com/robot/send?access_token=WARNING_TOKEN"
```

钉钉机器人在「群设置 → 智能群助手 → 添加机器人 → 自定义」创建，安全设置选「加签」。

## 5. Docker Compose 一键部署

可选：将 Prometheus + AlertManager + DingTalk 适配器加入 `docker-compose.yml`：

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./deploy/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./deploy/alerts.yml:/etc/prometheus/rules/alerts.yml
    ports: ['9090:9090']

  alertmanager:
    image: prom/alertmanager:latest
    volumes:
      - ./deploy/alertmanager.yml:/etc/alertmanager/alertmanager.yml
    ports: ['9093:9093']

  dingtalk:
    image: timonwong/prometheus-webhook-dingtalk:latest
    environment:
      - PROFILE_AI_TEST_SYSTEM=https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN
    ports: ['8060:8060']
```

## 6. 验证告警链路

```bash
# 1. 手动触发测试告警（Prometheus UI）
# 访问 http://localhost:9090/alerts，确认规则已加载

# 2. 停掉应用，触发 ServiceDown 告警
docker-compose stop app
# 1 分钟后应收到钉钉告警通知

# 3. 恢复应用，确认 resolve 通知
docker-compose start app
```

## 告警清单

| 告警名 | 级别 | 触发条件 | 含义 |
|--------|------|---------|------|
| `ServiceDown` | critical | `/metrics` 抓取失败 >1min | 进程崩溃或网络隔离 |
| `HighErrorRate` | critical | 5XX 错误率 >1% 持续 2min | 应用异常，检查日志 |
| `HighLatency` | warning | HTTP P99 >5s 持续 3min | LLM 慢或 DB 锁冲突 |
| `LLMErrorsSpike` | critical | LLM 错误率 >30% 持续 2min | API Key/额度/上游问题 |
| `LLMSlowResponse` | warning | LLM P99 >30s 持续 5min | Provider 限流或过载 |
| `LLMFallbackRate` | warning | 故障转移率 >20% 持续 5min | 主 Provider 不健康 |

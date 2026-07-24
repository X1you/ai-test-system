#!/usr/bin/env python3
"""
OpenTelemetry 分布式追踪 — FastAPI 自动埋点。

启用条件：
    1. 安装 opentelemetry 依赖（pip install -e ".[production]"）
    2. 设置环境变量 OTEL_EXPORTER_OTLP_ENDPOINT（如 http://jaeger:4317）

未配置时完全静默（不注册 exporter，不产生 span），零开销。

环境变量：
    OTEL_SERVICE_NAME        — 服务名（默认 ai-test-system）
    OTEL_EXPORTER_OTLP_ENDPOINT — OTLP gRPC 端点（不设则仅 console 输出）
    OTEL_TRACES_SAMPLER      — 采样器（默认 always_on，生产建议 parentbased_traceidratio）
    OTEL_TRACES_SAMPLER_ARG  — 采样率（如 0.1 = 10%）
"""

import logging
import os

logger = logging.getLogger(__name__)

# 追踪是否已初始化（避免重复 instrument）
_initialized = False


def setup_tracing(app) -> bool:
    """初始化 OpenTelemetry 追踪并挂载到 FastAPI app。

    Returns:
        True = 追踪已启用，False = 未启用（依赖缺失或未配置端点）
    """
    global _initialized
    if _initialized:
        return True

    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.debug("opentelemetry 未安装，跳过追踪初始化")
        return False

    # 未配置 OTLP 端点时不启用（避免开发环境产生无用 span）
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not otlp_endpoint:
        logger.debug("OTEL_EXPORTER_OTLP_ENDPOINT 未设置，跳过追踪初始化")
        return False

    service_name = os.environ.get("OTEL_SERVICE_NAME", "ai-test-system")

    # 构建 TracerProvider
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    # OTLP exporter（gRPC）
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except ImportError:
        logger.warning("opentelemetry-exporter-otlp 未安装，追踪 span 将无处导出")
        return False

    trace.set_tracer_provider(provider)

    # 自动埋点 FastAPI（所有 HTTP 请求自动生成 span）
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/health,/metrics",
    )

    _initialized = True
    logger.info("OpenTelemetry 追踪已启用 → %s (service=%s)", otlp_endpoint, service_name)
    return True


def get_tracer():
    """获取 tracer 实例（用于手动创建 span）。

    未初始化时返回 NoOp tracer，调用方无需判断。
    """
    from opentelemetry import trace

    return trace.get_tracer("ai-test-system")

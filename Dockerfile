# AI 测试用例生成系统 — Docker 镜像
# 多阶段构建：builder（安装依赖）+ runtime（精简运行时）

# ─── Builder 阶段 ───
FROM python:3.11-slim AS builder

WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY pyproject.toml ./
COPY core/ core/
COPY web/ web/
COPY scripts/ scripts/
COPY integrations/ integrations/
COPY db/ db/
COPY cli.py config_loader.py ./

# 安装依赖到 /install
RUN pip install --no-cache-dir --prefix=/install -e ".[web,xmind,excel,db,production]"

# ─── Runtime 阶段 ───
FROM python:3.11-slim

WORKDIR /app

# 从 builder 复制已安装的依赖
COPY --from=builder /install /usr/local

# 复制项目源码
COPY --from=builder /build/ /app/

# 创建数据目录
RUN mkdir -p /app/data /app/output /app/uploads

# 创建非 root 用户并设置目录权限
RUN useradd -r -s /bin/false appuser && chown -R appuser:appuser /app

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DATABASE_PATH=/app/data/app.db

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8080

# 健康检查（start_period 给冷启动宽限期）
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health/live')" || exit 1

# 启动命令
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8080"]

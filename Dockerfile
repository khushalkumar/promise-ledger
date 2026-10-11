FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG CODEX_VERSION=0.159.0
ARG ENTIRE_VERSION=0.11.4
ARG GH_VERSION=2.82.1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl git libpq5 xz-utils \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install --yes --no-install-recommends nodejs \
    && npm install --global "@openai/codex@${CODEX_VERSION}" \
    && curl -fsSL "https://github.com/entireio/cli/releases/download/v${ENTIRE_VERSION}/entire_linux_amd64.tar.gz" \
      | tar -xz -C /usr/local/bin entire git-remote-entire \
    && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.tar.gz" \
      | tar -xz --strip-components=2 -C /usr/local/bin "gh_${GH_VERSION}_linux_amd64/bin/gh" \
    && apt-get purge --yes --auto-remove curl xz-utils \
    && rm -rf /var/lib/apt/lists/* /root/.npm

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app /workspace \
    && chown -R app:app /app /workspace

WORKDIR /app

COPY --chown=app:app pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=app:app ledger ./ledger
COPY --chown=app:app contracts ./contracts
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app evidence/run_live_audit.json ./evidence/run_live_audit.json
RUN uv sync --frozen --no-dev \
    && chmod +x scripts/cloud-agent-run.sh scripts/render-agent-run.sh

USER app
ENV PATH="/app/.venv/bin:/usr/local/bin:${PATH}" \
    HOME=/home/app \
    PYTHONUNBUFFERED=1 \
    PROMISE_LEDGER_HOST=0.0.0.0 \
    PORT=8080

EXPOSE 8080
CMD ["ledger-ui"]

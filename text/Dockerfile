FROM public.ecr.aws/lambda/python:3.12
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN UV_PROJECT_ENVIRONMENT=/var/lang uv sync --frozen --no-dev --inexact --no-install-project --no-cache
ENV JEV_WEIGHTS=/opt/weights
COPY core/jev.py core/
COPY text/jev.py ./
# Importing jev downloads its weights into the image, so a cold start downloads nothing.
RUN python -c "import jev"
COPY text/handler.py ./
CMD ["handler.handler"]

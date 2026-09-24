# Static ffmpeg/ffprobe to sample video frames and the audio track, unpacked on the build host.
FROM --platform=$BUILDPLATFORM public.ecr.aws/docker/library/alpine:3.20 AS ffmpeg
ARG TARGETARCH
ADD https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-${TARGETARCH}-static.tar.xz /ffmpeg.tar.xz
RUN apk add --no-cache tar xz && tar -xJf /ffmpeg.tar.xz --strip-components=1 --wildcards '*/ffmpeg' '*/ffprobe'

FROM public.ecr.aws/lambda/python:3.12
COPY --from=ffmpeg /ffmpeg /ffprobe /usr/local/bin/
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN UV_PROJECT_ENVIRONMENT=/var/lang uv sync --frozen --no-dev --inexact --no-install-project --no-cache
ENV JEV_WEIGHTS=/opt/weights
COPY core/jev.py core/
COPY text-image-video/jev.py ./
# Importing jev downloads its weights into the image, so a cold start downloads nothing.
RUN python -c "import jev"
COPY text-image-video/handler.py ./
CMD ["handler.handler"]

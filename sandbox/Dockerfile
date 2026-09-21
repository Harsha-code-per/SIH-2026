# Code execution sandbox. Run with:
#   docker run --rm --network none --read-only --memory 512m --pids-limit 64 \
#              --cap-drop ALL --security-opt no-new-privileges \
#              -v "$WORK:/work" wb-sandbox python /work/snippet.py
FROM python:3.12-slim
RUN pip install --no-cache-dir numpy pandas
RUN useradd -u 65532 -m runner
USER runner
WORKDIR /work

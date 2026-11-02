# The CI Live UI job's machine, to run its checks locally: scripts/live-ui-docker.sh.
# Ubuntu 24.04 and its Python 3.12, as on GitHub's runner; a non-root user, as there.
FROM ubuntu:24.04

COPY scripts/live-ui-packages.txt /tmp/
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      python3 python3-venv python3-tk $(grep -v '^#' /tmp/live-ui-packages.txt) \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m tester && mkdir /repo && chown tester /repo
USER tester
WORKDIR /repo

# The dependencies first, in a layer of their own, so a change to the code doesn't
# reinstall them: pyproject.toml with an empty helper package.
COPY --chown=tester pyproject.toml ./
RUN mkdir helper && touch helper/__init__.py \
 && python3 -m venv /home/tester/venv \
 && /home/tester/venv/bin/pip install -q ".[dev]" \
 && rm -rf helper build *.egg-info

COPY --chown=tester . .
RUN /home/tester/venv/bin/pip install -q --no-deps -e .
ENV VENV=/home/tester/venv
CMD ["scripts/run-live-checks.sh"]

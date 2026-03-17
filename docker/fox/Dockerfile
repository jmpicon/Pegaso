# ──────────────────────────────────────────────────────────────────────────────
# Fox (Ferrumox) — build desde fuente
# https://github.com/ferrumox/fox
#
# Arg opcional: FOX_REF para anclar a un tag/commit concreto (default: main)
# ARG FOX_REF=v0.9.0
# ──────────────────────────────────────────────────────────────────────────────

# ── Stage 1: compilación ─────────────────────────────────────────────────────
FROM rust:1.85-bookworm AS builder

ARG FOX_REF=main

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    clang \
    libclang-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN git clone --recurse-submodules --depth 1 \
        --branch "${FOX_REF}" \
        https://github.com/ferrumox/fox . \
    || git clone --recurse-submodules --depth 1 \
        https://github.com/ferrumox/fox .

RUN cargo build --release

# ── Stage 2: runtime mínimo ──────────────────────────────────────────────────
FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/target/release/fox /usr/local/bin/fox

EXPOSE 8080

ENTRYPOINT ["fox"]

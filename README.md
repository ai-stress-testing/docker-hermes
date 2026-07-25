# docker-hermes

A sandboxed CLI agent harness implementing NousResearch's Hermes
tool-calling format, talking to a locally-running LM Studio instance as
its model backend.

## Running it

1. Copy the example env file and edit it if needed (in particular
   `LMSTUDIO_URL`, if LM Studio isn't listening on the default port 1234):

   ```sh
   cp .env.example .env
   ```

2. Build and run the agent against a task:

   ```sh
   docker compose build agent
   docker compose run --rm agent "your task here"
   ```

Output files the agent creates land in `./workspace/` on the host.

## The sandbox boundary

The agent runs in a container with exactly one path in and out: the
`./workspace` directory, bind-mounted read-write so the agent can create
and edit files there and nowhere else. The container's own root
filesystem is mounted read-only (with a small `/tmp` tmpfs for scratch
space that's discarded when the run ends), it runs as a non-root user,
and all Linux capabilities are dropped. It has no access to the host
network or any host devices — the one exception is `host.docker.internal`,
which lets it reach LM Studio's API on the host, since that's the whole
point of the harness. In short: it can read and write inside
`./workspace` and talk to LM Studio, and nothing else on your machine.

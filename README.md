# docker-hermes

Runs [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous
Research's agentic CLI) in a sandboxed Docker container, configured to
use a locally-running LM Studio instance as its model.

## Running it

1. Start LM Studio on the host with its OpenAI-compatible server
   enabled (Developer tab -> Start Server; default port 1234). If the
   container can't reach it, check whether LM Studio needs its "serve
   on local network" option on rather than loopback-only - `extra_hosts`
   below routes to the host's network-facing address, not `127.0.0.1`,
   so a loopback-only server may not be reachable from inside the
   container. Note this does widen what else on your LAN can reach LM
   Studio's API too (see "The sandbox boundary" below).

2. Create your env file and set `PUID`/`PGID` to your own user
   (`id -u` / `id -g`), so files Hermes creates are owned by you rather
   than the image's default uid:

   ```sh
   cp .env.example .env
   ```

3. First run: launch the setup wizard to configure LM Studio as the
   provider (this writes into `./hermes-data`, so you only do this
   once). This is the exact command from the project's own Docker guide
   (see Sources) - not something we invented:

   ```sh
   docker compose run --rm hermes setup
   ```

   When it asks for a provider, choose LM Studio / Custom Endpoint and
   give it `http://host.docker.internal:1234/v1`.

4. After that, start an interactive session:

   ```sh
   docker compose run --rm hermes
   ```

Everything Hermes persists or creates - config, sessions, memories,
skills, and any files it writes - lives under `./hermes-data` on the
host, which is bind-mounted to `/opt/data`. That's the only bind mount
in this deployment.

## The sandbox boundary

- **`./hermes-data` is the only bind mount.** Confirmed against the
  image's own Dockerfile (see Sources): it declares exactly one
  `VOLUME`, `/opt/data`, and sets `HERMES_WRITE_SAFE_ROOT=/opt/data` at
  the image level, so the application itself is built to confine its
  writes there. That's a claim about mounts, not about network
  reachability - see below for that.
- **No published ports.** This runs as an interactive CLI, not a
  network-facing service - nothing external can connect in.
- **Local terminal backend, not Hermes's own Docker backend.** Hermes
  Agent has a built-in option (`terminal.backend: docker`) to sandbox
  each command in its own nested Docker container. This deployment
  doesn't set that up - no `/var/run/docker.sock` is mounted, so there's
  no Docker daemon reachable from inside the container by default for
  it to use. That's a default, not an enforced guarantee: `config.yaml`
  lives in the writable `/opt/data` mount, so a manual edit (or, in
  principle, the agent itself, since it executes commands) could set
  `terminal.backend: docker` later - it just wouldn't have anything to
  connect to unless a Docker API became reachable some other way (a
  `DOCKER_HOST` value inherited via `.env`, or a daemon exposed
  elsewhere on the network this container can already reach). The
  project's own troubleshooting docs say the failure mode is a clear
  error ("Run `docker version` to verify Docker is working. If it
  fails, fix Docker or `hermes config set terminal.backend local`"),
  not a silent fallback to something weaker - but that's from reading
  the docs, not from having run it here; treat it as worth a smoke test
  before relying on it.
- **Capabilities are dropped explicitly, not deferred.** `cap_drop:
  ALL` plus an allowlist for exactly what the image's root-then-drop
  startup needs (see `docker-compose.yml` comments). This doesn't
  depend on knowing the app's internal write patterns, so - unlike the
  filesystem question - there was no reason to leave it unhardened.
- **Read-only root filesystem**, now that the Dockerfile confirms
  `/opt/data` is the only place the app writes, with `tmpfs` for the
  handful of paths a Linux init system typically still needs at
  runtime.
- **Full host CPU/RAM, no GPU passthrough**, by request - no resource
  limits are set.
- **Network egress is not scoped to LM Studio alone, and not scoped to
  "the host" either - it reaches your LAN too.** `host.docker.internal`
  resolves to the host's whole address, not just port 1234, this
  container has ordinary outbound internet access over its network the
  way any container does, and from there it can reach anything else on
  your local network that the host itself can reach - other machines,
  routers, NAS/SMB shares, printers. Nothing in this deployment
  restricts that. What actually bounds this setup is the single bind
  mount, the absence of published ports, and the dropped capabilities -
  not a network firewall. If you need egress locked to LM Studio's port
  specifically, that's a follow-up (an egress proxy or a custom bridge
  with firewall rules), not something this compose file does today.
- **None of the hardening above (`read_only`, `cap_drop`/`cap_add`) has
  been run against the real image.** It's grounded in the Dockerfile,
  not empirically verified - this environment can't pull from Docker
  Hub or run a Docker daemon to confirm the container still boots
  cleanly under these constraints. If `docker compose run --rm hermes
  setup` fails to start, try removing `read_only`/`tmpfs` first, then
  the `cap_drop`/`cap_add` block, and open an issue with what broke.

## Sources

Every factual claim above about the image itself (not about this
deployment's own config, which you can just read) is grounded in the
upstream project, fetched 2026-07-25:

- [`website/docs/user-guide/docker.md`](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/docker.md) - the `setup`/`gateway run` commands, the `/opt/data` volume layout, `PUID`/`PGID` support
- [`Dockerfile`](https://github.com/NousResearch/hermes-agent/blob/main/Dockerfile) - the single `VOLUME ["/opt/data"]`, `HERMES_WRITE_SAFE_ROOT`, the s6-overlay `/init` entrypoint, the non-root `hermes` user
- [`website/docs/user-guide/configuration.md`](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/configuration.md) - the `terminal.backend: docker` option and its troubleshooting fallback
- [`website/docs/getting-started/quickstart.md`](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/getting-started/quickstart.md) - the LM Studio / custom-endpoint provider setup flow

# docker-hermes

Runs [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous
Research's agentic CLI) in a sandboxed Docker container, configured to
use a locally-running LM Studio instance as its model.

## Running it

1. Start LM Studio on the host with its OpenAI-compatible server
   enabled (Developer tab -> Start Server; default port 1234).

2. Create your env file and set `PUID`/`PGID` to your own user
   (`id -u` / `id -g`), so files Hermes creates are owned by you:

   ```sh
   cp .env.example .env
   ```

3. First run: launch the setup wizard to configure LM Studio as the
   provider (this writes into `./hermes-data`, so you only do this
   once):

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
host. That's the only path shared between the container and your
machine.

## The sandbox boundary

- **One directory in, one directory out.** `./hermes-data` is the only
  bind mount. Nothing else on your filesystem is reachable from inside
  the container.
- **No published ports.** This runs as an interactive CLI, not a
  network-facing service - nothing external can connect in.
- **Local terminal backend, not Hermes's own Docker backend.** Hermes
  Agent has a built-in option to sandbox each command in its own nested
  Docker container, but that requires mounting the host's Docker socket
  into this container - which hands it the ability to launch arbitrary
  containers on your machine, the opposite of the point here. This
  deployment doesn't enable that; the outer container above is the
  sandbox boundary instead.
- **Full host CPU/RAM, no GPU passthrough**, by request - no resource
  limits are set.
- **Network egress is not scoped to LM Studio alone**, and worth being
  upfront about: `host.docker.internal` (added so the container can
  reach LM Studio) resolves to the host's whole IP, not just port 1234,
  and the container also has normal outbound access to the internet
  over Docker's default bridge network the way any container does.
  Nothing in this deployment restricts that further. What actually
  bounds this setup is the single bind mount and the absence of
  published ports, not a network firewall - if you need egress locked
  to LM Studio's port specifically, that's a follow-up (an egress proxy
  or a custom bridge with firewall rules), not something this compose
  file does today.
- **`read_only`/`cap_drop` container hardening was deliberately left
  off**, unlike a from-scratch image we'd fully control: this image's
  entrypoint intentionally starts as root (via s6-overlay) to fix up
  volume permissions before dropping to its own non-root user
  internally, and its write patterns beyond `/opt/data` aren't
  documented in enough detail to harden blind without risking a broken
  startup. Flagging this as a known gap rather than silently shipping
  less hardening than it looks like.

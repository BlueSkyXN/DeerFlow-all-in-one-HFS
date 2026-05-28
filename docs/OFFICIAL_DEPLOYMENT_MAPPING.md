# Mapping Official DeerFlow Deployment Modes to HFS

This project is derived from DeerFlow's official deployment concepts, but changes the packaging boundary to fit Hugging Face Docker Spaces.

## Official local development

Official shape:

```text
native processes
├─ gateway : 8001
├─ frontend: 3000
└─ nginx   : 2026
```

HFS adaptation:

```text
single Docker Space container
├─ gateway : 127.0.0.1:8001
├─ frontend: 127.0.0.1:3000
└─ nginx   : 0.0.0.0:7860
```

This is the closest conceptual match.

## Official Docker Compose / production app layer

Official service split:

```text
nginx
frontend
gateway
optional provisioner
```

HFS adaptation:

- Collapse nginx, frontend and gateway into one container.
- Replace Docker Compose service DNS with `127.0.0.1` upstreams.
- Keep path-based routing.
- Disable provisioner route by default.

## Official LocalSandboxProvider

Official mode:

```yaml
sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
  allow_host_bash: false
```

HFS adaptation:

- Keep this mode.
- Do not enable host bash for public demos.
- Keep tools read-oriented by default.

## Official AioSandboxProvider / Docker sandbox

Official mode:

```yaml
sandbox:
  use: deerflow.community.aio_sandbox:AioSandboxProvider
```

Why not included:

- It normally requires Docker/Apple Container style sandbox management.
- Docker-outside-of-Docker requires a Docker socket.
- Docker-in-Docker is not a good fit for a simple Space demo.

Possible later route:

- Use a separate VM or Kubernetes cluster for sandbox execution.
- Implement or adapt a remote sandbox provider.

## Official provisioner / Kubernetes sandbox

Official mode:

```yaml
sandbox:
  use: deerflow.community.aio_sandbox:AioSandboxProvider
  provisioner_url: http://provisioner:8002
```

Why not included:

- It expects a Kubernetes cluster and sandbox Pod lifecycle management.
- HFS is not a Kubernetes control plane for arbitrary Pods.
- Public provisioner APIs need authentication, quotas and network hardening.

HFS-compatible production-like split:

```text
HFS Space
  ├─ UI
  ├─ Gateway
  └─ Nginx
        │ HTTPS + auth
        ▼
External Sandbox Control Plane
  ├─ provisioner-like API
  ├─ Kubernetes cluster or VM pool
  └─ isolated sandbox workers
```

## Recommended roadmap

### Phase 1: Demo profile

- Single container.
- LocalSandboxProvider.
- Host bash disabled.
- File read tools only.
- External model APIs.
- `/data` persistence.

### Phase 2: Hardened private Space

- Private/Protected visibility.
- Stable secrets.
- Provider-side budget limits.
- Optional limited file write workspace.
- Better logs and request limits.

### Phase 3: External sandbox

- Keep HFS as app shell.
- Move code execution to an authenticated external sandbox service.
- Add per-thread workspaces, quotas, cleanup and audit logs.

### Phase 4: Production

- Use official DeerFlow deployment outside HFS.
- Put HFS in front only as documentation/demo/entry page if still useful.

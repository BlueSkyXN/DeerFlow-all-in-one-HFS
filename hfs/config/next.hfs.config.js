import upstreamConfig from "./next.config.upstream.js";

function withHfsBuildLimits(config = {}) {
  return {
    ...config,
    experimental: {
      ...(config.experimental ?? {}),
      // HF cpu-basic provides 2 vCPU. Do not inherit the builder host's much
      // larger CPU count and spawn excessive page-data workers.
      cpus: 2,
      webpackMemoryOptimizations: true,
    },
    typescript: {
      ...(config.typescript ?? {}),
      // Docker runs `pnpm typecheck` in a separate process first. Avoid holding
      // the completed Webpack graph and the TypeScript program at the same time.
      ignoreBuildErrors: true,
    },
  };
}

export default typeof upstreamConfig === "function"
  ? async (phase, context) =>
      withHfsBuildLimits(await upstreamConfig(phase, context))
  : withHfsBuildLimits(upstreamConfig);

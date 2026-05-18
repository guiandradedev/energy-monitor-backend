import { type RouteConfig, index, route } from "@react-router/dev/routes";

export default [
  index("routes/home.tsx"),
  route("devices", "routes/devices.tsx"),
  route("priorities", "routes/priorities.tsx"),
  route("safety-limits", "routes/safety-limits.tsx"),
  route("parameters", "routes/parameters.tsx"),
  route("events", "routes/events.tsx"),
  route("telemetry", "routes/telemetry.tsx"),
] satisfies RouteConfig;

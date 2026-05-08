# Capture Paths

Use capture paths only for authorized targets and only after the OpenAPI path is insufficient or the task specifically asks for client-path triage.

## Priority

1. Lark Web with browser DevTools and HAR export
2. mitmproxy regular proxy with system/browser proxy settings
3. mitmproxy local capture for a specific process/PID
4. mitmproxy transparent mode with explicit routing/pf setup
5. Static client analysis for routes, schema hints, or descriptors
6. Frida/runtime instrumentation for authorized debugging

## mitmproxy Notes

Transparent mode is not a one-command local app capture path. Prefer:

```bash
mitmweb
mitmproxy --mode local
mitmproxy --mode local:Lark
```

Install and trust the mitmproxy CA for the client being captured. `ssl_insecure=true` affects mitmproxy's upstream verification; it does not make the Lark client trust mitmproxy.

## WebSocket and Protobuf Triage

For each frame family, record:

- host and path
- direction
- timestamp
- length
- whether the frame is text or binary
- first bytes as hex
- whether strings are visible
- whether frames repeat around user actions

Do not assume binary means Protobuf. It may be compressed, encrypted, multiplexed, or a custom framing format.

Only attempt Protobuf decoding when there is evidence for one of:

- `.proto` files
- descriptor sets
- generated JS/TS/Swift/ObjC classes
- recognizable field-number patterns and stable sample frames

## Runtime Instrumentation Gate

Use Frida only when earlier evidence shows the required plaintext exists only inside the authorized client process. On macOS, expect hardened runtime, SIP, signing, and debug entitlement issues. Do not advise disabling protections on third-party production apps unless the user has explicit authorization and accepts the operational risk.

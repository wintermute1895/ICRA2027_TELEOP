# ACT Quality Gates

An episode is eligible for the positive ACT set only when all gates pass:

- Terminal audit: reviewed `success=true`, `safety_violation=false`, and `unlogged_external_override=false`.
- Capture validation: `artifacts/capture_validation.json` reports `passed=true`.
- Camera streams: every required camera has decodable RGB frames, stable dimensions, monotonic timestamps, and no black-frame run.
- Alignment: RGB-to-action/state age is within the configured tolerance; report max, mean, and p95 age per camera.
- Actions: fixed dimension, finite values, correct unit, and no unexplained discontinuity.
- Provenance: task ID/revision, camera serial/order, source bag hash, export hash, and projection hash are recorded.

For the current two-camera setup, run both streams through the same timestamp policy. D435i devices usually give more consistent firmware and timestamp behavior when used as a matched pair, but this is not a guarantee of shared clock synchronization. Keep the measured offset and dropped-frame statistics in the report.

Use reviewed audit sidecars explicitly when converting the practice batch:

```text
artifacts/audit_events_reviewed.jsonl
artifacts/terminal_audit_reviewed.json
```

Do not replace the raw sidecars. A failed or uncertain episode can remain in an audit-only buffer but must not enter the positive ACT imitation set.

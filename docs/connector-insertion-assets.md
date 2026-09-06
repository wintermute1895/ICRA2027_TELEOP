# Connector insertion asset source and license note

The initial USB-C laptop insertion scene is a fully runnable, parameterized
MuJoCo primitive baseline. It downloads no third-party laptop, plug, or cable
mesh. `usb_c_plug_seed` is a project-authored visual pipeline test asset; its
provenance and generated visual/collision SHA256 values are recorded in
`assets/tasks/connector_insertion/manifests/usb_c_plug_seed.manifest.json`.
It is not a claim of physical USB-C geometry fidelity and does not replace the
primitive baseline collider.

If a visual enhancement is added later, it must remain separate from the
collision model and receive its own JSON entry under
`assets/tasks/connector_insertion/manifests/` with the source URL, retrieval
time, license, attribution, SHA256, scale in metres, and `visual_only` use.

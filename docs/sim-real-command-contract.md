# Simulation/real command contract

The platform has one control decision and two endpoints:

```text
raw master input
  → One-Euro filter + joint index map + verified direction map + limits
  → FollowJoint / VendorArmCommand in radians, vendor order
      → real: lbot_driver → official SDK
      → sim: sim_robot_driver → MuJoCo
```

`VendorArmCommand` is emitted on `/robot1/{left,right}_arm/vendor_command` by
the driver after shape/finite/connection checks and immediately before the
corresponding official SDK call. Its `source` value is
`lbot_driver.accepted_for_sdk`; this means “accepted for an SDK attempt”, not
“the robot has completed the motion”.

`sim_robot_driver` never writes `/robot1/...` state topics. It uses
`/sim/robot1/...` so a shadow run can record hardware and simulation states at
the same time. `MoveJ` is visualized with a smooth ideal interpolation; the
interpolation is not yet a calibrated model of the vendor servo dynamics.

The real launch keeps the initial MoveJ service gate enabled. The simulation
launch explicitly disables that gate because it has no hardware service. This
parameter must not be changed in a real-robot launch.

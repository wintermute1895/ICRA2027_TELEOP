# Continuous Assistance Architecture Plan

## Purpose

This plan scopes architecture innovation for the teleoperation data-collection
filter. A component enters the paper's primary method only when it follows from
the collection-time assistance problem, has a defined training signal and
runtime input, and can be isolated in an ablation. This is a planning document;
it is not evidence that every item has already been implemented or validated.

## Central Insight

For visually observable precision teleoperation, assistance should not be a
binary intervention or an unconstrained autonomous replacement. It should be a
continuous, rate-limited control variable that preserves nominal human commands
while scaling a local corrective action when the observed history warrants it.

## Layer 1: Primary Paper Architecture (Must Implement and Evaluate)

### 1. Separate action-distribution and assistance-gain heads

**Problem:** Predicting a corrective action and deciding how strongly to apply
it are different decisions. A single action head entangles action direction with
control authority.

**Inheritance:** conditional generative action modeling, residual control, and
shared autonomy.

**Change:** a causal history encoder feeds two heads:

```text
CVAE action head:   p_theta(U_demo_t | h_t, z_t), U_demo_t in R^(H x d)
gain head:          alpha_bar_t = alpha_max sigmoid(g_theta(h_t))
```

The decoder predicts a short chunk of demonstrated joint increments. Online
collection uses receding-horizon execution: it applies the first action and
predicts a new chunk after the next visual update. The gain head independently
sets how much of the current residual is applied to the human command.

**Required evidence:** deterministic action regression versus CVAE; $H=1$
versus action chunks; open-loop versus receding-horizon execution; shared
single-head baseline versus separate action/gain heads.

### 2. Continuous, rate-limited assistance state

**Problem:** Framewise binary intervention causes abrupt authority changes and
does not match gradual precision alignment.

**Inheritance:** shared-autonomy authority allocation and bounded residual
control.

**Change:**

```math
alpha_bar_t = alpha_max sigmoid(g_theta(h_t)),
alpha_t = alpha_{t-1} + clip(alpha_bar_t - alpha_{t-1}, -r_alpha, r_alpha).
```

The correction interval is weak supervision for higher assistance, while
successful non-correction segments penalize needless assistance. The rate bound
is structural, not merely a reporting metric.

**Required evidence:** fixed gain versus framewise gain versus rate-limited
gain; gain distributions in correction and nominal intervals; gain variation;
nominal deviation and safety metrics.

### 3. Bounded residual composition and independent safety projection

**Problem:** a learned candidate action must not replace human teleoperation
without an explicit authority and safety boundary.

**Inheritance:** residual control and constrained control.

**Change:**

```math
delta_hat_t = clip(u_hat_demo_(t|t) - u_raw_t, -delta_max, delta_max),
u_tilde_t = u_raw_t + alpha_t delta_hat_t,
u_out_t = Pi_safe(u_tilde_t).
```

`Pi_safe` is an independent position, velocity, rate, numerical-validity, and
runtime-fallback layer. It is not learned by the CVAE.

**Required evidence:** residual bounds, projection/fallback frequency, and
safety violations under the same collection budget.

## Layer 2: Conditional Extensions (Only After Layer 1 Works)

### Dual-timescale visual-action encoder

Motivation: commands and robot state are higher-frequency than visual frames.
Risk: synchronization complexity, latency, and overfitting. Add only after the
single causal encoder has an established baseline and latency budget.

### Predictive uncertainty modulation

Motivation: reduce assistance when the corrective action is uncertain. Risk:
an uncalibrated variance head is not meaningful uncertainty. Requires NLL,
calibration, and error-versus-uncertainty evaluation.

### Explicit phase head

Motivation: task phase can explain changing assistance. Risk: phase-label
leakage and train/runtime mismatch. Use only when phase prediction is evaluated
from runtime-available inputs.

## Layer 3: Excluded From the Current Main Claim

- Multiple independent CVAE latents for nominal and correction behavior.
- Online Qwen-VL control or online VLM-generated action labels.
- Full KL-control or optimal-control guarantees.
- Any module without an independent ablation and runtime latency measurement.

## Narrative and Experiment Mapping

| Paper claim | Architectural mechanism | Required measurement |
|---|---|---|
| Preserve nominal teleoperation | low-gain supervision and residual penalty | nominal deviation / false assistance |
| Assist difficult local states continuously | separate rate-limited gain state | gain trajectory, correction timing, task outcome |
| Produce coherent local corrections | CVAE action-chunk head with receding-horizon execution | chunk error, $H=1$, deterministic-CVAE, and open-loop ablations |
| Never grant unconstrained autonomy | bounded residual plus safety projection | clipping, fallback, safety events |
| Improve collection rather than only policy rollout | cross-round admitted-data protocol | A_action episodes per operator-minute |

## Implementation Order

1. Standardize raw, demonstration, composed, and executed commands as joint increments.
2. Generalize the action target and decoder from one step to horizon $H>1$.
3. Add receding-horizon runtime execution and test that only the first action is applied.
4. Add and test the separate desired-gain head and rate-limited scalar state.
5. Align chunk, gain-band, nominal, KL, and smoothness losses with the paper contract.
6. Add reporting for chunk error, gain, residual, projection, latency, and fallback.
7. Run Layer-1 ablations before considering Layer-2 extensions.

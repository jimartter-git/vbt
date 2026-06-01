# Porter's Five Forces — the "dream" version

> Scope: the **platform** vision — a recovery/readiness layer that measures
> *muscular & CNS strain from lifting* ("Whoop for the weight room"), not the
> accessible velocity tool. Rough strategic read, May 2026. Comps/figures from
> `market-sizing.md`.

## Summary

| Force | Intensity | One-liner |
|---|---|---|
| Competitive rivalry | **High** | a hot, well-capitalized recovery-wearable category — that is structurally blind to lifting |
| Threat of new entrants | **High** | an incumbent bolting "lifting" onto its wearable is the real danger |
| Threat of substitutes | **Moderate** | feel/RPE, coaches, HR/HRV, BLE VBT — imperfect but "good enough" for many |
| Buyer power | **Moderate** | consumers are churn-prone & price-sensitive; personal data history locks them in over time |
| Supplier power | **Moderate–High** | Apple platform dependency — and Apple is also a potential competitor |

**Net:** an attractive, fast-growing category with a genuinely *unserved niche*
(lifting strain) — but ringed by giants and dependent on Apple's platform.
Defensibility rests on three moats; the two existential risks are incumbent entry
and platform dependency.

---

## 1. Competitive rivalry — HIGH
**Drivers.** Whoop (~$1.1B ARR, ~$10B), Oura (~$1B rev, ~$11B), Apple Watch
(100M+ users), Garmin, Fitbit/Google, Samsung — all racing for the
recovery/readiness wallet with deep pockets and fast cycles. Adjacent strength
players (Vitruve, GymAware, Perch, Output, Metric) crowd the measurement side.
**Our position.** The entire recovery category is **blind to resistance training** —
rivalry is fierce in "recovery score" broadly but *thin* in "muscular/lifting
strain" specifically. That's the lane.
**Play.** Don't fight Whoop on sleep/HRV; win decisively on the thing they can't
see. Compete on a metric we define, not one we're late to.

## 2. Threat of new entrants — HIGH  *(the #1 risk)*
**Drivers.** A basic app has low barriers. The dangerous entrant isn't a startup —
it's an **incumbent adding lifting detection** (Apple shipping watch-native bar
velocity; Whoop/Oura/Garmin adding a "strength strain" score). They already own
the sensors, distribution, brand, and capital.
**Barriers we can build.** Calibration/accuracy know-how; the **per-user learned
prior** (a compounding data moat); multi-source **fusion IP**; trust in a
lifting-specific score; the multi-vendor calibration dataset.
**Play.** Speed + data moat; go deep enough in strength that **buying us beats
building.** Strategic posture: become the obvious acquisition target.

## 3. Threat of substitutes — MODERATE
**Drivers.** Training by feel / RPE / RIR (free, entrenched), a coach, a notebook,
HR & HRV wearables (imperfect for lifting but "good enough"), BLE VBT devices,
generic sleep/recovery proxies. **Inertia is the real competitor.**
**Our position.** None of these actually *measures* muscular strain — they're
proxies or guesses. The job is real and unserved.
**Play.** Make the insight obviously better than feel (catch overreach /
under-recovery a notebook can't) and frictionless enough to beat "free by feel."

## 4. Bargaining power of buyers — MODERATE
**Consumers.** Low concentration, but price-sensitive, subscription-fatigued, and
**churn-prone** (a known Whoop pain). Switching cost is low *early*.
*Counter:* **data lock-in** — your velocity→RPE curve, strain history, and personal
prior get better the longer you stay; leaving resets your "readiness IQ."
**Institutions (teams).** Higher power per deal (budgets, RFPs, entrenched
incumbents) but **stickier and higher-ACV** once installed — a useful early-revenue
beachhead that reduces reliance on fickle consumers (see `market-sizing.md`).

## 5. Bargaining power of suppliers — MODERATE–HIGH
**The platform is the supplier.** Apple controls watchOS, HealthKit, Core Motion /
batched-sensor APIs, the App Store take (15–30%), and the power to restrict sensor
access or change terms — **and Apple is simultaneously a potential competitor.**
That's concentrated, structural supplier power.
**Hardware (if the sensor-cam ships):** IMU/camera/edge-SoC components are largely
commoditized — moderate.
**Talent & data:** CV/ML + sports-science talent is moderate; **data is
self-generated** (low dependency — a plus).
**Play.** Stay **device-agnostic** via the `VelocitySource` abstraction — ride
whatever the user already wears (Apple, Fitbit, Garmin, Whoop, Oura, or a
vendor-neutral tape-on IMU), sanctioned-API-first with reverse-engineered local
BLE only as a best-effort, never-load-bearing fallback. Own the data; keep a
hardware option so the company isn't 100% hostage to one OS. Interoperability
flips this force: the more sources we accept, the less any single supplier (Apple)
can squeeze us.

---

## Strategic implications

- **Three moats to build, in order:** (1) the **unique signal** no one else
  computes (lifting strain), (2) a **compounding per-user data/prior** moat,
  (3) **fusion + calibration IP** (the multi-vendor dataset).
- **Interoperability is a moat-*protector*, not a moat itself.** The defensible
  asset is the fusion model + the muscular layer; the **device is interchangeable.**
  Being source-agnostic (Apple/Fitbit/Garmin/Whoop/Oura, or a tape-on IMU) does
  triple duty: (a) **defuses Apple supplier power** — not hostage to one OS; (b)
  **lowers buyer adoption friction** — use the wearable you already own, no new
  purchase; (c) **widens TAM** beyond any one installed base. Policy: sanctioned
  APIs first; RE'd local BLE only as best-effort behind the abstraction — it's
  OTA-fragile (cf. the Whoop BLE-RE arms race), so never let it become load-bearing.
- **Two existential risks to manage:** incumbent entry (move fast, go deep) and
  Apple platform dependency (stay cross-platform, keep a hardware option).
- **Sequencing:** the *accessible velocity tool* is the wedge that builds moats #1
  and #2 cheaply and passively; **teams** give early, sticky revenue and
  credibility; the *strain platform* is where category-scale value (and strategic
  optionality) lives.
- **Most likely great outcome:** become the lifting-strain layer the recovery-
  wearable category structurally lacks — and therefore the natural acquisition for
  whoever realizes their platform can't see the weight room.

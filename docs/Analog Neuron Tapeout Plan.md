**You:**

I want to test an analog neuromorphic hardware on tiny tape out gf26c. Most neuromorphic hardware uses digital neurons. I want to test using analog neurons.

What is currently established for digital neurons and what is currently established for analog neurons.

I want to try multiple analog neuron designs. I am thinking of having a simple neuron that matches what is established in the digital neuron space.

I also want to look into designs that try to replicate neuron morphology much more accurately. What are all of the different properties that are important to neurons and then how might we model each of these properties with an analog neuron.

I want to achieve two design goals. I want to demonstrate an analog neuron in a much smaller area than a comparable digital neuron and I want to test expanding that analog neuron to be more biologically accurate. The tiny tap out should probably also include a digital neuron.

* * *

**ChatGPT:**

# Analog neuromorphic computing on GF 26C: research and tapeout proposal

I think the strongest approach is to build a **small neuromorphic test chip containing several analog neuron architectures alongside a digital reference neuron**, then characterize their silicon area, energy consumption, computational behavior, and biological fidelity.

Your two objectives are related, but they should be evaluated independently:

1. **Hardware efficiency:** Can an analog neuron reproduce the behavior of a conventional digital spiking neuron using substantially less silicon area and energy?
2. **Biological fidelity:** Can we exploit analog circuitry to reproduce neural dynamics that would be expensive to implement digitally, including dendritic computation, ion-channel dynamics, adaptation, and compartmental morphology?

There is an important distinction here: a neuron that reproduces the mathematical behavior of a biological neuron is not necessarily a good simulation of its morphology. We should investigate both.

I'd organize the project around three levels of biological complexity.

PROPOSED DESIGN PROGRESSION

**Level 1 — Point neuron** · (Baseline)

Leaky integrate-and-fire, threshold, reset, refractory period, spike output

Input

LIF

neuron

---

**Level 2 — Biophysically enriched point neuron**

Adaptation, conductance-based synapses, nonlinear excitability, bursting, and multiple time constants

Membrane

+ adaptation

+ ion currents

---

**Level 3 — Morphologically structured neuron**

Multiple dendritic compartments, axial coupling, local nonlinearities, and somatic integration

Axial

coupling

Soma

The key research question is whether the efficiency advantage survives as we move from Level 1 to Level 3.

We should also distinguish **neuron core area** from **complete system area**. Analog neurons can be extremely compact, but their apparent advantage can disappear once we account for synaptic storage, programmable parameters, spike routing, bias generators, and analog-to-digital interfaces.

## 1. What is established in digital and analog neuromorphic hardware?

One important finding from the literature is that **analog spiking neurons are already a well-established research field**. They are not as commercially prominent as digital neuromorphic processors, but several major research systems use analog neuron dynamics.

### Established architectures

| System | Implementation | Neuron model | Why it matters |
| --- | --- | --- | --- |
| > Interactive content unavailable: Entity | Digital | Configurable integrate-and-fire | Large-scale, compact digital spiking architecture |
| > Interactive content unavailable: Entity | Digital | Programmable state-based spiking neurons | Flexible neuron dynamics and event-driven execution |
| > Interactive content unavailable: Entity | Digital | Software-programmable neuron models | Flexibility and shared computation |
| > Interactive content unavailable: Entity | Analog + digital | Adaptive exponential integrate-and-fire | Strong precedent for analog dynamics with digital control |
| > Interactive content unavailable: Entity | Analog + digital | Configurable spiking neurons and synapses | Subthreshold, low-power circuits |
| > Interactive content unavailable: Entity | Analog + digital | Biophysically inspired point neurons | Efficient large-scale neural simulation |

Sources: neuromorphic architecture reviews and comparative specifications. 

[PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6287454/?utm_source=chatgpt.com) · [Oxford Academic](https://academic.oup.com/view-large/447942770?utm_source=chatgpt.com) · [Nature](https://www.nature.com/articles/s41467-024-44723-3.pdf?utm_source=chatgpt.com)

![A Look at Loihi 2 - Intel - Neuromorphic Chip - Open Neuromorphic](https://images.openai.com/static-rsc-4/tOYsr4GhPdS84lVm97cA3Y11y0LZcrFdc_Ysqojqf66aBf9k73Xccu5FuOGIDWqUybMX6eHbAkVQvVI2wws4EPlhKq2s-ub4apEhAv3y9v6yyNjL6VMuxobQzleEWQJos0P_ZEqZ2DrFwC4vgdHyQFlenFgNyos0H7zDyYje3Yw?purpose=inline)

Digital approach

Loihi 2 — digital state updates and event routing

![Visual material](https://images.openai.com/static-rsc-4/-MbH7t55dreCMN4hUXr4prHKAZGL-VAI8YHk0SJSPFCXvZ17GM-muzLAZ14CHsra5RoCExU5_7ciIgQ2VhTwoEibXaUYSpUBOT7ETIF3CMbNFN0e3D94dN4BlZmCwPG3NWLcorRxXJvmZwGe19-VOR5X-HRs72xDBzyWnm4wZoI?purpose=inline)

Mixed-signal approach

BrainScaleS-2 — physical analog neuron dynamics

The literature already reports impressive efficiency for analog neuromorphic systems, including accelerated simulation and very low energy per event. However, published neuron-area and energy figures often include different amounts of synaptic and communication circuitry. They cannot be used as direct evidence that an individual analog neuron is smaller than a particular digital neuron. 

[PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6287454/?utm_source=chatgpt.com) · [Nature](https://www.nature.com/articles/s41467-024-44723-3.pdf?utm_source=chatgpt.com)

### How digital neurons work

Most digital neuromorphic designs implement a discrete-time approximation of a neuron model. For a leaky integrate-and-fire (LIF) neuron:

$$
V_{t+1}=\alpha V_t+(1-\alpha)V_{\mathrm{rest}}+kI_t
$$

If 

$$
V_{t+1}
$$

 crosses a threshold, the neuron emits a spike and resets.

The core requires some combination of a state register, arithmetic, threshold comparison, reset logic, and control circuitry.

Importantly, a digital implementation doesn't necessarily give each neuron its own arithmetic unit. A single arithmetic pipeline can update many virtual neurons, which is why **we should compare both dedicated and time-multiplexed digital designs**.

### How analog neurons work

An analog LIF neuron can implement the corresponding continuous-time equation directly:

$$
C_m\frac{dV_m}{dt}
=
I_{\mathrm{in}}-g_L(V_m-E_L)
$$

The circuit can be constructed using:

- A capacitor to store membrane voltage.
- A transistor-based leakage path.
- A comparator or regenerative threshold circuit.
- A reset transistor.
- A spike pulse generator.

The physical circuit performs integration and leakage continuously, rather than executing numerical updates.

This is where your proposed area advantage could originate: **the capacitor voltage is already the neuron state, and the transistors themselves implement the differential equation.**

### Where each approach wins

| Criterion | Digital | Analog |
| --- | --- | --- |
| Numerical reproducibility | Excellent | Limited by mismatch and noise |
| Very compact dedicated LIF | More circuitry | Potential advantage |
| Shared simulation of thousands of neurons | Strong | Requires replicated physical state or multiplexing |
| Complex differential equations | More arithmetic | Potentially efficient if circuit structure matches equations |
| Biological variability | Explicitly programmed | Naturally present, but not necessarily biologically realistic |
| Reconfigurability | Excellent | Depends on bias and circuit design |
| Technology portability | Relatively straightforward | Requires substantial process-specific redesign |
| Fine-grained internal measurement | Readable state registers | Requires analog instrumentation |
| Scaling with smaller CMOS nodes | Generally favorable | Capacitor and analog headroom limitations |

My initial hypothesis is that the largest advantage will appear in compact, continuously operating neurons with relatively few parameters, while digital implementations will remain stronger when extensive programmability or high-precision reproducibility is required.

---

## 2. What makes a biological neuron biologically accurate?

I would divide biological fidelity into four distinct dimensions: membrane electrophysiology, spatial morphology, synaptic behavior, and slower adaptive processes.

These are not interchangeable. A neuron can reproduce realistic action potentials without having realistic dendrites, or reproduce dendritic integration while using simplified spikes.

The following is a practical feature inventory for your hardware project.

| Biological property | Importance | Possible analog implementation |
| --- | --- | --- |
| Membrane capacitance | Essential | Physical capacitor |
| Resting potential | Essential | Bias/reference voltage |
| Membrane leakage | Essential | MOS conductance |
| Spike threshold | Essential | Comparator or regenerative feedback |
| Reset and refractory period | Essential | Reset switch and timing circuit |
| Variable threshold | High | Dynamic bias with slow state capacitor |
| Spike-frequency adaptation | High | Slow feedback current |
| Nonlinear spike initiation | High | Exponential or regenerative transistor current |
| Sodium-channel activation | High for waveform fidelity | Fast voltage-dependent conductance |
| Potassium-channel activation | High for waveform fidelity | Delayed feedback conductance |
| Channel inactivation | High | Slow gating-state circuit |
| Bursting | High for some neuron classes | Coupled fast/slow feedback loops |
| Excitatory/inhibitory synapses | Essential for networks | Signed or conductance-based current injection |
| Synaptic decay | High | RC or log-domain filter |
| Synaptic plasticity | Network-dependent | Local analog state or digital weight storage |
| Dendritic cable propagation | Essential for morphology | Coupled RC compartments |
| Dendritic attenuation | Essential for morphology | Axial resistors and membrane leakage |
| Dendritic nonlinearities | High | Local threshold or conductance circuits |
| Backpropagating action potentials | High for detailed dendritic models | Active compartment coupling |
| Calcium dynamics | High for plasticity and bursting | Slow integrator with nonlinear feedback |
| Neuromodulation | Specialized | Programmable bias modulation |
| Stochastic ion-channel gating | Specialized | Noise-driven or stochastic switching circuits |
| Axonal conduction delays | Network-dependent | Delay circuits or event timing |
| Long-term biochemical processes | Specialized | Additional slow state variables |

The highest-priority additions beyond LIF are, in my view, **adaptation, nonlinear conductances, dendritic compartments, and conductance-based synapses**.

These introduce qualitatively new neural behaviors without immediately requiring a complete molecular simulation.

## 3. Candidate analog neuron designs

I would evaluate five analog architectures, but probably fabricate only three or four in the first tapeout.

![55 nm CMOS Mixed-Signal Neuromorphic Circuits for Constructing Energy-Efficient Reconfigurable SNNs](https://images.openai.com/static-rsc-4/wUtAgE-nvcq0RdzmXMlIMp_wRsFBJJGN1wWKKHN32B4KdvUlSox2k8qvYTpEfuLQ7qAUO03cP5Ao-4c7bphxf8PtfF9VXHSarrmaexz4Bgtf-uaOaFRWxukLR72wKLgj5VocfwN31s2tbHZr6y_P-gZu3-puyp2O9mC6th4EG98?purpose=inline) · **A. Minimal analog LIF**

One membrane state, leakage, threshold, and reset.

This is the most important design for demonstrating the smallest practical neuron. It should match the digital reference as closely as possible.

---

![Firing patterns in the adaptive exponential integrate-and-fire model | Biological Cybernetics | Springer Nature Link](https://images.openai.com/static-rsc-4/Bvzkf-E_3zHl3At-ifQy683ixjes97DqNg4bht9OmSnl1CuBUjrh-pjc_0dim07MGEP1yxV3usSU0iBwxPwPTD1M2ajYjx_D4kOFVcwDxRvKfPOQknAffoTrP4ByExI7qNl0kZbwqeveqknhJ6WMRfw_D7JqVuYkFhj0fc7blB0?purpose=inline) · **B. Adaptive exponential integrate-and-fire (AdEx)**

Adds an exponential spike-initiation term and an adaptation state.

Can reproduce regular spiking, adaptation, and some bursting behaviors with relatively few state variables.

---

![Biological/Electronic Equivalence — Hodgkin Huxley Tutorial 0.2.0 documentation](https://images.openai.com/static-rsc-4/eZFQA0SnIyxmL3Eb3vESQbC9qu0arCmLmqfb1sTEoTPuWdJP7kiCig0-IiMFMF5aDtvePO6pkKKnZUmVruVzGgt9q21pIX4EaGmwhjIKaLOTJXTULXCjVo-LHn_mqbrtxDCSEqYM6p_lLOwlbwK2VxKlNMUhH1k6yk9M0hpDX3g?purpose=inline) · **C. Conductance-based Hodgkin–Huxley-inspired neuron**

Models fast sodium and delayed potassium currents.

A much better test of biologically realistic spike waveforms and refractory behavior, although the nonlinear gating circuits will increase complexity.

---

![Compartmental Models in Neurosim](https://images.openai.com/static-rsc-4/3pZ8Qs5hTxVRPmWXutWhpHDcKYwEuD34KF1C-hJHexnMzF1wIg7mRBuDnbm7Tgy-WjOQr7I9MCBgi4o3if3jFGKVwfaPCw7-M0wMP_ApHlSNSbmBVd_5B9_tiG_dBTDACkUTGP7iOHozYgmqMsL0RZS0WF9D7l14EJhHSZXp5PA?purpose=inline) · **D. Passive multicompartment neuron**

Multiple membrane capacitors connected through axial conductances.

Tests dendritic propagation, attenuation, and spatial integration. This is the cleanest first experiment in neuron morphology.

---

![Frontiers | Can NMDA Spikes Dictate Computations of Local Networks and Behavior?](https://images.openai.com/static-rsc-4/XZGPUgNnj7Y8bb3_ZB4rMWwSJXDcnc2xGyK6VWxe3zP54YZSG9bOYhJsIKhpSW6vgJ5JYoun3IH7o3q45nDDwoCUUj49Rh8t8ftB_e6Gv98SvE90NZveEyzYUhLvHM_dSZLNxwyhbFQ9eIoaQIHnP99eaWxwfHVcrYjWGZEMtNk?purpose=inline) · **E. Active dendritic neuron**

Extends the multicompartment model with local nonlinear currents, potentially NMDA-like plateau responses and dendritic spikes.

Most biologically interesting, but also the highest verification risk.

For the first chip, I would prioritize A, B, D, and a limited version of E, with C as a possible alternative to E depending on available area.

A full Hodgkin–Huxley implementation is not necessarily the best first silicon target. Its gating variables, nonlinear functions, and parameter sensitivity could consume substantial area while making validation harder.

## 4. A morphology-first analog architecture

For biological realism, I think the most promising architecture is a **modular compartment circuit**, rather than a single increasingly complicated neuron.

Each compartment represents a small region of the neuron's membrane. Compartments connect electrically through conductances that represent the intracellular axial pathway.

A compartment can be described by:

$$
C_i\frac{dV_i}{dt}
=
I_{\mathrm{syn},i}
-I_{\mathrm{ion},i}
-g_{L,i}(V_i-E_{L,i})
+\sum_j g_{ij}(V_j-V_i)
$$

The final term is particularly important: it allows electrical signals to propagate between compartments.

Example: three-compartment neuron

Dendrite 1

C

g

Dendrite 2

C

g

Soma

C

g

Axial

Axial

Synaptic input

Synaptic input

Spike output

Each compartment stores its own membrane state

Conceptual architecture, not a transistor-level schematic. Axial coupling is implemented using conductance circuits, not necessarily physical resistors.

### Why this is interesting

A digital multicompartment simulation needs to update each compartment and calculate the currents between them. An analog circuit can potentially let those currents flow continuously.

That means adding a dendritic compartment could be as simple as adding a capacitor, leakage circuit, and axial coupling circuit.

The difficulty is that **accurate time constants and conductances may require capacitors or resistors much larger than the active transistor circuitry**.

This creates an important design tradeoff.

For example, suppose we use:

$$
C=1\ \mathrm{pF}, \qquad \tau=10\ \mathrm{ms}
$$

Then:

$$
g=\frac{C}{\tau}=100\ \mathrm{pS}
$$

This corresponds to an effective resistance of 10 GΩ. A literal integrated resistor of that magnitude is generally impractical. Instead, we would use a very small transistor current or a specialized pseudo-resistor circuit.

Subthreshold MOS circuits are especially relevant here, but leakage, temperature sensitivity, and transistor mismatch become critical.

We could also deliberately accelerate the biological timescale, allowing larger currents and easier measurement. BrainScaleS-2 demonstrates that accelerated analog neuron dynamics are a viable architectural choice. 

[Nature](https://www.nature.com/articles/s41467-024-44723-3.pdf?utm_source=chatgpt.com)

### A particularly useful experiment

Build two versions of the same multicompartment neuron:

- **Passive dendrites:** RC compartments with linear axial coupling.
- **Active dendrites:** The same topology, but with a local regenerative conductance in one dendritic compartment.

Then apply identical input patterns.

The passive neuron should exhibit graded spatial summation and attenuation. The active neuron may show a nonlinear response, such as a local dendritic spike or plateau, once a threshold is crossed.

That would demonstrate a meaningful biological capability beyond conventional LIF, rather than simply producing more elaborate somatic spikes.

---

## 5. What can we actually fit on Tiny Tapeout GF26c?

(Open for submission) · As of November 3, 2026

Shuttle

**Tiny Tapeout GF26c** · Deadline

**December 7, 2026**

---

Process

**GF180MCU, 180 nm**

Expected chips

**May 12, 2027**

Dates from the official shuttle schedule. 

[Chip Maker](https://www.tinytapeout.com/chips/?utm_source=chatgpt.com)

[Official shuttle schedule](https://www.tinytapeout.com/chips/?utm_source=chatgpt.com)

GF180MCU is a reasonable process for analog experimentation. Its documented device options include resistors, MIM capacitors, and analog layout guidance. Availability of particular optional devices and layers must be checked against the actual shuttle-supported PDK and rules. 

[GlobalFoundries GF180MCU PDK documentation](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/Design_Manual.html?utm_source=chatgpt.com)

There is an important practical issue: Tiny Tapeout's general analog documentation currently emphasizes SKY130 and IHP templates, although previous GF180 shuttles have carried analog experiments. We should confirm the **GF26c-specific analog submission template, supply configuration, tile sizes, pin pricing, and signoff requirements** before committing to a floorplan. 

[Chip Maker](https://tinytapeout.com/specs/analog/?utm_source=chatgpt.com) · [Chip Maker](https://tinytapeout.com/chips/ttgf0p3/tt_um_analog_factory_test?utm_source=chatgpt.com) · [Chip Maker](https://tinytapeout.com/chips/ttgf0p3/tt_um_algofoogle_gf_analog?utm_source=chatgpt.com)

### Proposed chip layout

Conceptual test-chip floorplan

Shared control, bias and measurement

Analog LIF array

Area + mismatch tests

Digital LIF

Matched reference

AdEx neuron

Adaptive dynamics

Dendritic neuron

3–4 compartments

Input selection · spike counters · analog probes

Illustrative allocation only. Actual proportions and number of neurons require PDK-based placement and layout.

I would include a small array of identical minimal analog neurons, not just one. That lets us measure transistor mismatch and neuron-to-neuron variability on real silicon.

For the digital reference, I would use a dedicated 8–12-bit fixed-point LIF implementation with the same input and spike-output semantics as the analog design. An additional time-multiplexed digital baseline can be synthesized off-chip if there is insufficient area.

**One major caution:** a GF180MCU digital reference is a fair process-matched comparison, but it will not by itself establish that analog is more area-efficient than modern 7–28 nm digital neuromorphic processors.

## 6. How to measure whether analog is actually better

I would structure the experiments around four questions.

| Experiment | Measurements | What it establishes |
| --- | --- | --- |
| Area efficiency | Physical neuron area, transistor count, capacitor area, shared overhead | Analog vs digital silicon efficiency |
| Energy efficiency | Idle power, energy per spike, energy per simulated second | Whether analog is actually lower-power |
| Functional accuracy | Spike timing, firing-rate curves, refractory behavior, membrane traces | Whether analog matches the reference model |
| Biological fidelity | Adaptation, bursting, dendritic attenuation, nonlinear integration | Whether added analog complexity produces useful behavior |

For area, report both:

$$
A_{\mathrm{core}}
$$

and

$$
A_{\mathrm{effective}}
=
A_{\mathrm{core}}
+
\frac{A_{\mathrm{shared}}}{N}
$$

where 

$$
N
$$

 is the number of neurons sharing the infrastructure.

For energy, distinguish the energy of producing a spike from the energy required to maintain membrane dynamics between spikes. Analog neurons may consume continuous bias current even when they are not spiking.

For accuracy, I would compare the measured hardware with a reference numerical simulation using the same differential equations, rather than comparing only analog against a coarsely discretized digital implementation.

### A useful design exploration tool

The following calculator illustrates how capacitor size, membrane time constant, and operating speed influence the effective conductance required for an analog neuron.

Membrane capacitance · 1.0 pF

> Slider: 1 (0.2–10)

Biological membrane time constant · 10 ms

> Slider: 10 (1–50)

Simulation acceleration · 1×

> Slider: 1 (1–1000)

---

Required conductance

**100.0 pS**

Equivalent resistance

**10.00 GΩ**

Idealized 

$$
g=C/\tau_{\mathrm{hardware}}
$$

, where 

$$
\tau_{\mathrm{hardware}}=\tau_{\mathrm{biological}}/\mathrm{acceleration}
$$

. Actual transistor behavior and parasitics require circuit simulation.

This calculation suggests another valuable experiment: use identical neuron circuitry with several membrane capacitances or bias settings to characterize how scaling time constants affects energy, accuracy, and stability.

## 7. Proposed research and development plan

Given the December 7 deadline, I would keep the first fabrication focused on circuits that can be simulated and verified reliably.

**Phase 1 — Literature and architecture selection**

Identify transistor-level analog neuron designs with published schematics or open-source implementations. Compare LIF, AdEx, conductance-based, and multicompartment approaches. Establish the smallest defensible digital reference.

**Phase 2 — GF180 transistor-level simulation**

Implement candidate circuits in SPICE using the GF180 PDK. Sweep biases, capacitances, temperature, and process corners. Run Monte Carlo mismatch tests where models support them.

**Phase 3 — Layout and digital synthesis**

Produce physical layouts and extract parasitics. Synthesize the digital LIF using GF180 standard cells. Compare actual area rather than transistor counts alone.

**Phase 4 — Measurement infrastructure**

Add configurable inputs, output multiplexing, spike counters, and analog probe points. Make sure the chip can be characterized without requiring expensive laboratory equipment wherever possible.

**Phase 5 — Tapeout verification**

Complete DRC, LVS, extracted simulation, mixed-signal verification, and shuttle-specific checks before submission.

## 8. Where I see the most promising research contribution

There are really three possible contributions here.

**First: a fair analog-versus-digital area comparison.** This is achievable, experimentally clean, and provides a foundation for later research.

**Second: a compact library of analog biological primitives.** Rather than designing one fixed neuron, develop reusable membrane, adaptation, conductance, and dendritic-coupling blocks. That would make future neuron models composable.

**Third: quantifying the marginal hardware cost of biological fidelity.** This is the most interesting research question to me.

For example, we could measure:

$$
\frac{\Delta A}{\Delta \text{biological capability}}
$$

Not as a single universal numerical score, but by measuring how much additional area is required to reproduce each new behavior: adaptation, bursting, dendritic integration, active dendritic spikes, and so on.

That could reveal whether analog hardware has a particularly strong advantage when modeling more realistic neurons, rather than merely implementing small LIF neurons.

I would also avoid assuming that detailed morphology is automatically more useful. A multicompartment model should be judged by whether it reproduces phenomena that a point neuron cannot, such as location-dependent synaptic integration and dendritic nonlinearities.

### Initial tapeout recommendation

I would target these four blocks:

1. **An array of minimal analog LIF neurons**, to test area, energy, and device variability.
2. **One digital LIF neuron**, with matched input/output behavior.
3. **One configurable AdEx neuron**, to test richer point-neuron dynamics.
4. **One three- or four-compartment analog neuron**, preferably with switchable active dendritic circuitry.

I would prioritize a robust measurement interface over fitting an additional complex neuron into the chip.

The immediate next step should be a deeper transistor-level prior-art review, particularly of compact subthreshold neuron circuits, AdEx implementations, and analog multicompartment dendrites. We should then estimate GF180 area and power before selecting the final designs.

That would let us make an evidence-based choice about what can fit on GF26c, while keeping the first tapeout useful even if the most biologically ambitious design proves difficult to fabricate.

* * *

**You:**

Should we also test small networks of neurons or focus on individual neurons. I think we should investigate this if space permits.

We should directly test programmability and reproducibility. We should evaluate what variables are important to program and test how easy or hard they are to program on an analog neuron. We should also test reproducibility across states and separate neurons on the chip.

Should we test both comparator and regenerative feedback. Is one preferred and what is the prior work.

I’m particularly interested in how cheaply we can model the dendrite properties with an analog system vs a digital system. Depending on the space, I don’t think we need an expansive digital replica of the dendrite.

I like your idea of a,b,d with c and e if we have space.

Can you go into more depth on how we might model the dendrite while minimizing board space. I don’t want huge capacitors and resistors.

I like the idea of testing different time scales too. How would this impact the design.

Can you do some ruff estimates on the space each of these neurons would take on the chip and compare that to how much space we have.

* * *

**ChatGPT:**

# Designing the GF26c neuromorphic test chip

I would include a small neuron network if space permits, but I would **prioritize programmability, reproducibility, and compact dendritic computation over network size**.

Your proposed selection of A (LIF), B (AdEx), and D (passive dendrites), with C (conductance-based) and E (active dendrites) as stretch goals, is a good basis for the design.

I would make one architectural change: instead of treating the dendritic neuron as a completely separate circuit, build it from reusable analog compartments. That lets us investigate the area cost of adding biological complexity incrementally.

The key experiments should be:

| Priority | Experiment | Research question |
| --- | --- | --- |
| 1 | Analog LIF vs digital LIF | How much area and energy can analog save? |
| 2 | Comparator vs regenerative threshold | Which spike-generation circuit is smaller, lower-power, and more reproducible? |
| 3 | Programmability | How many parameters can be controlled independently and accurately? |
| 4 | Reproducibility | How much do neurons differ across instances, power cycles, temperature, and bias settings? |
| 5 | Passive dendritic compartments | How cheaply can analog reproduce spatial neural dynamics? |
| 6 | Small network | Can several analog neurons interact reliably? |
| 7 | AdEx and active dendrites | How much additional hardware buys richer biological behavior? |

I would also keep the experiment physically measurable. It is easy to fabricate an analog neuron that spikes; it is considerably harder to prove what its internal membrane states are doing without suitable probe circuitry.

## 1. How much space do we have?

I found a useful GF180-specific reference from the previous GF26b shuttle. The published project dimensions are approximately:

| Tile allocation | Physical dimensions | Gross area |
| --- | --- | --- |
| 1×1 | 350 × 160 µm | 0.056 mm² |
| 1×2 | 350 × 330 µm | 0.116 mm² |
| 2×2 | 710 × 330 µm | 0.234 mm² |
| 3×2 | 1,080 × 330 µm | 0.356 mm² |
| 3×4 | 1,080 × 740 µm | 0.799 mm² |

These are rounded GF26b project-envelope dimensions, not confirmed GF26c analog-template dimensions. 

[wafer.space](https://wafer.space/tinytapeouts/ttgf26b/ws-run2-t26b/index.html?utm_source=chatgpt.com)

Tiny Tapeout's published analog rules require special analog templates and analog-pin allocation. The currently documented template examples are primarily for SKY130 and IHP, so GF26c analog-template support and the actual usable dimensions need confirmation. 

[Chip Maker](https://tinytapeout.com/specs/analog/?utm_source=chatgpt.com)

For initial budgeting, I would assume a **2×2 tile allocation**, about 234,000 µm² gross. This is large enough to justify investigating several circuits, but small enough that large capacitors, routing, and test infrastructure matter.

## 2. Rough silicon-area estimates

These are engineering planning ranges, not measured GF180 layouts. They assume compact transistor-level designs, small capacitors, modest programmability, and no large on-chip DAC per neuron.

| Circuit | Estimated area |
| --- | --- |
| Minimal analog LIF, regenerative | 150–600 µm² |
| Analog LIF, comparator-based | 300–1,200 µm² |
| Analog AdEx | 700–2,500 µm² |
| Passive dendritic compartment | 150–700 µm² |
| Three-compartment passive neuron, including soma | 800–3,000 µm² |
| Active dendritic compartment | 400–1,500 µm² |
| HH-inspired conductance-based soma | 2,000–8,000 µm² |
| Dedicated 8–12-bit digital LIF | 1,000–4,000 µm² |

The digital figure assumes dedicated arithmetic and registers. A time-multiplexed digital design can achieve much lower amortized area per neuron.

The biggest uncertainty in the analog figures is capacitor area.

The GF180 PDK documents MIM capacitor options of approximately 1, 1.5, and 2 fF/µm². The actual GF26c process option must be confirmed. 

[mithro-gf180mcu-pdk.readthedocs.io](https://mithro-gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_6_4.html?utm_source=chatgpt.com)

At 2 fF/µm², the capacitor plate alone occupies:

| Capacitance | Plate area |
| --- | --- |
| 50 fF | 25 µm² |
| 100 fF | 50 µm² |
| 200 fF | 100 µm² |
| 500 fF | 250 µm² |
| 1 pF | 500 µm² |
| 5 pF | 2,500 µm² |

These values exclude capacitor surrounds, contacts, and routing.

**This makes 100–300 fF an attractive initial design range**, provided SPICE simulations show that leakage, noise, charge injection, and parasitic capacitance are acceptable.

One caveat: the documented MIM rules include a 25 µm² minimum plate area for the cited option, so even very small MIM capacitors have a physical lower bound. 

[GlobalFoundries GF180MCU PDK documentation](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_10_4_1.html?utm_source=chatgpt.com)

### Interactive area budget

The following calculator uses illustrative component areas near the middle of the planning ranges. It is intended for exploring possible allocations, not predicting a completed layout.

Tile allocation

- [ ] 1×2

- [ ] 2×2

- [ ] 3×2

- [ ] 3×4

Analog LIF neurons · 12

> Slider: 12 (0–64)

AdEx neurons · 2

> Slider: 2 (0–12)

Three-compartment neurons · 2

> Slider: 2 (0–12)

Digital LIF neurons · 1

> Slider: 1 (0–8)

- [x] Include small network interconnect and synapses

---

Estimated allocated area

**30.4k µm²**

Share of gross tile area

**13.0%**

Includes a nominal 12,000 µm² shared-control allowance. Gross area is not fully usable; placement, routing, power distribution, and analog isolation reduce available capacity. No actual GF26c floorplan has been verified.

The estimates suggest that the **individual neuron circuits are unlikely to be the primary area bottleneck** if we use compact capacitors. Instead, the limiting factors may be programmability, test access, routing, and analog bias generation.

That is encouraging for including a small network.

## 3. How to minimize dendritic area

The main idea is to use **transistors as programmable conductances and small capacitors as local membrane states**.

A passive dendritic compartment needs surprisingly little circuitry:

$$
C_i\dot V_i
=
-g_{L,i}(V_i-E_L)
+\sum_jg_{ij}(V_j-V_i)
+I_{\mathrm{syn},i}
$$

The area cost is determined primarily by how we implement 

$$
C_i
$$

, 

$$
g_L
$$

, and 

$$
g_{ij}
$$

.

### Candidate dendritic circuit architectures

| Architecture | Area potential | Accuracy and tradeoffs |
| --- | --- | --- |
| Small MIM capacitor + MOS conductances | Very good | Simple; small-current mismatch and leakage |
| Subthreshold transconductance coupling | Very good | Compact, programmable, nonlinear at larger voltage differences |
| Switched-capacitor compartments | Good | Accurate charge ratios; clocking and switching artifacts |
| Current-mode/log-domain compartments | Very good | Efficient for certain dynamics; nonlinear state representation |
| Physical resistors + capacitors | Poor for long time constants | Simple and predictable, but large resistances are expensive |
| Fully active HH-style compartments | Expensive | More realistic propagation and spike dynamics |

I would prototype the first three, with a strong preference for the first two.

### Architecture A: MOS-based passive dendrites

V1

C

V2

C

V3

C

g12

g23

Programmable axial conductances

Small capacitors hold local membrane voltages

The difficulty is realizing a bidirectional, approximately linear, extremely small conductance. A single MOS transistor acting as a resistor may be compact, but its conductance varies with terminal voltage and bias.

A more sophisticated transconductor can improve linearity at the cost of more transistors.

I would build two versions of the axial coupling:

- A minimal MOS pseudo-resistor.
- A more controlled transconductance-based coupling element.

Then measure the tradeoff between area and agreement with the passive cable equation.

### Architecture B: Switched-capacitor dendrites

Instead of continuously passing current through an effective resistor, a small coupling capacitor periodically transfers charge between compartments.

The effective conductance scales approximately as:

$$
g_{\mathrm{eq}}\approx C_{\mathrm{switch}}f_{\mathrm{clock}}
$$

For example, a 10 fF switched capacitor clocked at 10 kHz gives an approximate effective conductance of 100 pS.

That is equivalent to 10 GΩ without fabricating a 10 GΩ resistor.

This is attractive because:

- The effective conductance is programmable through clock frequency.
- Capacitor ratios can be relatively reproducible.
- The required physical components can be small.

However, the system is now sampled-data rather than purely continuous-time. Clock feedthrough, switching noise, charge injection, and clock energy matter.

The clock also needs to be sufficiently fast relative to the fastest membrane dynamics.

**This is one of the most valuable architectural comparisons for your chip:** continuous-time subthreshold dendrites versus switched-capacitor dendrites.

### Architecture C: Active dendrites without full ion-channel models

We do not need to reproduce every ion channel to obtain interesting dendritic computation.

Consider adding a local regenerative current:

$$
I_{\mathrm{active}}(V)
=
g_A f(V)(E_A-V)
$$

where 

$$
f(V)
$$

 rises steeply once the compartment reaches a particular voltage.

This could approximate local dendritic excitability using a compact positive-feedback circuit.

A second, slower feedback state could terminate the event and allow plateau-like or bursting dynamics.

That would allow a three-compartment neuron to demonstrate:

- Spatial summation.
- Location-dependent attenuation.
- Nonlinear dendritic thresholds.
- Local dendritic events.
- Interaction between dendritic and somatic excitability.

It would not constitute a detailed NMDA or calcium-channel model without validating the relevant voltage dependence and time constants.

## 4. Comparator versus regenerative-feedback spike generation

Yes, I would test both.

They represent different design philosophies and are particularly suitable for your area-efficiency experiment.

| Property | Comparator threshold | Regenerative feedback |
| --- | --- | --- |
| Basic mechanism | Detect threshold crossing, trigger reset | Positive feedback produces rapid transition |
| Area | Moderate | Potentially smaller |
| Threshold programmability | Relatively straightforward | Often coupled to circuit bias |
| Threshold precision | Better with a carefully designed comparator | Sensitive to device parameters |
| Power | Depends on comparator design | Can be very low, but switching behavior matters |
| Biological spike initiation | Abstract threshold event | More naturally resembles regenerative excitation |
| Reset | Usually explicit | Can be integrated with feedback dynamics |
| Risk | Comparator offset, delay, static current | Hysteresis, unwanted oscillation, sensitivity |

The regenerative approach has substantial prior art. Classical silicon-neuron and axon-hillock circuits exploit positive feedback for spike generation. Indiveri, Chicca, and Douglas demonstrated low-power analog integrate-and-fire arrays with configurable network connectivity and plastic synapses in 2006. 

[PubMed](https://pubmed.ncbi.nlm.nih.gov/16526488/?utm_source=chatgpt.com)

I would not declare one universally preferable. A comparator can be compact if it is a minimal inverter-like threshold detector, while a fully featured regenerative circuit may require additional reset and refractory circuitry.

For the experiment, use the same membrane integrator and input circuit, and swap only the spike-generation block. This isolates the effect of the threshold architecture.

Measure threshold spread, hysteresis, latency, spike width, energy per event, and minimum reliable interspike interval.

## 5. Programmability and reproducibility

This deserves its own test structure, not merely a few configuration pins.

### Which variables should be programmable?

| Parameter | Priority | Proposed implementation |
| --- | --- | --- |
| Input current | Essential | Shared current DAC or externally supplied current |
| Leak conductance | Essential | Bias-controlled MOS conductance |
| Spike threshold | Essential | Reference voltage or threshold bias |
| Reset voltage | High | Programmable reference |
| Refractory period | High | Timing bias or digitally controlled delay |
| Membrane capacitance | High for research | Switchable capacitor bank |
| Adaptation strength | High | Bias-controlled feedback current |
| Adaptation time constant | High | Programmable slow conductance |
| Axial dendritic coupling | Essential for dendrites | MOS bias or switched-capacitor clock |
| Synaptic weight | Essential for networks | Programmable current amplitude or pulse width |
| Synaptic decay | High | Local RC or switched-capacitor time constant |
| Local dendritic threshold | High | Regenerative circuit bias |

I would avoid giving every neuron its own DAC. Instead, use shared analog bias generators and small digital configuration registers.

This creates two useful operating modes:

**Global mode:** All neurons receive identical biases. Differences in behavior reveal mismatch and process variability.

**Individual calibration mode:** Each neuron receives a limited trim adjustment. Differences remaining after calibration reveal the achievable reproducibility.

That directly tests how much programming hardware is needed to overcome analog variability.

### Reproducibility experiments

I would distinguish four kinds of reproducibility:

1. **Repeated trials:** Reset the same neuron and apply an identical stimulus many times.
2. **Across neurons:** Apply identical stimuli to nominally identical neuron instances.
3. **Across operating conditions:** Change supply voltage, temperature, and acceleration factor.
4. **Across power cycles:** Power down and restart the chip, reload settings, and repeat measurements.

For each, measure firing-rate curves, threshold, spike timing, adaptation dynamics, and dendritic response.

An important distinction: deterministic reproducibility is not the same as biological realism. Biological neurons exhibit stochasticity, but uncontrolled transistor mismatch is not automatically a realistic model of biological variability.

### Measuring programmability itself

I would quantify programming quality using:

- Effective number of distinct, reliably attainable parameter settings.
- Monotonicity of parameter changes.
- Parameter cross-coupling.
- Calibration time.
- Additional circuit area per programmable parameter.
- Retention and repeatability of settings.

For example, changing a leak-bias voltage may alter both the effective membrane time constant and the resting potential. That means two parameters that are independent in the mathematical model may not be independent in the hardware.

This is precisely the kind of limitation worth measuring.

## 6. Testing different time scales

I would include three operating regimes, with the same neuron topology wherever possible.

| Regime | Approximate acceleration | Main purpose |
| --- | --- | --- |
| Biological real time | 1× | Direct comparison with neural physiology |
| Accelerated | 10–100× | Lower sensitivity to very small leakage currents |
| Highly accelerated | 1,000× | Test speed limits and energy/performance scaling |

For a biological membrane time constant of 10 ms, the corresponding hardware time constants would be 10 ms, 100–1,000 µs, and 10 µs.

Because

$$
\tau=\frac{C}{g},
$$

we can change time scale by adjusting capacitance, conductance, or both.

I would favor **programmable conductance with fixed capacitance** for the primary experiment. It is easier to vary continuously, and it avoids the area of large capacitor banks.

However, increasing conductance also changes current levels, energy consumption, and potentially the circuit's linearity. Acceleration is not necessarily free.

One subtle issue is that accelerating the membrane without accelerating synapses, adaptation, and refractory dynamics by the same factor changes the neuron's behavior. Therefore, the design should support coordinated scaling of all relevant time constants.

I would test whether a neuron preserves its dimensionless response properties under acceleration. For example, if an input spike train is accelerated 100×, does the membrane trajectory remain the same after rescaling time?

This would be a much stronger result than simply showing that the neuron can spike faster.

## 7. Should we include a network?

Yes. I would add a small, configurable network of four to eight LIF neurons, preferably reusing neurons from the mismatch-test array.

That way, the network does not require a second complete set of neuron cores.

I would test three configurations:

**Feedforward chain**

Tests spike transmission, synaptic delay, and accumulated timing variability. · 1

2

3

---

**Excitatory/inhibitory pair**

Tests competition, feedback, and stability under programmable synaptic strengths. · E

I

---

**Recurrent network**

Tests whether small analog circuits can support stable, repeatable population dynamics.

I would use a small digitally configured crossbar or selection network to connect the neurons, with analog synaptic-current injection.

A fully programmable synaptic matrix is not necessary. Four neurons with a handful of configurable connections are enough to establish whether the analog neurons work together.

The network should be a stretch goal if verification time becomes limited. A malfunctioning network must not prevent us from independently testing the neuron cores.

## 8. Proposed 2×2 tile allocation

Using the approximate 234,000 µm² GF26b envelope as a planning reference, I would reserve generous space for the measurement infrastructure and physical-layout overhead.

Illustrative area allocation

LIF array + comparator tests · 12k µm²

AdEx + passive dendrites · 12k µm²

Digital reference · 4k µm²

Small network · 10k µm²

Bias, programming and test · 25k µm²

Routing, isolation, reserve · 171k µm²

Conceptual budget, not a floorplan. The large reserve is intentional because GF26c analog constraints, power structures, and final layout overhead are not yet established.

This allocation suggests that we might fit more neurons than initially proposed. But I would not fill the remaining area until we have laid out at least one complete LIF neuron, one dendritic compartment, and the shared programming infrastructure.

A 2×2 tile could potentially accommodate:

- 8–16 minimal analog LIF neurons.
- 2 comparator-based LIF variants.
- 2 AdEx neurons.
- 2 passive multicompartment neurons.
- 1 dedicated digital LIF.
- A four-neuron configurable network.
- Shared bias, programming, and measurement circuits.

That is a plausible target, not yet a verified capacity claim.

The main risk is not transistor count alone. It is whether the GF26c shuttle provides the analog access and layout support needed for reliable characterization.

## 9. Prior work worth studying first

I would start with these sources:

- [Indiveri, Chicca & Douglas (2006): Low-power spiking neurons and plastic synapses](https://pubmed.ncbi.nlm.nih.gov/16526488/?utm_source=chatgpt.com) — A foundational mixed-signal neuron-array architecture with programmable network connectivity.
- [Tiny Tapeout analog specifications](https://tinytapeout.com/specs/analog/?utm_source=chatgpt.com) — Pin limitations, template rules, and analog submission requirements.
- [GF180 MIM capacitor electrical specifications](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_6_4.html?utm_source=chatgpt.com) — Crucial for estimating compartment area.
- [GF26b physical tile dimensions and density](https://wafer.space/tinytapeouts/ttgf26b/ws-run2-t26b/index.html?utm_source=chatgpt.com) — A useful starting point for budgeting the GF26c project.

### My recommended next engineering decision

Before designing all the neurons, I would create **three transistor-level benchmark cells** in the GF180 PDK:

1. A minimal regenerative LIF.
2. A comparator-based LIF using the same membrane circuit.
3. A passive dendritic compartment with programmable MOS coupling, plus a switched-capacitor variant.

These three cells will answer most of the questions that currently determine the chip architecture: achievable area, useful capacitance range, parameter independence, mismatch, and viable time scales.

If the passive compartment proves sufficiently small, I would prioritize adding more dendritic compartments over adding a full HH soma. That aligns particularly well with your goal of investigating whether analog hardware can make morphologically detailed neuron simulation substantially cheaper than digital simulation.

The first concrete milestone should be **post-layout area and extracted-SPICE results for these three benchmark architectures**. Those measurements will turn the current rough estimates into a defensible GF26c floorplan.

* * *

**You:**

Let’s target the 1x2 chip if we can. We have 2 analog pins available.

We can use extra space to test different versions of the core neurons. I am interested in testing the various architectures at different speeds.

Should we also have a group with internal probes and a group without as a control.

* * *

**ChatGPT:**

# Revised GF26c plan: 1×2 tile, two analog pins

I would target the **1×2 tile (~116,000 µm² gross, pending confirmation of the GF26c usable layout)** and organize the chip as a set of controlled experiments rather than trying to fit the maximum number of neurons.

And yes, I strongly support including **probed and unprobed versions of the same neuron**. Analog measurement circuitry can change the behavior being measured, especially when membrane capacitances are only 50–300 fF.

However, I would distinguish three kinds of test structures:

1. **Uninstrumented reference:** A neuron with no internal probe wiring or attached measurement circuits.
2. **Probe-ready neuron:** The same neuron with internal nodes routed to a selectable, buffered measurement circuit.
3. **Dedicated characterization neuron:** A neuron with additional observability, such as membrane voltage, adaptation voltage, and dendritic compartment voltages.

The first two give us a controlled experiment in measurement-induced perturbation. The third makes it easier to understand why the neuron behaves as it does.

## 1. How to use the two analog pins

I would allocate the pins as follows:

| Pin | Function | Purpose |
| --- | --- | --- |
| Analog 0 | Programmable stimulus or bias input | Inject test signals or supply an externally controlled bias |
| Analog 1 | Buffered analog monitor output | Observe membrane voltage, adaptation state, or dendritic voltage |

The analog monitor should use a low-input-capacitance buffer followed by an analog multiplexer. We should avoid connecting a large external load directly to a membrane capacitor.

An alternative is to use both pins as measurement outputs and generate inputs on-chip, which may be better for simultaneous dendritic measurements. I would make the final choice after confirming the shuttle's pin circuitry and available digital I/O.

**Important:** two analog pins do not mean we can only measure two internal variables. We can multiplex many internal nodes to one output, provided we account for loading, settling time, and switching artifacts.

For dynamic signals, though, multiplexing is not equivalent to simultaneous measurement. That matters for dendritic propagation experiments.

## 2. Should we test different neuron architectures at different speeds?

Yes, but I would avoid fabricating a separate neuron for every speed.

Instead, make time constants programmable over several orders of magnitude and test the same physical circuit at different speeds.

For a first version, target three nominal regimes:

| Regime | Membrane time constant | Acceleration relative to 10 ms |
| --- | --- | --- |
| Biological | 10 ms | 1× |
| Intermediate | 100 µs | 100× |
| Fast | 10 µs | 1,000× |

These are target values, not guaranteed achievable ranges.

For a 100 fF membrane capacitor:

$$
g=C/\tau
$$

| Time constant | Required conductance |
| --- | --- |
| 10 ms | 10 pS |
| 100 µs | 1 nS |
| 10 µs | 10 nS |

The slow regime is particularly challenging because parasitic leakage may be comparable to the intended membrane current.

That gives us a meaningful reason to include a few different physical implementations.

For example, one neuron could use a 100 fF capacitor and programmable conductance, while another uses a 300 fF capacitor. We could then compare achievable time constants, noise, power, and area.

I would aim for **programmable speed within each architecture**, and only duplicate an architecture when the duplicate tests a distinct physical design choice.

## 3. Proposed neuron test matrix

I would make the minimal LIF the most thoroughly characterized architecture, followed by the dendritic neuron and AdEx.

| Design | Quantity | Probe configuration | Speed control |
| --- | --- | --- | --- |
| Regenerative LIF | 4 | 2 probed, 2 unprobed | Programmable |
| Comparator LIF | 4 | 2 probed, 2 unprobed | Programmable |
| AdEx | 2 | 1 probed, 1 unprobed | Programmable |
| Passive 3-compartment neuron | 2 | 1 probed, 1 unprobed | Programmable |
| Digital LIF | 1 | Digital state readout | Programmable |
| Small network | Reuse 4 LIFs | Digital spike outputs | Programmable |

This is an initial target of 13 physical neurons, including the digital reference. The network reuses existing neurons rather than requiring additional cores.

I would consider a switched-capacitor dendritic variant if area allows. It is potentially more scientifically valuable than adding another identical neuron.

### One important improvement to the control experiment

We should distinguish *probe presence* from *probe activation*.

For the probe-ready neuron, test:

- Probe circuit disabled.
- Probe circuit enabled but output disconnected.
- Probe connected to the analog output.
- Probe connected while the output is being measured.

That allows us to separate the effects of probe input capacitance, buffer bias, output loading, and measurement activity.

An unprobed neuron is still needed as a physical control. Simply disabling a buffer does not eliminate its parasitic capacitance.

**Proposed paired test structures**

LIF core

Unprobed

LIF core

Probe-ready

Buffer

Analog out

Input

Input

Spike output

Spike output

Both neuron cores should use matched layouts and common bias conditions. Only the intentional probe circuitry and routing should differ.

For reproducibility, we should also compare the same neuron across repeated trials, not just different neurons. Four copies of each LIF architecture give us a useful first look at mismatch, but not enough for a statistically strong characterization of manufacturing variability.

## 4. Revised 1×2 area budget

I would treat 116,000 µm² as a gross planning envelope, not available circuit area. The earlier core estimates were optimistic and must be checked against real GF180 layouts.

Provisional area allocation

| Eight analog LIFs | 8,000 µm² |
| --- | --- |
| Two AdEx neurons | 5,000 µm² |
| Two dendritic neurons | 8,000 µm² |
| Digital LIF reference | 4,000 µm² |
| Network synapses and routing | 8,000 µm² |
| Bias, configuration, probing | 25,000 µm² |
| Physical overhead and contingency | 58,000 µm² |
| **Total** | **116,000 µm²** |

Illustrative targets, not validated layout estimates. The overhead allowance includes space that may be lost to routing, power, isolation, and template constraints.

Gross allocation · 116,000 µm²

About half the gross envelope is reserved for physical overhead and contingency. This does not imply that all remaining space will be placeable.

If the layout becomes tight, I would remove features in this order: extra network connectivity, duplicate AdEx, duplicate dendritic neuron, then excess LIF replicas. I would preserve the two threshold architectures, at least one dendritic experiment, the digital baseline, and probe controls.

## 5. Two refinements I would make before implementation

**First, share bias generation but retain independent trimming.** A shared bias system saves substantial area, but we should reserve a few digital trim bits for selected neurons. Otherwise, differences between nominally identical neurons may be impossible to correct or characterize independently.

**Second, include a calibration and probe-test structure.** A known small capacitor or test node connected to the same buffer and analog-output path would help quantify measurement loading and bandwidth. This is particularly valuable for the accelerated 10 µs regime, where a slow output buffer could obscure the dynamics.

For the two analog pins, I would initially favor one external stimulus input and one buffered measurement output, with digital configuration and spike counting. We should verify that the shuttle's analog pins support the intended voltage ranges and direction before finalizing the design.

## 6. Final design priorities

The 1×2 chip should answer three central questions:

1. **How compact can we make a functional, programmable analog neuron relative to a dedicated digital neuron?**
2. **How much biological complexity can we add through analog dendritic compartments, and how does that cost scale?**
3. **How stable and reproducible are these circuits across time scales, neurons, and measurement configurations?**

I would make the core speed range a design target rather than fabricate separate fixed-speed replicas immediately. Then use a few intentionally different capacitor or conductance implementations to test whether one architecture scales better than another.

The most valuable next step is to lay out a minimal regenerative LIF, a comparator LIF, and one passive dendritic compartment in GF180. Their actual area, leakage, parasitics, and achievable time constants will tell us whether the full test matrix fits the 1×2 allocation.

**One question that materially affects the design:** Do you want the chip to operate at biological real-time speeds as a firm requirement, or would you accept an accelerated-only implementation if that allows significantly smaller and more reproducible dendritic compartments?

* * *

**You:**

I think your point about testing different capacitance values is more important than you give it credit for. I would be tempted to partially add it to the matrix.

Also add the switched capacitor dendritic variant.

I think reproducibility is important even if we don’t have a large sample size.

Can you make an updated prediction of area usage and a priority list for what to cut if we run out of space.

* * *

**ChatGPT:**

# Updated GF26c 1×2 design and area budget

I agree that **physical capacitance should be an experimental variable**, not just a parameter we change in simulation. It affects neuron area, leakage sensitivity, noise, achievable time constants, power, and measurement loading. It may also determine whether a particular analog architecture is practical at biological timescales.

I would therefore add a capacitance sweep to the LIF test matrix, and add a switched-capacitor dendritic variant alongside the continuous-time dendritic design.

My revised target is **approximately 65,000–75,000 µm² of placed circuit and infrastructure within the nominal 116,000 µm² 1×2 envelope**, leaving the remainder for physical constraints and contingency. This is a planning target, not a verified GF180 layout result.

## 1. Revised experimental matrix

| Architecture | Quantity | Configuration |
| --- | --- | --- |
| Regenerative LIF | 6 | 3 capacitances × probed/unprobed |
| Comparator LIF | 4 | 2 capacitances × probed/unprobed |
| AdEx | 2 | Probed/unprobed, programmable adaptation |
| Continuous-time dendritic neuron | 2 | Probed/unprobed, 3 compartments |
| Switched-capacitor dendritic neuron | 1 | 3 compartments, instrumented |
| Digital LIF | 1 | 8–12-bit dedicated digital baseline |
| Network | Reuses 4 LIFs | Configurable feedforward and recurrent connections |

**Total: 16 neuron implementations**, including one digital reference, plus shared network circuitry.

This prioritizes physical capacitance variation in the simpler neurons, where we can isolate its effects most cleanly.

### Proposed capacitance sweep

Small

**50 fF**

Noise / leakage limit

Medium

**200 fF**

Balanced design

Large

**800 fF**

Stability / area cost

These are nominal physical capacitors, not guaranteed total membrane capacitances. At the smallest value, parasitic capacitance may be a substantial fraction of the effective total.

At a nominal MIM density of 2 fF/µm², the capacitor plate areas would be 25, 100, and 400 µm² respectively. At 1 fF/µm², they would double.

I would preserve the same transistor geometry, threshold circuitry, and bias configuration within each architecture. That makes the capacitor sweep interpretable.

The effective membrane time constant is

$$
\tau=\frac{C_{\mathrm{effective}}}{g_{\mathrm{leak}}}.
$$

There are two complementary tests:

- **Fixed conductance:** Vary capacitance and observe changes in time constant, noise, and energy.
- **Matched time constant:** Adjust conductance to compensate for capacitance, then compare accuracy, variability, and power at identical dynamics.

The second is particularly valuable because it isolates the physical implementation cost of capacitance rather than merely observing that larger capacitors produce slower neurons.

## 2. Updated area estimates

I would increase the estimated area for the measurement and programming infrastructure compared with our earlier budget. Supporting 15 analog neurons, several speed regimes, and internal voltage measurements is more demanding than simply generating spikes.

The following estimates are deliberately more conservative than the original minimal-core estimates.

All figures below are preliminary engineering estimates, not GF180 post-layout measurements. They include local routing allowances but exclude the global floorplanning reserve.

| Block | Count | Nominal area | Plausible range |
| --- | --- | --- | --- |
| Regenerative LIF | 6 | 4,800 µm² | 3,000–8,000 |
| Comparator LIF | 4 | 5,200 µm² | 3,200–8,000 |
| AdEx | 2 | 5,000 µm² | 3,000–8,000 |
| Continuous dendritic | 2 | 7,000 µm² | 4,000–12,000 |
| Switched-cap dendritic | 1 | 5,000 µm² | 3,000–9,000 |
| Digital LIF | 1 | 3,500 µm² | 2,000–6,000 |
| Network synapses/interconnect | Shared | 5,000 µm² | 3,000–9,000 |
| Bias and programmability | Shared | 10,000 µm² | 6,000–17,000 |
| Analog probes and multiplexing | Shared | 8,000 µm² | 5,000–14,000 |
| Digital control and test | Shared | 5,000 µm² | 3,000–9,000 |
| **Total before global reserve** |  | **58,500 µm²** | **35,200–100,000** |

This is a wide range because the circuit architecture, capacitor density, number of individually trimmed parameters, and analog buffer design have not been fixed.

For a 1×2 allocation, I would budget another 20,000–30,000 µm² for global routing, isolation, power distribution, placement inefficiency, and contingency. Some of these costs may already be included in the template, so they must be reconciled against its actual usable area rather than simply added to the gross envelope.

Nominal 1×2 area budget

Neuron cores + digital

30.5k µm²

Shared infrastructure

28.0k µm²

Physical reserve

25.0k µm²

Unallocated headroom

32.5k µm²

---

Nominal budget including reserve

**83,500 µm²**

Unallocated headroom

**28.0%**

Assumes a 116,000 µm² gross envelope. This is not a claim that 83,500 µm² of circuitry is physically placeable under the shuttle's actual rules.

My interpretation is that **the full revised matrix is plausible on a 1×2 tile**, but it is not yet safe to commit to every block. In particular, the switched-capacitor implementation, analog probe network, and digital configuration logic could grow substantially.

I would set a provisional target of 60,000 µm² for the implemented circuits, excluding the global reserve, and use the remaining space only after initial layouts establish actual density.

## 3. Capacitance and reproducibility: an improved experiment

I would slightly modify the test matrix to preserve useful replication.

The regenerative LIF group would have six neurons:

| Nominal capacitance | Unprobed | Probe-ready |
| --- | --- | --- |
| 50 fF | R1 | R2 |
| 200 fF | R3 | R4 |
| 800 fF | R5 | R6 |

The comparator group would use 50 fF and 200 fF, each with an unprobed and probe-ready version.

This gives us two independent threshold architectures and lets us compare their behavior at matched capacitance.

There is one statistical limitation: each capacitance/probe combination has only one physical instance. We can measure repeatability within each neuron, but cannot reliably estimate the manufacturing distribution of that exact design.

To improve this without adding much area, I would use some of the unallocated headroom for **additional identical regenerative LIF replicas at 200 fF**.

Four extra unprobed LIF neurons might cost roughly 2,000–4,000 µm². That would give us a small but useful mismatch sample under common bias conditions.

We should randomize or interleave their physical locations rather than place all replicas together. Otherwise, spatial gradients in fabrication or temperature could be confused with random mismatch.

## 4. Switched-capacitor dendrite: what exactly to test

I would implement one three-compartment switched-capacitor dendritic neuron with the same nominal compartment capacitances and coupling topology as the continuous-time dendritic neuron.

The goal is to compare:

| Metric | Continuous-time MOS | Switched capacitor |
| --- | --- | --- |
| Silicon area | Transconductors and capacitors | Switches, capacitors, clock distribution |
| Conductance programmability | Bias current/voltage | Clock frequency and capacitor ratio |
| Reproducibility | Device mismatch and bias drift | Capacitor matching and clock accuracy |
| Noise | Subthreshold and device noise | Sampling and charge-injection noise |
| Energy | Continuous bias current | Dynamic switching power |
| Time-scale control | Bias scaling | Clock scaling |
| Dendritic accuracy | Continuous approximation | Discrete charge transfer |

I would provide at least two clock-frequency settings and ideally a wider programmable range.

For example, with a 10 fF coupling capacitor:

$$
g_{\mathrm{effective}}\approx C_{\mathrm{switch}}f_{\mathrm{clock}}
$$

At 1 kHz, 10 kHz, and 100 kHz, the idealized conductances would be 10 pS, 100 pS, and 1 nS.

This is an attractive way to achieve extremely weak axial coupling without large physical resistors. But the approximation is valid only in the appropriate sampling regime, and the 10 fF capacitor may be too small for a reliable standalone MIM structure under the applicable layout rules. We may need a different capacitor structure or larger values.

I would explicitly test the relationship between clock frequency, effective coupling, noise, and power.

## 5. Priority list: what to cut if area runs out

I would make the cuts in stages, rather than remove entire research objectives at once.

| Cut order | Modification | Estimated area saved | Scientific cost |
| --- | --- | --- | --- |
| 1 | Reduce network connectivity to a fixed chain and E/I pair | 2,000–4,000 µm² | Low |
| 2 | Remove one AdEx duplicate | 1,500–3,000 µm² | Low–moderate |
| 3 | Reduce comparator LIFs from four to two, retaining 200 fF probed/unprobed | 1,600–3,000 µm² | Moderate |
| 4 | Remove one continuous-time dendritic duplicate | 2,000–4,000 µm² | Moderate |
| 5 | Remove extra 200 fF mismatch replicas, if added | 2,000–4,000 µm² | Moderate |
| 6 | Remove the 800 fF regenerative LIF pair | 1,500–3,000 µm² | Moderate–high |
| 7 | Simplify switched-capacitor clock programmability | 1,000–3,000 µm² | Moderate |
| 8 | Remove the switched-capacitor dendrite | 3,000–9,000 µm² | High |
| 9 | Remove the AdEx architecture | 2,000–5,000 µm² | High |

The savings are not strictly additive because removing neurons can also reduce shared routing and control overhead.

I would protect the following components until the very end:

- One regenerative LIF at each of the three capacitances.
- One comparator LIF for the threshold-architecture comparison.
- At least one genuinely unprobed control and one probe-ready neuron.
- One passive continuous-time multicompartment neuron.
- One digital LIF reference.
- Enough bias and measurement infrastructure to characterize them properly.

I would also protect **programmability of membrane leakage and dendritic coupling**, even if we have to reduce the number of neurons. Otherwise, the chip would tell us relatively little about the usefulness of analog neuromorphic computing beyond a few fixed circuits.

## 6. What I would fabricate if everything fits

**Preferred 1×2 configuration** · (Target)

The full matrix, plus four additional identical LIF replicas for mismatch characterization.

| Regenerative LIF | 10 |
| --- | --- |
| Comparator LIF | 4 |
| AdEx | 2 |
| Continuous-time dendritic | 2 |
| Switched-capacitor dendritic | 1 |
| Digital LIF | 1 |
| **Total neuron instances** | **20** |

Network experiments reuse the LIF instances. No full Hodgkin–Huxley or active-dendrite implementation is included in this first tapeout.

This would give us an unusually useful experimental dataset for a small chip: capacitance scaling, analog versus digital, threshold architecture, parameter programmability, cross-neuron variation, probe loading, time-scale acceleration, and continuous-time versus switched-capacitor dendritic computation.

The next decision should be driven by actual circuit layouts, particularly the 50 fF LIF and the switched-capacitor coupling element.

**My strongest recommendation is to preserve the capacitance sweep and both dendritic implementations, even if that means sacrificing most of the network.** Those experiments are more directly connected to your two central research goals: compact analog neuron hardware and the marginal cost of biological fidelity.

* * *

**You:**

I also think we should include more replication of the small capacitor lif. It doesn’t take up much space and could answer questions about reproducibility that are important for everything else.

I see you’re already suggesting this so I agree.

Why do you want to keep both dendritic implementations over other experiments? The switched capacitor sounds expensive and doesn’t quite align with my goals. Is this interpretation correct or am I missing something?

* * *

**ChatGPT:**

I agree with both points. I would increase replication of the small-capacitance LIF, and I think your criticism of the switched-capacitor dendrite is justified.

I previously prioritized the switched-capacitor implementation because it provides a potentially more reproducible way to implement extremely small conductances. But **your primary research goal is to demonstrate the area advantage of continuous-time analog neural dynamics**, especially as biological complexity increases.

A switched-capacitor dendrite addresses a somewhat different question: whether sampled-data analog circuitry can efficiently approximate dendritic dynamics. That is interesting, but it is not necessarily the best use of your limited silicon area.

## 1. Why I originally recommended switched capacitors

The attraction is that an effective conductance can be implemented using a capacitor and clock:

$$
g_{\mathrm{effective}}\approx C_{\mathrm{switch}}f_{\mathrm{clock}}
$$

For example, 10 fF at 10 kHz approximates a conductance of 100 pS, or an effective resistance of 10 GΩ.

This avoids implementing an extremely weak continuous-time conductance, which can be difficult because of leakage and transistor mismatch.

However, there are several disadvantages.

| Property | Continuous-time MOS dendrite | Switched-capacitor dendrite |
| --- | --- | --- |
| Physical membrane state | Capacitor voltage | Capacitor voltage |
| Axial current | Continuous | Discrete charge transfers |
| Clock required | No | Yes |
| Conductance programming | Analog bias | Clock frequency |
| Very weak coupling | Challenging | Potentially easier |
| Area | Potentially very small | Switches, clocking, capacitors |
| Power | Continuous bias/leakage | Switching energy and clock overhead |
| Noise | Device and thermal noise | Sampling noise, charge injection |
| Biological time dynamics | Naturally continuous | Approximate, sampled-data |

The switched-capacitor implementation could be more efficient for some parameter ranges, but it would require additional circuitry that the continuous-time design does not.

It is also not guaranteed to be smaller. If the clock is shared across hundreds of compartments, the overhead becomes relatively inexpensive. On a tiny test chip with only three or six compartments, the clock infrastructure may dominate.

That is an important distinction between **a scalable architecture and a small experimental demonstration**.

## 2. Why I now favor removing it

Your most interesting research question is not whether analog circuits can implement an RC network. We already know they can.

It is whether we can implement increasingly sophisticated biological neural behavior with a relatively small incremental hardware cost.

For example:

$$
A_{\mathrm{neuron}}
=
A_{\mathrm{soma}}
+
N_{\mathrm{comp}}A_{\mathrm{comp}}
+
A_{\mathrm{coupling}}
$$

If the compartment circuitry is small, we could potentially implement many dendritic compartments for the area required by a relatively modest digital simulation.

That is the result worth investigating.

A switched-capacitor implementation adds another architectural dimension without necessarily helping us answer this question.

It also introduces clocking, which complicates comparisons with continuous-time analog neurons.

**I would therefore demote switched-capacitor dendrites from a primary experiment to an optional stretch goal.**

There is one condition under which I would reconsider: if transistor-level simulation shows that continuous-time MOS coupling cannot reliably reproduce the required conductances at biological time scales.

In that case, switched capacitors become a potential solution to a demonstrated limitation rather than an additional experiment without a clear purpose.

---

## 3. I would spend the recovered area on LIF replication

I think the small-capacitance LIF replication experiment is more valuable than I initially gave it credit for.

It directly tests one of the biggest potential weaknesses of analog neuromorphic hardware: **whether extremely compact neurons can be made reproducible without expensive per-neuron calibration**.

For example, suppose we fabricate 16 nominally identical 50 fF regenerative LIF neurons.

With a shared input and identical bias settings, we could measure:

- Firing threshold distribution.
- Membrane time-constant distribution.
- Firing-rate distribution.
- Trial-to-trial spike timing variability.
- Sensitivity to temperature and supply voltage.
- How well global calibration corrects variation.
- How much additional per-neuron calibration is needed.

The important question is whether these variations are small enough for practical applications.

### A particularly useful experiment: calibration versus area

We could divide the 16 neurons into two groups:

| Group | Configuration | Purpose |
| --- | --- | --- |
| 8 minimal LIFs | Shared global bias, no individual calibration | Measure the lowest-cost practical architecture |
| 8 programmable LIFs | Shared bias plus per-neuron trim | Measure the area cost and effectiveness of calibration |

This would allow us to establish a relationship between area and reproducibility.

However, there is a subtle confound: adding trim circuitry changes the neuron itself.

I would therefore prefer making the physical cores identical and placing optional calibration circuitry outside them, so we can compare the same neuron before and after calibration. We can still fabricate a few completely minimal cores to quantify the overhead of making a neuron trim-capable.

That gives us three relevant quantities:

$$
A_{\mathrm{minimal}}
$$

$$
A_{\mathrm{trim-capable}}
$$

$$
\sigma_{\mathrm{before/after\ calibration}}
$$

The resulting experiment is potentially more informative than simply measuring whether the analog neuron is smaller than a digital one.

---

## 4. Updated priorities

I would organize the 1×2 chip around four experiments.

**1. Minimal LIF area and reproducibility**

12–20 small-capacitance regenerative LIFs, with a subset available for probing and calibration. This is the primary quantitative experiment.

**2. Architectural and capacitance variation**

Comparator versus regenerative feedback, and 50/200/800 fF capacitances. Test multiple time scales using programmable conductances.

**3. Continuous-time dendritic computation**

One or two passive multicompartment neurons, ideally with a configurable local nonlinear conductance. Measure the incremental area per compartment.

**4. Digital reference and AdEx**

One dedicated digital LIF and at least one AdEx neuron to establish both the area baseline and the cost of more complex point-neuron dynamics.

A small network would remain optional, using existing LIF neurons.

## 5. Revised approximate area allocation

I would tentatively target the following configuration.

| Component | Quantity | Nominal area |
| --- | --- | --- |
| Small regenerative LIF array | 16 | 8,000 µm² |
| Other LIF capacitance/threshold variants | 6 | 6,000 µm² |
| AdEx neurons | 2 | 5,000 µm² |
| Passive dendritic neurons | 2 | 7,000 µm² |
| Digital LIF | 1 | 3,500 µm² |
| Small network circuitry | Shared | 3,000 µm² |
| Bias and programmability | Shared | 10,000 µm² |
| Probe and measurement circuits | Shared | 8,000 µm² |
| Digital control | Shared | 5,000 µm² |
| **Total estimated circuitry** |  | **55,500 µm²** |

This leaves about 60,500 µm² of the nominal 116,000 µm² envelope for physical overhead, contingency, and possible additional experiments.

These figures are still rough planning estimates. We need transistor-level schematics and physical layouts before treating them as reliable.

### What I would cut first

1. Network interconnect and synapses.
2. Second AdEx neuron.
3. Extra comparator variants, preserving at least one matched comparison.
4. Second passive dendritic neuron.
5. Largest-capacitance LIF variants.
6. Extra calibration hardware, while preserving global programmability.
7. Additional LIF replicas beyond the minimum useful sample.

I would protect the digital reference, the basic comparator-versus-regenerative experiment, the small-capacitance replication array, and at least one passive dendritic neuron.

---

## 6. One further experiment worth considering

Rather than spending all the recovered area on additional identical neurons, I would consider making **two small-capacitance LIF arrays with different physical layouts**.

For example:

- **Array A:** Minimum-area, aggressively compact placement.
- **Array B:** Slightly larger, matched and more carefully isolated placement.

Both would use the same schematic, capacitance, and global biases.

This would allow us to measure whether layout quality materially affects reproducibility, and whether the additional area is justified.

That connects directly to your primary goal: finding the smallest analog neuron that remains practical.

It would also help distinguish transistor-level mismatch from layout-induced systematic effects, although multiple chips would still be needed to characterize die-to-die process variation.

**My recommendation is to remove the switched-capacitor dendrite from the baseline design**, increase small-LIF replication, and preserve the continuous-time dendritic experiments. I would only bring switched capacitors back if SPICE simulations reveal that continuous-time coupling cannot achieve the required time constants or reproducibility.

The result would be a more focused tapeout: instead of testing many unrelated neuromorphic techniques, we would be testing how small, programmable, reproducible, and biologically sophisticated a continuous-time analog neuron can become.

* * *

**You:**

I think your going to far. We should include the switched capacitor dendrites if space permits. We should also balance replication more with the other experiments. I think testing our full range in exchange for some replication is a good trade off. It’s more about how we prioritize this. Ideally we end up with extra space and we can increase and expand replication.

* * *

**ChatGPT:**

Agreed. I overcorrected by prioritizing LIF replication at the expense of architectural diversity. For this first tapeout, **we should prioritize covering the full experimental range, then use remaining area to improve replication and statistical confidence.**

The 1×2 chip should be a platform for exploring analog neuron architectures, not primarily a reproducibility study.

## Revised GF26c experimental matrix

| Architecture | Baseline quantity | Expansion if space permits |
| --- | --- | --- |
| Regenerative LIF, 50 fF | 4 | +4–8 replicas |
| Regenerative LIF, 200 fF | 2 | +2 replicas |
| Regenerative LIF, 800 fF | 2 | +2 replicas |
| Comparator LIF, 50 fF | 2 | +2 replicas |
| Comparator LIF, 200 fF | 2 | +2 replicas |
| AdEx | 2 | +1–2 variants |
| Continuous-time dendritic, 3 compartments | 2 | +1 larger morphology |
| Switched-capacitor dendritic, 3 compartments | 1 | +1 variant |
| Digital LIF | 1 | Additional precision/configuration |
| Small network | Reuse LIFs | More connectivity |
| **Total physical neurons** | **18** | **Up to ~34** |

The baseline provides capacitance variation, threshold architectures, reproducibility comparisons, biological complexity, and a digital reference.

For the regenerative 50 fF group, I would use two unprobed and two probe-ready neurons. Other paired designs would similarly allow us to quantify probe loading. The 800 fF group should be retained because it gives us a useful physical capacitance range.

## Revised priority hierarchy

Rather than one rigid cut list, I would use three tiers.

**Tier 1 — Essential experiments**

Preserve these even if the chip becomes crowded: regenerative and comparator LIFs, the 50/200/800 fF capacitance sweep, a digital LIF reference, programmable time constants, basic probe controls, and one continuous-time dendritic neuron.

---

**Tier 2 — Strongly preferred experiments**

Two AdEx neurons, a switched-capacitor dendritic variant, a second continuous-time dendritic neuron, and a small network reusing existing LIFs.

We should actively design for these, not automatically discard them.

---

**Tier 3 — Expansion and replication**

Additional 50 fF LIF replicas, extra comparator and AdEx variants, different dendritic compartment counts, active dendritic conductances, and more extensive network connectivity.

## Estimated area for the baseline

Using our previous provisional GF180 area assumptions:

| Component | Estimated area |
| --- | --- |
| 12 LIF neurons across capacitances and thresholds | 10,000 µm² |
| 2 AdEx neurons | 5,000 µm² |
| 2 continuous-time dendritic neurons | 7,000 µm² |
| 1 switched-capacitor dendritic neuron | 5,000 µm² |
| 1 digital LIF | 3,500 µm² |
| Small network | 4,000 µm² |
| Bias, programming, and measurement | 18,000 µm² |
| Digital control | 5,000 µm² |
| **Estimated circuit area** | **57,500 µm²** |

For a nominal 116,000 µm² gross envelope, that leaves 58,500 µm² before global physical overhead, routing, isolation, and contingency.

These estimates are not post-layout results, and the available area may be smaller than the gross envelope. Still, this is a reasonable starting budget for attempting the full baseline.

## How I would allocate additional space

If initial layout results leave extra space, I would add experiments in this order:

1. **Additional 50 fF regenerative LIF replicas**, bringing that group from four to eight.
2. Additional 50 fF comparator LIF replicas, improving the architectural comparison.
3. A continuous-time dendritic neuron with more compartments, to measure how area and behavior scale with morphology.
4. Additional AdEx or switched-capacitor variants.
5. More extensive network connectivity and active dendritic circuitry.

This is an expansion order, not an absolute ranking of scientific value. For example, if a four-compartment dendritic variant requires very little incremental area, it might be worth adding before another four LIF replicas.

I would also keep the physical layouts modular so additional copies can be inserted late without redesigning the shared measurement infrastructure.

### One important refinement

I suggest we treat **replication and architecture coverage as separate budget categories**.

The baseline should contain enough replication to establish basic reproducibility and probe-loading effects. Once all major architectures are represented, we can allocate additional area according to which measurements would benefit most from more samples.

That gives us the balance you're describing: a broad experimental chip first, with deeper reproducibility studies as space allows.

**The design target is therefore 18 baseline neuron instances, including the digital reference, with a stretch goal of roughly 25–30 instances** if the actual layouts are sufficiently compact. The next step is to replace our rough area assumptions with GF180 schematic and layout estimates, then make additions or cuts based on measured area rather than prematurely narrowing the experiment.

* * *

**You:**

Can you now make a todo list for the design. What neurons should we design first. How do we validate them in silico. How do we expand our capabilities to more complex neurons. What surrounding circuitry do we need to build?

* * *

**ChatGPT:**

# GF26c analog neuromorphic chip — design and validation roadmap

I would organize development around **reusable circuit primitives**, rather than designing all 18 neurons independently. This lets us validate each component, reuse it in increasingly complex neurons, and maintain fair comparisons between architectures.

The development sequence should be:

**Membrane integrator + leak**

↓

Regenerative LIF

Comparator LIF

↓

AdEx + adaptation

Passive dendrites

↓

**Switched-capacitor dendrites + small network**

Develop shared blocks first, then compose them into progressively more sophisticated neurons.

## 1. Master design checklist

Project checklist

0 of 24 tasks complete · Copy checklist

1 · **Architecture and specifications**

- [ ] Confirm GF26c 1×2 analog template, power rails, usable dimensions, digital I/O and two analog pins

- [ ] Define biological model equations and numerical reference implementations

- [ ] Freeze initial 50/200/800 fF capacitance sweep and target time scales

- [ ] Define area, power, accuracy, reproducibility and programmability metrics

---

2 · **Foundational analog circuits**

- [ ] Design membrane capacitor, leakage conductance and current-input block

- [ ] Design regenerative threshold and reset circuit

- [ ] Design comparator threshold and reset circuit

- [ ] Validate both LIF implementations against numerical models

- [ ] Sweep capacitance, speed, temperature and process variation

---

3 · **Advanced neuron models**

- [ ] Design adaptation and exponential-current blocks for AdEx

- [ ] Design continuous-time dendritic compartment and axial coupling

- [ ] Design three-compartment passive dendritic neuron

- [ ] Design switched-capacitor coupling and clock control

- [ ] Evaluate active dendritic nonlinearities as a stretch goal

---

4 · **Digital reference and infrastructure**

- [ ] Implement dedicated fixed-point digital LIF

- [ ] Design shared bias generation and configuration registers

- [ ] Design stimulus generator and synaptic current injection

- [ ] Design probe buffers, analog multiplexer and digital spike readout

- [ ] Design small configurable network using existing LIF cores

---

5 · **Physical implementation**

- [ ] Create matched probed and unprobed neuron layouts

- [ ] Create repeated 50 fF LIF cells for mismatch experiments

- [ ] Perform DRC, LVS and parasitic extraction

- [ ] Run post-layout transient, Monte Carlo and corner simulations

- [ ] Verify pin behavior, chip-level integration and tapeout signoff

## 2. Design order and validation criteria

I would use the following order. Each stage should produce a reusable circuit, a numerical reference, and a SPICE testbench before proceeding.

| Order | Design | What must work before advancing |
| --- | --- | --- |
| 1 | Membrane integrator and leak | Predictable resting voltage, exponential decay, tunable time constant |
| 2 | Regenerative LIF | Reliable spiking, reset, refractory behavior |
| 3 | Comparator LIF | Same functional behavior with different threshold circuitry |
| 4 | Digital LIF | Matched model and defined numerical precision |
| 5 | Adaptation circuit / AdEx | Spike-frequency adaptation and nonlinear excitability |
| 6 | Passive dendritic compartment | Correct coupling, attenuation, and spatial summation |
| 7 | Three-compartment dendrite | Agreement with multicompartment numerical model |
| 8 | Switched-capacitor dendrite | Effective conductance versus clock frequency |
| 9 | Small network | Reliable propagation, excitation, inhibition |
| 10 | Optional active dendrite | Local nonlinear event or plateau behavior |

The surrounding measurement and programming circuitry should begin in parallel with stages 1–3. It should not be postponed until the neuron designs are finished.

## 3. How to validate each neuron in silico

Use three levels of simulation.

**Level 1 — Numerical reference**

Python with SciPy, Brian2, or NEURON. Implement the exact intended differential equations and generate expected membrane trajectories and spike events.

**Level 2 — Transistor-level SPICE**

Use the GF180 PDK models with ngspice or a compatible simulator. Evaluate whether the physical circuit actually implements the intended dynamics.

**Level 3 — Extracted-layout SPICE**

Include parasitic capacitance, resistance, and layout effects. Repeat the critical tests to verify that the circuit still works after physical implementation.

For every architecture, I would run the following common test suite:

| Test | Stimulus | Measurements |
| --- | --- | --- |
| Resting state | Zero input, reset initial conditions | Equilibrium, leakage, drift |
| Impulse response | Short current pulse | Voltage amplitude and decay |
| Step response | Constant current steps | Firing threshold and rate |
| Repeated spikes | Periodic input pulses | Spike timing, jitter, refractory behavior |
| Speed sweep | Scale input timing and conductances | Accuracy at 1×, 10×, 100×, 1,000× |
| Capacitance sweep | 50, 200, 800 fF | Noise, power, time constants |
| Programming sweep | Change one bias at a time | Range, monotonicity, parameter coupling |
| Process corners | PDK corner models | Sensitivity to manufacturing variation |
| Monte Carlo | Device mismatch models | Predicted neuron-to-neuron distribution |
| Supply/temperature | Sweep operating conditions | Stability and calibration requirements |

For the LIF models, useful numerical metrics include membrane-voltage RMSE, firing-rate error, threshold error, spike-time displacement, and refractory-period error.

For AdEx, additionally measure adaptation time constant, first-versus-steady-state firing rate, and the ability to reproduce selected firing patterns.

For dendrites, measure attenuation, transfer impedance, temporal summation, and location-dependent input integration.

### Critical point: comparing different speeds

We should not only measure whether the neuron operates at different speeds. We should measure whether it implements **the same normalized dynamics**.

For example, if a neuron runs 100× faster, compare its waveform with the original after dividing the hardware time axis by the acceleration factor.

Define:

$$
\epsilon_V =
\sqrt{\frac{1}{N}\sum_i
\left(V_{\mathrm{SPICE}}(t_i)-V_{\mathrm{ref}}(t_i)\right)^2}
$$

The two traces should first be aligned using the intended time-scale mapping and voltage calibration.

Then measure how 

$$
\epsilon_V
$$

, spike-time error, and energy change with acceleration.

This could establish an optimal speed regime for each architecture.

## 4. How to validate the dendritic designs

Dendrites deserve a more extensive testbench because their primary purpose is spatial computation.

I would implement the numerical reference as a compartmental cable model, initially with three compartments.

$$
C_i\frac{dV_i}{dt}
=
-g_{L,i}(V_i-E_L)
+\sum_j g_{ij}(V_j-V_i)
+I_i
$$

Use identical capacitance and coupling parameters in the numerical and analog models.

Example dendritic validation experiment

Input A

Input B

Soma

Output

Compare inputs delivered to different dendritic locations and measure their effects on the soma.

Run four experiments:

1. **Single-location stimulation:** Apply identical current pulses at different compartments. Measure somatic attenuation and delay.
2. **Spatial summation:** Apply simultaneous inputs at two dendritic locations. Verify linear summation for passive dendrites.
3. **Temporal summation:** Vary the interval between inputs and measure how their effects combine.
4. **Coupling sweep:** Change axial conductance and verify that measured transfer behavior follows the numerical model.

For the switched-capacitor version, repeat the same tests at multiple clock frequencies. Also measure clock feedthrough and deviations from the continuous-time reference.

An important additional comparison is the **incremental area per dendritic compartment**. We should extract the area of a single compartment, each coupling element, and the shared soma independently.

That allows us to estimate how a 10-, 100-, or 1,000-compartment analog neuron might scale without actually fabricating one.

These extrapolations should include routing, bias distribution, and measurement overhead, not just replicated circuit area.

## 5. Surrounding circuitry to design

The supporting circuitry is effectively a miniature neuromorphic test platform. It determines whether we can obtain meaningful results from the fabricated neurons.

| Block | Function | Design priority |
| --- | --- | --- |
| Shared bias/reference generation | Establish leak, threshold, reset, adaptation biases | Essential |
| Digital configuration registers | Select neurons, set parameters, control experiments | Essential |
| Input stimulus generator | Apply controlled currents and spike pulses | Essential |
| Analog output multiplexer | Select internal voltages for measurement | Essential |
| Low-loading probe buffer | Prevent measurement circuitry from disturbing neuron state | Essential |
| Spike detection/counters | Record spike counts and event timing | Essential |
| Reset and initialization | Establish repeatable initial conditions | Essential |
| Power and bias monitoring | Measure supply and operating stability | Essential |
| Calibration/trim controls | Evaluate programmability and mismatch correction | High |
| Network synapses | Connect a small group of neurons | High |
| Switched-capacitor clock generation | Control sampled-data dendrites | High |
| Per-neuron spike timestamping | Measure fine timing variation | Optional |
| Active dendrite controls | Enable local nonlinear conductances | Optional |

### Shared bias architecture

I would avoid duplicating full DACs across neurons.

Instead, use a small set of shared biases with digital selection and limited local trimming.

Shared bias

generation

DAC / references

LIF array

Local trim / enable

AdEx

Local trim / enable

Dendrites

Local trim / enable

Conceptual distribution. Actual bias buffering and local trimming must be designed to avoid coupling and loading errors.

A critical design choice is how many independently programmable bias domains we need.

For example, the LIF array might share one leak bias and one threshold bias, while the AdEx and dendritic circuits have additional independent controls.

We should build a parameter-to-bias dependency matrix before implementing the DACs. This prevents allocating separate hardware for parameters that can share a control, while identifying cases where shared biases would make experiments impossible.

### Stimulus and measurement with two analog pins

My provisional allocation remains:

- Analog input: external current or voltage stimulus, with on-chip conversion as required.
- Analog output: buffered, multiplexed internal state.

Digital I/O would handle configuration, reset, spike readout, and event timing.

The external stimulus input should not be connected directly to every neuron simultaneously without isolation. Use a programmable selection network or an on-chip stimulus source.

For dendritic experiments, we need to stimulate different compartments independently. With only one analog input, this can be achieved using digitally controlled routing and on-chip pulse/current generators.

If we need simultaneous independent waveforms, we will need at least two local stimulus channels or another mechanism for storing and replaying stimuli.

## 6. Design-for-test requirements

These are especially important for analog hardware.

**Every architecture should have a reliable external observable.** At minimum, each neuron should expose its spike output digitally, even if its membrane voltage is not externally accessible.

**Selected neurons should have analog state access.** We should be able to observe the membrane voltage of the LIF, the adaptation state of AdEx, and individual dendritic compartment voltages.

**Unprobed controls should remain genuinely unprobed.** They should not have extra mux inputs or buffer gates connected to their internal membrane nodes.

**All neurons should support repeatable initialization.** Otherwise, differences in initial conditions could be mistaken for mismatch or stochasticity.

**Power measurements should be designed in advance.** Measuring the energy of a tiny neuron is difficult when its current is mixed with bias generators, digital counters, and output buffers. At minimum, provide separately controllable blocks and characterize idle versus active current. Separate power domains would improve measurement quality if the shuttle permits them.

**Avoid making shared infrastructure a single point of failure.** A failed analog output buffer should not prevent digital spike readout. A failed network should not prevent standalone neuron testing.

## 7. Suggested implementation milestones

I would use explicit acceptance gates so we do not spend time laying out circuits that have not demonstrated the required behavior.

**Milestone 1 — Functional LIF primitives**

Deliver regenerative and comparator LIF schematics, numerical reference models, SPICE simulations, and preliminary area estimates.

Acceptance: stable spiking, reset, tunable leak, and correct responses to standard stimuli.

**Milestone 2 — Capacitance and speed characterization**

Simulate 50/200/800 fF variants across biological and accelerated time scales.

Acceptance: measured operating ranges, leakage/noise limitations, programming curves, and energy estimates.

**Milestone 3 — Advanced neurons**

Implement AdEx, passive continuous-time dendrites, and switched-capacitor dendrites.

Acceptance: each architecture reproduces its defining behavior against a numerical reference.

**Milestone 4 — Chip-level integration**

Add digital LIF, shared biases, configuration, measurement, and optional network circuitry.

Acceptance: every neuron can be selected, stimulated, reset, and observed through the available pins.

**Milestone 5 — Physical verification**

Complete layout, DRC, LVS, extraction, and post-layout functional tests.

Acceptance: verified area fit, valid pin connections, and acceptable behavior under the chosen process and operating corners.

## 8. What I would do first

I would start three parallel workstreams:

**Circuit design:** Build the membrane integrator, leak, regenerative threshold, and comparator threshold in GF180 SPICE. Begin with the 200 fF variant, then scale to 50 and 800 fF.

**Simulation and analysis:** Create a Python reference framework that automatically generates stimuli, runs SPICE, extracts traces, and compares them with the mathematical neuron models. This framework should support parameter sweeps, process corners, and Monte Carlo results.

**Infrastructure:** Confirm the GF26c analog template and design the minimum viable control interface: bias distribution, reset, input selection, and digital spike readout.

The first major decision gate should come after we have SPICE results and at least a preliminary physical layout of the two LIF architectures.

At that point we can establish whether 50 fF is practical, how much area the comparator costs relative to regenerative feedback, and whether the desired speed range is achievable.

Then we can expand into AdEx and dendritic compartments with a validated set of primitives, rather than designing each advanced neuron from scratch.

The final goal is not merely a chip that contains many neuron types. It is a **reproducible experimental platform that measures the cost of increasing biological fidelity in analog silicon**, with enough digital comparison and instrumentation to make those measurements credible.

* * *

**You:**

Can we really test different speeds with just different run time parameters or might we need design different circuits.

* * *

**ChatGPT:**

**We can test different speeds by changing runtime parameters, but I would not assume one analog circuit can operate accurately across the entire 1×–1,000× range.** In fact, I think testing the limits of runtime scaling versus physically different circuit designs should become one of our experiments.

There are two distinct questions:

1. Can a single circuit reproduce the same neural dynamics at different speeds?
2. Can a circuit optimized for a particular speed achieve better area, energy efficiency, or accuracy?

The first tests programmability. The second tests hardware optimization. Both are relevant to your project.

## 1. Why changing runtime parameters might not be enough

For a simple LIF neuron:

$$
C_m\frac{dV}{dt}=I_{\mathrm{in}}-g_L(V-E_L)
$$

Its membrane time constant is:

$$
\tau_m=\frac{C_m}{g_L}
$$

We can change the speed by adjusting 

$$
g_L
$$

, without changing the physical capacitor.

For a 200 fF capacitor:

| Target acceleration | Time constant | Required conductance | Leak current at 100 mV |
| --- | --- | --- | --- |
| 1× | 10 ms | 20 pS | 2 pA |
| 10× | 1 ms | 200 pS | 20 pA |
| 100× | 100 µs | 2 nS | 200 pA |
| 1,000× | 10 µs | 20 nS | 2 nA |

Mathematically, this is straightforward. Electrically, the difference between a 2 pA current and a 2 nA current is substantial.

At the slow end, leakage and mismatch can dominate. At the fast end, transistor bandwidth, spike-generation delay, and reset circuitry can become limiting factors.

### The problem with a wide programmable range

Illustrative operating regions

1×

10×

100×

1,000×

10,000×

Leakage

limited

Potential useful

operating range

Speed

limited

Simulation acceleration (log scale)

Conceptual illustration only. The boundaries are not measured GF180 performance limits.

A circuit might work well over a 10× or 100× range but become inaccurate beyond that. The actual range depends on its transistor topology, bias circuitry, capacitance, and process characteristics.

## 2. Which neuron components can be scaled at runtime?

| Component | Runtime scaling | Potential limitation |
| --- | --- | --- |
| Membrane leakage | Bias-controlled conductance | Leakage, mismatch, nonlinear response |
| Input current | Current bias or DAC | Current accuracy and range |
| Spike threshold | Reference voltage | Usually not speed-dependent |
| Reset circuit | Adjustable pulse/timing | Reset speed and charge injection |
| Refractory period | Programmable timing | Minimum circuit delay |
| AdEx adaptation | Bias current/conductance | Slow-state leakage and fast-state bandwidth |
| Exponential spike current | Bias adjustment | Changes excitability as well as speed |
| Dendritic axial coupling | Conductance bias | Voltage dependence and mismatch |
| Dendritic membrane leakage | Conductance bias | Must scale with axial coupling |
| Switched-capacitor coupling | Clock frequency | Switching noise and sampling artifacts |
| Synaptic decay | Bias-controlled time constant | Must track membrane acceleration |

For an ideal continuous-time circuit, scaling every current and conductance by the same factor 

$$
s
$$

, while holding capacitances constant, produces an 

$$
s
$$

-fold acceleration.

But this requires scaling **all relevant dynamics together**. Scaling only the membrane leak does not preserve the neuron's behavior.

For example, an AdEx neuron has both a membrane time constant and an adaptation time constant. If only one changes, the firing pattern can change substantially.

## 3. Why different physical designs may be better

There are several reasons to fabricate variants optimized for different speeds.

### A. Different membrane capacitances

Our existing 50/200/800 fF sweep is already a way to investigate this.

At a fixed 10 ms time constant:

| Capacitance | Required conductance | Leak current at 100 mV |
| --- | --- | --- |
| 50 fF | 5 pS | 0.5 pA |
| 200 fF | 20 pS | 2 pA |
| 800 fF | 80 pS | 8 pA |

The 50 fF neuron is physically smaller, but the 0.5 pA current may be difficult to control reliably.

The 800 fF neuron consumes more area and generally needs larger currents to maintain the same time constant, but its dynamics may be less sensitive to some parasitic effects.

This means our capacitance sweep is also a **speed-range and robustness experiment**.

### B. Different leakage architectures

A MOS pseudo-resistor might be excellent for slow operation but become nonlinear or difficult to program over a large conductance range.

A transconductance-based leak could provide better control over a different range, but consume more area and power.

We could therefore design:

- A minimum-area subthreshold leakage circuit.
- A more controlled programmable transconductance circuit.

Using the same membrane capacitance and spike-generation circuitry would isolate the difference.

This may be more informative than fabricating several otherwise identical neurons with different fixed speeds.

### C. Different spike-generation circuits

Our comparator-versus-regenerative experiment also becomes relevant.

At very high acceleration, threshold detection delay, regenerative switching time, and reset recovery may occupy a significant fraction of the membrane time constant.

A circuit that works well at 10 ms may not behave equivalently at 10 µs.

This is another reason to test both threshold architectures across the speed range.

## 4. My proposed speed experiment for GF26c

I would not add a completely separate 1×, 10×, 100×, and 1,000× version of every neuron. That would use space inefficiently.

Instead, I would structure the experiment in two stages.

**Experiment A — Runtime speed scaling**

Sweep leak, input, reset, and other time-dependent biases on the same physical neuron.

Test nominal acceleration factors of 1×, 10×, 100×, and 1,000×. Record the actual achieved time constants rather than assuming the bias settings produce the target values.

**Experiment B — Physically optimized speed variants**

Compare different capacitances and, if area permits, a second leakage implementation.

Determine whether a circuit optimized for one speed can outperform a broadly programmable design in area, power, or accuracy.

### How to evaluate the results

For each circuit, I would measure:

- Achievable membrane time-constant range.
- Error relative to the numerical reference at each speed.
- Spike-timing accuracy after rescaling time.
- Power and energy per simulated biological second.
- Sensitivity to supply and temperature.
- Parameter calibration required at each speed.

The key output would be a curve showing how biological fidelity changes with acceleration.

| speed | Small-capacitance LIF | Large-capacitance LIF |
| --- | --- | --- |
| 1× | 18% | 5% |
| 10× | 8% | 3% |
| 100× | 3% | 3% |
| 1,000× | 12% | 9% |

The ideal result would be a broad range where one compact design performs well. But if different capacitances or leakage architectures dominate in different regimes, that would justify specialized neuron designs.

## 5. What I would change in our design matrix

I would keep our existing capacitance sweep and add **one additional leakage-circuit variant** if space permits.

| Design | Primary purpose |
| --- | --- |
| 50 fF regenerative LIF | Minimum area, leakage-limited behavior |
| 200 fF regenerative LIF | Balanced reference |
| 800 fF regenerative LIF | Larger-capacitance stability |
| Comparator LIF variants | Threshold architecture and speed limits |
| Alternative leak LIF, 200 fF | Test whether a different physical circuit improves the programmable speed range |
| AdEx | Test coordinated scaling of fast and slow dynamics |
| Continuous-time dendrite | Test scaling of multiple coupled membrane time constants |
| Switched-capacitor dendrite | Test clock-based time scaling |

I would also make sure the analog bias infrastructure can cover the necessary range. A wide-range bias generator may require multiple current ranges or coarse/fine controls, rather than a single DAC spanning three orders of magnitude.

**My recommendation is to treat speed scaling as an experimental result, not a guaranteed circuit feature.** We should first determine the achievable range through SPICE, then fabricate a small number of physically distinct variants that expose the tradeoffs.

That keeps the chip aligned with your original goals while allowing us to discover whether analog neurons should be designed for particular operating speeds or can be made broadly programmable without much additional area.

* * *

**You:**

I like the current plan. Can you do another pass on prior R&D that has been done for analog neurons.

* * *

**ChatGPT:**

# Prior R&D review: analog silicon neurons and implications for our GF180 tapeout

I would approach this review with one central question: **which parts of our proposed chip are already well demonstrated, and which experiments could produce genuinely useful new results?**

Analog silicon neurons have a substantial research history, extending from early neuromorphic VLSI through adaptive silicon neurons, dendritic processors, and modern mixed-signal accelerators.

That changes how I would frame our project. Demonstrating that a transistor circuit can reproduce LIF or AdEx dynamics is not novel by itself. The more interesting contribution would be a controlled, process-specific comparison of:

- Minimum achievable neuron area.
- Biological fidelity versus silicon area.
- Physical capacitance and operating-speed tradeoffs.
- Reproducibility, mismatch, and calibration overhead.
- Continuous-time versus switched-capacitor dendritic computation.
- The cost of programmability and internal observability.

I would also distinguish prior demonstrations on specialized research processes from what is realistically reproducible in the GF180 process available to our Tiny Tapeout project.

## 1. The most relevant prior work

These are the projects and papers I would study first, ranked by how directly they inform our design.

![Visual material](https://images.openai.com/static-rsc-4/-MbH7t55dreCMN4hUXr4prHKAZGL-VAI8YHk0SJSPFCXvZ17GM-muzLAZ14CHsra5RoCExU5_7ciIgQ2VhTwoEibXaUYSpUBOT7ETIF3CMbNFN0e3D94dN4BlZmCwPG3NWLcorRxXJvmZwGe19-VOR5X-HRs72xDBzyWnm4wZoI?purpose=inline) · 1. 

> Interactive content unavailable: Entity

Schemmel, Kaiser and colleagues · 2020–2024

The closest architectural precedent. It implements 512 analog neuron circuits with configurable LIF/AdEx behavior. Individual circuits can be coupled into multicompartment neurons, with analog membrane readout and accelerated dynamics.

**For us:** Study how they reuse soma circuits as dendritic compartments, distribute biases, and calibrate mismatch.

[Multicompartment architecture and calibration](https://pmc.ncbi.nlm.nih.gov/articles/PMC11635192/?utm_source=chatgpt.com) · [Hardware characterization](https://pmc.ncbi.nlm.nih.gov/articles/PMC8794842/?utm_source=chatgpt.com)

---

![Overview of Dynap-SE2 — Rockpool 3.0.5 documentation](https://images.openai.com/static-rsc-4/Gmlb3e9Q0AV5MxjlmkECJJxkcsDPWR6Y_y-iGCvC6dO8HaDy5_6a_-bg364jMdku3lGJOBulc2btU9F2ob2onFtc9_rpXTAR3vPSgOJFvHpdU10Kesjl3vZw_uGvmbwXol_X8pblJW3n044O068lVFtetFAges5WsBkMeVqNPnI?purpose=inline) · 2. 

> Interactive content unavailable: Entity

2024 · Mixed-signal asynchronous architecture

Implements analog neural and synaptic dynamics, including adaptation, conductance-based dendritic behavior, and biologically motivated synaptic mechanisms, alongside digital event routing.

**For us:** Particularly relevant to real-time, low-power neuron and synapse design. Its mixed analog/digital division is a useful reference for our support circuitry.

[DYNAP-SE2 paper](https://doi.org/10.1088/2634-4386/ad1cd7?utm_source=chatgpt.com)

---

![Giacomo INDIVERI | Professor (Full) | PhD | University of Zurich, Zürich | UZH | Institute of Neuroinformatics | Research profile](https://images.openai.com/static-rsc-4/BEgH4mAr3kDzziETW3Lxe9by73YZOUuUFS0aDx8ThlEkpSrfNpqlWUA30npUqgUGLrYtogjJmr1E7kNy-8BJHp5iY79nTCtfJAohSKlHNVkAOk1PZj2rg8hvHmq-IAP3_m73RXUAhkjRJUvR2XOwOtvb4Y-lmsbKf9EUTzfXcd4?purpose=inline) · 3. 

> Interactive content unavailable: Entity

Indiveri et al. · 2011

An extensive review of subthreshold LIF, adaptive neurons, conductance-based circuits, log-domain filters, and switched-capacitor designs, including measured silicon implementations.

**For us:** The best starting reference for selecting transistor-level primitives rather than inventing them independently.

[Open-access review](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2011.00073/full?utm_source=chatgpt.com)

---

![Frontiers | Neuromorphic Silicon Neuron Circuits](https://images.openai.com/static-rsc-4/EGDBgtH7KvhPsJ_vNG30eXQnvt_UOgIAYPNPVzKO9XVD0HMSc9QvwYLKq2SuatQO4LyZ4o96zXbKfm773IuQnbs3stj7yyMxrv4vlDfaHKWB-IFCucKvMovwxgU6DbPMtuWJGY8bTglG4oOR2R5zsi5UCa8y1FZppZhk2XbWcbw?purpose=inline) · 4. Biological-real-time switched-capacitor neuromorphic system

Mayr et al. · 2016

Demonstrated 64 neurons and 8,192 synapses in 28 nm CMOS, with biological-real-time dynamics and dedicated leakage compensation.

**For us:** Strong evidence that switched capacitors deserve a place in the comparison, particularly for very slow dynamics. It does not establish that they are the best area choice in GF180.

[Published paper](https://doi.org/10.1109/TBCAS.2014.2379294?utm_source=chatgpt.com)

The BrainScaleS-2 results are especially significant. They have already demonstrated passive dendritic propagation, local nonlinear events, plateau potentials, and BAC firing using configurable analog hardware. We should not frame any of those capabilities as unexplored. 

[ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0306452221004218?utm_source=chatgpt.com) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11635192/?utm_source=chatgpt.com) · [the University of Groningen research portal](https://research.rug.nl/en/publications/dynap-se2-a-scalable-multi-core-dynamic-neuromorphic-asynchronous/?utm_source=chatgpt.com) · [PubMed](https://pubmed.ncbi.nlm.nih.gov/25680215/?utm_source=chatgpt.com)

## 2. What the literature says about minimum-area LIF neurons

There is already a long history of highly compact silicon neurons.

One useful comparison appears in the 2017 paper *A 4-fJ/Spike Artificial Neuron in 65 nm CMOS Technology*.

| Prior design | Technology | Reported neuron core area | Nominal membrane capacitor |
| --- | --- | --- | --- |
| Indiveri et al. (2006) | 350 nm | 2,573 µm² | 432 fF |
| Wijekoon & Dudek (2008) | 350 nm | 2,800 µm² | 100 fF |
| Joubert et al. (2012) | 65 nm | 538 µm² | 500 fF |

These are published comparison figures, not normalized like-for-like measurements. They use different circuit architectures, operating conditions, and definitions of core area. 

[Frontiers](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2017.00123/full?utm_source=chatgpt.com) · [Frontiers](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2021.644604/full?utm_source=chatgpt.com)

This is important for our previous area estimates.

We have been assuming that a regenerative LIF might occupy roughly 500 µm². That is a reasonable design hypothesis to test, but **not yet a demonstrated GF180 result**. Historical 350 nm designs can be substantially larger, especially once their capacitors, bias circuitry, and routing are included.

A 50 fF design could be smaller, but capacitance alone does not determine neuron area.

### Three circuit families worth comparing

| Circuit family | Strength | Main concern |
| --- | --- | --- |
| Compact regenerative / axon-hillock LIF | Few devices; potentially very small | Spike threshold and reset may be sensitive to transistor parameters |
| Comparator-based LIF | More explicit control of threshold | Comparator area, bias power, and delay |
| DPI / log-domain adaptive LIF | Natural biological time constants and adaptation | Bias complexity and mismatch |

The DPI family is particularly interesting. A differential-pair integrator exploits transistor physics to implement first-order temporal dynamics using small currents and capacitances.

It also provides a natural route toward adaptation and synaptic filtering, which could reduce the amount of new circuitry required for AdEx.

The 2011 Indiveri review provides equations and circuit examples for these building blocks. 

[Neuromorphic Silicon Neuron Circuits](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2011.00073/full?utm_source=chatgpt.com) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC3130465/?utm_source=chatgpt.com)

**Design implication:** I would retain regenerative and comparator LIFs, but add a DPI/log-domain integrator to our transistor-level investigation. It does not necessarily need to become a third complete LIF architecture on silicon.

We should first compare its area and controllable time-constant range with our simpler leakage implementations.

## 3. The most important lesson for our speed experiments

The literature supports both of the competing approaches we discussed.

BrainScaleS-2 uses physical analog dynamics accelerated by approximately 1,000× relative to biological time. Its small capacitances and comparatively large currents are part of the reason it can operate so quickly. 

[PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8794842/?utm_source=chatgpt.com) · [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0306452221004218?utm_source=chatgpt.com)

Meanwhile, Mayr and colleagues demonstrated a switched-capacitor system reproducing biological time constants extending to hundreds of milliseconds, using techniques specifically intended to counter leakage. 

[PubMed](https://pubmed.ncbi.nlm.nih.gov/25680215/?utm_source=chatgpt.com) · [arXiv](https://arxiv.org/abs/1412.3233?utm_source=chatgpt.com)

These are not contradictory results. They represent different hardware optimization targets.

| Objective | Promising approach |
| --- | --- |
| Biological real-time operation | Very weak continuous-time conductances, or leakage-compensated switched capacitors |
| 100×–1,000× acceleration | Larger currents, smaller capacitors, faster threshold circuits |
| Wide programmable speed range | Multiple bias ranges, potentially selectable circuit branches |
| Minimum area | Highly compact continuous-time circuits, with less programmability |
| Reproducible timing | Carefully controlled conductances or clock-defined transfer |

One caution: scaling current and conductance at runtime does not necessarily preserve the characteristics of MOS devices as they transition between operating regions.

For instance, a transistor acting as a pseudo-resistor in weak inversion may become more nonlinear as its bias changes. The mathematical neuron model may scale perfectly, while the physical circuit does not.

This suggests a valuable experiment: compare a neuron designed for wide speed programmability against a more compact neuron optimized for one regime.

I would still prioritize the full existing matrix before adding dedicated speed-specialized neurons.

## 4. Dendritic hardware: what has already been demonstrated?

This is the area where the prior work most strongly informs our design choices.

### Passive and active dendrites

The 2022 BrainScaleS-2 dendritic study demonstrated three classes of computation:

- Passive propagation of postsynaptic potentials.
- Spatiotemporal coincidence detection in dendritic branches.
- Active dendritic events and backpropagation-activated calcium-like burst firing.

These are substantial demonstrations of biologically inspired multicompartment computation in silicon. 

[ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0306452221004218?utm_source=chatgpt.com) · [PubMed](https://pubmed.ncbi.nlm.nih.gov/34428499/?utm_source=chatgpt.com)

The particularly useful architectural insight is that their neuron circuits can be linked using configurable conductances. In other words, they reuse a general-purpose neural compartment instead of creating an entirely separate dendrite processor.

That is close to our proposed approach.

However, I would consider two implementations for our continuous-time dendrite:

**Option A: Fully replicated compartments.** Each compartment uses the same membrane integrator and leakage primitive, with optional spike-generating circuitry. This is flexible and extensible toward active dendrites.

**Option B: Minimal passive compartments.** Each compartment contains only its membrane capacitance, leak, and axial coupling circuitry. The soma alone generates spikes.

Option B could be significantly smaller. It may also be more appropriate for studying the incremental area cost of passive dendritic morphology.

I would design the minimal passive compartment first, then investigate adding local nonlinear conductances.

### Compact ion-channel circuits

A particularly relevant paper is Hynna and Boahen's 2007 *Thermodynamically equivalent silicon models of voltage-dependent ion channels*.

They demonstrated a compact transistor-based representation of voltage-dependent channel activation and its time constant, using eight transistors for the channel dynamics described in the paper. 

[PubMed](https://pubmed.ncbi.nlm.nih.gov/17206867/?utm_source=chatgpt.com)

This is useful for our longer-term HH-like and active-dendrite goals.

It suggests we should not assume every additional ion-channel state requires a large operational amplifier or conventional analog computing block.

Instead, we could construct biologically inspired nonlinear conductances from small transistor networks.

That said, an eight-transistor channel primitive is not an eight-transistor Hodgkin–Huxley neuron. A complete conductance-based model still needs state storage, current generation, coupling, and bias circuitry.

### What I would add to our dendritic research plan

I would compare three levels of complexity:

| Level | Circuit | What we learn |
| --- | --- | --- |
| 1 | Passive RC compartment | Minimum cost of morphology |
| 2 | Passive compartment + nonlinear conductance | Incremental cost of active dendritic behavior |
| 3 | Full conductance-based compartment | Feasibility of more biophysical dynamics |

For the first tapeout, level 1 remains essential. Level 2 should be considered if the circuits and area budget permit. Level 3 is better treated as a longer-term research direction unless early layouts show it is unexpectedly compact.

The switched-capacitor dendrite remains in our preferred matrix, subject to available area.

## 5. Reproducibility: prior work supports your emphasis

Analog mismatch is not merely a theoretical concern.

BrainScaleS-2 provides individual parameter controls partly to compensate for variations between physical neuron circuits. Its researchers have also studied using hardware-in-the-loop learning to compensate for mismatch. 

[PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8794842/?utm_source=chatgpt.com) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11635192/?utm_source=chatgpt.com)

The 2024 work on parametrizing multicompartment neurons with genetic algorithms is especially relevant. It examines how to tune hardware parameters to reproduce desired neural dynamics when parameters such as leakage and intercompartment conductance are difficult to infer or set directly. 

[Open Research Europe](https://ore.eu/ore/article/view/447?utm_source=chatgpt.com)

This suggests we should test three calibration levels:

| Calibration | Description | Question |
| --- | --- | --- |
| None | All replicas share nominal biases | How reproducible is the smallest architecture? |
| Global | One shared set of optimized biases | Can a whole array be corrected cheaply? |
| Individual | Per-neuron adjustments | How much improvement requires extra hardware? |

I would also preserve a distinction between:

- **Repeatability:** Does the same neuron behave consistently across trials?
- **Mismatch:** Do nominally identical neurons behave differently?
- **Drift:** Does behavior change with temperature, supply, or time?
- **Calibration stability:** Does a calibration remain useful after operating conditions change?

These are different failure modes, and each requires a different experiment.

For our 50 fF LIF replicas, I would particularly measure the relationship between capacitance, threshold dispersion, time-constant dispersion, and calibration cost.

One interesting addition would be a small number of replicas with intentionally different transistor geometries. Increasing device area generally improves random matching, but may increase parasitic capacitance. This creates another meaningful area-versus-reproducibility comparison.

I would not add those variants until we have established the basic neuron layout.

## 6. Switched capacitors are more relevant than they initially appeared

The Mayr paper is an important counterexample to the idea that switched capacitors are necessarily too expensive or too indirect for biologically realistic neural hardware.

Its 28 nm system integrated 64 neurons and thousands of synapses into a 600 × 600 µm circuit, demonstrating that shared switched-capacitor infrastructure can be practical at scale. 

[PubMed](https://pubmed.ncbi.nlm.nih.gov/25680215/?utm_source=chatgpt.com)

However, its architecture is not a direct comparison with a minimal continuous-time GF180 dendritic circuit. The fabrication process, array size, circuit partitioning, and leakage behavior differ.

For our chip, the experiment should answer a narrower question:

**For the same three-compartment model and operating speed, which implementation delivers the better combination of area, accuracy, power, and parameter control?**

I would avoid optimizing the switched-capacitor dendrite for the entire 1×–1,000× range at first. That could introduce substantial complexity.

Instead, build one functional design and determine its achievable range through clock-frequency sweeps.

If it fits, it gives us a useful architectural comparison. If it does not, the main continuous-time experiments remain intact.

## 7. GF180-specific implications

The process documentation adds two important practical constraints.

First, GF180MCU offers documented MIM capacitor densities of 1.0, 1.5, and 2.0 fF/µm², depending on the selected process option. The MIM layout rules also impose a minimum capacitor area of 25 µm² for the documented options. 

[GlobalFoundries GF180MCU PDK documentation](https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_6_4.html?utm_source=chatgpt.com) · [GlobalFoundries GF180MCU PDK documentation](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_10_4_1.html?utm_source=chatgpt.com)

That means our 50 fF capacitor is near the minimum MIM structure at 2 fF/µm². At 1 fF/µm², it requires 50 µm² of plate area.

This reinforces the importance of the small-capacitance experiment. It is close to a practical process-design boundary, where layout parasitics, device capacitances, and measurement loading become particularly significant.

Second, the GF26b shuttle used a nominal 1×2 project area of approximately 0.12 mm², consistent with our earlier gross estimate. However, we still need the actual GF26c analog template before confirming usable dimensions and power routing. 

[wafer.space](https://wafer.space/tinytapeouts/ttgf26b/ws-run2-t26b/index.html?utm_source=chatgpt.com) · [ChipMaker](https://tinytapeout.com/specs/analog/?utm_source=chatgpt.com)

There is also a useful open-source precedent: IIT Delhi's INTRINSIC Lab reports Tiny Tapeout neuromorphic blocks including a stochastic LIF neuron and associated control circuitry, with additional GF shuttle designs planned. Their existing digital-oriented implementations are not substitutes for our continuous-time analog experiments, but may be useful references for test infrastructure. 

[Prof. Santhosh Sivasubramani IIT Delhi](https://web.iitd.ac.in/~ssivasub/chip-design.html?utm_source=chatgpt.com)

## 8. Where our project could contribute new knowledge

Based on this research pass, I would rank the scientific opportunities as follows.

| Research question | Prior-art maturity | Value of our experiment |
| --- | --- | --- |
| Basic analog LIF operation | Very mature | Low alone |
| LIF threshold architectures | Mature | Moderate as a controlled comparison |
| Physical capacitance vs speed, accuracy, and area | Established principles, less standardized comparison | High |
| Minimum-area neuron reproducibility | Established problem | High with matched layouts |
| Calibration overhead vs neuron area | Active research area | High |
| Analog vs digital LIF area/energy | Extensively studied | High if comparison is rigorously matched |
| Passive dendritic compartment area scaling | Demonstrated, but architecture-dependent | High |
| Switched-capacitor vs continuous dendritic coupling | Both established approaches | Moderate–high |
| AdEx and active dendritic dynamics | Mature in research hardware | Moderate as a compact implementation study |
| Fully HH-like compartments | Substantial prior work | Potentially high, but ambitious for this tapeout |

The strongest contribution would be a **common GF180 characterization framework** in which circuit variants share the same stimuli, numerical references, operating-speed definitions, and measurement methodology.

That would make our results more directly comparable than simply collecting published neuron area and power figures from different fabrication processes.

## 9. What I would change after this research pass

I would keep the overall architecture matrix intact. The literature suggests several refinements, but does not justify dropping major experiments.

Recommended R&D adjustments

1. **Investigate a DPI/log-domain leak primitive** alongside the simple MOS leak. It could become a valuable alternative for long time constants and adaptation.
2. **Design a minimal passive dendritic compartment separately from the soma.** This gives us a clean estimate of the marginal area cost of morphology.
3. **Preserve the 50/200/800 fF sweep and small-capacitance replication.** These experiments address important practical constraints not resolved by demonstrations of basic LIF functionality.
4. **Use the same numerical reference and test conditions for all architectures.** Compare physical accuracy, not just qualitative spike generation.
5. **Design calibration and probe isolation early.** Existing systems show that these are important parts of analog neuromorphic hardware, not optional afterthoughts.
6. **Retain the switched-capacitor dendrite as space permits.** Its main value is testing a different method of implementing weak coupling, not simply adding another neuron.

### The five papers I would read in depth first

1. [Neuromorphic Silicon Neuron Circuits (2011)](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2011.00073/full?utm_source=chatgpt.com) — transistor-level circuit families and design principles.
2. [A 4-fJ/Spike Artificial Neuron (2017)](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2017.00123/full?utm_source=chatgpt.com) — minimum-area and energy-focused LIF designs.
3. [Emulating Dendritic Computing Paradigms (2022)](https://doi.org/10.1016/j.neuroscience.2021.08.013?utm_source=chatgpt.com) — passive and active multicompartment neurons.
4. [Parametrizing Analog Multi-Compartment Neurons (2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11635192/?utm_source=chatgpt.com) — configuration and calibration of physical dendritic circuits.
5. [Biological-Realtime Switched-Capacitor Neuromorphic System (2016)](https://doi.org/10.1109/TBCAS.2014.2379294?utm_source=chatgpt.com) — an alternative approach to long time constants.

### One practical scheduling concern

Tiny Tapeout currently lists **December 7, 2026** as the GF26c submission deadline. That leaves approximately five weeks from today. 

[ChipMaker](https://www.tinytapeout.com/chips/?utm_source=chatgpt.com)

That is a tight schedule for designing and physically verifying a broad analog chip from scratch.

I would therefore separate the research matrix into a baseline that must reach DRC/LVS and post-layout simulation before submission, and expansion blocks that are added only after they have passed their own verification.

**My overall conclusion:** The research strongly supports our direction. The most promising work is not inventing a new neuron model, but determining how efficiently existing neural dynamics can be physically implemented, scaled, programmed, and reproduced in a relatively accessible CMOS process. Our current combination of capacitance variation, architecture comparison, dendritic complexity, and replication is well suited to answering that question.

* * *

**You:**

Can you reconcile this plan with our prior conversation about scaling neuromorphic hardware to a full brain. I think one of our findings was that optimizing the trim/live variables for the analog neurons was very important. Can you look at what all we discussed and see how it incorporates into this current plan. I think this current plan is a great starting point for the ambition of that conversation.

* * *

**ChatGPT:**

# Connecting our GF26c test chip to the full-brain neuromorphic hardware goal

I think this is an important connection. The GF26c chip should be viewed as **the first experimental step toward a scalable analog neural computing architecture**, not simply a collection of interesting neuron circuits.

I searched our earlier discussions. I recovered our work on scaling connectome simulations, shared physiological parameters, heterogeneous neuron models, and the importance of minimizing per-neuron calibration overhead. I couldn't recover the exact earlier full-brain hardware conversation containing the original trim/live-variable analysis, so I'll distinguish those recovered conclusions from the architectural recommendations I'm developing here.

The most important principle is:

**A neuron circuit isn't truly scalable just because its membrane integrator is small. Its configuration storage, calibration, synaptic connections, routing, and supporting circuitry must also scale efficiently.**

That principle should influence our first tapeout now.

## 1. The distinction between trim, live, and shared variables

I would divide the analog neuron's parameters into three categories, plus one separate category for its dynamic state.

| Category | Examples | Expected update frequency | Preferred hardware |
| --- | --- | --- | --- |
| **Trim variables** | Threshold offset, leak correction, transistor mismatch compensation | Calibration; occasionally for drift | Compact local trim storage |
| **Live variables** | Neuromodulation, adaptation gain, synaptic strength, excitability | During operation | Shared controls, local modulation, or writable state |
| **Shared parameters** | Cell-type leak, membrane timescale, synaptic decay, nominal threshold | Infrequent or experiment-dependent | Shared bias generators |
| **Dynamic state** | Membrane voltage, adaptation current, channel gating variables | Continuously | Analog capacitors or other local state |

The distinction matters because these categories have different hardware requirements.

A trim variable might only need a few bits of nonvolatile or retained digital configuration. A live variable might require frequent updates, fast settling, and a different control path. A membrane state must evolve continuously without digital intervention.

There is also a subtlety: a parameter such as leak conductance can have both a shared physiological value and a local trim correction.

For neuron 

$$
i
$$

:

$$
g_{L,i}
=
g_{L,\mathrm{type}}
\cdot F_{\mathrm{trim},i}
\cdot F_{\mathrm{live},i}
$$

This multiplicative representation is a useful architectural target, not a requirement that the circuit literally implement three analog multipliers.

It lets us separate the intended biological behavior from manufacturing corrections and runtime modulation.

That separation could become one of the most important features of the chip.

## 2. Why parameter storage can overwhelm a small neuron

Suppose we eventually achieve a 500 µm² analog LIF core. That sounds excellent, but consider what happens when we add programmable parameters.

Illustrative area accounting for one neuron

Trim bits per parameter · 4

> Slider: 4 (0–8)

Individually trimmed parameters · 3

> Slider: 3 (0–8)

Neuron core

**500 µm²**

Local configuration

**459 µm²**

---

Combined area · **959 µm²**

Hypothetical model only: 12 µm² per stored bit, 65 µm² per trim actuator, and 120 µm² local interface overhead. These are not GF180 layout measurements. Shared infrastructure is excluded.

The point is not the particular area estimate. It is that every additional trim parameter introduces both storage and circuitry to apply that trim.

At a brain-scale target, even small per-neuron overheads become enormous.

For illustration, at 86 billion neurons:

| Additional local overhead | Total silicon area |
| --- | --- |
| 10 µm²/neuron | 0.86 m² |
| 100 µm²/neuron | 8.6 m² |
| 500 µm²/neuron | 43 m² |
| 1,000 µm²/neuron | 86 m² |

These are aggregate active silicon areas, not packaged system footprints or feasible wafer yields. They also exclude synapses, wiring, power delivery, cooling, and communication.

This is why I would treat **calibration cost per neuron** as a first-class research metric, alongside core area and energy.

## 3. The scaling strategy we previously developed

One relevant conclusion from our connectome simulation discussions was to avoid fitting a separate physiological parameter for every neuron or synapse unless necessary.

For the fly simulation, we considered keeping connectome topology and neuron identities fixed while calibrating shared parameters such as membrane time constants, synaptic decay, cell-type interaction gains, and tonic drives.

We also discussed heterogeneous fidelity: simple LIF neurons where adequate, adaptation models where necessary, and multicompartment models for neurons whose morphology materially changes behavior.

Both ideas translate directly into hardware.

Proposed hierarchical parameter architecture

Global operating controls

Supply, speed regime, reference biases

↓

Cell type A

Shared physiology

Cell type B

Shared physiology

↓

Neuron 1

Local trim

Local state

Neuron 2

Local trim

Local state

Neuron 3

Local trim

Local state

Shared physiological settings define the intended neuron behavior; small local corrections compensate for physical variation.

The central scaling hypothesis becomes:

> Most neurons of the same functional class can share their nominal physiological parameters, while a small number of local trim variables compensate for manufacturing variation.

That hypothesis is plausible, but it is not guaranteed. Biological variability may require more individual parameter freedom than manufacturing calibration alone.

Our chip can begin measuring how much local programmability is necessary.

## 4. How this should change the current GF26c chip

I would preserve the full architecture matrix: regenerative LIF, comparator LIF, 50/200/800 fF capacitors, AdEx, continuous-time dendrites, switched-capacitor dendrites if space permits, digital LIF, and the small network.

Rather than adding many new neuron architectures, I would improve the way we design and characterize their controls.

### A. Make the small-LIF replication array a trim experiment

For the four baseline 50 fF regenerative LIFs, plus any additional replicas, I would use a structured comparison:

| Neuron group | Configuration | What it tests |
| --- | --- | --- |
| Minimal reference | Shared bias, no local trim | Lowest-area implementation |
| Trim-capable, trim disabled | Same global settings | Cost of adding trim circuitry |
| Trim-capable, calibrated | Individually corrected | Benefit of local calibration |
| Trim-capable, live modulation | Calibration held fixed; runtime parameter varied | Whether modulation preserves calibration |

The last experiment is particularly valuable.

A neuron might calibrate perfectly at one operating point but become inaccurate when its leak conductance or input current changes.

That means we need to characterize **calibration across operating ranges**, not just at a single nominal bias.

For the minimal versus trim-capable comparison, we should use matched neuron cores and layout practices. The trim circuitry should be disabled without introducing unnecessary loading.

### B. Compare different trim resolutions

Instead of assuming every neuron needs 8-bit parameter correction, I would experimentally investigate whether 2, 4, or 6 bits are sufficient.

This does not require fabricating separate neurons for every bit depth. A 6-bit trim circuit can be characterized using restricted subsets of its codes to estimate lower-resolution calibration performance.

However, this only measures calibration quality at reduced resolution. It does **not** measure the actual area savings of a physically smaller 2-bit or 4-bit trim circuit.

For area comparisons, we should lay out representative trimmed configurations separately.

### C. Measure the marginal cost of each parameter

For a LIF, possible local trim targets are:

- Leak conductance.
- Spike threshold.
- Reset level or reset effectiveness.
- Input gain.

I would not automatically implement all four.

Instead, SPICE sensitivity analysis should identify which parameters contribute most to output variability.

For example, if threshold mismatch dominates firing-rate variation, local threshold trim may be more valuable than local reset trim.

We can quantify this with a sensitivity matrix:

$$
J_{ij}=\frac{\partial y_i}{\partial p_j}
$$

where 

$$
y_i
$$

 represents an observable such as firing rate, threshold, or time constant, and 

$$
p_j
$$

 represents a controllable circuit parameter.

Combining this with process-variation simulations tells us which parameters are worth trimming.

We can then test whether a smaller set of trim controls produces nearly the same improvement as a fully programmable neuron.

This is one of the most useful direct links between our first tapeout and a full-brain architecture.

## 5. Trim versus live variables should influence circuit topology

A particularly important design principle is that **live modulation should not overwrite calibration**.

Suppose we want to change the leak conductance to accelerate the neuron by 100×. If the only control is a local DAC code, we might have to recompute and rewrite every neuron's calibration.

At large scale, that becomes expensive.

A better target is:

$$
g_{L,i}(s)=g_{L,\mathrm{shared}}(s)\,k_i
$$

where 

$$
s
$$

 is the selected speed regime and 

$$
k_i
$$

 is a stored local calibration factor.

The local trim stays fixed while the shared bias changes.

That would allow a population of neurons to change speed without rewriting all their local configuration.

But the circuit must actually support this behavior. In a MOS pseudo-resistor, for example, the effect of a trim code may vary nonlinearly with bias.

So we should measure the normalized trim response over the full speed range.

| speed | Ideal stable trim factor | Example bias-dependent trim factor |
| --- | --- | --- |
| 1× | 1 | 1 |
| 10× | 1 | 1.02 |
| 100× | 1 | 1.1 |
| 1,000× | 1 | 1.24 |

This creates a new experiment: **calibrate at 1×, then measure whether the same calibration remains valid at 10×, 100×, and 1,000×**.

If it does, that is a strong result for scalable analog hardware. If not, we can investigate whether a small lookup table of speed-dependent trim settings is sufficient.

## 6. The biggest full-brain scaling challenge may be outside the neuron

Our earlier fly simulation work exposed an important problem: the number and distribution of synaptic connections can dominate hardware requirements.

We encountered this directly with the high-fan-in neurons in the maleCNS simulation. A small number of hub neurons caused disproportionate memory and execution costs.

Analog neuromorphic hardware does not automatically eliminate that problem.

A compact analog soma still needs some way to receive thousands of synaptic inputs, maintain synaptic strengths, and communicate with other neurons.

At full-brain scale, we need to consider:

| Resource | Scaling concern | What GF26c can test |
| --- | --- | --- |
| Soma circuitry | Area per neuron | Direct measurement |
| Dendritic compartments | Area per compartment | Direct measurement |
| Trim storage | Bits and actuator area per neuron | Direct measurement |
| Live controls | Update bandwidth and local circuitry | Small-scale measurement |
| Synaptic weights | Storage per connection | Limited small-network experiment |
| Communication | Routing, fan-in, fan-out | Small-scale prototype only |
| Power distribution | Current delivery and heat | Block-level measurement |
| Calibration | Time and energy to configure many neurons | Small-scale measurement and extrapolation |

The full-brain system may eventually require a hierarchy of local analog computation, shared parameters, compressed synaptic representation, and digital communication between regions.

That is an architectural hypothesis rather than something this first chip can prove.

In particular, we should avoid assuming that a neuron with 10,000 synapses needs 10,000 independent high-precision analog weight-storage cells. There may be opportunities for shared, sparse, structured, or digitally stored connectivity. But those alternatives need separate evaluation against the required biological fidelity.

## 7. A new experiment: parameter economy

I would add a specific benchmark to our validation framework.

The objective is to determine how many locally programmable variables are actually necessary to reproduce a desired set of neural behaviors.

For each neuron architecture:

1. Generate a population of device-mismatched instances in Monte Carlo SPICE.
2. Fit each instance to the same reference neural model.
3. Start with global biases only.
4. Add one local trim parameter at a time.
5. Measure how much the error decreases.
6. Repeat across operating speeds and environmental conditions.

We can plot accuracy against the number of local trim bits.

| bits | Median normalized model error |
| --- | --- |
| 0 | 18% |
| 2 | 10% |
| 4 | 6% |
| 8 | 3.5% |
| 12 | 3% |
| 16 | 2.8% |

The ideal result would show that a small number of trim bits captures most of the calibration benefit.

We should also record the worst-case errors and the fraction of neurons that cannot be calibrated within tolerance. A good median can conceal unusable outliers.

This is much more useful for scaling than simply demonstrating that an individually calibrated neuron can reproduce a reference waveform.

## 8. How I would incorporate this into the tapeout priorities

I would make one adjustment to our existing design plan: add a **parameter architecture workstream** that runs alongside neuron circuit design.

| Priority | Task | Deliverable |
| --- | --- | --- |
| P0 | Define shared, trim, live, and dynamic-state variables for every neuron type | Parameter classification table |
| P0 | Run sensitivity and mismatch analysis on the first LIF | Ranking of useful trim controls |
| P0 | Design a shared-bias + local-trim interface | Reusable circuit primitive |
| P0 | Measure minimal versus trim-capable LIF area | Physical overhead estimate |
| P1 | Test calibration stability across speeds | Trim portability curves |
| P1 | Test 2/4/6-bit effective trim resolution | Accuracy-versus-storage results |
| P1 | Extend the control architecture to AdEx and dendrites | Common parameter interface |
| P1 | Measure calibration time and write energy | Scaling estimates |
| P2 | Test local live modulation independent of trim | Runtime control prototype |
| P2 | Explore hierarchical cell-type parameter distribution | Small population demonstration |

This does not require removing the switched-capacitor dendrite or sacrificing the capacitance sweep. Most of the early work is simulation and architecture design.

We should only allocate extra silicon to trim circuitry after the sensitivity analysis identifies what is worth implementing.

## 9. How this fits into a longer-term roadmap

**Stage 1 — GF26c: neuron primitives**

Characterize area, fidelity, capacitance, speed, mismatch, calibration, and basic dendritic computation across our planned 18-neuron baseline.

---

**Stage 2 — Small configurable populations**

Scale to hundreds or thousands of neurons. Test shared biases, local trims, synapse storage, calibration throughput, and communication.

---

**Stage 3 — Biologically structured neural circuits**

Implement heterogeneous cell types and morphology where needed. Use real connectome structures and electrophysiology to validate biological behavior.

---

**Stage 4 — Large-scale neuromorphic systems**

Investigate chiplets, interconnects, power distribution, hierarchical calibration, and the feasibility of scaling toward whole-brain models.

Your maleCNS work is particularly relevant to Stage 3. It gives us a way to compare a hardware neural population with a software reference using the same connectivity, neuron models, and stimuli.

That could eventually let us distinguish errors caused by the analog hardware from errors caused by inadequate biological models.

## 10. The key design decision I would make now

I would establish a reusable neuron control interface with four logical layers:

- **Global controls:** operating speed, reference voltages, and common biases.
- **Cell-type controls:** nominal physiological parameters shared by groups of neurons.
- **Local trim:** a small, preferably static correction for physical mismatch.
- **Live modulation:** independent control of biologically meaningful parameters during operation.

Not every neuron needs dedicated circuitry for every layer. The architecture should allow unused layers to collapse into shared controls.

Most importantly, we should measure the actual area of the control infrastructure, including digital storage, analog actuators, routing, and bias distribution.

I would make the central benchmark:

$$
\boxed{
\text{Effective neuron cost}
=
\text{core}
+
\text{local configuration}
+
\text{amortized shared infrastructure}
}
$$

We should report this alongside biological accuracy, energy, operating speed, and calibration cost.

**My main conclusion:** The current GF26c plan is a strong starting point for the full-brain ambition, but its most important addition should be an explicit investigation of *parameter economy*. We want to discover not only how few transistors can reproduce neural dynamics, but how few independently controlled variables are needed to make a large population of those neurons useful.

That could ultimately matter more to whole-brain scaling than saving another 100 µm² from an individual LIF circuit.

> Interactive content unavailable: MemoryCite

* * *

**You:**

I think an important experiment we should include is hardcoding trim and other parameters and compare them to dynamically set values. If we can create neurons based on known characteristics and set them with those characteristics in the silicon design, that could significantly reduce the space and complexity of these variables. We would have to test for repeatability and quality of these preset neuron parameters but this could be a valuable solution for keeping analog neurons compact and I think it is an important addition to our experimental design.

* * *

**ChatGPT:**

I agree. This deserves to be a **primary experiment in the GF26c design**, because it directly tests whether we can eliminate much of the configuration circuitry required by large-scale analog neuromorphic hardware.

There is an important distinction, though: **hardcoding a neuron's intended physiological parameters is different from hardcoding its manufacturing trim.** The first is straightforward in principle. The second is more difficult because the manufacturing deviations do not exist until the chip is fabricated.

We should test both, but separately.

## 1. Three approaches to neuron parameterization

I would compare three physical implementations of the same LIF architecture.

**A. Hardcoded neuron**

Threshold, leak, reset, and other selected parameters are determined by transistor geometry, capacitor values, fixed ratios, and shared reference voltages. No individual digital configuration is required.

This is the candidate for minimum area.

---

**B. Programmable neuron**

The same nominal architecture, but selected parameters can be configured using digital controls and local analog switches or bias circuits.

This is our flexibility and calibration reference.

---

**C. Hybrid neuron**

Nominal physiological characteristics are physically fixed, but one or two small local trim controls compensate for manufacturing variation. Live modulation, where needed, uses shared controls.

This may be the best compromise for large-scale hardware.

The hybrid is particularly interesting. It allows a neuron to be manufactured for a known functional class without requiring a complete set of individually programmable parameters.

## 2. What can actually be hardcoded?

| Parameter | Physical implementation | Expected difficulty |
| --- | --- | --- |
| Membrane capacitance | Fixed MIM/MOS capacitor | Low |
| Nominal leak | Fixed transistor geometry or bias ratio | Moderate |
| Spike threshold | Fixed device ratios or reference | Moderate |
| Reset level | Fixed reference or transistor arrangement | Low–moderate |
| Adaptation strength | Fixed current ratios or transistor sizing | Moderate |
| Adaptation time constant | Fixed capacitor and conductance | Moderate |
| Dendritic axial coupling | Fixed conductance element | Moderate |
| Synaptic decay | Fixed capacitor/conductance ratio | Moderate |
| Synaptic weight | Fixed device sizing or capacitor ratio | Moderate–high |

The difficulty is that many analog parameters depend on transistor characteristics that vary with process and temperature.

For example, fixing a transistor's dimensions does not guarantee a precise leak conductance.

We should therefore distinguish between:

- **Hardcoded circuit geometry:** No individual programming, but actual behavior may vary.
- **Shared-bias hardcoding:** Fixed local geometry with a common adjustable reference.
- **Individually calibrated circuitry:** Additional per-neuron controls to correct deviations.

These can be compared experimentally.

## 3. The experiment I would add

I would introduce a dedicated **fixed-versus-programmable LIF test group**.

Proposed matched LIF comparison

| Variant | Instances | Purpose |
| --- | --- | --- |
| Fixed | 4 | Area and reproducibility |
| Shared bias | 4 | Population-wide correction |
| Hybrid trim | 4 | Minimal local calibration |
| Fully programmable | 2 | Accuracy and flexibility reference |

Proposed characterization group, not an addition that must be accommodated on top of every previously planned replica. We should reuse the existing small-capacitance LIF allocation where possible.

This would give us 14 physical implementations spanning four parameterization strategies.

I would initially use 200 fF for the primary matched comparison, because it may be easier to characterize than 50 fF. However, the 50 fF variants remain important for measuring minimum-area behavior.

Ideally, we would implement at least a few matched comparisons at 50 fF as well.

### What to measure

For each variant:

1. **Physical area:** Core area plus its local configuration and amortized shared infrastructure.
2. **Parameter accuracy:** How closely does the fabricated neuron match its intended threshold, time constant, and firing response?
3. **Repeatability:** How consistently does the same neuron behave across trials?
4. **Mismatch:** How much do nominally identical neurons differ?
5. **Temperature and supply sensitivity:** How stable are the preset characteristics?
6. **Calibration cost:** How much correction is needed, and how much circuitry does it require?
7. **Speed range:** Does fixing parameters restrict operation to a particular acceleration regime?

The most important metric may be the percentage of fixed neurons that fall within an acceptable tolerance without any individual calibration.

## 4. An important extension: hardcode multiple neuron classes

We should not only fabricate multiple copies of one preset.

We could fabricate neurons designed for different physiological characteristics.

For example:

| Preset class | Nominal time constant | Threshold | Intended behavior |
| --- | --- | --- | --- |
| Fast | 2 ms | Low | Rapid response |
| Medium | 10 ms | Medium | General LIF behavior |
| Slow | 30 ms | High | Strong temporal integration |

These are illustrative model classes, not universal biological neuron categories.

The question becomes whether changing a few physical dimensions can reliably produce meaningfully different neural behavior.

We can then compare the measured distribution of each preset class with its intended specification.

This is more directly relevant to manufacturing large numbers of neuron types than replicating only one configuration.

One subtlety: we should not change capacitance, threshold, and leak simultaneously in the first controlled experiment, because that would make it difficult to identify why one preset performs better or worse. Start with a single parameter sweep, then fabricate a small number of combined presets.

## 5. Hardcoding trim is a different challenge

We should be careful with the terminology.

A fixed transistor ratio can encode a *nominal* correction. But if a neuron has a random threshold offset caused by manufacturing mismatch, we cannot know the exact correction before fabrication.

Hardcoded trim is therefore most useful for:

- Compensating predictable systematic circuit offsets.
- Selecting a nominal neuron type.
- Reducing the number of runtime-configurable parameters.
- Applying shared corrections to a group of similarly designed neurons.

It cannot generally eliminate the need for post-fabrication calibration when random mismatch exceeds the application's tolerance.

There is a possible intermediate approach: fabricate a small set of fixed neuron variants and select the best-matching instances after testing.

That trades spare neuron area and selection circuitry for local trim circuitry. It may be worthwhile for some applications, but it is not automatically cheaper.

## 6. How this changes our chip priorities

I would add fixed-parameter design as a new major research axis, without abandoning the existing architectures.

| Priority | Experiment |
| --- | --- |
| P0 | Fixed versus shared-bias versus locally trimmed LIF |
| P0 | 50/200/800 fF capacitance sweep |
| P0 | Regenerative versus comparator LIF |
| P0 | Small-capacitance reproducibility |
| P0 | Digital LIF baseline |
| P1 | AdEx and continuous-time dendritic neurons |
| P1 | Switched-capacitor dendritic comparison |
| P1 | Different fixed physiological presets |
| P2 | Small network and additional replicas |
| P2 | Active dendritic nonlinearities |

I would make one further adjustment: **do not automatically treat hardcoding as eliminating every external control.**

A fixed-parameter neuron can still benefit from a shared operating-speed bias, provided the physical design supports it.

For example, a hardcoded neuron could have a fixed ratio between membrane capacitance and nominal leak conductance, while a global bias scales its absolute operating speed.

That would preserve some runtime flexibility without requiring individual parameter registers.

## 7. The full-brain scaling implication

Suppose a future system has billions of neurons divided into a manageable number of physiological classes.

Instead of storing a complete set of parameters for every neuron, we could manufacture a library of physically specialized neuron types.

Potential scalable architecture

Physiological neuron library

Fixed circuit designs for cell classes

↓

Fast LIF

Fixed parameters

Adaptive

Fixed parameters

Dendritic

Fixed parameters

↓

Shared global / cell-type controls

Speed, modulation, environmental compensation

The central research question becomes:

**How much biological variability can be represented through a library of fixed analog neuron types, and how much truly requires per-neuron programmability?**

That question connects our GF26c experiment directly to the full-brain ambition.

A fixed neuron might be substantially smaller than a programmable one, but only if its variability is acceptable. If the fixed design requires extensive redundancy, selection, or compensation, some of the area advantage disappears.

The chip should measure that tradeoff rather than assume the answer.

### My recommended next design change

I would revise the LIF matrix so that the existing replication budget explicitly includes fixed, shared-bias, hybrid, and fully programmable variants. We should not simply add 14 more neurons on top of the current plan.

The first SPICE study should compare those four implementations at matched nominal dynamics, then evaluate their area, mismatch, speed range, and calibration overhead.

**This is one of the strongest additions to our experimental plan so far.** It gives us a direct way to test whether manufacturing neurons with predefined characteristics can substantially reduce the hardware overhead of scaling analog neuromorphic systems.

* * *

**You:**

A short tangent that is not relevant to this design. Could we use technology like intel optane to solve this problem without introducing significant complexity. Suppose we run neurons outside of their normal operating ranges to heat them up and cool them at specific rate to program intel optane like parameters. This could solve the issue without adding significant complexity.

* * *

**ChatGPT:**

**Yes, in principle. What you're describing is a nonvolatile, physically programmable analog neuron, and it is a promising way to reduce per-neuron configuration storage.** There is already substantial research on using phase-change materials and other programmable resistive devices for neuromorphic computing.

Your idea has two parts:

1. Use a material whose electrical properties can be permanently or semi-permanently modified by heating and controlled cooling.
2. Integrate that material into a neuron so its conductance, threshold, or other parameters can be calibrated after fabrication without continuously powering a DAC or storing digital trim settings.

The first part is established technology. The second is feasible in principle, but whether it reduces *total* neuron area and complexity depends heavily on the programming circuitry and fabrication process.

The distinction is that we would not ordinarily heat the entire neuron. We would heat a **small programmable material element** integrated into the neuron, ideally using a short electrical pulse.

## How it would work inside an analog neuron

Imagine replacing the fixed leak conductance with a programmable phase-change element.

Input

PCM trim

Programmable leak

Membrane C

Soma

Write pulses

Conceptual only. A real circuit would need isolation between the high-energy programming path and the low-current membrane dynamics.

The programming procedure would be:

1. Measure the neuron's actual time constant or firing behavior.
2. Apply a programming pulse to the phase-change element.
3. Read its new conductance and remeasure the neuron.
4. Repeat until the desired behavior is reached.
5. Disconnect the programming circuit and operate the neuron normally.

The material stores the calibration physically, without requiring an SRAM register to retain the setting.

This has already been demonstrated at the memory-device level. A 2021 study programmed 512 embedded PCM cells to four conductance levels using iterative programming, although it also documented noise and drift. 

[PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8037667/?utm_source=chatgpt.com)

## The major obstacle: resistance range

For our small-capacitance LIF, the required conductances are extraordinarily low.

Using 

$$
C=50\text{ fF}
$$

 and 

$$
\tau=10\text{ ms}
$$

:

$$
g=\frac{C}{\tau}=5\text{ pS}
$$

That corresponds to:

$$
R=\frac{1}{g}=200\text{ G}\Omega
$$

A conventional PCM cell is not naturally designed to be a precisely controlled 200 GΩ resistor.

We could instead use PCM to set a bias in a transistor circuit, or combine it with a current mirror or transconductance stage. That is more realistic, but reintroduces some circuitry.

The advantage would be **nonvolatile calibration**, not necessarily eliminating every transistor associated with parameter control.

## Other technical challenges

| Challenge | Implication |
| --- | --- |
| Programming voltage/current | Requires circuitry much larger than the normal neuron currents |
| Analog precision | Intermediate resistance states can be noisy and difficult to set |
| Resistance drift | Neuron parameters may change after calibration |
| Temperature sensitivity | Heating elsewhere on the chip could change operating characteristics |
| Endurance | Repeated reprogramming eventually wears out devices |
| Fabrication | Phase-change materials require specialized process integration |

The fabrication issue is particularly significant. Standard GF180 CMOS does not provide an Optane-style phase-change memory element as a normal design-library component. We could simulate one, but we could not simply create it by drawing a custom transistor layout.

Also, deliberately overheating ordinary CMOS transistors would generally cause degradation rather than the controlled, reversible phase transitions of a PCM device.

### A potentially better alternative: resistive RAM

![Resistive Random Access Memory (ReRAM) | Tutorials on Electronics | Next Electronics](https://images.openai.com/static-rsc-4/2L9E2NqhXF5vhqpoRmcxcAVvjcZ8t6oG56xOATAOb75Ssvs__r50Dp7gHU4MY6f4W5FQD1EAAFbveWdp6Tj9byxLPyqkPlpj_29QrnJJessVCgr2ktdP0vvRkHDZBY1B_PurtlqbmRUHhaeaOnmdv3M1VEo_xicxAgLBVxxuLzw?purpose=inline) · **

> Interactive content unavailable: Entity

** uses changes in conductive pathways or interfaces in thin insulating films to store resistance states.

It can support analog conductance programming, potentially with simpler write mechanisms than melting and quenching a phase-change material. But it also faces variability, retention, endurance, and integration challenges. 

[PubMed Central (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC13609352/?utm_source=chatgpt.com)

Other technologies worth comparing include floating-gate analog memory, ferroelectric devices, and programmable transistor threshold structures. Each has different tradeoffs in density, precision, and fabrication compatibility.

## Would this actually help full-brain scaling?

Potentially, substantially.

If a nonvolatile analog element could replace a local DAC, calibration register, and associated switching circuitry, it could make a very large difference across billions of neurons.

But the correct comparison is not just the memory cell area.

$$
A_{\mathrm{effective}}
=
A_{\mathrm{memory}}
+
A_{\mathrm{access}}
+
A_{\mathrm{write/read}}
+
A_{\mathrm{amortized\ programming}}
$$

For example, if the high-voltage programming circuits can be shared across thousands of neurons, their amortized cost could become small. If every neuron needs a large individual programming transistor, the advantage could disappear.

There is another subtlety: Optane's extreme density came partly from its specialized memory-array structure. We should not assume that density transfers directly to isolated programmable analog elements embedded throughout neuron circuits.

## My assessment

I would distinguish three levels of feasibility.

Nonvolatile analog neuron calibration · (Demonstrated principles)

Analog conductance programming and nonvolatile memory are established. Applying them to neuron parameters is technically credible.

---

Very compact PCM-trimmed neurons · (Research opportunity)

The area savings depend on the memory device, programming topology, required precision, and drift tolerance.

---

Direct implementation in GF180 · (Not supported by standard PDK)

Would require a compatible memory process, additional fabrication steps, or a different technology platform.

**The most interesting part of your idea is the possibility of one-time physical calibration.** Manufacture a neuron with approximately correct characteristics, program one or two nonvolatile elements after fabrication, and then operate it for years without individual digital trim storage or continuous calibration power.

For a future chip, I would investigate **PCM, RRAM, and floating-gate trim elements** side by side, especially focusing on whether a tiny stored conductance can control a much smaller effective leak current through a transistor.

I would not add this to the current GF26c tapeout, consistent with your tangent. But as a longer-term research direction, it could be an important bridge between hardcoded neuron designs and fully programmable analog neurons.
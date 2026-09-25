# Quantum Coalition QSITE 2026 Challenge

Welcome to the Quantum Coalition's QSITE 2026 hackathon challenge! There are two tracks available. The first track will have you thinking like a quantum computer scientist by solving a routing problem relevant to NISQ hardware. The second track will get you thinking like a physicist by exploring how a quantum computer could be used to probe phases of matter.

---

##  Introducing the tracks

| | Computational Track | Scientific Track |
|---|---|---|
| **Topic** | Quantum circuit compilation | Quantum phase detection |
| **Core skill** | Graph algorithms, optimization | Quantum simulation, data analysis |
| **Output** | A `solve()` function | Phase diagrams + writeup |
| **Presentation** | 3–5 min demo | 5–7 min presentation |
| **Background needed** | CS (graphs, heuristics) | Physics or ML helpful, not required |

---

## Reading Order

### Computational Track

1. **`Computational Track/README.md`** - the full hacker handout. Read this first. Covers the compilation pipeline, hardware graph, and scoring formula in detail.
2. **`Computational Track/starter.ipynb`** - animated walkthrough. Opens with the hardware graph, then routes a real program step-by-step, explains where the baseline fails, and ends with a submission template.
3. **`Computational Track/starter_kit/`** - the minimum viable solution. All six modules are intentionally weak; your job is to beat them.

### Scientific Track

1. **`Scientific Track/README.md`** - the full hacker handout. Covers the ANNNI Hamiltonian, all four phases, phase detection approaches, the noise model, and the judging rubric.
2. **`Scientific Track/starter.ipynb`** - guided walkthrough. Builds the Hamiltonian, surveys all four phases, plots a clean 20×20 phase diagram with analytical boundaries overlaid, then demonstrates the noise model.
3. **`Scientific Track/starter_kit/`** - utility functions for building Hamiltonians, exact diagonalization, noise circuits, observables, reference boundaries, and plotting.

---

## Setup

Each track includes its own `uv` project so you can recreate the environment locally instead of depending on a prebuilt `venv`.

```bash
# install uv first if needed:
# https://docs.astral.sh/uv/getting-started/installation/
# If you are using conda:
conda install -c conda-forge uv

# clone the repo
git clone https://github.com/benmcdonough20/QSITE-2026-QuantumCoalition.git

# create the Computational Track environment (from root dir)
uv sync --project "Computational Track"

# within the root directory,
# create the Scientific Track environment
uv sync --project "Scientific Track"
```
Both track environments target Python 3.14. The Scientific Track environment pins PennyLane `0.44.1`.

To work on a track, the simplest option is to run Jupyter through `uv`:

```bash
uv run --project "Computational Track" jupyter lab "Computational Track/starter.ipynb"
uv run --project "Scientific Track" jupyter lab "Scientific Track/starter.ipynb"
```

If you prefer activation, `uv sync` creates a local `.venv` inside each track:

```bash
source "Computational Track/.venv/bin/activate"
jupyter lab "Computational Track/starter.ipynb"

source "Scientific Track/.venv/bin/activate"
jupyter lab "Scientific Track/starter.ipynb"
```

---

## Computational Track - Quick Summary

**The problem**: given a set of quantum programs and a 20-qubit hardware connectivity graph, find a qubit placement and SWAP routing strategy that executes all required two-qubit interactions using the fewest operations and parallel time steps.

**Scoring** (lower is better):
```
score = swap_count + 0.5 × depth
```

**What you implement**:
```python
def solve(program, hardware_graph):
    # Returns: (initial_placement: dict, routed_program: list[tuple])
```

The starter kit provides a scorer, six benchmark programs, a hardware graph, and three bad baselines to improve on.

---

## Scientific Track - Quick Summary

**The problem**: map the phase diagram of the 1D ANNNI model in the (κ, h) parameter plane using PennyLane. Then study how depolarizing noise distorts the phase boundaries.

**The model**:
```
H = -ΣZᵢZᵢ₊₁ + κΣZᵢZᵢ₊₂ - hΣXᵢ
```
Four phases: ferromagnetic, antiphase, paramagnetic, and floating.

**What you submit**: phase diagrams at p=0, p=0.01, p=0.05 (noise levels), a 2–3 page writeup, and a presentation.

**Phase detection approaches** (pick one or more):
- Order parameters via exact diagonalization or VQE
- Quantum convolutional neural network (QCNN, supervised)
- Quantum autoencoder (unsupervised)
- Fidelity susceptibility
- Trotterized time evolution

The starter kit provides the Hamiltonian builder, exact diagonalization, noisy circuit utilities, observables, analytical reference boundaries, and plotting helpers.

---

## External Resources

**Computational Track**
- [PostQuantum: Routing Quantum Information](https://postquantum.com/quantum-computing/routing-quantum-information/) - visual intro to SWAP routing
- [IBM SABRE Tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/transpilation-optimizations-with-sabre) - the industry-standard routing algorithm

**Scientific Track**
- [PennyLane: ANNNI Phase Detection Demo](https://pennylane.ai/qml/demos/tutorial_annni) - primary starting point; covers Hamiltonian, VQE, QCNN, and autoencoder approaches
- [PennyLane: A Noisy Heisenberg Model](https://pennylane.ai/challenges/heisenberg_model) - the noise model this track extends

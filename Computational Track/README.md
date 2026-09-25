# Challenge 1: Compiling for Quantum Computers

# Overview

> **You are given a set of quantum programs and a hardware connectivity graph. Your core job: find a qubit placement and SWAP routing strategy that executes all required interactions using the fewest SWAP operations and parallel time steps.**
>
> **For extra points**, optimize the gate decomposition and single-qubit gate layers - we provide intentionally bad baselines for both that are easy to beat.

The problem can be broken roughly into three sub-problems:

### 1. Placement

**Question**: which logical qubit goes on which physical qubit?

**Why it matters**: a good placement puts frequently-interacting logical qubits on nearby physical qubits, reducing the number of SWAPs needed. A bad placement puts them far apart.

**CS framing**: this is a **graph assignment** problem. You're mapping the nodes of one graph (your program's interaction pattern) onto the nodes of another graph (the hardware), trying to minimize some distance metric.

**Possible approaches**: random assignment, degree-matching heuristics, simulated annealing, exhaustive search on small instances.

### 2. Routing

**Question**: when two qubits need to interact but aren't adjacent, which SWAPs do you insert?

**Why it matters**: every SWAP adds cost. Greedy routing (always SWAP along the shortest path to the current gate) ignores the rest of the program - a SWAP that helps gate #5 might make gate #6 much harder.

**CS framing**: this is a **path planning** problem with a twist - every SWAP changes the state of the graph (qubit positions move), so future routing depends on past decisions.

**Possible approaches**: greedy shortest-path, look-ahead heuristics that consider upcoming gates, SABRE-style bidirectional search. See the [IBM SABRE tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/transpilation-optimizations-with-sabre) for a detailed walkthrough of the best known heuristic.

### 3. Scheduling

**Question**: which two-qubit operations can run at the same time?

**Why it matters**: running gates in parallel reduces the total circuit depth (execution time). Two 2-qubit gates can run simultaneously if they act on disjoint sets of qubits.

**CS framing**: this is a **DAG scheduling** / **bin packing** problem. Build a dependency graph of operations that respects both the original gate order and qubit conflicts, then assign operations to time slots such that no two operations in the same slot share a qubit.

**Possible approaches**: sequential execution (no parallelization), greedy layer packing, DAG-based topological scheduling.

---



## The Compilation Pipeline

```
Abstract Circuit
      ↓
  [Placement]        assign logical qubits to physical qubits       ⬅ CORE CHALLENGE
      ↓
  [Routing]          insert SWAPs so all 2Q gates are on neighbors   ⬅ CORE CHALLENGE
      ↓
  [Scheduling]       pack gates into parallel time steps              ⬅ CORE CHALLENGE
      ↓
  [Decomposition]    rewrite gates into hardware-native gate set     ⬅ STRETCH GOAL A
      ↓
  [1Q Optimization]  fuse/cancel redundant single-qubit gates        ⬅ STRETCH GOAL B
      ↓
Executable Circuit
```

## What You Receive

| Item | Description |
|---|---|
| **Hardware graph** | A 20-qubit connectivity graph (which physical qubits are wired together) |
| **Benchmark programs** | 5–8 quantum programs of increasing difficulty, as lists of two-qubit interactions |
| **Bad baselines** | Three intentionally terrible solutions you can immediately beat |
| **Scorer** | An autograder that checks correctness and computes your score |
| **Starter notebook** | Setup, examples, walkthrough, and submission template |

## What You Submit

1. A `solve(program, hardware_graph)` function that returns a placement and routed program
2. A 1–2 page writeup explaining your approach
3. A 3–5 minute demo/presentation

## How You're Scored

```
score = Σ_benchmarks [ swap_count + 0.5 × depth ]
```

## Essential Resources

- [PostQuantum: Routing Quantum Information](https://postquantum.com/quantum-computing/routing-quantum-information/) - visual intro to SWAP routing
- [IBM SABRE Tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/transpilation-optimizations-with-sabre) - the industry-standard routing algorithm explained
- [Python `networkx` docs](https://networkx.org/documentation/stable/) - graph algorithms you'll use heavily
- [PennyLane: Compilation of Quantum Circuits](https://pennylane.ai/qml/demos/tutorial_circuit_compilation)

---

# Introduction to the problem

## Delivery Routing Problem

Imagine you're a logistics planner. You have:

- A **street map** where buildings (qubits) are connected by roads (wires). Not every building connects to every other - most connect to only 2 or 3 neighbors.
- A **delivery list**: pairs of buildings that need to exchange packages. The exchanges must happen in a specific order.
- A **constraint**: you can only hand off a package between buildings that share a road.

If two buildings that need to exchange packages don't share a road, you have to **relay** the package through intermediate buildings - each relay is expensive and slow.

Your job: decide where to place your people (placement), how to relay packages when needed (routing), and which exchanges to run simultaneously (scheduling).

**That's the entire problem.** Replace "buildings" with "qubits," "roads" with "physical connections," "package exchange" with "two-qubit gate," and "relay" with "SWAP" - and you have quantum circuit compilation.

### Hardware Graph

Your "street map" is a **20-qubit heavy-hex-style teaching graph**. It looks like this:

```
    0 - 1 - 2 - 3
    |       |       
    4 - 5 - 6 - 7
        |       |   
    8 - 9 -10 -11
    |       |       
   12 -13 -14 -15
        |       |
   16 -17 -18 -19
```

Key properties:
- Each qubit connects to **1–3 neighbors** (nodes 3 and 16 are dead ends with a single connection; all other nodes have 2 or 3)
- There is **no direct connection** between most qubit pairs (e.g., qubit 0 and qubit 19 are 7 hops apart)
- A two-qubit gate can **only** execute between qubits that share an edge

In the starter notebook, this graph is built directly in code as a `networkx.Graph`. You can visualize it, query shortest paths, check adjacency, and test heuristics with standard NetworkX functions.

### What Is a SWAP gate?

A SWAP exchanges the quantum states of two adjacent qubits. After a SWAP between qubits A and B, the state that was in A is now in B, and vice versa.

**Why you need SWAPs**: if your program says "qubit 0 must interact with qubit 7" but they aren't neighbors, you need to move one of them closer by doing a chain of SWAPs along a path in the hardware graph.

### Walkthrough: Routing a Single Interaction

Suppose your program needs a two-qubit gate between logical qubits 0 and 3, and you've placed them on physical qubits 0 and 11:

```
Step 0 (initial):
    [L0] - 1  - 2  - 3
     |         |       
     4  - 5  - 6  - 7
          |         |   
     8  - 9  -10  -[L3]
```

Physical qubits 0 and 11 aren't adjacent. Shortest path: 0 → 1 → 2 → 6 → 7 → 11 (length 5).

We can SWAP L0 toward L3:

```
Step 1: SWAP(0, 1) - L0 moves from physical qubit 0 to physical qubit 1
     0  -[L0]- 2  - 3
     |         |       
     4  - 5  - 6  - 7
          |         |   
     8  - 9  -10  -[L3]

Step 2: SWAP(1, 2) - L0 moves to physical qubit 2
     0  - 1  -[L0]- 3
     |         |       
     4  - 5  - 6  - 7
          |         |   
     8  - 9  -10  -[L3]

Step 3: SWAP(2, 6) - L0 moves to physical qubit 6
     0  - 1  - 2  - 3
     |        |       
     4  - 5  -[L0]- 7
          |         |   
     8  - 9  -10  -[L3]

Step 4: SWAP(6, 7) - L0 moves to physical qubit 7
     0  - 1  - 2  - 3
     |         |       
     4  - 5  - 6  -[L0]
          |         |   
     8  - 9  -10  -[L3]

Step 5: Now L0 (physical 7) and L3 (physical 11) ARE adjacent!
        → Execute the two-qubit gate. Done.
```

That took **4 SWAPs**. A better initial placement (e.g., putting L0 and L3 on adjacent physical qubits) could have taken **0 SWAPs**. That's why placement matters.

## Quantum parallelization

For scoring purposes, the hardware works like this:

- **Single-qubit gates take zero time.** They're instant. Don't worry about them for scheduling.
- **Two-qubit gates** (including SWAPs) execute in **layers**. Each layer is one time step.
- Within a layer, you can run **any number of 2Q gates** - as long as they all act on **non-overlapping qubits** (no qubit appears in two gates in the same layer) and you do not violate the original program order.

### Example: Sequential vs. Parallel

Consider this routed program (all gates on adjacent qubits):

```
CNOT(0,1), CNOT(4,5), CNOT(1,2), CNOT(5,6), CNOT(2,6)
```

**Sequential scheduling** (no parallelism):
```
Layer 1: CNOT(0,1)
Layer 2: CNOT(4,5)
Layer 3: CNOT(1,2)
Layer 4: CNOT(5,6)
Layer 5: CNOT(2,6)
→ Depth = 5
```

**Parallel scheduling** (pack non-overlapping gates together):
```
Layer 1: CNOT(0,1) + CNOT(4,5)    ← qubits {0,1} and {4,5} don't overlap → OK
Layer 2: CNOT(1,2) + CNOT(5,6)    ← qubits {1,2} and {5,6} don't overlap → OK
Layer 3: CNOT(2,6)                  ← both qubits were used in layer 2 → new layer
→ Depth = 3
```

Same gates, same SWAPs, but **depth drops from 5 to 3** - a 40% improvement just from better scheduling.

---

# Scoring & Submission

## Scoring Formula - Worked Example

Your benchmark score is calculated as follows:

```
benchmark_score = (# SWAPS) × 1.0 + (circuit depth) × 0.5 
```

Your total core score is the sum across all benchmarks. A lower score is better.

## What "Correct" Means

A routed program is **correct** if:

1. Every two-qubit gate in the output acts on **adjacent physical qubits** (qubits that share an edge in the hardware graph)
2. If you strip out all the inserted SWAPs, the remaining operations match the **original program in order** (you haven't reordered, dropped, or added any program gates)
3. The qubit placement and SWAP tracking are **consistent** (after all SWAPs, every logical qubit's physical position is well-defined)

If any of these fail, that benchmark gets a score of **∞** (disqualified).

## Submission Format

Your core submission is a Python function:

```python
def solve(program, hardware_graph):
    """
    Args:
        program: list of tuples
            ("2Q", i, j) = two-qubit gate between logical qubits i and j
            ("1Q", i)    = single-qubit gate on logical qubit i
        hardware_graph: networkx.Graph
            Nodes are physical qubit indices, edges are connections

    Returns:
        initial_placement: dict
            Maps logical qubit index → physical qubit index
            e.g. {0: 5, 1: 6, 2: 9, 3: 10}
        routed_program: list of tuples
            Same format as input, but on PHYSICAL qubits,
            with ("SWAP", p, q) operations inserted as needed.
            Every ("2Q", p, q) must have (p,q) as an edge in hardware_graph.
    """
```

# Strategy Guide & Resources

## Key Resources

### For the Core Challenge
- 📖 [PostQuantum: Routing Quantum Information](https://postquantum.com/quantum-computing/routing-quantum-information/) - start here for the big picture
- 📖 [IBM SABRE Tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/transpilation-optimizations-with-sabre) - detailed walkthrough of the best known routing heuristic
- 🔧 [networkx: Shortest Paths](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html) - `nx.shortest_path()` is your best friend
- 🔧 [networkx: Graph Generators](https://networkx.org/documentation/stable/reference/generators.html) - if you want to test on other topologies

### For Stretch Goals
- 📖 [PennyLane: Compilation of Quantum Circuits](https://pennylane.ai/qml/demos/tutorial_circuit_compilation) - full walkthrough of gate cancellation, rotation merging, and decomposition
- 🔧 [PennyLane `qml.compile` docs](https://docs.pennylane.ai/en/stable/code/api/pennylane.compile.html) - one-liner compilation with configurable pipeline
- 🔧 [PennyLane `qml.transforms` reference](https://docs.pennylane.ai/en/stable/code/qml_transforms.html) - `cancel_inverses`, `merge_rotations`, `single_qubit_fusion`, `decompose`

### For Going Deep
- 📄 Li et al., "Tackling the Qubit Mapping Problem for NISQ-Era Quantum Devices" (ASPLOS 2019) - the original SABRE paper
- 📄 [RL-based transpilation (arXiv:2405.13196)](https://arxiv.org/abs/2405.13196) - reinforcement learning for SWAP selection
- 📄 [NASSC: Not All SWAPs Have the Same Cost (HPCA 2022)](https://hzhou.wordpress.ncsu.edu/files/2022/12/HPCA22_NASSC.pdf) - choosing SWAPs that enable downstream gate cancellation

## If You're Stuck

- **"My routing produces invalid output"** → print your routed program and check each 2Q gate: is it on an edge? Use `hardware_graph.has_edge(p, q)` to verify.
- **"My SWAP tracking is wrong"** → maintain a `placement` dict that you update after every SWAP. Print it frequently.
- **"I can't beat the baseline on the dense benchmarks"** → that's expected - dense programs need many SWAPs no matter what. Focus on placement optimization; even small improvements compound across many gates.
- **"I don't know where to start"** → implement the greedy baseline yourself (don't just use ours). Understanding *why* it's bad will give you ideas for improvement.

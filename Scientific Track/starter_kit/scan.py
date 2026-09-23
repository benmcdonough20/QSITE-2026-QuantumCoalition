"""(kappa, h, p) grid scan for the ANNNI phase diagrams.

p=0 goes through exact diagonalization -- exact, and orders of magnitude
cheaper than optimizing a noisy circuit to approximate a state we can just
diagonalize for. p>0 needs an actual noisy circuit, since depolarizing noise
only means something at the gate level. Each h-row is warm-started across
kappa (only the first point per row is a cold VQE run; the rest reuse the
previous point's converged params), and rows are independent, so they're
farmed out across worker processes.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
from itertools import product

import numpy as np
import pennylane as qml
from pennylane import numpy as pnp

from .annni import build_annni_hamiltonian
from .exact_diag import exact_ground_state

I2 = np.eye(2, dtype=np.complex128)
XMAT = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
ZMAT = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)

OBSERVABLE_KEYS = [
    "energy",
    "x_mean",
    "zz_nearest_mean",
    "zz_next_nearest_mean",
    "structure_factor_pi2",
    "antiphase_4point_mean",
]


@lru_cache(maxsize=None)
def _pauli_string_matrix(n_qubits: int, sites: tuple[int, ...], kind: str) -> np.ndarray:
    """Tensor product of `kind` ('x' or 'z') Pauli at `sites`, identity elsewhere."""
    base = XMAT if kind == "x" else ZMAT
    factors = [I2] * n_qubits
    for site in sites:
        factors[site] = base
    result = factors[0]
    for factor in factors[1:]:
        result = np.kron(result, factor)
    return result


def _expval(rho: np.ndarray, op: np.ndarray) -> float:
    return float(np.real(np.trace(rho @ op)))


def _to_density_matrix(state_or_rho: np.ndarray) -> np.ndarray:
    """Take either a state vector (exact diag) or a density matrix (noisy circuit)."""
    arr = np.asarray(state_or_rho)
    if arr.ndim == 1:
        return np.outer(arr, np.conj(arr))
    return arr


def extract_observables(state_or_rho: np.ndarray, n_qubits: int) -> dict[str, float]:
    """<X> for the paramagnet, <Z_i Z_i+1> for the ferro order, and two
    antiphase indicators: the S(pi/2) structure factor and the raw
    <Z_i Z_i+1 Z_i+2 Z_i+3> four-point string."""
    rho = _to_density_matrix(state_or_rho)
    x_vals = [_expval(rho, _pauli_string_matrix(n_qubits, (i,), "x")) for i in range(n_qubits)]

    zz_by_lag: dict[int, list[float]] = {}
    for i, j in product(range(n_qubits), repeat=2):
        if i == j:
            continue
        lag = (j - i) % n_qubits
        zz_by_lag.setdefault(lag, []).append(_expval(rho, _pauli_string_matrix(n_qubits, (i, j), "z")))
    zz_mean_by_lag = {lag: float(np.mean(vals)) for lag, vals in zz_by_lag.items()}

    structure_factor_pi2 = sum(
        zz_mean_by_lag.get(d, 0.0) * np.cos(np.pi / 2 * d) for d in range(1, n_qubits)
    ) / n_qubits

    four_point_sites = [
        (i, (i + 1) % n_qubits, (i + 2) % n_qubits, (i + 3) % n_qubits) for i in range(n_qubits)
    ]
    four_point_vals = [_expval(rho, _pauli_string_matrix(n_qubits, sites, "z")) for sites in four_point_sites]

    return {
        "x_mean": float(np.mean(x_vals)),
        "zz_nearest_mean": zz_mean_by_lag.get(1, 0.0),
        "zz_next_nearest_mean": zz_mean_by_lag.get(2, 0.0),
        "structure_factor_pi2": float(structure_factor_pi2),
        "antiphase_4point_mean": float(np.mean(four_point_vals)),
    }


def noisy_ansatz(params, n_qubits: int, p: float) -> None:
    """Layered RY + CNOT-ring ansatz; DepolarizingChannel(p) after each CNOT target."""
    layers = params.shape[0]
    for layer in range(layers):
        for wire in range(n_qubits):
            qml.RY(params[layer, wire], wires=wire)
        for wire in range(n_qubits):
            target = (wire + 1) % n_qubits
            qml.CNOT(wires=[wire, target])
            if p > 0:
                qml.DepolarizingChannel(p, wires=target)


def optimize_point(
    kappa: float,
    h: float,
    p: float,
    n_qubits: int = 8,
    layers: int = 3,
    steps: int = 30,
    stepsize: float = 0.1,
    init_params: np.ndarray | None = None,
    seed: int = 0,
) -> dict[str, object]:
    """Run noisy VQE at one (kappa, h, p) point. Pass `init_params` to warm-start
    from a previous point's converged params instead of a random start.

    Top-level function on purpose -- ProcessPoolExecutor needs to pickle it.
    """
    dev = qml.device("default.mixed", wires=n_qubits)
    hamiltonian = build_annni_hamiltonian(n_qubits=n_qubits, kappa=kappa, h=h)

    @qml.qnode(dev, diff_method="backprop")
    def cost(params):
        noisy_ansatz(params, n_qubits, p)
        return qml.expval(hamiltonian)

    @qml.qnode(dev)
    def density_matrix(params):
        noisy_ansatz(params, n_qubits, p)
        return qml.density_matrix(wires=range(n_qubits))

    if init_params is None:
        rng = np.random.default_rng(seed)
        params = pnp.array(rng.uniform(0, 2 * np.pi, size=(layers, n_qubits)), requires_grad=True)
    else:
        params = pnp.array(np.asarray(init_params), requires_grad=True)

    opt = qml.AdamOptimizer(stepsize=stepsize)
    energy = None
    for _ in range(steps):
        params, energy = opt.step_and_cost(cost, params)

    rho = np.array(density_matrix(params))
    observables = extract_observables(rho, n_qubits)
    return {
        "kappa": kappa,
        "h": h,
        "p": p,
        "energy": float(energy),
        "params": np.array(params),
        **observables,
    }


def warm_started_row(
    kappa_row: list[float],
    h: float,
    p: float,
    n_qubits: int = 8,
    layers: int = 3,
    first_steps: int = 30,
    warm_steps: int = 6,
    stepsize: float = 0.1,
    seed: int = 0,
) -> list[dict[str, object]]:
    """Sweep `kappa_row` at fixed h, warm-starting each point from the last."""
    results = []
    init_params = None
    for i, kappa in enumerate(kappa_row):
        steps = first_steps if i == 0 else warm_steps
        res = optimize_point(
            kappa, h, p, n_qubits=n_qubits, layers=layers, steps=steps,
            stepsize=stepsize, init_params=init_params, seed=seed,
        )
        init_params = res.pop("params")
        results.append(res)
    return results


def run_exact_grid_scan(kappas: np.ndarray, hs: np.ndarray, n_qubits: int = 8) -> dict[str, np.ndarray]:
    """The p=0 diagram, straight from exact diagonalization."""
    grids = {k: np.zeros((len(hs), len(kappas))) for k in OBSERVABLE_KEYS}
    for row, h in enumerate(hs):
        for col, kappa in enumerate(kappas):
            res = exact_ground_state(n_qubits=n_qubits, kappa=float(kappa), h=float(h), periodic=True)
            observables = extract_observables(res["state"], n_qubits)
            grids["energy"][row, col] = res["ground_energy"]
            for k, v in observables.items():
                grids[k][row, col] = v
    return grids


def run_noisy_grid_scan(
    kappas: np.ndarray,
    hs: np.ndarray,
    p: float,
    n_qubits: int = 8,
    layers: int = 3,
    first_steps: int = 30,
    warm_steps: int = 6,
    stepsize: float = 0.1,
    workers: int | None = None,
    seed: int = 0,
) -> dict[str, np.ndarray]:
    """A p>0 diagram: one warm-started VQE row per h, farmed out over `workers`
    processes. Uses ProcessPoolExecutor, so on Windows this needs to run from
    a notebook cell or an `if __name__ == "__main__":` guard."""
    workers = workers or min(len(hs), os.cpu_count() or 1)
    grids = {k: np.zeros((len(hs), len(kappas))) for k in OBSERVABLE_KEYS}

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                warm_started_row, list(kappas), float(h), p, n_qubits, layers,
                first_steps, warm_steps, stepsize, seed,
            ): row_idx
            for row_idx, h in enumerate(hs)
        }
        for future in as_completed(futures):
            row_idx = futures[future]
            row_results = future.result()
            for col_idx, point in enumerate(row_results):
                for k in OBSERVABLE_KEYS:
                    grids[k][row_idx, col_idx] = point[k]

    return grids

"""Starter-kit utilities for the scientific track."""

from .annni import build_annni_hamiltonian
from .exact_diag import exact_ground_state
from .noise_utils import noisy_entangling_layer, simple_noisy_energy
from .observables import order_parameter_summary
from .plotting import animate_linecut, plot_coupling_graph, plot_observable_heatmap
from .reference import bkt_transition, ising_transition, kt_transition

__all__ = [
    "animate_linecut",
    "build_annni_hamiltonian",
    "bkt_transition",
    "exact_ground_state",
    "ising_transition",
    "kt_transition",
    "noisy_entangling_layer",
    "order_parameter_summary",
    "plot_coupling_graph",
    "plot_observable_heatmap",
    "simple_noisy_energy",
]
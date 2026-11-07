# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""sipi — signal- and power-integrity analysis of PCB interconnects.

    from sipi import CrossSection, Layer, Trace
    cs = CrossSection(
        layers=[Layer("FR-4", 0.2e-3, eps_r=4.3, tan_delta=0.02),
                Layer("air", 2e-3)],
        traces=[Trace("sig", x=0.0, width=0.35e-3, y=0.2e-3, thickness=35e-6)],
        width=6e-3)
    p = cs.analyze()
    p.z0, p.eps_eff, p.L, p.C, p.G(1e9)

Signal integrity: quasi-static (quasi-TEM) cross-sections give the
per-unit-length capacitance, inductance and dielectric conductance matrices,
single-line impedance and effective permittivity, and coupled-line modes.
Uniform-line S-parameters accept explicit RLGC.

Power integrity: ``PowerPlane`` solves the DC voltage drop (IR drop) on a
copper plane fed by voltage sources and loaded by current sinks.

High-frequency conductor loss is available in ``sipi.conductor`` with explicit
skin-depth and mesh validity checks.
Finite-metal current diffusion is available in ``sipi.conductor_diffusion``.
Distributed AC power-plane impedance and 3D structures are not implemented.
"""

from .crosssection import CrossSection, Layer, MeshedCrossSection, Trace
from .aperture import CircularAperture, ApertureDocument
from .aperture_section import RoundConductor, EllipticalAperture, MeshedAperture, ApertureSectionDocument
from .aperture_study import (ApertureStudyDocument, CapacitanceStudy, CapacitanceStudyRow,
                             ApertureDesignDocument, CapacitanceDesign, CapacitanceEvaluation, CapacitanceGoalError)
from .polygons import PolygonTrace, DielectricRegion
from .document import CrossSectionDocument
from .templates import microstrip, stripline, coupled_microstrip, grounded_coplanar
from .templates import asymmetric_coupled_microstrip
from .templates import coupled_grounded_coplanar
from .templates import coupled_coated_microstrip
from .templates import coated_grounded_coplanar, coupled_coated_grounded_coplanar
from .templates import unbacked_coplanar, coupled_unbacked_coplanar
from .templates import coated_unbacked_coplanar, coupled_coated_unbacked_coplanar
from .templates import conformal_coated_microstrip, coupled_conformal_coated_microstrip
from .templates import conformal_coated_grounded_coplanar, coupled_conformal_coated_grounded_coplanar
from .templates import conformal_coated_unbacked_coplanar, coupled_conformal_coated_unbacked_coplanar
from .templates import layered_stripline, coupled_layered_stripline
from .design import DesignEvaluation, ImpedanceDesign, GoalSeekError, seek_impedance
from .design_document import ImpedanceDesignDocument
from .plane import (COPPER_CONDUCTIVITY, IRDropResult, PowerPlane, Sink, Source, circle, edge,
                    rectangle_outline)
from .quasistatic import LineParameters, capacitance_matrix, line_parameters

from .network import LineNetwork, rlgc_network, quasistatic_network
from .lumped import lumped_network, LumpedNetworkDocument
from .connection import cascade_networks, deembed_network, connect_networks, ideal_junction
from .propagation import LinePropagation, rlgc_propagation
from .characteristic import LineCharacteristic, rlgc_characteristic
from .modes import LineModes, ModeTrackingError, rlgc_modes
from .termination import terminate_ports
from .network_document import NetworkTransformDocument, NetworkTransformResult
from .assembly_document import NetworkAssemblyDocument, NetworkAssemblyResult

__version__ = "0.1.0"
__all__ = ["CircularAperture", "ApertureDocument",
           "RoundConductor", "EllipticalAperture", "MeshedAperture", "ApertureSectionDocument",
           "ApertureStudyDocument", "CapacitanceStudy", "CapacitanceStudyRow",
           "ApertureDesignDocument", "CapacitanceDesign", "CapacitanceEvaluation", "CapacitanceGoalError",
           "CrossSection", "Layer", "Trace", "PolygonTrace", "DielectricRegion", "MeshedCrossSection", "LineParameters",
           "LineNetwork", "rlgc_network", "quasistatic_network",
           "lumped_network", "LumpedNetworkDocument",
           "cascade_networks", "deembed_network", "connect_networks", "ideal_junction",
           "LinePropagation", "rlgc_propagation",
           "LineCharacteristic", "rlgc_characteristic",
           "LineModes", "ModeTrackingError", "rlgc_modes",
           "terminate_ports",
           "NetworkTransformDocument", "NetworkTransformResult",
           "NetworkAssemblyDocument", "NetworkAssemblyResult",
           "capacitance_matrix", "line_parameters", "CrossSectionDocument",
           "microstrip", "stripline", "coupled_microstrip", "grounded_coplanar",
           "asymmetric_coupled_microstrip",
           "coupled_grounded_coplanar",
           "coupled_coated_microstrip",
           "coated_grounded_coplanar", "coupled_coated_grounded_coplanar",
           "unbacked_coplanar", "coupled_unbacked_coplanar",
           "coated_unbacked_coplanar", "coupled_coated_unbacked_coplanar",
           "conformal_coated_microstrip", "coupled_conformal_coated_microstrip",
           "conformal_coated_grounded_coplanar", "coupled_conformal_coated_grounded_coplanar",
           "conformal_coated_unbacked_coplanar", "coupled_conformal_coated_unbacked_coplanar",
           "layered_stripline", "coupled_layered_stripline",
           "DesignEvaluation", "ImpedanceDesign", "GoalSeekError", "seek_impedance",
           "ImpedanceDesignDocument",
           "PowerPlane", "Source", "Sink", "IRDropResult", "circle", "edge", "rectangle_outline",
           "COPPER_CONDUCTIVITY", "__version__"]

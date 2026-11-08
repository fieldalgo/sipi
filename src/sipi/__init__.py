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
Bounded static 3D capacitance is available in ``sipi.capacitance3d``.
Bounded homogeneous Maxwell fields with local TEM-admittance ports are
available in ``sipi.ports3d``; this is not a full multimode port model.
Distributed AC power-plane impedance and full 3D interconnect transitions are not implemented.
"""

from .volume_grid_strip import VolumeGridStripCell, VolumeGridStripCapacitance, volume_grid_strip_cell, extract_volume_grid_strip_capacitance
from .thick_grid_strip import ThickGridStripCell, ThickGridStripCapacitance, thick_grid_strip_cell, extract_thick_grid_strip_capacitance
from .partitioned_capacitance import extract_partitioned_capacitance_3d
from .crosssection import CrossSection, Layer, MeshedCrossSection, Trace
from .aperture import CircularAperture, ApertureDocument
from .aperture_section import RoundConductor, EllipticalAperture, MeshedAperture, ApertureSectionDocument
from .aperture_study import (ApertureStudyDocument, CapacitanceStudy, CapacitanceStudyRow,
                             ApertureDesignDocument, CapacitanceDesign, CapacitanceEvaluation, CapacitanceGoalError)
from .polygons import PolygonTrace, DielectricRegion
from .document import CrossSectionDocument
from .templates import microstrip, stripline, coupled_microstrip, grounded_coplanar
from .conductivity_profile import GaussianConductivityProfile, ConductivityProfileResult
from .conductivity_profile_document import ConductivityProfileDocument
from .templates import asymmetric_coupled_microstrip
from .templates import asymmetric_coupled_stripline
from .templates import asymmetric_coupled_layered_stripline
from .templates import asymmetric_coupled_grounded_coplanar
from .templates import asymmetric_coupled_unbacked_coplanar
from .templates import asymmetric_coupled_coated_grounded_coplanar
from .templates import asymmetric_coupled_layered_coplanar_stripline
from .templates import asymmetric_coupled_coplanar_stripline
from .templates import coupled_grounded_coplanar
from .templates import coupled_coated_microstrip
from .templates import coated_grounded_coplanar, coupled_coated_grounded_coplanar
from .templates import unbacked_coplanar, coupled_unbacked_coplanar
from .templates import coated_unbacked_coplanar, coupled_coated_unbacked_coplanar
from .templates import conformal_coated_microstrip, coupled_conformal_coated_microstrip
from .templates import conformal_coated_grounded_coplanar, coupled_conformal_coated_grounded_coplanar
from .templates import conformal_coated_unbacked_coplanar, coupled_conformal_coated_unbacked_coplanar
from .templates import layered_stripline, coupled_layered_stripline
from .templates import layered_broadside_stripline
from .templates import coplanar_stripline, coupled_coplanar_stripline
from .templates import layered_coplanar_stripline, coupled_layered_coplanar_stripline
from .pair_design_document import PairImpedanceDesignDocument
from .sampled_design import (SampledImpedanceEvaluation, SampledImpedanceDesign,
                             SampledImpedanceGoalError, seek_sampled_impedance)
from .sampled_design_document import SampledImpedanceDesignDocument
from .startup import LosslessLineResponse, lossless_line_response
from .startup_document import LosslessStartupDocument
from .rlgc_startup_document import RLGCLadderDocument
from .rlgc_startup import RLGCLadderResponse, rlgc_ladder_response
from .coupled_startup import CoupledRLGCLadderResponse, coupled_rlgc_ladder_response
from .coupled_startup_document import CoupledRLGCLadderDocument
from .coupled_boundary_startup import MixedBoundaryRLGCLadderResponse, coupled_boundary_ladder_response
from .coupled_boundary_startup_document import MixedBoundaryRLGCLadderDocument
from .coupled_capacitive_startup import CapacitiveRLGCLadderResponse, coupled_capacitive_ladder_response
from .coupled_capacitive_startup_document import CapacitiveRLGCLadderDocument
from .coupled_reactive_startup import ReactiveRLGCLadderResponse, coupled_reactive_ladder_response
from .coupled_reactive_startup_document import ReactiveRLGCLadderDocument
from .startup_waves import StartupPortWaves, startup_port_waves
from .startup_waves_document import StartupPortWavesDocument
from .norton_startup import NortonReactiveRLGCLadderResponse, coupled_norton_reactive_ladder_response
from .norton_startup_document import NortonReactiveRLGCLadderDocument
from .mixed_startup import MixedSourceRLGCLadderResponse, coupled_mixed_source_ladder_response
from .mixed_startup_document import MixedSourceRLGCLadderDocument
from .debye_startup import DebyeRLGCLadderResponse, debye_rlgc_ladder_response
from .debye_startup_document import DebyeRLGCLadderDocument
from .coupled_debye_startup import CoupledDebyeRLGCLadderResponse, coupled_debye_rlgc_ladder_response
from .psd_debye_startup import PSDCoupledDebyeRLGCLadderResponse, psd_coupled_debye_rlgc_ladder_response
from .psd_debye_startup_document import PSDCoupledDebyeRLGCLadderDocument
from .debye_capacitive_startup import DebyeCapacitiveLadderResponse, psd_coupled_debye_capacitive_ladder_response
from .debye_capacitive_startup_document import DebyeCapacitiveLadderDocument
from .debye_reactive_startup import DebyeReactiveLadderResponse, psd_coupled_debye_reactive_ladder_response
from .debye_reactive_startup_document import DebyeReactiveLadderDocument
from .coupled_debye_startup_document import CoupledDebyeRLGCLadderDocument
from .pair_design import (PairImpedanceEvaluation, PairImpedanceDesign,
                          PairImpedanceGoalError, seek_pair_impedances)
from .design import DesignEvaluation, ImpedanceDesign, GoalSeekError, seek_impedance
from .design_document import ImpedanceDesignDocument
from .plane import (COPPER_CONDUCTIVITY, IRDropResult, PowerPlane, Sink, Source, circle, edge,
                    rectangle_outline)
from .quasistatic import LineParameters, capacitance_matrix, line_parameters

from .network import LineNetwork, rlgc_network, quasistatic_network
from .periodic import PeriodicResponse, PeriodicImpulse, periodic_response, periodic_impulse
from .periodic_termination import PeriodicTerminatedResponse, periodic_terminated_response
from .lumped import lumped_network, LumpedNetworkDocument
from .connection import cascade_networks, deembed_network, connect_networks, ideal_junction
from .propagation import LinePropagation, rlgc_propagation
from .characteristic import LineCharacteristic, rlgc_characteristic
from .modes import LineModes, ModeTrackingError, rlgc_modes
from .termination import terminate_ports
from .norton_termination import NortonTerminatedNetwork, terminate_norton_network
from .periodic_norton import PeriodicNortonResponse, periodic_norton_response
from .mixed_termination import MixedTerminatedNetwork, terminate_mixed_network
from .periodic_mixed import PeriodicMixedResponse, periodic_mixed_response
from .network_document import NetworkTransformDocument, NetworkTransformResult
from .assembly_document import NetworkAssemblyDocument, NetworkAssemblyResult

__version__ = "0.1.0"
from .multiconductor_startup import MulticonductorRLGCLadderResponse, multiconductor_rlgc_ladder_response

from .multiconductor_startup_document import MulticonductorRLGCLadderDocument

from .grid_plate import GridPlateCell, GridPlateCapacitance, grid_plate_cell, extract_grid_plate_capacitance

from .grid_plate_document import GridPlateCapacitanceDocument

from .parameter_network import impedance_network, admittance_network

from .strip_grid import StripGridCell, StripGridCapacitance, strip_grid_cell, extract_strip_grid_capacitance

from .strip_grid_document import StripGridCapacitanceDocument
from .thick_grid_strip_document import ThickGridStripCapacitanceDocument
from .volume_grid_strip_document import VolumeGridStripCapacitanceDocument

__all__ = [
    'MulticonductorDebyeReactiveLadderDocument',
    'MulticonductorDebyeReactiveLadderResponse',
    'psd_multiconductor_debye_reactive_ladder_response',
    'MulticonductorDebyeCapacitiveLadderDocument',
    'MulticonductorDebyeCapacitiveLadderResponse',
    'psd_multiconductor_debye_capacitive_ladder_response',
    'PSDMulticonductorDebyeRLGCLadderDocument',
    'PSDMulticonductorDebyeRLGCLadderResponse',
    'psd_multiconductor_debye_rlgc_ladder_response',
    'MulticonductorDebyeRLGCLadderDocument',
    'MulticonductorDebyeRLGCLadderResponse', 'multiconductor_debye_rlgc_ladder_response','hybrid_network','inverse_hybrid_network','VolumeGridPairCapacitanceDocument','VolumeGridPairCell','VolumeGridPairCapacitance','volume_grid_pair_cell','extract_volume_grid_pair_capacitance','VolumeGridStripCapacitanceDocument', 'VolumeGridStripCell', 'VolumeGridStripCapacitance', 'volume_grid_strip_cell', 'extract_volume_grid_strip_capacitance', 'extract_partitioned_capacitance_3d', 'ThickGridStripCapacitanceDocument', 'ThickGridStripCell', 'ThickGridStripCapacitance', 'thick_grid_strip_cell', 'extract_thick_grid_strip_capacitance', "StripGridCapacitanceDocument", "StripGridCell", "StripGridCapacitance", "strip_grid_cell", "extract_strip_grid_capacitance", "impedance_network", "admittance_network", "GridPlateCapacitanceDocument", "GridPlateCell", "GridPlateCapacitance", "grid_plate_cell", "extract_grid_plate_capacitance", "MulticonductorRLGCLadderDocument", "MulticonductorRLGCLadderResponse", "multiconductor_rlgc_ladder_response",
'DebyeReactiveLadderDocument', 'DebyeReactiveLadderResponse', 'psd_coupled_debye_reactive_ladder_response', 'DebyeCapacitiveLadderDocument', 'DebyeCapacitiveLadderResponse', 'psd_coupled_debye_capacitive_ladder_response', 'PSDCoupledDebyeRLGCLadderDocument', 'PSDCoupledDebyeRLGCLadderResponse', 'psd_coupled_debye_rlgc_ladder_response', 'CoupledDebyeRLGCLadderDocument', 'CoupledDebyeRLGCLadderResponse', 'coupled_debye_rlgc_ladder_response', 'DebyeRLGCLadderDocument', 'DebyeRLGCLadderResponse', 'debye_rlgc_ladder_response', 'MixedSourceRLGCLadderDocument', 'MixedSourceRLGCLadderResponse', 'coupled_mixed_source_ladder_response', 'NortonReactiveRLGCLadderDocument', 'NortonReactiveRLGCLadderResponse', 'coupled_norton_reactive_ladder_response', 'StartupPortWavesDocument', 'StartupPortWaves', 'startup_port_waves', 'ReactiveRLGCLadderDocument', 'ReactiveRLGCLadderResponse', 'coupled_reactive_ladder_response', 'CapacitiveRLGCLadderDocument', 'CapacitiveRLGCLadderResponse', 'coupled_capacitive_ladder_response', 'MixedBoundaryRLGCLadderDocument', 'MixedBoundaryRLGCLadderResponse', 'coupled_boundary_ladder_response', 'CoupledRLGCLadderDocument', 'CoupledRLGCLadderResponse', 'coupled_rlgc_ladder_response', 'RLGCLadderDocument', 'RLGCLadderResponse', 'rlgc_ladder_response', 'LosslessStartupDocument', 'LosslessLineResponse', 'lossless_line_response', 'SampledImpedanceDesignDocument', 'SampledImpedanceEvaluation', 'SampledImpedanceDesign', 'SampledImpedanceGoalError', 'seek_sampled_impedance',
           'PairImpedanceDesignDocument', 'PairImpedanceEvaluation', 'PairImpedanceDesign', 'PairImpedanceGoalError', 'seek_pair_impedances', "GaussianConductivityProfile", "ConductivityProfileResult", "ConductivityProfileDocument",
           "CircularAperture", "ApertureDocument",
           "RoundConductor", "EllipticalAperture", "MeshedAperture", "ApertureSectionDocument",
           "ApertureStudyDocument", "CapacitanceStudy", "CapacitanceStudyRow",
           "ApertureDesignDocument", "CapacitanceDesign", "CapacitanceEvaluation", "CapacitanceGoalError",
           "CrossSection", "Layer", "Trace", "PolygonTrace", "DielectricRegion", "MeshedCrossSection", "LineParameters",
           "LineNetwork", "rlgc_network", "quasistatic_network",
           "PeriodicResponse", "PeriodicImpulse", "periodic_response", "periodic_impulse",
           "PeriodicTerminatedResponse", "periodic_terminated_response",
           "lumped_network", "LumpedNetworkDocument",
           "cascade_networks", "deembed_network", "connect_networks", "ideal_junction",
           "LinePropagation", "rlgc_propagation",
           "LineCharacteristic", "rlgc_characteristic",
           "LineModes", "ModeTrackingError", "rlgc_modes",
           "terminate_ports",
           "NortonTerminatedNetwork", "terminate_norton_network",
           "PeriodicNortonResponse", "periodic_norton_response",
           "MixedTerminatedNetwork", "terminate_mixed_network",
           "PeriodicMixedResponse", "periodic_mixed_response",
           "NetworkTransformDocument", "NetworkTransformResult",
           "NetworkAssemblyDocument", "NetworkAssemblyResult",
           "capacitance_matrix", "line_parameters", "CrossSectionDocument",
           "microstrip", "stripline", "coupled_microstrip", "grounded_coplanar",
           "asymmetric_coupled_microstrip",
           "asymmetric_coupled_stripline",
           "asymmetric_coupled_layered_stripline",
           "asymmetric_coupled_grounded_coplanar",
           "asymmetric_coupled_unbacked_coplanar",
           "asymmetric_coupled_coated_grounded_coplanar",
           "asymmetric_coupled_coplanar_stripline",
           "asymmetric_coupled_layered_coplanar_stripline",
           "coupled_grounded_coplanar",
           "coupled_coated_microstrip",
           "coated_grounded_coplanar", "coupled_coated_grounded_coplanar",
           "unbacked_coplanar", "coupled_unbacked_coplanar",
           "coated_unbacked_coplanar", "coupled_coated_unbacked_coplanar",
           "conformal_coated_microstrip", "coupled_conformal_coated_microstrip",
           "conformal_coated_grounded_coplanar", "coupled_conformal_coated_grounded_coplanar",
           "conformal_coated_unbacked_coplanar", "coupled_conformal_coated_unbacked_coplanar",
           "layered_stripline", "coupled_layered_stripline",
           "layered_broadside_stripline",
           "coplanar_stripline", "coupled_coplanar_stripline",
           "layered_coplanar_stripline", "coupled_layered_coplanar_stripline",
           "DesignEvaluation", "ImpedanceDesign", "GoalSeekError", "seek_impedance",
           "ImpedanceDesignDocument",
           "PowerPlane", "Source", "Sink", "IRDropResult", "circle", "edge", "rectangle_outline",
           "COPPER_CONDUCTIVITY", "__version__"]

from .volume_grid_pair import (VolumeGridPairCell, VolumeGridPairCapacitance,
                               volume_grid_pair_cell, extract_volume_grid_pair_capacitance)

from .volume_grid_pair_document import VolumeGridPairCapacitanceDocument

from .hybrid_parameters import hybrid_network, inverse_hybrid_network

from .multiconductor_debye_startup import MulticonductorDebyeRLGCLadderResponse, multiconductor_debye_rlgc_ladder_response

from .multiconductor_debye_startup_document import MulticonductorDebyeRLGCLadderDocument

from .psd_multiconductor_debye_startup import PSDMulticonductorDebyeRLGCLadderResponse, psd_multiconductor_debye_rlgc_ladder_response

from .psd_multiconductor_debye_startup_document import PSDMulticonductorDebyeRLGCLadderDocument

from .multiconductor_debye_capacitive_startup import MulticonductorDebyeCapacitiveLadderResponse, psd_multiconductor_debye_capacitive_ladder_response

from .multiconductor_debye_capacitive_startup_document import MulticonductorDebyeCapacitiveLadderDocument

from .multiconductor_debye_reactive_startup import MulticonductorDebyeReactiveLadderResponse, psd_multiconductor_debye_reactive_ladder_response

from .multiconductor_debye_reactive_startup_document import MulticonductorDebyeReactiveLadderDocument

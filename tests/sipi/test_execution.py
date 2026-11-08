# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved transport contract, direct API parity and retained physical failures."""
import json

import numpy as np
import pytest

from sipi import (CrossSectionDocument, microstrip, ApertureDocument, CircularAperture,
    ApertureSectionDocument, EllipticalAperture, RoundConductor, ApertureStudyDocument,
    ApertureDesignDocument, ImpedanceDesignDocument, LumpedNetworkDocument,
    NetworkAssemblyDocument, NetworkTransformDocument, LineNetwork, GoalSeekError,
    CapacitanceGoalError)
from sipi.execution import normalize_saved, execute_saved, saved_schemas
from sipi.study import ImpedanceStudyDocument
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument
from sipi.circuit_document import CircuitDocument
from sipi.dielectric import ConstantDielectric
from sipi.dielectric_fit import DebyeFitDocument
from sipi.line_goal_document import LineQuantityDesignDocument
from sipi.line_study import LineQuantityStudyDocument


def cross():
    return CrossSectionDocument(microstrip(width=.4e-3, substrate_height=.5e-3,
        thickness=.1e-3, eps_r=4, tan_delta=.02, air_height=.5e-3, box_width=2e-3),
        mesh=dict(edge_size=20e-6, far_size=.2e-3, grade=.2))


def aperture():
    return ApertureSectionDocument(EllipticalAperture(.8e-3, .8e-3,
        [RoundConductor('s', .28e-3)], eps_r=3.96), mesh=dict(size=40e-6, angular_divisions=64))


def lumped():
    return LumpedNetworkDocument([0, 1e9], resistance=10., inductance=2e-9)


def source():
    return dict(kind='lumped-network', document=lumped().to_dict())


def studies():
    sampling = dict(kind='sweep', count=2, variables=[dict(name='eps_r', lower=3., upper=5.)])
    return [ImpedanceStudyDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3, eps_r=4.),
        sampling=sampling, quantity='z0', mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.15)),
        ApertureStudyDocument(aperture(), sampling=sampling)]


def goals():
    return [ImpedanceDesignDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3, eps_r=4.),
        variable='width', bounds=[.3e-3, .8e-3], target=50., tolerance=.5,
        mesh=dict(edge_size=1e-6, far_size=.125e-3, grade=.075)),
        ApertureDesignDocument(aperture(), variable='conductor_0_diameter',
            bounds=[.2e-3, .35e-3], target=200e-12, tolerance=2e-12)]


def line(volume=False, *, dc=False):
    f = [0, 1e3] if dc else [1e3, 2e3]
    if volume:
        return VolumeLineDocument(CrossSectionDocument(cross().section), f, materials={}, conductivity=58e6, length=.1,
            mesh=dict(ground_thickness=.1e-3, padding=2e-3, metal_size=50e-6,
                      far_size=.5e-3, grade=.2, min_angle=28))
    return TransmissionLineDocument(cross(), f, materials={}, conductor={'kind': 'perfect'}, length=.1)


def decoded(value):
    return np.asarray(value['real'])+1j*np.asarray(value['imag'])


def network_equal(output, expected):
    np.testing.assert_allclose(decoded(output['s']), expected.s, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(output['frequency_hz'], expected.frequency)
    np.testing.assert_array_equal(output['reference_ohms'], expected.z_ref)
    assert output['port_names'] == list(expected.port_names) and output['basis'] == expected.basis


def documents():
    from galerkin.mesh3d import box_mesh
    from sipi import GaussianConductivityProfile, ConductivityProfileDocument
    from sipi.capacitance3d_document import Capacitance3DDocument
    mesh = box_mesh(.004, .003, .002, 2, 2, 2)
    base = [cross(), ApertureDocument(CircularAperture(.28e-3, .8e-3, eps_r=3.96)), aperture(),
        *studies(), *goals(), line(), line(True), lumped(),
        NetworkAssemblyDocument(source(), connections=[dict(network=dict(kind='lumped-network',
            document=LumpedNetworkDocument([0, 1e9], resistance=20., port_names=('in', 'out')).to_dict()),
            ports=[['far', 'in']])]),
        NetworkTransformDocument(source(), operations=[dict(kind='renormalize', reference_ohms=75)]),
        CircuitDocument(source(), excitation=dict(kind='sources', voltages={'near': 1}), terminations={})]
    # Exercise every registry version through its real validator.
    base.append(ConductivityProfileDocument(
        GaussianConductivityProfile(conductivity=58e6,rms_m=1e-6),[1e9,4e9]))
    second = cross().to_dict(); second['schema'] = 'sipi.cross-section/2'
    for trace in second['traces']:
        trace['top_width'] = trace['width']
    base.append(CrossSectionDocument.from_dict(second))
    from sipi import CrossSection, Layer, PolygonTrace
    polygon = PolygonTrace('p', [(-.1e-3, .5e-3), (.1e-3, .5e-3), (0, .6e-3)])
    base.append(CrossSectionDocument(CrossSection([Layer('d', 1e-3, 4)], [polygon], 2e-3)))
    for version in (2, 3):
        data = studies()[0].to_dict(); data.update(schema=f'sipi.impedance-study/{version}', fixed_plane_spacing_m=None)
        if version == 3:
            data['material_evaluation'] = dict(frequency_hz=1e9, materials={})
            data['sampling']['variables'] = [dict(name='width', lower=.4e-3, upper=.6e-3)]
        base.append(ImpedanceStudyDocument.from_dict(data))
    base.append(ImpedanceDesignDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3, eps_r=4.),
        variable='width', bounds=[.3e-3, .8e-3], target=50., frequency=1e9,
        materials={'dielectric': ConstantDielectric(4)}))
    data = line().to_dict(); data['schema'] = 'sipi.transmission-line/2'
    base.append(TransmissionLineDocument.from_dict(data))
    data = line().to_dict(); data['schema'] = 'sipi.transmission-line/3'
    base.append(TransmissionLineDocument.from_dict(data))
    data = line().to_dict(); data['schema'] = 'sipi.transmission-line/4'
    base.append(TransmissionLineDocument.from_dict(data))
    data = line().to_dict(); data['schema'] = 'sipi.transmission-line/5'
    base.append(TransmissionLineDocument.from_dict(data))
    data = line().to_dict(); data['schema'] = 'sipi.transmission-line/6'
    base.append(TransmissionLineDocument.from_dict(data))
    base.append(NetworkTransformDocument(source(), operations=[dict(kind='renormalize', reference_ohms=75)],
        schema='sipi.network-transforms/2'))
    base.append(DebyeFitDocument([1e5, 1e7], eps_real=[3., 2.], eps_loss=[.2, .3],
                                relaxation_hz=[1e6], max_error=.01))
    base.append(LineQuantityDesignDocument(ImpedanceStudyDocument('stripline',
        dict(width=.5e-3, plane_spacing=1e-3, eps_r=4.), quantity='z0', frequency=1e9, materials={},
        sampling=dict(kind='sweep', count=2, variables=[dict(name='width', lower=.3e-3, upper=.8e-3)])),
        conductor=dict(kind='perfect'), quantity='impedance_real', target=50., tolerance=.5))
    base.append(LineQuantityStudyDocument(base[-1].to_dict()['study'],
                                         conductor=dict(kind='perfect'), quantity='attenuation'))
    scalar_study = base[-1].to_dict(); scalar_study['schema'] = 'sipi.line-quantity-study/2'
    base.append(LineQuantityStudyDocument.from_dict(scalar_study))
    scalar_goal = base[-3].to_dict(); scalar_goal['schema'] = 'sipi.line-quantity-design/2'
    base.append(LineQuantityDesignDocument.from_dict(scalar_goal))
    base.append(ImpedanceStudyDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3, eps_r=1),
        quantity='z0', frequency=1e8, materials={'dielectric':ConstantDielectric(4)},
        material_variables={'dk':dict(region='dielectric',path=['eps_r'])},
        sampling=dict(kind='sweep',count=2,variables=[dict(name='dk',lower=3,upper=5)])))
    base.append(ImpedanceDesignDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3, eps_r=1),
        variable='dk', bounds=[2,6], target=50., frequency=1e8, materials={'dielectric':ConstantDielectric(4)},
        material_variables={'dk':dict(region='dielectric',path=['eps_r'])}))
    from sipi.band import NetworkBandDocument
    from sipi.periodic_document import PeriodicNetworkDocument
    from sipi.periodic_circuit import PeriodicCircuitDocument
    from sipi.norton_circuit import NortonCircuitDocument
    from sipi.mixed_circuit import MixedCircuitDocument
    from sipi.periodic_mixed_circuit import PeriodicMixedCircuitDocument
    from sipi.periodic_norton_circuit import PeriodicNortonCircuitDocument
    base.append(PeriodicNetworkDocument(source(), incident={'near': [1, 0, -1], 'far': [0, 0, 0]}))
    base.append(PeriodicCircuitDocument(source(), source_voltages={'near': [1,0,-1], 'far': 0.},
                                        terminations={'near': 50., 'far': 75.}))
    base.append(NortonCircuitDocument(source(), source_currents={'near': .001, 'far': 0.},
                                      termination_admittances={'near': .02, 'far': 0.}))
    base.append(PeriodicNortonCircuitDocument(source(), source_currents={'near': [.001,0,-.001], 'far': 0.},
        termination_admittances={'near': .02, 'far': 0.}))
    base.append(MixedCircuitDocument(source(), boundaries={
        'near': dict(kind='thevenin', source_voltage=1., impedance=0.),
        'far': dict(kind='norton', source_current=0., admittance=0.)}))
    base.append(PeriodicMixedCircuitDocument(source(), boundaries={
        'near': dict(kind='thevenin', source_voltage=[1.,0.,-1.], impedance=0.),
        'far': dict(kind='norton', source_current=0., admittance=0.)}))
    base.append(NetworkBandDocument(source(),limits=[dict(name='through',input_port='near',output_port='far',
        frequency_hz=[0,1e9],minimum=0,maximum=None)]))
    from sipi.length_design import LineLengthDesignDocument
    base.append(LineLengthDesignDocument(dict(kind='rlgc',frequency_hz=[0,1e9],R=[[10]],L=[[2.5e-7]],
        G=[[.004]],C=[[1e-10]],length_m=0,reference_ohms=50,names=['s']),bounds=[0,10],
        limits=[dict(name='loss',input_port='near:s',output_port='far:s',frequency_hz=[0,1e9],minimum=.5,maximum=None)]))
    field = line().to_dict(); field['length_m'] = 0.
    base.append(LineLengthDesignDocument(dict(kind='transmission-line', document=field), bounds=[0, 10],
        limits=[dict(name='loss', input_port='near:signal', output_port='far:signal',
                     frequency_hz=[1e3, 2e3], minimum=.5, maximum=None)], schema='sipi.line-length-design/2'))
    base.append(Capacitance3DDocument(mesh, conductors={'top': mesh.boundary['z1']},
                                    ground=mesh.boundary['z0']))
    from test_ports3d_document import document as tem_document
    base.append(tem_document())
    from sipi.yield_assessment import ImpedanceYieldDocument
    from sipi.line_yield import LineQuantityYieldDocument
    from test_study import document as study_document, bounded
    base.append(ImpedanceYieldDocument(study_document(bounded('uniform', 2)), minimum=45, maximum=55))
    random_line = LineQuantityStudyDocument(study_document(bounded('uniform', 2), frequency=1e9, materials={}),
        conductor=dict(kind='perfect'), quantity='impedance_real')
    base.append(LineQuantityYieldDocument(random_line, minimum=45, maximum=55))
    from sipi.yield_design import YieldDesignDocument
    base.append(YieldDesignDocument([dict(name='nominal', cost=1.,
        study=study_document(bounded('uniform', 2)).to_dict())],
        cost_unit='relative cost', minimum=45, maximum=55, minimum_yield=.9))
    base.append(YieldDesignDocument([dict(name='nominal', cost=1., study=random_line.to_dict())],
        cost_unit='relative cost', minimum=45, maximum=55, minimum_yield=.9, schema='sipi.yield-design/2'))
    from sipi import PairImpedanceDesignDocument
    base.append(PairImpedanceDesignDocument('coupled_grounded_coplanar',
        dict(width=.5e-3,gap=.3e-3,ground_gap=.2e-3,ground_width=1e-3,
             substrate_height=.5e-3,eps_r=1.,box_width=12e-3,air_height=6e-3),
        variables=['width','gap'],bounds=[[.3e-3,.7e-3],[.1e-3,.5e-3]],
        targets={'z_diff':172.45677879183611,'z_common':65.9597000672247},
        tolerances={'z_diff':1.5,'z_common':.5},max_evaluations=2,
        mesh=dict(edge_size=2e-6,far_size=.125e-3,grade=.15)))
    from sipi.dielectric import DebyeDielectric
    base.append(PairImpedanceDesignDocument('coupled_stripline',
        dict(width=.5e-3,gap=.1e-3,plane_spacing=1e-3,eps_r=1.,box_width=8e-3),
        variables=['width','strength'],bounds=[[.3e-3,.7e-3],[2.,6.]],
        targets={'z_diff':69.86609070536932,'z_common':30.721416289368904},
        tolerances={'z_diff':.5,'z_common':.2},max_evaluations=2,
        mesh=dict(edge_size=1e-6,far_size=.125e-3,grade=.1),frequency=1e9,
        materials={'dielectric':DebyeDielectric(2.,[4.],[1e9])},
        material_variables={'strength':dict(region='dielectric',path=['strengths',0])}))
    from sipi import SampledImpedanceDesignDocument
    base.append(SampledImpedanceDesignDocument('coupled_stripline',
        dict(width=.5e-3,gap=.1e-3,plane_spacing=1e-3,eps_r=1.,box_width=8e-3),
        variables=['width','strength'],bounds=[[.3e-3,.7e-3],[2.,6.]],
        frequencies=[1e8,1e10],targets=[57.23463009022641,97.84159316427296],
        tolerances=[.5,.5],quantity='z_diff',max_evaluations=2,
        mesh=dict(edge_size=1e-6,far_size=.125e-3,grade=.1),
        materials={'dielectric':DebyeDielectric(2.,[4.],[1e9])},
        material_variables={'strength':dict(region='dielectric',path=['strengths',0])}))
    from sipi import LosslessStartupDocument
    base.append(LosslessStartupDocument([0.,1e-9,2e-9,3e-9],
        source_times=[0.],source_voltages=[1.],z0_ohm=50.,delay_s=1e-9,
        source_resistance=50.,load_resistance=None,max_terms=10000))
    from sipi import RLGCLadderDocument
    base.append(RLGCLadderDocument([0.,1e-9,2e-9], [0.,1.,1.],
        R=20.,L=500e-9,G=.002,C=200e-12,length=.1,cells=8,
        source_resistance=25.,load_resistance=100.))
    from sipi import CoupledRLGCLadderDocument
    base.append(CoupledRLGCLadderDocument([0.,1e-9,2e-9], [[0.,0.],[1.,0.],[1.,0.]],
        R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,
        G=[[.002,-.0003],[-.0003,.002]],C=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        length=.1,cells=8,source_resistance=[25.,25.],load_resistance=[100.,100.]))
    from sipi import MixedBoundaryRLGCLadderDocument
    base.append(MixedBoundaryRLGCLadderDocument([0.,1e-9,2e-9], [[0.,0.],[1.,0.],[1.,0.]],
        R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,
        G=[[.002,-.0003],[-.0003,.002]],C=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        length=.1,cells=8,source_resistance=[0.,37.],load_resistance=[0.,None]))
    from sipi import CapacitiveRLGCLadderDocument
    base.append(CapacitiveRLGCLadderDocument([0.,1e-9,2e-9], [[0.,0.],[1.,0.],[1.,0.]],
        R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,
        G=[[.002,-.0003],[-.0003,.002]],C=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        length=.1,cells=8,source_resistance=[0.,37.],load_resistance=[91.,None],
        load_capacitance=np.array([[20.,-4.],[-4.,30.]])*1e-12))
    from sipi import ReactiveRLGCLadderDocument
    base.append(ReactiveRLGCLadderDocument([0.,1e-9,2e-9], [[0.,0.],[1.,0.],[1.,0.]],
        R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,
        G=[[.002,-.0003],[-.0003,.002]],C=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        length=.1,cells=8,source_resistance=[0.,37.],load_resistance=[91.,None],
        load_capacitance=np.array([[20.,-4.],[-4.,30.]])*1e-12,
        load_branch_resistance=[[13.,1.],[1.,9.]],load_branch_inductance=np.array([[12.,2.],[2.,8.]])*1e-9))
    from sipi import StartupPortWavesDocument
    base.append(StartupPortWavesDocument(base[-1],z_ref=[35.,45.,55.,65.]))
    from sipi import NortonReactiveRLGCLadderDocument
    base.append(NortonReactiveRLGCLadderDocument([0.,1e-9,2e-9], [[0.,0.],[.02,0.],[.02,0.]],
        R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,
        G=[[.002,-.0003],[-.0003,.002]],C=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        length=.1,cells=8,source_shunt_resistance=[None,37.],load_resistance=[91.,None],
        load_capacitance=np.array([[20.,-4.],[-4.,30.]])*1e-12,
        load_branch_resistance=[[13.,1.],[1.,9.]],load_branch_inductance=np.array([[12.,2.],[2.,8.]])*1e-9))
    base.append(StartupPortWavesDocument(base[-1],z_ref=[35.,45.,55.,65.],version=2))
    from sipi import MixedSourceRLGCLadderDocument
    data=base[-2].to_dict();data['schema']='sipi.mixed-rlgc-startup/1'
    currents=data.pop('source_currents_a');shunts=data.pop('source_shunt_resistance_ohm')
    data['sources']=[dict(kind='voltage',voltage_v=[0.,1.,1.],series_resistance_ohm=0.),
        dict(kind='current',current_a=[row[1] for row in currents],shunt_resistance_ohm=shunts[1])]
    base.append(MixedSourceRLGCLadderDocument.from_dict(data))
    base.append(StartupPortWavesDocument(base[-1],z_ref=[35.,45.,55.,65.],version=3))
    from sipi import DebyeRLGCLadderDocument
    base.append(DebyeRLGCLadderDocument([0.,1e-9,2e-9],[0.,1.,1.],
        R=20.,L=500e-9,G=.002,C_inf=200e-12,delta_C=[150e-12,50e-12],
        relaxation_hz=[1e9,1e8],length=.1,cells=8,source_resistance=25.,load_resistance=100.))
    base.append(StartupPortWavesDocument(base[-1],z_ref=[35.,75.],version=4))
    from sipi import CoupledDebyeRLGCLadderDocument
    base.append(CoupledDebyeRLGCLadderDocument([0.,1e-9,2e-9],[[0.,0.],[1.,0.],[1.,0.]],
        R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,
        G=[[.002,-.0003],[-.0003,.002]],C_inf=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        delta_C=np.array([[[150.,-25.],[-25.,150.]]])*1e-12,relaxation_hz=[1e9],
        length=.1,cells=8,source_resistance=[25.,25.],load_resistance=[100.,100.]))
    base.append(StartupPortWavesDocument(base[-1],z_ref=[35.,45.,55.,65.],version=5))
    from sipi import PSDCoupledDebyeRLGCLadderDocument
    base.append(PSDCoupledDebyeRLGCLadderDocument([0.,1e-9,2e-9],[[0.,0.],[1.,0.],[1.,0.]],
        R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,
        G=[[.002,-.0003],[-.0003,.002]],C_inf=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        delta_C=np.array([[[150.,-150.],[-150.,150.]]])*1e-12,relaxation_hz=[1e9],
        length=.1,cells=8,source_resistance=[25.,25.],load_resistance=[100.,100.]))
    base.append(StartupPortWavesDocument(base[-1],z_ref=[35.,45.,55.,65.],version=6))
    from sipi import DebyeCapacitiveLadderDocument
    base.append(DebyeCapacitiveLadderDocument([0.,1e-9,2e-9],[[0.,0.],[1.,0.],[1.,0.]],
        R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,
        G=[[.002,-.0003],[-.0003,.002]],C_inf=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        delta_C=np.array([[[150.,-150.],[-150.,150.]]])*1e-12,relaxation_hz=[1e9],
        length=.1,cells=8,source_resistance=[25.,25.],load_resistance=[100.,100.],
        load_capacitance=np.array([[30.,-5.],[-5.,30.]])*1e-12))
    base.append(StartupPortWavesDocument(base[-1],z_ref=[35.,45.,55.,65.],version=7))
    from sipi import DebyeReactiveLadderDocument
    base.append(DebyeReactiveLadderDocument([0.,1e-9,2e-9],[[0.,0.],[1.,0.],[1.,0.]],
        R=[[20.,3.],[3.,20.]],L=np.array([[500.,100.],[100.,500.]])*1e-9,
        G=[[.002,-.0003],[-.0003,.002]],C_inf=np.array([[220.,-40.],[-40.,220.]])*1e-12,
        delta_C=np.array([[[150.,-150.],[-150.,150.]]])*1e-12,relaxation_hz=[1e9],
        length=.1,cells=8,source_resistance=[25.,25.],load_resistance=[100.,100.],
        load_capacitance=np.array([[30.,-5.],[-5.,30.]])*1e-12,
        load_branch_resistance=[[150.,20.],[20.,150.]],
        load_branch_inductance=np.array([[200.,30.],[30.,200.]])*1e-9))
    base.append(StartupPortWavesDocument(base[-1],z_ref=[35.,45.,55.,65.],version=8))
    from sipi import MulticonductorRLGCLadderDocument
    base.append(MulticonductorRLGCLadderDocument([0.,1e-9,2e-9],[[0.,0.,0.],[1.,-.4,.2],[1.,-.4,.2]],
        signals=3,R=np.diag([20.,23.,26.]),L=np.diag([450.,470.,490.])*1e-9,
        G=np.diag([.002,.0022,.0024]),C=np.diag([210.,220.,230.])*1e-12,
        length=.1,cells=8,source_resistance=[25.]*3,load_resistance=[100.]*3))
    base.append(StartupPortWavesDocument(base[-1],z_ref=[35.,45.,55.,65.,75.,85.],version=9))
    from sipi import GridPlateCapacitanceDocument
    base.append(GridPlateCapacitanceDocument(pitch=1e-3,width=.5e-3,height=.5e-3,
        backside_depth=1e-3,eps_r=3.8,cells_xy=4,cells_above=2,cells_below=4))
    from sipi import StripGridCapacitanceDocument
    base.append(StripGridCapacitanceDocument(pitch=1e-3,grid_width=.5e-3,trace_width=.5e-3,
        height=.5e-3,top_clearance=1e-3,backside_depth=1e-3,eps_substrate=3.8,eps_above=1.,eps_below=1.,
        transverse_periods=1,cells_per_pitch=4,cells_substrate=2,cells_above=4,cells_below=4))
    from sipi import ThickGridStripCapacitanceDocument
    base.append(ThickGridStripCapacitanceDocument(pitch=1e-3,grid_width=.5e-3,trace_width=.5e-3,
        height=.5e-3,top_clearance=1e-3,backside_depth=1e-3,ground_thickness=.25e-3,
        eps_substrate=3.8,eps_above=1.,eps_below=1.,transverse_periods=1,cells_per_pitch=4,
        cells_substrate=2,cells_above=4,cells_below=3,cells_grid=1))
    from sipi import VolumeGridStripCapacitanceDocument
    base.append(VolumeGridStripCapacitanceDocument(pitch=1e-3,grid_width=.5e-3,trace_width=.5e-3,
        height=.5e-3,top_clearance=1e-3,backside_depth=1e-3,ground_thickness=.25e-3,trace_thickness=.25e-3,
        eps_substrate=3.8,eps_above=1.,eps_below=1.,transverse_periods=1,cells_per_pitch=4,
        cells_substrate=2,cells_above=4,cells_below=3,cells_grid=1,cells_trace=1))
    from sipi import VolumeGridPairCapacitanceDocument
    base.append(VolumeGridPairCapacitanceDocument(pitch=1e-3,grid_width=.5e-3,
        trace_width=.5e-3,trace_gap=.5e-3,height=.5e-3,top_clearance=1e-3,
        backside_depth=1e-3,ground_thickness=.125e-3,trace_thickness=.125e-3,
        eps_substrate=3.8,eps_above=1.,eps_below=1.,transverse_periods=3,
        cells_per_pitch=4,cells_substrate=2,cells_above=4,cells_below=4,
        cells_grid=1,cells_trace=1))
    from sipi import MulticonductorDebyeRLGCLadderDocument
    base.append(MulticonductorDebyeRLGCLadderDocument(
        [0.,1e-9,2e-9],[[0.,0.,0.],[1.,-.4,.2],[1.,-.4,.2]],
        signals=3,R=np.diag([20.,23.,26.]),L=np.diag([450.,470.,490.])*1e-9,
        G=np.diag([.002,.0022,.0024]),C_inf=np.diag([210.,220.,230.])*1e-12,
        delta_C=np.array([np.diag([130.,140.,150.]),np.zeros((3,3))])*1e-12,
        relaxation_hz=[8e7,7e8],length=.1,cells=4,
        source_resistance=[25.]*3,load_resistance=[100.]*3))
    base.append(StartupPortWavesDocument(base[-1], z_ref=[35.,45.,55.,65.,75.,85.], version=10))
    from sipi import PSDMulticonductorDebyeRLGCLadderDocument
    base.append(PSDMulticonductorDebyeRLGCLadderDocument(
        [0.,1e-9,2e-9],[[0.,0.,0.],[1.,-.4,.2],[1.,-.4,.2]],signals=3,
        R=np.diag([20.,0.,26.]),L=np.diag([450.,470.,490.])*1e-9,
        G=np.diag([0.,.0022,.0024]),C_inf=np.diag([210.,220.,230.])*1e-12,
        delta_C=np.array([np.diag([130.,0.,0.]),np.zeros((3,3))])*1e-12,
        relaxation_hz=[8e7,7e8],length=.1,cells=4,
        source_resistance=[25.]*3,load_resistance=[100.]*3))
    base.append(StartupPortWavesDocument(base[-1], z_ref=[35.,45.,55.,65.,75.,85.], version=11))
    from sipi import MulticonductorDebyeCapacitiveLadderDocument
    base.append(MulticonductorDebyeCapacitiveLadderDocument(
        [0.,1e-9,2e-9],[[0.,0.,0.],[1.,-.4,.2],[1.,-.4,.2]],signals=3,
        R=np.diag([20.,0.,26.]),L=np.diag([450.,470.,490.])*1e-9,
        G=np.diag([0.,.0022,.0024]),C_inf=np.diag([210.,220.,230.])*1e-12,
        delta_C=np.array([np.diag([130.,0.,0.]),np.zeros((3,3))])*1e-12,
        relaxation_hz=[8e7,7e8],length=.1,cells=4,
        source_resistance=[25.]*3,load_resistance=[100.]*3,
        load_capacitance=np.diag([30.,0.,20.])*1e-12))
    base.append(StartupPortWavesDocument(base[-1], z_ref=[35.,45.,55.,65.,75.,85.], version=12))
    from sipi import MulticonductorDebyeReactiveLadderDocument
    base.append(MulticonductorDebyeReactiveLadderDocument(
        [0.,1e-9,2e-9],[[0.,0.,0.],[1.,-.4,.2],[1.,-.4,.2]],signals=3,
        R=np.diag([20.,0.,26.]),L=np.diag([450.,470.,490.])*1e-9,
        G=np.diag([0.,.0022,.0024]),C_inf=np.diag([210.,220.,230.])*1e-12,
        delta_C=np.array([np.diag([130.,0.,0.]),np.zeros((3,3))])*1e-12,
        relaxation_hz=[8e7,7e8],length=.1,cells=4,
        source_resistance=[25.]*3,load_resistance=[100.]*3,
        load_capacitance=np.diag([30.,0.,20.])*1e-12,
        load_branch_resistance=np.diag([30.,0.,40.]),
        load_branch_inductance=np.diag([180.,200.,220.])*1e-9))
    base.append(StartupPortWavesDocument(base[-1], z_ref=[35.,45.,55.,65.,75.,85.], version=13))
    from sipi import NortonMulticonductorDebyeReactiveLadderDocument
    base.append(NortonMulticonductorDebyeReactiveLadderDocument(
        [0.,1e-9,2e-9],[[0.,0.,0.],[.02,-.008,.004],[.02,-.008,.004]],signals=3,
        R=np.diag([20.,0.,26.]),L=np.diag([450.,470.,490.])*1e-9,
        G=np.diag([0.,.0022,.0024]),C_inf=np.diag([210.,220.,230.])*1e-12,
        delta_C=np.array([np.diag([130.,0.,0.]),np.zeros((3,3))])*1e-12,
        relaxation_hz=[8e7,7e8],length=.1,cells=4,
        source_shunt_conductance=[0.,.02,0.],load_resistance=[100.]*3,
        load_capacitance=np.diag([30.,0.,20.])*1e-12,
        load_branch_resistance=np.diag([30.,0.,40.]),
        load_branch_inductance=np.diag([180.,200.,220.])*1e-9))
    base.append(StartupPortWavesDocument(base[-1], z_ref=[35.,45.,55.,65.,75.,85.], version=14))
    from sipi import MixedSourceMulticonductorDebyeReactiveLadderDocument
    base.append(MixedSourceMulticonductorDebyeReactiveLadderDocument(
        [0.,1e-9,2e-9],[
            dict(kind='current',current_a=[0.,.02,.02],shunt_conductance_s=0.),
            dict(kind='voltage',voltage_v=[0.,-.4,-.4],series_resistance_ohm=50.),
            dict(kind='current',current_a=[0.,.004,.004],shunt_conductance_s=.01)],signals=3,
        R=np.diag([20.,0.,26.]),L=np.diag([450.,470.,490.])*1e-9,
        G=np.diag([0.,.0022,.0024]),C_inf=np.diag([210.,220.,230.])*1e-12,
        delta_C=np.array([np.diag([130.,0.,0.]),np.zeros((3,3))])*1e-12,
        relaxation_hz=[8e7,7e8],length=.1,cells=4,load_resistance=[100.]*3,
        load_capacitance=np.diag([30.,0.,20.])*1e-12,
        load_branch_resistance=np.diag([30.,0.,40.]),
        load_branch_inductance=np.diag([180.,200.,220.])*1e-9))
    base.append(StartupPortWavesDocument(base[-1], z_ref=[35.,45.,55.,65.,75.,85.], version=15))
    return base


def test_registry_all_versions_normalize_without_field_solve(monkeypatch):
    docs = documents()
    assert {d.to_dict()['schema'] for d in docs} == set(saved_schemas())
    def forbidden(*args, **kwargs):
        pytest.fail('normalization performed a field solve')
    from sipi import CrossSection
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    for doc in docs:
        assert normalize_saved(doc.dumps()) == doc.dumps()


@pytest.mark.parametrize('text', ['[]', '{}', 'null', '{"schema":1}', '{"schema":[]}',
    '{"schema":"unknown"}', '{"schema":"a","schema":"b"}', '{"x":NaN}',
    '{"x":Infinity}', '{"x":1e999}', '{"x":{"a":1,"a":2}}'])
def test_reject_ambiguous_unknown_nonfinite_inputs(text):
    with pytest.raises(ValueError):
        execute_saved(text)


def test_input_bytes_not_characters_and_options_are_checked():
    doc = LumpedNetworkDocument([0], port_names=('입력', '출력'))
    text = doc.dumps()
    with pytest.raises(ValueError, match='max_input_bytes'):
        normalize_saved(text, max_input_bytes=len(text))
    assert normalize_saved(text, max_input_bytes=len(text.encode())) == text
    for bad in (True, 0, 1.5):
        with pytest.raises(ValueError): normalize_saved(text, max_input_bytes=bad)
    for bad in (True, 1, 10001, 2.5):
        with pytest.raises(ValueError): execute_saved(text, max_evaluations=bad)
    for bad in ('modes', [None], ['modes', 'modes'], ['unknown']):
        with pytest.raises(ValueError): execute_saved(text, diagnostics=bad)
    with pytest.raises(TypeError): normalize_saved(doc.to_dict())
    with pytest.raises(ValueError, match='top-level'): execute_saved(text, diagnostics=['modes'])


def test_geometry_and_local_complex_capacitance_match_direct_api():
    doc = cross(); direct = doc.analyze(); out = execute_saved(doc.dumps())
    assert out['input'] == doc.to_dict() and out['status'] == 'complete' and out['error'] is None
    for key, field in [('C_f_per_m', 'C'), ('C0_f_per_m', 'C0'), ('C_loss_f_per_m', 'C_loss'), ('L_h_per_m', 'L')]:
        np.testing.assert_array_equal(out['result'][key], getattr(direct, field))
    assert out['result']['z0_ohm'] == direct.z0
    for doc in [ApertureDocument(CircularAperture(.28e-3, .8e-3, eps_r=3.96, tan_delta=.02)), aperture()]:
        np.testing.assert_array_equal(decoded(execute_saved(doc.dumps())['result']['capacitance_f_per_m']), doc.analyze())


@pytest.mark.parametrize('volume', [False, True])
def test_line_rlgc_network_and_optional_diagnostics_match_direct(volume):
    doc = line(volume); direct = doc.analyze()
    out = execute_saved(doc.dumps(), diagnostics=['characteristic', 'modes'])['result']
    for key, field in [('R_ohm_per_m', 'R'), ('L_h_per_m', 'L'), ('G_s_per_m', 'G'), ('C_f_per_m', 'C')]:
        np.testing.assert_array_equal(out[key], getattr(direct, field))
    network_equal(out['network'], direct.network)
    for name, fields in [('characteristic', ['gamma_voltage', 'z_characteristic', 'y_characteristic']),
                         ('modes', ['gamma', 'voltage', 'current', 'alpha_conductor', 'alpha_dielectric', 'overlap', 'assignment_gap'])]:
        expected = getattr(direct, name)(); got = out['diagnostics'][name]
        assert got['status'] == 'complete'
        for key in fields:
            value = got[key]; value = decoded(value) if isinstance(value, dict) else value
            np.testing.assert_array_equal(value, getattr(expected, key))


def test_optional_diagnostic_rejection_keeps_dc_rlgc():
    doc = line(dc=True)
    out = execute_saved(doc.dumps(), diagnostics=['characteristic', 'modes'])
    assert out['status'] == 'complete'
    network_equal(out['result']['network'], doc.analyze().network)
    for diag in out['result']['diagnostics'].values():
        assert diag['status'] == 'failed' and 'positive' in diag['error']['message']


def test_asymmetric_tensor_matrices_and_tracked_mode_errors_are_preserved(monkeypatch):
    from sipi import coupled_microstrip, ModeTrackingError
    from sipi.dielectric import PrincipalAxisDielectric, DebyeDielectric
    from sipi.line_model import TransmissionLineResult
    section = coupled_microstrip(width=.4e-3, gap=.2e-3, substrate_height=.5e-3,
        thickness=.1e-3, eps_r=4, air_height=.5e-3, box_width=2e-3)
    model = PrincipalAxisDielectric(DebyeDielectric(2, [2], [1e4]), ConstantDielectric(5, .02), .4)
    doc = TransmissionLineDocument(CrossSectionDocument(section,
        mesh=dict(edge_size=10e-6, far_size=.25e-3, grade=.2)), [1e3, 1e4, 1e5],
        materials={'substrate': model}, conductor={'kind': 'perfect'}, length=.01)
    direct = doc.analyze()
    out = execute_saved(doc.dumps(), diagnostics=['modes'])['result']
    np.testing.assert_array_equal(out['C_f_per_m'], direct.C)
    np.testing.assert_array_equal(decoded(out['diagnostics']['modes']['gamma']), direct.modes().gamma)
    # Transport of an existing tracking failure must retain index and frequency.
    def unresolved(self):
        raise ModeTrackingError('ambiguous assignment', index=1, frequency=1e4)
    monkeypatch.setattr(TransmissionLineResult, 'modes', unresolved)
    out = execute_saved(doc.dumps(), diagnostics=['modes'])
    assert out['status'] == 'complete'
    error = out['result']['diagnostics']['modes']['error']
    assert error['index'] == 1 and error['frequency_hz'] == 1e4
    network_equal(out['result']['network'], direct.network)


@pytest.mark.parametrize('index', [0, 1])
def test_study_values_rows_and_summary_match_direct(index):
    doc = studies()[index]; direct = doc.analyze(); out = execute_saved(doc.dumps())['result']
    assert out['summary'] == dict(direct.summary) and out['failed'] == 0
    for got, expected in zip(out['rows'], direct.rows):
        assert got['value'] == getattr(expected, 'capacitance' if index else 'impedance')
        assert got['document'] == expected.document.to_dict() and got['parameters'] == dict(expected.parameters)


def test_invalid_sample_rows_are_not_dropped():
    doc = ApertureStudyDocument(aperture(), sampling=dict(kind='normal', count=3, seed=771,
        variables=[dict(name='width', mean=.8e-3, std=1e-3)], correlation=[[1.]]))
    direct = doc.analyze(); out = execute_saved(doc.dumps())
    assert direct.failed > 0 and out['status'] == 'incomplete' and out['result']['summary'] is None
    assert len(out['result']['rows']) == 3
    assert [(r['error_type'], r['error']) for r in out['result']['rows']] == [(r.error_type, r.error) for r in direct.rows]


@pytest.mark.parametrize('index', [0, 1])
def test_goal_success_and_failure_preserve_history(index):
    doc = goals()[index]; direct = doc.solve(); out = execute_saved(doc.dumps())
    value = 'capacitance' if index else 'impedance'
    assert out['status'] == 'complete' and out['result']['parameter'] == direct.parameter
    assert out['result']['refined_value'] == getattr(direct, 'refined_'+value)
    data = doc.to_dict(); data['target_f_per_m' if index else 'target_ohm'] = 1e-14 if index else 1e4
    failed = type(doc).from_dict(data)
    with pytest.raises((GoalSeekError, CapacitanceGoalError)) as caught: failed.solve()
    output = execute_saved(failed.dumps())
    assert output['status'] == 'failed' and output['result'] is None
    assert output['error']['message'] == str(caught.value)
    assert output['error']['history'] == [dict(parameter=r.parameter, value=getattr(r, value), stage=r.stage) for r in caught.value.history]


def test_goal_and_sample_budget_reject_before_solve(monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('budget rejection reached solver')
    monkeypatch.setattr(ApertureSectionDocument, 'analyze', forbidden)
    with pytest.raises(ValueError, match='before any solve'): execute_saved(goals()[1].dumps(), max_evaluations=3)
    doc = ApertureStudyDocument(aperture(), sampling=dict(kind='sweep', count=3,
        variables=[dict(name='eps_r', lower=3, upper=5)]))
    with pytest.raises(ValueError, match='before any solve'): execute_saved(doc.dumps(), max_evaluations=2)


def test_refined_goal_miss_retains_requested_success_and_failed_parameter():
    coarse = ApertureSectionDocument(aperture().section, mesh=dict(size=.1e-3, angular_divisions=16))
    doc = ApertureDesignDocument(coarse, variable='conductor_0_diameter', bounds=[.2e-3, .35e-3],
        target=200e-12, tolerance=1e-14)
    output = execute_saved(doc.dumps())
    assert output['status'] == 'failed' and 'refined mesh misses' in output['error']['message']
    history = output['error']['history']
    assert abs(history[-2]['value']-200e-12) <= 1e-14
    assert abs(history[-1]['value']-200e-12) > 1e-14 and history[-1]['stage'] == 'refinement'
    assert output['error']['parameter'] == history[-1]['parameter']


def test_network_documents_and_loaded_circuit_parity():
    docs = [d for d in documents() if isinstance(d, (LumpedNetworkDocument, NetworkAssemblyDocument,
            NetworkTransformDocument, CircuitDocument))]
    for doc in docs:
        direct = doc.analyze(); out = execute_saved(doc.dumps())['result']
        network_equal(out['network'], direct if isinstance(doc, LumpedNetworkDocument) else direct.network)
        if isinstance(doc, NetworkAssemblyDocument):
            for got, expected in zip(out['source_networks'], direct.source_networks): network_equal(got, expected)
        if isinstance(doc, NetworkTransformDocument): network_equal(out['source_network'], direct.source_network)
        if isinstance(doc, CircuitDocument):
            for key in ('voltage', 'current', 'a', 'b', 'source_voltages', 'terminations'):
                np.testing.assert_array_equal(decoded(out['response'][key]), getattr(direct.response, key))
            np.testing.assert_array_equal(out['response']['network_power'], direct.response.network_power)
    net = LineNetwork([1e9], np.arange(16).reshape(1, 4, 4)/100+.01j,
        [25, 50, 75, 100], ('a', 'n', 't', 'f'))
    doc = CircuitDocument(dict(kind='touchstone', text=net.touchstone(), ports=4, port_names=list(net.port_names)),
        excitation=dict(kind='crosstalk', aggressor='a', near_victim='n', far_victim='f'), terminations={'f': 125})
    direct = doc.analyze(); out = execute_saved(doc.dumps())['result']
    for key in ('next_ratio', 'fext_ratio'):
        np.testing.assert_array_equal(decoded(out['crosstalk'][key]), getattr(direct.crosstalk, key))
    # No non-standard NaN/Infinity tokens; a client can round-trip without loss.
    assert json.loads(json.dumps(out, allow_nan=False)) == out

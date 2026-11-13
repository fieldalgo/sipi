# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Tiny branch currents must retain the explicit inductor flux/energy limit."""
import numpy as np
import pytest
from scipy.integrate import simpson
from sipi import coupled_debye_rlgc_ladder_response
from test_debye_reactive_startup import run, R, L, G, C, F

DELTA=np.array([[[150.,-25.],[-25.,150.]],[[50.,-10.],[-10.,50.]]])*1e-12


def drive_at(t,pulse):
 d=np.minimum(t/2e-9,1.)
 if pulse:d-=np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
 return d[:,None]*[1.,-.4]

@pytest.fixture(scope='module',params=[False,True],ids=['ramp','pulse'])
def reference(request):
 pulse=request.param;integrals=[]
 for count in [241,481]:
  t=np.linspace(0,12e-9,count);drive=drive_at(t,pulse)
  ref=coupled_debye_rlgc_ladder_response(t,drive,R=R,L=L,G=G,C_inf=C,
   delta_C=DELTA,relaxation_hz=F,length=.1,cells=16,
   source_resistance=[25.,25.],load_resistance=[100.,100.])
  integrals.append(simpson(ref.voltage[:,2:],x=t,axis=0))
 # At large L and zero branch resistance, L*I(t)=integral(Vfar dt).
 # This independent quadrature uses the strict no-branch line and converges
 # separately. Branch feedback tends to zero; no candidate state matrix is used.
 np.testing.assert_allclose(integrals[0],integrals[1],rtol=1e-5,atol=0)
 return t,drive,integrals[1]


@pytest.mark.parametrize('inductance',[1e6,1e7,1e8])
def test_large_inductance_retains_flux_and_inverse_energy(reference,inductance,record_property):
 t,drive,flux=reference
 a=run(t,drive,delta_C=DELTA,load_capacitance=np.zeros((2,2)),
       load_branch_resistance=np.zeros((2,2)),load_branch_inductance=np.eye(2)*inductance)
 actual_flux=inductance*a.load_branch_current[-1]
 expected_energy=np.dot(flux,flux)/(2*inductance)
 record_property('flux_and_energy',str(dict(inductance=inductance,
  flux=flux.tolist(),actual_flux=actual_flux.tolist(),energy=float(a.load_branch_energy[-1]),
  expected_energy=float(expected_energy),power_error=a.total_power_balance_relative_error)))
 np.testing.assert_allclose(actual_flux,flux,rtol=1e-5,atol=0)
 assert abs(a.load_branch_energy[-1]/expected_energy-1)<=1e-5
 assert a.power_balance_relative_error<=1e-10
 assert a.total_power_balance_relative_error<=1e-10
 assert np.all(np.isfinite(a.load_branch_current))
 assert np.all(a.load_branch_energy>=0)

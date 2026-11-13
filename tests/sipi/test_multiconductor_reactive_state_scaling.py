# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Large finite branch inductances retain flux in three/four-signal circuits."""
import numpy as np
import pytest
from scipy.integrate import simpson
from sipi import psd_multiconductor_debye_capacitive_ladder_response as reference_response
from sipi import psd_multiconductor_debye_reactive_ladder_response as response
from test_multiconductor_debye_reactive_startup import modal_data,amp

@pytest.fixture(scope='module',params=[(3,False),(3,True),(4,False),(4,True)],
                ids=['3-ramp','3-pulse','4-ramp','4-pulse'])
def flux_reference(request):
 signals,pulse=request.param;*_,mats=modal_data(signals)
 mats['load_capacitance']=np.zeros((signals,signals))
 mats['load_branch_resistance']=np.zeros((signals,signals))
 opts=dict(signals=signals,length=.1,cells=16,
           source_resistance=np.full(signals,25.),load_resistance=np.full(signals,100.))
 integrals=[]
 for count in [241,481]:
  t=np.linspace(0,12e-9,count);d=np.minimum(t/2e-9,1.)
  if pulse:d-=np.minimum(np.maximum(t-5e-9,0)/2e-9,1.)
  drive=d[:,None]*amp(signals)
  ref=reference_response(t,drive,**{k:v for k,v in mats.items() if not k.startswith('load_branch_')},**opts)
  integrals.append(simpson(ref.voltage[:,signals:],x=t,axis=0))
 np.testing.assert_allclose(integrals[0],integrals[1],rtol=1e-5,atol=0)
 return t,drive,mats,opts,integrals[1]


@pytest.mark.parametrize('inductance',[1e6,1e7,1e8])
def test_large_branch_flux_and_energy_limit(flux_reference,inductance,record_property):
 t,drive,mats,opts,flux=flux_reference;signals=opts['signals']
 a=response(t,drive,**{**mats,'load_branch_inductance':np.eye(signals)*inductance},**opts)
 actual=inductance*a.load_branch_current[-1];energy=np.dot(flux,flux)/(2*inductance)
 record_property('flux_and_energy',str(dict(signals=signals,inductance=inductance,
  expected_flux=flux.tolist(),actual_flux=actual.tolist(),expected_energy=float(energy),
  actual_energy=float(a.load_branch_energy[-1]),power_error=a.total_power_balance_relative_error)))
 np.testing.assert_allclose(actual,flux,rtol=1e-5,atol=0)
 assert abs(a.load_branch_energy[-1]/energy-1)<=1e-5
 assert a.power_balance_relative_error<=1e-10
 assert a.total_power_balance_relative_error<=1e-10
 assert np.all(np.isfinite(a.load_branch_current)) and np.all(a.load_branch_energy>=0)

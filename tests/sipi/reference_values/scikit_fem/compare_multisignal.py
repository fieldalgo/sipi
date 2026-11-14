# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Manual heavy P2 replay; compare only, with no baseline-writing option."""
from pathlib import Path
import argparse
import json
import sys
from importlib.metadata import version
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/_support'))
from galerkin import assemble_stiffness,solve_dirichlet
from sipi.document import CrossSectionDocument
from sipi.fem_shape_conductor import _boundary_motion
from quadratic_shape_energy import quadratic_shape_energy


def compare(count):
    path=Path(__file__).with_name('three_signal_fem_shape.json' if count==3 else 'four_signal_fem_shape.json')
    record=json.loads(path.read_text());expected=record['references'][0]['version']
    if version('scikit-fem')!=expected:raise ValueError('replay needs scikit-fem=='+expected)
    doc=CrossSectionDocument.from_dict(record['inputs']['cross_section'])
    field=doc.section.mesh(**doc.mesh_options);mesh=field.mesh
    fixed,prescribed,_,_=_boundary_motion(mesh,field.signals,field.ground)
    centers=mesh.nodes[mesh.triangles].mean(axis=1)
    origin=mesh.nodes[0]+(mesh.nodes-mesh.nodes[0]).mean(axis=0)
    radius2=float(np.max(np.sum((mesh.nodes-origin)**2,axis=1)))
    matrices=[assemble_stiffness(mesh,1.),assemble_stiffness(mesh,1+.5*np.sum((centers-origin)**2,axis=1)/radius2)]
    velocities=np.array([[np.column_stack([solve_dirichlet(matrix,np.zeros(mesh.num_nodes),
        {tuple(fixed):values[fixed,j]}) for j in range(2)]) for values in prescribed] for matrix in matrices])
    result=quadratic_shape_energy(mesh,field.signals,field.ground,velocities)
    different=False
    for entry in record['values']:
        old=np.asarray(entry['data'],dtype=entry['dtype']).reshape(entry['shape'])
        actual=np.asarray(result[entry['name']],dtype=entry['dtype'])
        equal=actual.shape==old.shape and actual.tobytes()==old.tobytes()
        print(count,entry['name'],'exact' if equal else 'DIFFERENT',flush=True)
        different|=not equal
    return different


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--signals',type=int,choices=(3,4),required=True)
    args=parser.parse_args()
    return int(compare(args.signals))


if __name__=='__main__':raise SystemExit(main())

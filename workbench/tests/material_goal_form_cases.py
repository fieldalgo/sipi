"""Changed scalar-target settings for the actual form workflow."""
import json
from sipi import ImpedanceDesignDocument
from sipi.execution import execute_saved
from material_goal_cases import material_goal


def edited_goal(kind, target=51.):
    data = material_goal(kind).to_dict()
    data.update(target_ohm=target, bounds=[2.5, 7.5], max_evaluations=48)
    data['material_evaluation']['frequency_hz'] = 2e8
    return ImpedanceDesignDocument.from_dict(data)


if __name__ == '__main__':
    print(json.dumps([dict(id=name, kind=kind, target=target,
        text=edited_goal(kind,target).dumps(), expected=execute_saved(edited_goal(kind,target).dumps()))
        for name,kind,target in [('constant','constant',51.),
            ('debye-unbracketed','debye',51.),('debye-recovery','debye',56.)]]))

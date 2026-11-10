"""Retained scalar target failures for read-only browser history views."""
import json
from sipi.execution import execute_saved
from material_goal_cases import material_goal
from material_goal_form_cases import edited_goal


def failed_goal(name):
    data = edited_goal('debye').to_dict() if name == 'unbracketed' else material_goal('constant').to_dict()
    if name == 'budget':
        data['max_evaluations'] = 3
    elif name == 'refinement':
        data['tolerance_ohm'] = .01
    elif name != 'unbracketed':
        raise ValueError('unknown failure fixture')
    return data


if __name__ == '__main__':
    print(json.dumps([dict(name=name, input=failed_goal(name),
        execution=execute_saved(json.dumps(failed_goal(name))))
        for name in ['unbracketed', 'budget', 'refinement']]))

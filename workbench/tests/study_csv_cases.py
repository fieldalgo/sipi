"""Existing study executions for native/Worker CSV transport acceptance."""
import json
from material_uniform_form_cases import uniform_study
from material_corner_form_cases import corner_study
from material_normal_form_cases import normal_study
from sipi.execution import execute_saved


def cases():
    documents = [('uniform', uniform_study('constant', edited=True)),
                 ('corners', corner_study(reversed_order=True, edited=True)),
                 ('incomplete', normal_study('constant', mixed=True))]
    return [dict(name=name, input=document, execution=execute_saved(json.dumps(document)))
            for name, document in documents]


if __name__ == '__main__':
    print(json.dumps(cases(), allow_nan=False))

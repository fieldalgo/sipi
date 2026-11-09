"""Input-only projects for actual browser history acceptance."""
import json

from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.project import SavedProject


def request(resistance=10, *, evaluations=128, byte_limit=200*1024, padding=0):
    return SavedExecutionRequest(LumpedNetworkDocument([0, 1e9], resistance=resistance).dumps()+' '*padding,
        max_input_bytes=byte_limit, max_evaluations=evaluations)


base = SavedProject(request(), project_id='browser-fixture', design_id='a',
    title='Analysis project', label='A', max_project_bytes=200*1024)
large = base.duplicate_design('a', 'b', 'B')
padding = 200*1024 - 500 - len(large.dumps().encode())
large = large.update_design('b', request(padding=padding))
assert len(large.dumps().encode()) == 200*1024-500
long = SavedProject(request(), project_id='long', design_id='a', title='T'*512,
    label='L'*256, max_project_bytes=200*1024)
print(json.dumps(dict(input=request().source_text, changed=request(20).source_text,
    changed_again=request(30).source_text,
    limit17=base.update_design('a', request(evaluations=17, byte_limit=100000)).dumps(),
    limit129=base.update_design('a', request(evaluations=129)).dumps(),
    large=large.dumps(), long=long.dumps())))

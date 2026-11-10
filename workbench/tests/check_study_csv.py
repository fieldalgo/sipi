"""Independently read an exported study CSV against its full execution JSON."""
import csv
import io
import json
import math
import sys
from pathlib import Path


def protected_text(value):
    # Expected spreadsheet treatment of text, independent of CSV quoting.
    text = str(value)
    return "'" + text if text.startswith(('\t', '\r', '\n')) or next((char for char in text if not char.isspace() and char != '\ufeff'), '') in ('=', '+', '-', '@') else text


def check(text, execution):
    assert text.startswith('\ufeff') and text.endswith('\r\n')
    rows = list(csv.reader(io.StringIO(text.removeprefix('\ufeff'), newline=''), strict=True))
    document, result = execution['input'], execution['result']
    variables = [v['name'] for v in document['sampling']['variables']]
    expected_headers = ['Input schema', 'Quantity', 'Row index', *variables, 'Impedance (Ω)', 'Outcome']
    assert rows[0] == [protected_text(value) for value in expected_headers]
    assert len(rows) == len(result['rows']) + 1
    numbers = 0
    for exported, sample in zip(rows[1:], result['rows']):
        assert len(exported) == len(expected_headers)
        assert exported[:3] == [document['schema'], document['quantity'], str(sample['index'])]
        for name, cell in zip(variables, exported[3:-2]):
            binding = document.get('material_variables', {}).get(name)
            if binding:
                value = sample['material_evaluation']['materials'][binding['region']]['parameters']
                for key in binding['path']:
                    value = value[key]
            else:
                value = sample['parameters'][name]
            assert math.isfinite(float(cell)) and float(cell) == value, (name, cell, value)
            numbers += 1
        if sample['error'] is None:
            assert math.isfinite(float(exported[-2])) and float(exported[-2]) == sample['value']
            assert exported[-1] == 'Calculated'
            numbers += 1
        else:
            assert exported[-2] == ''
            assert exported[-1] == protected_text(sample['error_type'] + ': ' + sample['error'])
    return dict(status='passed', rows=len(rows)-1, numeric_values=numbers)


if __name__ == '__main__':
    # newline='' preserves quoted newlines and record terminators for inspection.
    with Path(sys.argv[1]).open(encoding='utf-8', newline='') as stream:
        text = stream.read()
    print(json.dumps(check(text, json.loads(Path(sys.argv[2]).read_text()))))

"""Exercise the search handler without loading unrelated application services."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import Flask, jsonify, request


@pytest.mark.parametrize('column,direction,expected', [
    ('name', 'asc', 'name.asc'),
    ('erp_code', 'desc', 'erp_code.desc'),
    ('received_date', 'asc', 'received_date.asc'),
    ('budget_year', 'desc', 'budget_year.desc'),
    ('procurement_no', 'asc', 'procurement_no.asc'),
    ('available', 'desc', 'available.desc'),
    ('check', 'asc', None),
    ('query', 'desc', None),
    (None, 'asc', None),
])
def test_search_orders_before_pagination(column, direction, expected):
    path = Path(__file__).resolve().parents[1] / 'app/procurement/views.py'
    tree = ast.parse(path.read_text())
    handler = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef)
                   and node.name == 'get_procurement_search_data')
    handler.decorator_list = []
    query = MagicMock()
    for method in ('options', 'order_by', 'offset', 'limit'):
        getattr(query, method).return_value = query
    query.count.return_value = 25
    query.all.return_value = []
    model = SimpleNamespace(query=query)
    for name in ('id', 'name', 'procurement_no', 'erp_code', 'budget_year',
                 'received_date', 'available', 'image_thumbnail_url', 'image_url'):
        field = MagicMock()
        field.asc.return_value = name + '.asc'
        field.desc.return_value = name + '.desc'
        setattr(model, name, field)
    scope = dict(ProcurementDetail=model, request=request, jsonify=jsonify,
                 load_only=lambda *args: None)
    exec(compile(ast.Module(body=[handler], type_ignores=[]), str(path), 'exec'), scope)
    args = {'start': '10', 'length': '5', 'draw': '2'}
    if column is not None:
        args.update({'order[0][column]': '2', 'columns[2][data]': column,
                     'order[0][dir]': direction})
    with Flask(__name__).test_request_context('/api/data/search', query_string=args):
        payload = scope['get_procurement_search_data']().get_json()
    orders = [call.args for call in query.order_by.call_args_list]
    assert orders[-1] == ((expected, 'id.asc') if expected else ('id.asc',))
    query.offset.assert_called_once_with(10)
    query.limit.assert_called_once_with(5)
    calls = [call[0] for call in query.mock_calls]
    assert calls.index('offset') > max(i for i, name in enumerate(calls) if name == 'order_by')
    assert payload['recordsTotal'] == payload['recordsFiltered'] == 25

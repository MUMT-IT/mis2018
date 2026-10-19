"""Run the CLI with real JWT handlers, without database or external services."""
import ast
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

import click
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager, get_current_user, get_jwt_identity, jwt_required

ROOT = Path(__file__).resolve().parents[1]


def load_functions(path, names, namespace, keep_decorators=False):
    tree = ast.parse(path.read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(nodes) == len(names)
    if not keep_decorators:
        for node in nodes:
            node.decorator_list = [
                dec for dec in node.decorator_list
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name)
                and dec.func.id == 'jwt_required'
            ]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)


class ScbJwtSmokeTest(unittest.TestCase):
    def invoke(self, broken_refresh=False):
        app = Flask(__name__)
        jwt = JWTManager(app)
        original_lookup = lambda *_args: None
        jwt.user_lookup_loader(original_lookup)
        views = ModuleType('app.scb_payment_service.views')
        namespace = dict(jsonify=jsonify, get_current_user=get_current_user,
                         get_jwt_identity=get_jwt_identity, jwt_required=jwt_required)
        from flask_jwt_extended import create_access_token
        namespace['create_access_token'] = create_access_token
        load_functions(ROOT / 'app/scb_payment_service/views.py', {'refresh', 'test_login'}, namespace)
        views.refresh = namespace['refresh']
        views.test_login = namespace['test_login']
        if broken_refresh:
            views.refresh = lambda: (jsonify(message='failure'), 500)
        load_functions(ROOT / 'app/main.py', {'test_scb_auth'},
                       {'app': app, 'click': click, 'Flask': Flask, 'JWTManager': JWTManager}, True)
        with patch.dict(sys.modules, {'app.scb_payment_service.views': views}):
            result = app.test_cli_runner().invoke(args=['test-scb-auth', '--jwt-only'])
        self.assertIs(jwt._user_lookup_callback, original_lookup)
        self.assertEqual(list(app.url_map.iter_rules())[0].endpoint, 'static')
        return result

    def test_creation_refresh_without_credentials(self):
        result = self.invoke()
        self.assertEqual(result.exit_code, 0, result.output)
        for step in ('Access token verification', 'Token refresh', 'Refreshed access token verification'):
            self.assertIn(step + ': passed', result.output)
        self.assertNotIn('eyJ', result.output)

    def test_refresh_failure_is_reported(self):
        result = self.invoke(broken_refresh=True)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn('Token refresh failed (HTTP 500)', result.output)


if __name__ == '__main__':
    unittest.main()

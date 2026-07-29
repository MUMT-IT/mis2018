bandit -r . -f json -o security/bandit.json
pip-audit -r requirements.txt -f json -o security/pip-audit.json
semgrep --config p/python --config p/flask --json -o security/semgrep.json .
"""Verify scan failures cannot reach AWS uploads or image publication."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImageGateTest(unittest.TestCase):
    def test_failures_stop_before_aws(self):
        for scenario in ('frontend', 'backend', 'scanner-error'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temp:
                work = Path(temp)
                shutil.copytree(ROOT / 'ci', work / 'ci')
                tools = work / 'bin'
                tools.mkdir()
                scripts = {
                    'git': '#!/bin/sh\nprintf "%s\\n" "$EXPECTED_COMMIT"\n',
                    'aws': '#!/bin/sh\necho called >> aws-called\nexit 99\n',
                    'docker': '''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
if args[0] == 'build': raise SystemExit(0)
component='frontend' if 'frontend:' in args[-1] else 'backend'
with open('scanned','a') as f: f.write(component+'\\n')
if os.environ['SCENARIO']=='scanner-error': raise SystemExit(3)
v=[{'Severity':'CRITICAL','VulnerabilityID':'TEST','PkgName':'example'}] if component==os.environ['SCENARIO'] else []
Path('reports/'+component+'-trivy.json').write_text(json.dumps({'SchemaVersion':2,'Results':[{'Vulnerabilities':v}]}))
'''
                }
                for name, content in scripts.items():
                    path = tools / name
                    path.write_text(content)
                    path.chmod(0o755)
                env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'],
                           SCENARIO=scenario, EXPECTED_COMMIT='a' * 40,
                           CODEBUILD_RESOLVED_SOURCE_VERSION='a' * 40, AWS_ACCOUNT_ID='123456789012',
                           AWS_DEFAULT_REGION='eu-west-2', SCAN_REPORT_BUCKET='test',
                           FRONTEND_ECR_REPOSITORY='frontend', BACKEND_ECR_REPOSITORY='backend')
                result = subprocess.run(['bash', 'ci/build-images.sh'], cwd=work, env=env,
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((work / 'aws-called').exists(), result.stdout + result.stderr)
                self.assertEqual((work / 'scanned').read_text().splitlines(),
                                 ['frontend', 'backend'] if scenario == 'backend' else ['frontend'])


if __name__ == '__main__':
    unittest.main()

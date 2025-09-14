import os
import argparse
import subprocess

parser = argparse.ArgumentParser(usage='Wrapper for clean building Illuminator')
parser.add_argument('-o', '--override-version', help='Override default version for testing')
parser.add_argument('-c', '--clean', action='store_true', help='Delete leftovers and old compiles')
parser.add_argument('-u', '--upload', action='store_true', help='Upload dists to test.pypi')

args = parser.parse_args()

if os.path.exists('build') and os.path.exists('dist') and os.path.exists('maica'):
    pass
else:
    print('Wrong directory, should be running in project root!')
    exit(1)

if args.override_version:
    o = f'-o {args.override_version}'
else:
    o = ''

if args.clean:
    subprocess.run('rm -r build/*', shell=True)
    subprocess.run('rm dist/*', shell=True)

subprocess.run(f'python setup.py {o} build sdist bdist_wheel', shell=True)

if args.upload:
    subprocess.run('twine upload --repository testpypi dist/*', shell=True)

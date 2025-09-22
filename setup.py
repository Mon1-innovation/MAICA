import os
import re
import sys
import argparse
import setuptools

custom_parser = argparse.ArgumentParser(add_help=False)
custom_parser.add_argument('-o', '--override-version', help='Override default version for testing')

custom_args, remaining_args = custom_parser.parse_known_args()
sys.argv = [sys.argv[0]] + remaining_args

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("maica/env_example", "r", encoding="utf-8") as env:
    curr_version_line = re.compile(r'^MAICA_CURR_VERSION\s*=\s*\'(.*)\'')
    for line in env:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        res = curr_version_line.match(line)
        if res:
            curr_version = res[1]
            break
    else:
        raise Exception('no version line found')

curr_version = custom_args.override_version if custom_args.override_version else curr_version

def parse_requirements(filename='requirements.txt'):
    """从requirements.txt文件中加载依赖列表"""
    with open(filename, 'r') as f:
        lines = f.read().splitlines()
    # 过滤空行、注释和可选索引链接
    requirements = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('-'):
            requirements.append(line)
    return requirements

setuptools.setup(
    name="mi-maica", # 用自己的名替换其中的YOUR_USERNAME_
    version=curr_version,    #包版本号，便于维护版本
    author="EdgeInfinity",    #作者，可以写自己的姓名
    author_email="dcc@monika.love",    #作者联系方式，可写自己的邮箱地址
    description="MAICA Illuminator (Backend)",#包的简述
    long_description=long_description,    #包的详细介绍，一般在README.md文件内
    long_description_content_type="text/markdown",
    url="https://github.com/Mon1-innovation/MAICA",    #自己项目地址，比如github的项目地址
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.12',
    install_requires=parse_requirements(),
    entry_points={
        'console_scripts': [
            'maica = maica.maica_starter:full_start',
        ],
    },
    package_data={
        'maica': ['env_example'],
    },
)
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = f.read().splitlines()

setuptools.setup(
    name="fairyfly-next-therm",
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    description=(
        "Exploratory Fairyfly THERM extension targeting "
        "pyHygroThermFEM-Fairyfly (AGPL-3.0 derivative)."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    project_urls={
        "Repository": "https://github.com/LoftyTao/fairyfly-next-therm",
        "Upstream Fairyfly source": "https://github.com/ladybug-tools/fairyfly-therm"
    },
    packages=setuptools.find_packages(exclude=["tests*", "equest_docs*"]),
    install_requires=requirements,
    include_package_data=True,
    entry_points={
        "console_scripts": ["fairyfly-next-therm = fairyfly_next_therm.cli:therm"]
    },
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: IronPython",
        "Operating System :: OS Independent"
    ],
    license="AGPL-3.0"
)

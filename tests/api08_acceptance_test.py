# coding=utf-8
"""Public object and independent-process archive acceptance for ticket 08."""
import hashlib
from collections import Counter
import importlib.metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import pytest

from fairyfly.model import Model
from fairyfly_next_therm.condition.transient import Transient
from fairyfly_next_therm.material.hygrothermal import HygrothermalMaterial
from fairyfly_next_therm.simulation.parameter import SimulationParameter
from fairyfly_next_therm.simulation.transient import TransientCalculation
from fairyfly_next_therm.writer import model_to_thmz


def _material():
    """Return a modeled material with fixed, physically meaningful values."""
    material = HygrothermalMaterial(
        0.62, density=1700, porosity=0.28, specific_heat=840,
        vapor_diffusion_resistance=38,
        moisture_storage_function=[[0, 0], [0.5, 60], [1, 300]],
        liquid_transport_suction=[[0, 0], [300, 1e-6]],
        emissivity=0.93, emissivity_back=0.85,
        identifier='00000000-0000-4000-8000-000000000008')
    material.display_name = 'API08 Brick'
    return material


def test_api08_public_dict_duplicate_lock_and_xml():
    """New materials and conditions retain values and the source lock state."""
    material = _material()
    condition = Transient(timesteps=[
        {'temperature': 10, 'humidity': 0.4, 'film_coefficient': 7},
        {'temperature': 12, 'humidity': 0.6, 'film_coefficient': 8}])
    condition.display_name = 'API08 Outside'
    for obj, field, replacement in (
            (material, 'density', 1800),
            (condition, 'surface_tilt', 45)):
        before = obj.to_dict()
        obj.lock()
        clone = obj.duplicate()
        assert clone is not obj
        assert clone.to_dict() == before
        assert type(obj).from_dict(before).to_dict() == before
        assert obj.display_name in repr(obj)
        with pytest.raises(AttributeError):
            setattr(obj, field, replacement)
        setattr(clone, field, replacement)
        assert obj.to_dict() == before
        obj.unlock()
        setattr(obj, field, replacement)
    assert HygrothermalMaterial.from_therm_xml(
        material.to_therm_xml()).to_dict() == material.to_dict()
    steps = Transient.timesteps_from_xml(condition.to_timestep_xml())
    assert steps == {1: {'temperature': 10, 'humidity': 0.4,
                        'film_coefficient': 7},
                     2: {'temperature': 12, 'humidity': 0.6,
                         'film_coefficient': 8}}
    parsed = Transient.from_therm_xml(condition.to_therm_xml(), steps)
    assert parsed.timesteps == condition.timesteps
    assert parsed.identifier == condition.identifier
    assert parsed.display_name == 'API08 Outside'


def test_api08_transient_parameter_public_protocol():
    """Transient options duplicate independently and survive XML and dicts."""
    calc = TransientCalculation(
        time_range=7200, timestep=3600, initial_temperature=15,
        initial_humidity=0.6, simulate_moisture=True)
    assert calc.time_range == 7200
    assert calc.number_of_timesteps == 2
    assert TransientCalculation.from_therm_xml(
        calc.to_therm_xml()).to_dict() == calc.to_dict()
    parameter = SimulationParameter(transient=calc)
    clone = parameter.duplicate()
    assert clone.to_dict() == parameter.to_dict()
    assert SimulationParameter.from_dict(parameter.to_dict()) == parameter
    clone.transient.initial_temperature = 17
    assert parameter.transient.initial_temperature == 15
    assert 'TransientCalculation' in repr(calc)
    assert 'transient' not in SimulationParameter().to_dict()


# This program imports only the fixed solver installation. No Fairyfly source
# or parent-process sys.path is passed to the independent CPython interpreter.
_READER_PROGRAM = r'''
from dataclasses import asdict
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import zipfile
import pyhygrothermfem_fairyfly
from pyhygrothermfem_fairyfly.transient_input import (
    load_transient_type_bc, save_transient_type_bc,
    load_timestep_file, save_timestep_file, validate_transient_inputs)

path = Path(sys.argv[1])
with zipfile.ZipFile(path) as archive:
    assert archive.testzip() is None
    members = {name: archive.read(name) for name in archive.namelist()}
records = load_transient_type_bc(members['TransientTypeBC.xml'])
assert load_transient_type_bc(save_transient_type_bc(records)) == records
references = validate_transient_inputs(members)
timesteps = {}
for name, content in members.items():
    if name.startswith('timestep input files/'):
        parsed = load_timestep_file(content, member=name)
        assert load_timestep_file(save_timestep_file(parsed)) == parsed
        timesteps[name] = asdict(parsed)
native = list(Path(pyhygrothermfem_fairyfly.__file__).parent.glob('_native*.pyd'))
assert len(native) == 1
print(json.dumps({
    'python': sys.version, 'executable': sys.executable,
    'solver': metadata.version('pyHygroThermFEM-Fairyfly'),
    'libraryfemtherm': metadata.version('libraryfemtherm'),
    'packages': sorted(d.metadata['Name'] for d in metadata.distributions()),
    'native_sha256': hashlib.sha256(native[0].read_bytes()).hexdigest(),
    'archive_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    'member_sha256': {n: hashlib.sha256(b).hexdigest()
                      for n, b in members.items()},
    'records': records, 'timesteps': timesteps,
    'reference_count': len(references)
}, sort_keys=True))
'''


@pytest.mark.parametrize('kind', [
    'convection', 'humidity-pin', 'dual-pin', 'heat-flux', 'steady-type',
    'constant-boundaries'])
def test_api08_thmz_reader_in_independent_process(kind, tmp_path):
    """The ticket 04 reader losslessly consumes freshly exported THMZ inputs."""
    python = os.environ.get('API08_SOLVER_PYTHON')
    if not python:
        pytest.skip('Set API08_SOLVER_PYTHON to a separate solver installation.')
    output = Path(os.environ.get('API08_EVIDENCE_DIR', tmp_path)) / 'archives'
    output.mkdir(parents=True, exist_ok=True)
    path = output / (kind + '.thmz')
    assert not path.exists(), 'Acceptance evidence must never be overwritten.'
    model = Model.from_layers([200], height=1000)
    material = _material()
    model.shapes[0].properties.therm.material = material
    kwargs = {
        'convection': dict(use_humidity=True, radiation_model='Black Body Radiation',
                           timesteps=[dict(temperature=10, humidity=0.4,
                                           film_coefficient=7,
                                           radiation_temperature=5, emissivity=0.9),
                                      dict(temperature=12, humidity=0.6,
                                           film_coefficient=8,
                                           radiation_temperature=6, emissivity=0.8)]),
        'humidity-pin': dict(bc_model='Dirichlet', use_humidity=True,
                             convection_model=None,
                             timesteps=[{'humidity': 0.8}, {'humidity': 0.6}]),
        'dual-pin': dict(bc_model='Dirichlet', use_humidity=True,
                         use_temperature=True, convection_model=None,
                         timesteps=[{'humidity': 0.8, 'surface_temperature': 20},
                                    {'humidity': 0.6, 'surface_temperature': 18}]),
        'heat-flux': dict(use_heat_flux=True, convection_model=None,
                          timesteps=[{'heat_flux': -20}, {'heat_flux': -15}]),
        'steady-type': dict(bc_type='SteadyState', temperature=22,
                            film_coefficient=2.5),
    }
    condition = None
    if kind != 'constant-boundaries':
        condition = Transient(**kwargs[kind])
        condition.display_name = 'API08 ' + kind
        condition.timestep_file_name = kind + '.xml'
        model.boundaries[0].properties.therm.condition = condition
    parameter = SimulationParameter(transient=TransientCalculation(
        time_range=7200, timestep=3600, initial_temperature=15,
        initial_humidity=0.6, simulate_moisture=True))
    material.unlock()
    if condition is not None:
        condition.unlock()
    material_before = material.to_dict()
    condition_before = condition.to_dict() if condition is not None else None
    model_to_thmz(model, str(path), parameter)
    # Explicit mutations are legal after export: neither resource is re-locked.
    material.density = 1700
    assert material.to_dict() == material_before
    if condition is not None:
        condition.display_name = 'API08 ' + kind
        assert condition.to_dict() == condition_before
    with zipfile.ZipFile(path) as archive:
        materials = ET.fromstring(archive.read('Materials.xml'))
        assert HygrothermalMaterial.from_therm_xml(
            materials.find('Material')).to_dict() == material_before
        model_xml = ET.fromstring(archive.read('Model.xml'))
        options = model_xml.find('Properties/CalculationOptions')
        assert options.findtext('CalculationMode') == 'Transient'
        assert options.findtext('SimulateMoisture') == 'true'
        assert options.findtext('EngineParameters/TimeStep') == '3600.0'
        assert options.findtext('EngineParameters/NumberOfTimesteps') == '2'
    result = subprocess.run([python, '-I', '-c', _READER_PROGRAM, str(path)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    evidence['writer_python'] = sys.executable
    evidence['writer_package'] = importlib.metadata.version('fairyfly-next-therm')
    evidence['input_path'] = str(path.resolve())
    assert not any(
        'fairyfly' in name.lower() and name.lower() != 'pyhygrothermfem-fairyfly'
        for name in evidence['packages'])
    assert evidence['archive_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    expected = 0 if condition is None else 1
    assert len(evidence['records']) == expected
    assert evidence['reference_count'] == expected
    if condition is not None:
        record = evidence['records'][0]
        assert record['name'] == 'API08 ' + kind
        assert record['uuid'] == condition.identifier
        step_file = evidence['timesteps']['timestep input files/' + kind + '.xml']
        assert step_file['name'] == 'API08 ' + kind
        if kind == 'convection':
            assert step_file['convection']['FixedConvectionFilmTimestep'] == [
                dict(index=1, temperature=10, humidity=0.4, film_coefficient=7),
                dict(index=2, temperature=12, humidity=0.6, film_coefficient=8)]
            assert step_file['radiation']['BlackBodyRadiationTimestep'] == [
                dict(index=1, temperature=5, emissivity=0.9),
                dict(index=2, temperature=6, emissivity=0.8)]
        elif kind in ('humidity-pin', 'dual-pin'):
            assert step_file['humidity'] == [dict(index=1, humidity=0.8),
                                             dict(index=2, humidity=0.6)]
            if kind == 'dual-pin':
                assert step_file['temperature'] == [dict(index=1, temperature=20),
                                                    dict(index=2, temperature=18)]
        elif kind == 'heat-flux':
            assert step_file['heat_flux'] == [dict(index=1, heat_flux=-20),
                                              dict(index=2, heat_flux=-15)]
        elif kind == 'steady-type':
            assert record['convection']['temperature'] == 22
            assert record['convection']['film_coefficient'] == 2.5
            assert step_file['convection']['FixedConvectionFilmTimestep'] == [
                dict(index=1, temperature=22, humidity=0, film_coefficient=2.5)]
    (output / (kind + '-reader.json')).write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def test_api08_official_restart_compatibility_boundary(tmp_path):
    """Official restarted-index input is retained by the reader, not collapsed.

    This is an unsolved official input, not a release-archive comparison and
    not evidence that the numerical solver accepts or solves the case.
    """
    python = os.environ.get('API08_SOLVER_PYTHON')
    source = os.environ.get('API08_OFFICIAL_SAMPLE')
    if not python or not source:
        pytest.skip('Set separate solver and official-sample paths for acceptance.')
    output = Path(os.environ.get('API08_EVIDENCE_DIR', tmp_path))
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / 'official-restart-reader.json'
    assert not result_path.exists(), 'Acceptance evidence must never be overwritten.'
    source = Path(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    result = subprocess.run([python, '-I', '-c', _READER_PROGRAM, str(source)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    boundaries = {}
    with zipfile.ZipFile(source) as archive:
        for member, timestep in evidence['timesteps'].items():
            raw = ET.fromstring(archive.read(member))
            entries = timestep['convection']['FixedConvectionFilmTimestep']
            assert len(entries) == 120
            assert Counter(step['index'] for step in entries) == dict(
                (index, 12) for index in range(1, 11))
            # The official schema-location attribute is known to the reader
            # but cannot be retained by the object's dictionary-only interface.
            with pytest.raises(ValueError, match='THMZ-E2001') as metadata_error:
                Transient.timesteps_from_xml(raw)
            # Selecting the supported public subtree exposes the independent
            # restarted-sequence limitation without modifying the input asset.
            with pytest.raises(ValueError, match='THMZ-E2005') as restart_error:
                Transient.timesteps_from_xml(raw.find('BoundaryConditionTransient'))
            boundaries[member] = {
                'reader_record_count': 120, 'index_repetitions': 12,
                'object_metadata_rejection': str(metadata_error.value),
                'object_restart_rejection': str(restart_error.value),
                'status': 'reader-passed-object-unrepresentable'}
    assert len(boundaries) == 2
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_sha
    evidence.update(input_path=str(source.resolve()), source_unchanged=True,
                    object_compatibility=boundaries, solved_archive=False)
    result_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n',
                           encoding='utf-8')

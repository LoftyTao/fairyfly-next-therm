# coding=utf-8
"""Tests the fairyfly_next_therm run module."""
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from fairyfly_next_therm.result import THMZResult
from fairyfly_next_therm.run import run_thmz


def test_model_rerun_publishes_only_after_success(monkeypatch, tmp_path):
    """A failed GH rerun leaves its previous result intact."""
    from fairyfly.model import Model
    from fairyfly_next_therm import run as runner
    from fairyfly_next_therm.simulation.parameter import SimulationParameter

    model = Model.from_layers([100], height=100)
    model.display_name = 'Rerun'
    settings = SimulationParameter()
    settings.mesh.run_error_estimator = False
    target = tmp_path / 'Rerun.thmz'
    target.write_bytes(b'previous valid result')

    def write_model(_, path, *args, **kwargs):
        Path(path).write_bytes(b'new input')

    def fail_solve(path, silent):
        raise ValueError('solver did not converge')

    monkeypatch.setattr(runner, 'model_to_thmz', write_model)
    monkeypatch.setattr(runner, 'run_thmz', fail_solve)
    with pytest.raises(ValueError, match='did not converge'):
        runner.run_model(model, str(tmp_path), simulation_par=settings)
    assert target.read_bytes() == b'previous valid result'

    def solve(path, silent):
        Path(path).write_bytes(b'new valid result')

    monkeypatch.setattr(runner, 'run_thmz', solve)
    assert runner.run_model(model, str(tmp_path), simulation_par=settings) == str(target)
    assert target.read_bytes() == b'new valid result'


def _runner_paths(monkeypatch, tmp_path):
    """Use the current isolated wheel for public subprocess tests."""
    root = Path(__file__).resolve().parents[2]
    python = (os.environ.get('PYHYGROTHERMFEM_FAIRYFLY_PYTHON')
              or os.environ.get('PYHYGROTHERM_PYTHON'))
    if python is None:
        pytest.skip('Set PYHYGROTHERMFEM_FAIRYFLY_PYTHON to an installed CPython venv.')
    if not Path(python).is_file():
        pytest.skip('Set PYHYGROTHERMFEM_FAIRYFLY_PYTHON to an installed CPython venv.')
    monkeypatch.setenv('PYHYGROTHERMFEM_FAIRYFLY_PYTHON', python)
    source = (root / 'pyHygroThermFEM-Fairyfly' / 'tests' / 'assets' /
              'thmz-contract' / 'slab.thmz')
    if not source.is_file():
        pytest.skip('The pyHygroThermFEM-Fairyfly premeshed slab fixture is unavailable.')
    folder = tmp_path / '中文 folder'
    folder.mkdir()
    target = folder / 'wall with 空格.thmz'
    shutil.copyfile(source, target)
    return target, python


@pytest.mark.parametrize('problem', ['bad_zip', 'missing_model', 'bad_xml'])
def test_run_thmz_wraps_invalid_input_model_errors(
        monkeypatch, tmp_path, problem):
    from fairyfly_next_therm import run as runner

    target = tmp_path / 'invalid input.thmz'
    if problem == 'bad_zip':
        target.write_bytes(b'not a THMZ archive')
    else:
        with zipfile.ZipFile(target, 'w') as archive:
            if problem == 'missing_model':
                archive.writestr('Other.xml', b'<Other/>')
            else:
                archive.writestr('Model.xml', b'<ThermModel>')
    original = target.read_bytes()
    monkeypatch.setenv(
        'PYHYGROTHERMFEM_FAIRYFLY_PYTHON', str(Path(sys.executable).resolve()))

    def check_interpreter(command, silent, timeout=3600):
        assert '-c' in command
        return 0, 'interpreter ready\n', ''

    monkeypatch.setattr(runner, '_run_process', check_interpreter)
    with pytest.raises(ValueError) as error:
        runner.run_thmz(str(target), silent=True)

    assert str(target.resolve()) in str(error.value)
    assert target.read_bytes() == original
    assert not list(tmp_path.glob('.pyhygrotherm-*.thmz'))


@pytest.mark.parametrize(
    ('result_tags', 'extra_case', 'missing_field', 'projection_fault',
     'valid'), [
    pytest.param([], False, None, None, False, id='missing'),
    pytest.param(['Warm Face', 'Warm Face', 'Cold Face'], False, None, None,
                 False,
                 id='duplicate'),
    pytest.param(['Warm Face', 'Cold Face', 'Unexpected'], False, None, None,
                 False,
                 id='extra'),
    pytest.param(['Warm Face', 'Cold Face'], True, None, None, False,
                 id='extra-case'),
    pytest.param(['Warm Face', 'Cold Face'], False, 'DeltaT', None, False,
                 id='missing-delta-t'),
    pytest.param(['Warm Face', 'Cold Face'], False, 'HeatFlux', None, False,
                 id='missing-heat-flux'),
    pytest.param(['Warm Face', 'Cold Face'], False, None, 'missing_total',
                 False, id='missing-total-projection'),
    pytest.param(['Warm Face', 'Cold Face'], False, None, 'unknown_type',
                 False, id='unknown-projection'),
    pytest.param(['Warm Face', 'Cold Face'], False, None, 'duplicate_type',
                 False, id='duplicate-projection'),
    pytest.param(['Warm Face', 'Cold Face'], False, None, 'missing_length',
                 False, id='missing-length'),
    pytest.param(['Warm Face', 'Cold Face'], False, None, 'nan_delta',
                 False, id='nan-delta'),
    pytest.param(['Warm Face', 'Cold Face'], False, None, 'inf_heat',
                 False, id='infinite-heat'),
    pytest.param(['Warm Face', 'Cold Face'], False, None, 'nan_length',
                 False, id='nan-length'),
    pytest.param(['Warm Face', 'Cold Face'], False, None, 'negative_length',
                 False, id='negative-length'),
    pytest.param(['Warm Face', 'Cold Face'], False, None, 'inf_u_factor',
                 False, id='infinite-u-factor'),
    pytest.param(['Warm Face', 'Cold Face'], False, None, 'missing_u_factor',
                 False, id='missing-u-factor'),
    pytest.param(['Warm Face', 'Cold Face'], False, None, None, True,
                 id='undefined-values'),
])
def test_external_result_matches_input_u_factor_tags(
        monkeypatch, tmp_path, result_tags, extra_case, missing_field,
        projection_fault, valid):
    from fairyfly_next_therm import run as runner

    monkeypatch.setenv(
        'PYHYGROTHERMFEM_FAIRYFLY_PYTHON', str(Path(sys.executable).resolve()))
    target, _ = _runner_paths(monkeypatch, tmp_path)
    fixture = (Path(__file__).resolve().parents[2] /
               'pyHygroThermFEM-Fairyfly' / 'tests' / 'assets' /
               'ticket07_series_wall.thmz')
    if not fixture.is_file():
        pytest.skip(
            'The pyHygroThermFEM-Fairyfly series wall fixture is unavailable.')
    shutil.copyfile(fixture, target)
    original = target.read_bytes()

    def child(command, silent, timeout=3600):
        if '-c' in command:
            return 0, 'interpreter ready\n', ''
        with zipfile.ZipFile(target) as source:
            members = {name: source.read(name) for name in source.namelist()}
        mesh = ET.fromstring(members['Mesh.xml'])
        mesh_results = ET.Element('SteadyStateMeshResults')
        result_case = ET.SubElement(mesh_results, 'Case')
        result_nodes = ET.SubElement(result_case, 'Nodes')
        for node in mesh.findall('Case/Nodes/Node'):
            result_node = ET.SubElement(result_nodes, 'Node')
            ET.SubElement(result_node, 'Index').text = node.findtext('index')
            for field, value in (('Temperature', '20'),
                                 ('X-flux', '0'), ('Y-flux', '0')):
                ET.SubElement(result_node, field).text = value
        steady = ET.Element('Results')
        ET.SubElement(steady, 'Version').text = '1'
        result_case = ET.SubElement(steady, 'Case')
        ET.SubElement(result_case, 'ModelType').text = 'U-factor'
        for tag in result_tags:
            factor = ET.SubElement(result_case, 'U-factors')
            ET.SubElement(factor, 'Tag').text = tag
            delta_t = '0' if tag == 'Warm Face' else '20'
            heat_flux = '0'
            if projection_fault == 'nan_delta':
                delta_t = 'NaN'
            if projection_fault == 'inf_heat':
                heat_flux = 'Infinity'
            if projection_fault == 'missing_u_factor' and tag == 'Warm Face':
                delta_t = '20'
            for field, value in (
                    ('DeltaT', delta_t), ('HeatFlux', heat_flux)):
                if field != missing_field:
                    ET.SubElement(factor, field).text = value
            length_type = ('Projected X' if projection_fault == 'missing_total'
                           else 'Total Length')
            length = '200' if tag == 'Warm Face' else '0'
            if projection_fault == 'nan_length':
                length = 'NaN'
            elif projection_fault == 'negative_length':
                length = '-1'
            projection = ET.SubElement(factor, 'Projection')
            ET.SubElement(projection, 'Length-type').text = length_type
            if projection_fault != 'missing_length':
                ET.SubElement(projection, 'Length').text = length
            if projection_fault == 'inf_u_factor':
                ET.SubElement(projection, 'U-factor').text = 'Infinity'
            if projection_fault in ('unknown_type', 'duplicate_type'):
                extra = ET.SubElement(factor, 'Projection')
                extra_type = ('bogus' if projection_fault == 'unknown_type'
                              else 'Total Length')
                ET.SubElement(extra, 'Length-type').text = extra_type
                ET.SubElement(extra, 'Length').text = '0'
        if extra_case:
            extra = ET.SubElement(steady, 'Case')
            ET.SubElement(extra, 'ModelType').text = 'U-factor'
        members['SteadyStateMeshResults.xml'] = ET.tostring(mesh_results)
        members['SteadyStateResults.xml'] = ET.tostring(steady)
        members['pyHygroTherm.json'] = json.dumps({
            'input_sha256': hashlib.sha256(original).hexdigest()}).encode()
        result_path = Path(command[-1])
        with zipfile.ZipFile(result_path, 'w') as output:
            for name, content in members.items():
                output.writestr(name, content)
        return 0, str(result_path) + '\n', ''

    monkeypatch.setattr(runner, '_run_process', child)
    if valid:
        assert runner.run_thmz(
            str(target), silent=True) == str(target.resolve())
        factors = THMZResult(str(target)).u_factors
        assert [factor.name for factor in factors] == [
            'Warm Face', 'Cold Face']
        assert factors[0].total_length == 200
        assert factors[0].total_u_factor is None
        assert factors[1].total_length == 0
        assert factors[1].total_u_factor is None
    else:
        with pytest.raises(ValueError, match='U-factor'):
            runner.run_thmz(str(target), silent=True)
        assert target.read_bytes() == original
        assert not list(target.parent.glob('.pyhygrotherm-*.thmz'))


def test_run_thmz_solves_in_place_through_isolated_python(
        monkeypatch, tmp_path, capsys):
    """The public Fairyfly-Next runner keeps the input path and publishes results."""
    target, python = _runner_paths(monkeypatch, tmp_path)
    with zipfile.ZipFile(target) as archive:
        original_model = archive.read('Model.xml')
        original_mesh = archive.read('Mesh.xml')

    result = run_thmz(str(target), silent=True)

    assert result == str(target.resolve())
    assert capsys.readouterr().out == ''
    assert THMZResult(result).temperatures == pytest.approx(
        [19.09090909, 10.0, 0.90909091] * 3, abs=1e-6)
    with zipfile.ZipFile(target) as archive:
        assert archive.read('Model.xml') == original_model
        assert archive.read('Mesh.xml') == original_mesh
        assert 'SteadyStateMeshResults.xml' in archive.namelist()

    log = (target.parent / 'pyhygrotherm.log').read_text(encoding='utf-8')
    assert 'CPython 3.13' in log
    assert str(Path(python).resolve()) in log
    assert 'exit code: 0' in log


def test_run_thmz_shows_status_when_not_silent(monkeypatch, tmp_path, capsys):
    """The normal run mode shows the solver's successful CLI output."""
    target, _ = _runner_paths(monkeypatch, tmp_path)

    assert run_thmz(str(target), silent=False) == str(target.resolve())

    assert str(target.resolve()) in capsys.readouterr().out


def test_run_thmz_logs_solver_failure_without_changing_input(
        monkeypatch, tmp_path):
    """A failed external solve reports its actual status and keeps the input."""
    target, _ = _runner_paths(monkeypatch, tmp_path)
    with zipfile.ZipFile(target) as archive:
        members = {name: archive.read(name) for name in archive.namelist()
                   if name != 'Mesh.xml'}
    with zipfile.ZipFile(target, 'w') as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    original = target.read_bytes()

    with pytest.raises(ValueError, match='Mesh.xml'):
        run_thmz(str(target), silent=True)

    assert target.read_bytes() == original
    log = (target.parent / 'pyhygrotherm.log').read_text(encoding='utf-8')
    assert 'exit code: 1' in log
    assert 'Mesh.xml' in log


@pytest.mark.parametrize('failure', ['exit', 'timeout', 'false_success'])
def test_external_failures_do_not_publish_old_results(
        monkeypatch, tmp_path, failure):
    """Exit status, timeout, and output validation guard the same public path."""
    from fairyfly_next_therm import run as runner

    target, _ = _runner_paths(monkeypatch, tmp_path)
    original = target.read_bytes()

    def child(command, silent, timeout=3600):
        if '-c' in command:
            return 0, 'interpreter ready\n', ''
        if failure == 'timeout':
            raise RuntimeError('timed out after {} seconds'.format(timeout))
        if failure == 'exit':
            return 1, '', 'solver crashed at assembly'
        return 0, command[-1] + '\n', ''

    monkeypatch.setattr(runner, '_run_process', child)
    with pytest.raises(ValueError):
        runner.run_thmz(str(target), silent=True)
    assert target.read_bytes() == original
    assert not list(target.parent.glob('.pyhygrotherm-*.thmz'))
    log = (target.parent / 'pyhygrotherm.log').read_text(encoding='utf-8')
    assert ('process failed' in log if failure == 'timeout' else
            'Solver exit code:' in log)


def test_writer_failure_preserves_existing_thmz(monkeypatch, tmp_path):
    """Direct GH write cannot truncate a prior valid archive."""
    from fairyfly.model import Model
    from fairyfly_next_therm.writer import model_to_thmz

    model = Model.from_layers([100], height=100)
    target = tmp_path / '中文 with spaces.thmz'
    model_to_thmz(model, str(target))
    original = target.read_bytes()

    def fail_write(*args, **kwargs):
        raise OSError('disk full')

    monkeypatch.setattr(zipfile.ZipFile, 'writestr', fail_write)
    with pytest.raises(OSError, match='disk full'):
        model_to_thmz(model, str(target))
    assert target.read_bytes() == original
    assert not list(tmp_path.glob('.fairyfly-*.thmz'))

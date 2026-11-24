# coding=utf-8
"""Regression tests for SteadyState-type Transient records in THMZ output."""
import os
import sys
import zipfile
from xml.etree import ElementTree as ET

import pytest

from fairyfly_next_therm.condition.transient import Transient
from fairyfly_next_therm.simulation.parameter import SimulationParameter
from fairyfly_next_therm.simulation.transient import TransientCalculation
from fairyfly_next_therm.writer import model_to_thmz

from tests.writer_transient_test import _wall


def _transient_par():
    return SimulationParameter(
        transient=TransientCalculation(
            time_range=86400, timestep=3600, initial_temperature=10,
            initial_humidity=0.6))


def _steady_wall():
    model = _wall()
    steady = Transient(
        bc_type='SteadyState', temperature=22, film_coefficient=2.5)
    steady.display_name = 'Steady Interior'
    model.boundaries[1].properties.therm.condition = steady
    return model, steady


def _load_transient_input():
    """Import the pyhygrothermfem_fairyfly transient-input reader if available."""
    try:
        from pyhygrothermfem_fairyfly import transient_input
        return transient_input
    except ImportError:
        pass
    here = os.path.abspath(os.path.dirname(__file__))
    candidates = (
        os.path.join(here, os.pardir, os.pardir, 'pyHygroThermFEM-Fairyfly'),
        os.path.join(here, os.pardir, 'pyHygroThermFEM-Fairyfly'))
    for candidate in candidates:
        package = os.path.join(
            candidate, 'pyhygrothermfem_fairyfly', '__init__.py')
        if os.path.isfile(package):
            sys.path.insert(0, os.path.abspath(candidate))
            try:
                from pyhygrothermfem_fairyfly import transient_input
            except ImportError:
                pytest.skip('pyhygrothermfem_fairyfly is not importable in this venv')
            return transient_input
    pytest.skip('pyHygroThermFEM-Fairyfly not available in this venv')


def test_steady_type_record_writes_real_timestep_member(tmp_path):
    """A bcType=SteadyState record writes a referenced timestep member.

    The reader convention (pyhygrothermfem_fairyfly.transient_input) requires every
    Boundary/TransientData TimestepFileName to be non-empty and to resolve
    to an existing 'timestep input files/' member. SteadyState semantics
    are a constant condition, so the member holds a single Index=1 step
    echoing the record constants.
    """
    model, cond = _steady_wall()
    thmz_path = str(tmp_path / 'steady_type.thmz')
    model_to_thmz(model, thmz_path, _transient_par())

    with zipfile.ZipFile(thmz_path) as archive:
        names = archive.namelist()
        member = 'timestep input files/{}'.format(cond.timestep_file_name)
        assert member in names
        model_xml = ET.fromstring(archive.read('Model.xml'))
        ts_xml = archive.read(member).decode('utf-8')

    td = next(b.find('TransientData') for b in
              model_xml.findall('Boundaries/Boundary')
              if b.findtext('Name') == 'Steady Interior')
    # the reference must be a non-empty bare file name that resolves
    assert td.findtext('TimestepFileName') == cond.timestep_file_name

    # the member is a constant one-step series echoing the record constants
    root = ET.fromstring(ts_xml)
    assert root.tag == 'InputBoundaryConditionsData'
    steps = root.findall(
        'BoundaryConditionTransient/ConvectionTimesteps/'
        'FixedConvectionFilmTimestep')
    assert len(steps) == 1
    assert steps[0].findtext('Index') == '1'
    assert steps[0].findtext('Temperature') == '22.0'
    assert steps[0].findtext('FilmCoefficient') == '2.5'
    assert steps[0].findtext('Humidity') is not None


def test_steady_type_timestep_member_passes_reader_validation(tmp_path):
    """The written members satisfy pyhygrothermfem_fairyfly's transient input reader."""
    transient_input = _load_transient_input()
    model, cond = _steady_wall()
    thmz_path = str(tmp_path / 'steady_type.thmz')
    model_to_thmz(model, thmz_path, _transient_par())

    with zipfile.ZipFile(thmz_path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}

    references = transient_input.validate_transient_inputs(members)
    reference = next(
        ref for ref in references
        if ref['record']['uuid'] == cond.identifier)
    timestep_file = reference['timestep_file']
    assert reference['record']['bc_type'] == 'SteadyState'
    assert len(timestep_file.convection['FixedConvectionFilmTimestep']) == 1


def test_steady_type_missing_constant_is_explicit(tmp_path):
    """A SteadyState record without the required constants raises ValueError."""
    model = _wall()
    steady = Transient(bc_type='SteadyState')
    steady.display_name = 'Steady Interior'
    model.boundaries[1].properties.therm.condition = steady
    with pytest.raises(ValueError, match='constant'):
        model_to_thmz(model, str(tmp_path / 'bad.thmz'), _transient_par())

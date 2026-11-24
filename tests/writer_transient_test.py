# coding=utf-8
"""Tests for transient members in the THERM/THMZ write path."""
import zipfile
from xml.etree import ElementTree as ET

import pytest
from fairyfly.model import Model
from fairyfly_next_therm.condition.steadystate import SteadyState
from fairyfly_next_therm.condition.transient import Transient
from fairyfly_next_therm.lib.conditions import interior
from fairyfly_next_therm.lib.materials import concrete
from fairyfly_next_therm.material.hygrothermal import HygrothermalMaterial
from fairyfly_next_therm.simulation.parameter import SimulationParameter
from fairyfly_next_therm.simulation.transient import TransientCalculation
from fairyfly_next_therm.writer import model_to_therm_xml, model_to_thmz


def _wall(transient_bc=False):
    model = Model.from_layers([100, 200], height=1000)
    model.display_name = 'Transient Wall'
    model.shapes[0].properties.therm.material = concrete
    model.shapes[1].properties.therm.material = HygrothermalMaterial(
        0.62, density=1700, specific_heat=840, vapor_diffusion_resistance=38,
        moisture_storage_function=[[0.0, 0.0], [0.95, 120.0], [1.0, 300.0]])
    if transient_bc:
        ext = Transient(
            convection_model='ASHRAE/NFRC Outside',
            timesteps={i: {'temperature': -10 + i, 'humidity': 0.7,
                           'wind_speed': 4.0}
                       for i in range(1, 4)})
        ext.display_name = 'ORNL Exterior'
        model.boundaries[0].properties.therm.condition = ext
    model.boundaries[1].properties.therm.condition = interior
    return model


def _transient_par():
    return SimulationParameter(
        transient=TransientCalculation(
            time_range=86400, timestep=3600, initial_temperature=10,
            initial_humidity=0.6, methodology='Use first timestep'))


@pytest.mark.parametrize('transient_bc', [False, True])
@pytest.mark.parametrize('output_kind', ['xml', 'thmz'])
def test_fresh_transient_input_has_empty_calculation_version(
        transient_bc, output_kind, tmp_path):
    """A new transient input retains the empty calculation-origin element."""
    model = _wall(transient_bc=transient_bc)
    if output_kind == 'xml':
        root = model_to_therm_xml(model, _transient_par())
    else:
        path = str(tmp_path / 'fresh_transient.thmz')
        model_to_thmz(model, path, _transient_par())
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read('Model.xml'))
            assert not any(name.startswith('transient results/')
                           for name in archive.namelist())
    general = root.find('Properties/General')
    calculation_version = general.find('CalculationVersion')
    assert calculation_version is not None
    assert calculation_version.text is None
    assert general.findtext('CreationVersion') == 'Version 8.1.30.0'
    assert general.findtext('LastModifiedVersion') == 'Version 8.1.30.0'
    assert root.findtext('Properties/CalculationOptions/CalculationMode') == \
        'Transient'


def test_steady_model_has_no_transient_members(tmp_path):
    """Steady-state THMZ output is unchanged by the transient additions."""
    model = _wall()
    thmz_path = str(tmp_path / 'steady.thmz')
    model_to_thmz(model, thmz_path)

    with zipfile.ZipFile(thmz_path) as archive:
        names = archive.namelist()
        assert 'TransientTypeBC.xml' not in names
        assert not any(n.startswith('timestep input files/') for n in names)
        model_xml = ET.fromstring(archive.read('Model.xml'))
        steady_xml = ET.fromstring(archive.read('SteadyStateBC.xml'))
        materials_xml = ET.fromstring(archive.read('Materials.xml'))
    options = model_xml.find('Properties/CalculationOptions')
    assert options.findtext('CalculationMode') == 'Steady-State'
    general = model_xml.find('Properties/General')
    assert general.findtext('CalculationVersion') == 'Version 8.1.30.0'
    assert general.findtext('CreationVersion') == 'Version 8.1.30.0'
    assert general.findtext('LastModifiedVersion') == 'Version 8.1.30.0'
    for boundary in model_xml.findall('Boundaries/Boundary'):
        assert boundary.find('TransientData') is None
    bc_names = [bc.findtext('Name') for bc in steady_xml.findall(
        'BoundaryCondition')]
    assert set(bc_names) == \
        {'Adiabatic', 'Generic Exterior', 'Generic Interior'}


def test_steady_model_xml_unchanged_options():
    """model_to_therm_xml keeps the steady calculation options."""
    model = _wall()
    root = model_to_therm_xml(model)
    options = root.find('Properties/CalculationOptions')
    assert options.findtext('CalculationMode') == 'Steady-State'
    assert options.findtext('SimulationEngine') == 'Conrad'
    general = root.find('Properties/General')
    assert general.findtext('CalculationVersion') == 'Version 8.1.30.0'
    assert general.findtext('CreationVersion') == 'Version 8.1.30.0'
    assert general.findtext('LastModifiedVersion') == 'Version 8.1.30.0'


def test_transient_model_xml_writes_transient_data():
    """A Transient boundary condition emits Boundary/TransientData."""
    model = _wall(transient_bc=True)
    cond = model.boundaries[0].properties.therm.condition
    root = model_to_therm_xml(model, _transient_par())

    options = root.find('Properties/CalculationOptions')
    assert options.findtext('CalculationMode') == 'Transient'
    assert options.findtext('SimulationEngine') == 'HygroThermFEM'
    assert options.findtext('SimulateMoisture') == 'false'
    assert options.findtext('TransientCalculationMethodology') == \
        'Use first timestep'
    assert options.findtext(
        'ConstantInitialConditionsTransient/Temperature') == '10.0'
    assert options.findtext(
        'ConstantInitialConditionsTransient/Humidity') == '0.6'
    assert options.findtext('EngineParameters/TimeStep') == '3600.0'
    assert options.findtext('EngineParameters/NumberOfTimesteps') == '24'

    boundaries = root.findall('Boundaries/Boundary')
    transient_bounds = [
        b for b in boundaries if b.findtext('Name') == 'ORNL Exterior']
    assert len(transient_bounds) == 1
    td = transient_bounds[0].find('TransientData')
    assert [child.tag for child in td] == \
        ['UUID', 'TimestepFileName', 'Surface']
    assert td.findtext('UUID') == cond.identifier
    assert td.findtext('TimestepFileName') == cond.timestep_file_name
    assert float(td.findtext('Surface/Length')) > 0
    interior_bounds = [
        b for b in boundaries if b.findtext('Name') == 'Generic Interior']
    assert len(interior_bounds) == 1
    assert interior_bounds[0].find('TransientData') is None


def test_transient_thmz_with_constant_boundaries_has_empty_type_table(tmp_path):
    """Transient THMZ with constant boundaries includes an empty type table."""
    model = _wall()
    thmz_path = str(tmp_path / 'constant_boundaries_transient.thmz')
    model_to_thmz(model, thmz_path, _transient_par())

    with zipfile.ZipFile(thmz_path) as archive:
        names = archive.namelist()
        assert names.count('TransientTypeBC.xml') == 1
        assert not any(n.startswith('timestep input files/') for n in names)
        bct_xml = ET.fromstring(archive.read('TransientTypeBC.xml'))
        model_xml = ET.fromstring(archive.read('Model.xml'))
        steady_xml = ET.fromstring(archive.read('SteadyStateBC.xml'))

    assert bct_xml.tag == 'BoundaryConditionsType'
    assert [child.tag for child in bct_xml] == ['Version']
    assert bct_xml.findtext('Version') == '1'
    options = model_xml.find('Properties/CalculationOptions')
    assert options.findtext('CalculationMode') == 'Transient'
    for boundary in model_xml.findall('Boundaries/Boundary'):
        assert boundary.find('TransientData') is None
    bc_names = [bc.findtext('Name') for bc in steady_xml.findall(
        'BoundaryCondition')]
    assert set(bc_names) == \
        {'Adiabatic', 'Generic Exterior', 'Generic Interior'}


def test_transient_thmz_members_roundtrip(tmp_path):
    """Transient members land in the archive and read back losslessly."""
    model = _wall(transient_bc=True)
    cond = model.boundaries[0].properties.therm.condition
    thmz_path = str(tmp_path / 'transient.thmz')
    model_to_thmz(model, thmz_path, _transient_par())

    with zipfile.ZipFile(thmz_path) as archive:
        names = archive.namelist()
        assert 'TransientTypeBC.xml' in names
        member = 'timestep input files/{}'.format(cond.timestep_file_name)
        assert member in names
        bct_xml = ET.fromstring(archive.read('TransientTypeBC.xml'))
        ts_xml = archive.read(member).decode('utf-8')
        model_xml = ET.fromstring(archive.read('Model.xml'))
        materials_xml = ET.fromstring(archive.read('Materials.xml'))
        steady_xml = ET.fromstring(archive.read('SteadyStateBC.xml'))

    # the type record and its timesteps read back losslessly
    assert bct_xml.tag == 'BoundaryConditionsType'
    records = bct_xml.findall('BoundaryConditionType')
    assert len(records) == 1
    cond_dup = Transient.from_therm_xml(
        records[0], Transient.timesteps_from_xml_str(ts_xml))
    assert cond_dup == cond

    # steady library holds only steady records
    bc_names = [bc.findtext('Name')
                for bc in steady_xml.findall('BoundaryCondition')]
    assert 'ORNL Exterior' not in bc_names
    assert 'Generic Interior' in bc_names
    assert 'Adiabatic' in bc_names

    # the boundary links to the type record and its timestep member
    td = next(b.find('TransientData') for b in
              model_xml.findall('Boundaries/Boundary')
              if b.findtext('Name') == 'ORNL Exterior')
    assert td.findtext('UUID') == cond.identifier
    assert td.findtext('TimestepFileName') == cond.timestep_file_name

    # the hygrothermal material survives the archive roundtrip
    mat = next(m for m in materials_xml.findall('Material')
               if m.find('Solid/HygroThermal/MoistureStorageFunction')
               is not None)
    mat_dup = HygrothermalMaterial.from_therm_xml(mat)
    assert mat_dup == model.shapes[1].properties.therm.material


def test_transient_par_dict_roundtrip():
    """SimulationParameter carries the optional transient block."""
    par = _transient_par()
    par_dict = par.to_dict()
    par_dup = SimulationParameter.from_dict(par_dict)

    assert par_dict == par_dup.to_dict()
    assert par == par_dup
    assert par_dup.transient.number_of_timesteps == 24
    assert par_dup.transient.timestep == 3600
    assert par_dup.transient.methodology == 'Use first timestep'
    # a steady parameter dict has no transient key
    steady = SimulationParameter()
    assert 'transient' not in steady.to_dict()
    assert SimulationParameter.from_dict(steady.to_dict()).transient is None


def test_transient_calculation_checks():
    """Time range, step count and methodology are consistent."""
    calc = TransientCalculation(time_range=86400, timestep=3600)
    assert calc.number_of_timesteps == 24
    assert calc.time_range == 86400
    with pytest.raises(ValueError, match='multiple'):
        TransientCalculation(time_range=10000, timestep=3600)
    with pytest.raises(ValueError, match='do not agree'):
        TransientCalculation(
            time_range=86400, timestep=3600, number_of_timesteps=25)
    with pytest.raises(ValueError, match='THMZ-E2000'):
        TransientCalculation(methodology='Values from input file')
    with pytest.raises(ValueError, match='methodology'):
        TransientCalculation(methodology='Rolling')

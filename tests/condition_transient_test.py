# coding=utf-8
import pytest
import uuid
import xml.etree.ElementTree as ET

from fairyfly_next_therm.condition.steadystate import SteadyState
from fairyfly_next_therm.condition.transient import Transient


def _exterior_transient():
    cond_id = uuid.uuid4()
    cond = Transient(
        convection_model='Fixed Convection Coefficient',
        radiation_model='Black Body Radiation',
        timesteps={
            1: {'temperature': 10, 'humidity': 0.1, 'film_coefficient': 7,
                'radiation_temperature': 10, 'emissivity': 0.9},
            2: {'temperature': 11, 'humidity': 0.2, 'film_coefficient': 8,
                'radiation_temperature': 11, 'emissivity': 0.9}},
        identifier=cond_id)
    cond.display_name = 'ORNL Exterior'
    return cond


def test_transient_init():
    """Test the initialization of Transient objects and basic properties."""
    cond = _exterior_transient()
    str(cond)  # test the string representation of the condition
    cond_dup = cond.duplicate()

    assert cond.identifier == cond_dup.identifier
    assert cond.display_name == cond_dup.display_name == 'ORNL Exterior'
    assert cond.bc_type == cond_dup.bc_type == 'Transient'
    assert cond.bc_model == cond_dup.bc_model == 'Neumann'
    assert cond.convection_model == \
        cond_dup.convection_model == 'Fixed Convection Coefficient'
    assert cond.radiation_model == \
        cond_dup.radiation_model == 'Black Body Radiation'
    assert cond.timesteps == cond_dup.timesteps
    assert cond.timestep_file_name == \
        'BC_TS_{}.xml'.format(cond.identifier)


def test_transient_equivalency():
    """Test the equality of a condition to another Transient."""
    cond_1 = _exterior_transient()
    cond_2 = cond_1.duplicate()
    interior = Transient(
        timesteps={1: {'temperature': 20, 'humidity': 0.5,
                       'film_coefficient': 2.5}})
    interior.display_name = 'ORNL Interior'

    assert cond_1 == cond_2
    assert cond_1 != interior
    collection = [cond_1, cond_2, interior]
    assert len(set(collection)) == 2

    cond_2.timesteps[1]['temperature'] = 36
    assert cond_1 != cond_2
    assert len(set(collection)) == 3


def test_transient_lockability():
    """Test the lockability of the Transient condition."""
    cond = _exterior_transient()
    cond.surface_tilt = 45
    cond.lock()
    with pytest.raises(AttributeError):
        cond.surface_tilt = 90
    cond.unlock()
    cond.surface_tilt = 90


def test_transient_model_checks():
    """The record validates bc_type, models, timesteps and member names."""
    with pytest.raises(ValueError, match='THMZ-E5001'):
        Transient(convection_model='Montazeri',
                  timesteps={1: {'temperature': 10, 'humidity': 0.1,
                                 'wind_speed': 1.0,
                                 'wind_direction': 220}})
    with pytest.raises(ValueError, match='bc_type'):
        Transient(bc_type='Monthly')
    with pytest.raises(ValueError, match='bc_model'):
        Transient(bc_model='Robin')
    with pytest.raises(ValueError, match='timestep'):
        Transient()  # a Transient record requires a timestep series
    with pytest.raises(ValueError, match='cannot carry timesteps'):
        Transient(bc_type='SteadyState', temperature=21,
                  film_coefficient=2.5,
                  timesteps={1: {'temperature': 21, 'humidity': 0.5}})
    with pytest.raises(ValueError, match='missing values'):
        Transient(timesteps={1: {'temperature': 10}})  # film/humidity missing
    with pytest.raises(ValueError, match='1 or greater'):
        Transient(timesteps={0: {'temperature': 10, 'humidity': 0.1,
                                 'film_coefficient': 7}})
    with pytest.raises(ValueError, match='unknown keys'):
        Transient(timesteps={1: {'temperature': 10, 'humidity': 0.1,
                                 'film_coefficient': 7, 'pressure': 1}})
    with pytest.raises(ValueError, match='bare file name'):
        Transient(timesteps={1: {'temperature': 10, 'humidity': 0.1,
                                 'film_coefficient': 7}},
                  timestep_file_name='dir/BC_TS_x.xml')
    with pytest.raises(ValueError, match='.xml'):
        Transient(timesteps={1: {'temperature': 10, 'humidity': 0.1,
                                 'film_coefficient': 7}},
                  timestep_file_name='BC_TS_x.csv')


def test_transient_to_from_xml():
    """Test the BoundaryConditionType XML roundtrip."""
    cond = _exterior_transient()
    xml_cond = cond.to_therm_xml_str()
    cond_dup = Transient.from_therm_xml_str(xml_cond, cond.timesteps)

    assert cond == cond_dup
    assert cond_dup.display_name == 'ORNL Exterior'
    assert cond_dup.bc_type == 'Transient'
    assert cond_dup.timesteps == cond.timesteps
    root = ET.fromstring(xml_cond)
    tags = [child.tag for child in root]
    assert tags == ['UUID', 'Name', 'Protected', 'bcType', 'bcModel',
                    'Convection', 'Radiation', 'UseHeatFlux',
                    'UseTemperature', 'UseHumidity', 'Color']
    assert root.findtext('bcType') == 'Transient'
    assert root.findtext('bcModel') == 'Neumann'
    assert root.findtext('Convection/Model') == 'Fixed Convection Coefficient'
    assert root.findtext('Radiation/Model') == 'Black Body Radiation'


def test_transient_to_timestep_xml():
    """Timestep input files mirror the THERM InputBoundaryConditionsData."""
    cond = _exterior_transient()
    root = cond.to_timestep_xml()

    assert root.tag == 'InputBoundaryConditionsData'
    assert root.findtext('Version') == '1'
    assert root.findtext('Name') == 'ORNL Exterior'
    records = root.findall(
        'BoundaryConditionTransient/ConvectionTimesteps/'
        'FixedConvectionFilmTimestep')
    assert len(records) == 2
    assert records[0].findtext('Index') == '1'
    assert records[0].findtext('Temperature') == '10'
    assert records[0].findtext('Humidity') == '0.1'
    assert records[0].findtext('FilmCoefficient') == '7'
    rad = root.findall(
        'BoundaryConditionTransient/RadiationTimesteps/'
        'BlackBodyRadiationTimestep')
    assert len(rad) == 2
    assert rad[1].findtext('Temperature') == '11'
    assert rad[1].findtext('Emissivity') == '0.9'


def test_transient_timestep_roundtrip():
    """Timestep dictionaries survive an XML roundtrip."""
    cond = _exterior_transient()
    parsed = Transient.timesteps_from_xml_str(cond.to_timestep_xml_str())
    assert parsed == cond.timesteps


def test_transient_dirichlet_omits_convection_series():
    """A UseTemperature record writes Temperature/Humidity series only."""
    cond = Transient(
        bc_model='Dirichlet', use_temperature=True, use_humidity=True,
        convection_model=None,
        timesteps={1: {'surface_temperature': 10, 'humidity': 0.8},
                   2: {'surface_temperature': 11, 'humidity': 0.9}})
    root = cond.to_timestep_xml()

    assert root.find('BoundaryConditionTransient/ConvectionTimesteps') is None
    temps = root.findall('BoundaryConditionTransient/TemperatureTimestep')
    hums = root.findall('BoundaryConditionTransient/HumidityTimestep')
    assert [t.findtext('Temperature') for t in temps] == ['10', '11']
    assert [h.findtext('Humidity') for h in hums] == ['0.8', '0.9']
    # pinned records carry no convection declaration of their own
    assert Transient.from_therm_xml_str(
        cond.to_therm_xml_str()).convection_model is None


def test_humidity_only_pin_writes_humidity_series():
    """A humidity-only Dirichlet record writes HumidityTimestep only."""
    cond = Transient(
        bc_model='Dirichlet', use_humidity=True, convection_model=None,
        timesteps={1: {'humidity': 0.8}, 2: {'humidity': 0.6}})
    root = cond.to_timestep_xml()

    assert root.find('BoundaryConditionTransient/ConvectionTimesteps') is None
    assert root.find('BoundaryConditionTransient/RadiationTimesteps') is None
    hums = root.findall('BoundaryConditionTransient/HumidityTimestep')
    assert [h.findtext('Humidity') for h in hums] == ['0.8', '0.6']
    # the type record carries no Convection block
    record = cond.to_therm_xml()
    assert record.find('Convection') is None
    cond_dup = Transient.from_therm_xml(record, cond.timesteps)
    assert cond_dup.convection_model is None


def test_convection_driven_record_needs_convection_model():
    """convection_model=None is rejected on convection-driven records."""
    with pytest.raises(ValueError, match='convection_model'):
        Transient(convection_model=None,
                  timesteps={1: {'temperature': 10, 'humidity': 0.5}})


def test_transient_heat_flux_series():
    """A UseHeatFlux record writes HeatFluxTimestep elements only."""
    cond = Transient(
        use_heat_flux=True, convection_model=None,
        timesteps={1: {'heat_flux': -20}, 2: {'heat_flux': -15}})
    root = cond.to_timestep_xml()

    assert root.find('BoundaryConditionTransient/ConvectionTimesteps') is None
    fluxes = root.findall('BoundaryConditionTransient/HeatFluxTimestep')
    assert [f.findtext('HeatFlux') for f in fluxes] == ['-20', '-15']


def test_transient_steady_type_record():
    """A bcType=SteadyState record carries constant values, no timesteps."""
    cond = Transient(
        bc_type='SteadyState', temperature=22, film_coefficient=2.5,
        radiation_model='Automatic Enclosure', radiation_temperature=10,
        surface_emissivity=0.9, view_factor=1)
    xml_root = cond.to_therm_xml()

    assert xml_root.findtext('bcType') == 'SteadyState'
    assert xml_root.findtext('Convection/Temperature') == '22.0'
    assert xml_root.findtext('Convection/FilmCoefficient') == '2.5'
    assert xml_root.findtext('Radiation/Temperature') == '10.0'
    assert xml_root.findtext('Radiation/SurfaceEmissivity') == '0.9'
    cond_dup = Transient.from_therm_xml(ET.fromstring(
        ET.tostring(xml_root)))
    assert cond_dup.bc_type == 'SteadyState'
    assert cond_dup.temperature == 22
    assert cond_dup.film_coefficient == 2.5


def test_transient_data_xml():
    """The Boundary TransientData block follows the serializer order."""
    cond = _exterior_transient()
    boundary = ET.Element('Boundary')
    cond.to_transient_data_xml(boundary, 150.5)
    td = boundary.find('TransientData')

    assert [child.tag for child in td] == \
        ['UUID', 'TimestepFileName', 'Surface']
    assert td.findtext('UUID') == cond.identifier
    assert td.findtext('TimestepFileName') == cond.timestep_file_name
    assert td.findtext('Surface/Tilt') == '90'
    assert td.findtext('Surface/Length') == '150.5'
    # explicit geometry overrides and a Building block
    cond_2 = Transient(
        timesteps={1: {'temperature': 10, 'humidity': 0.1,
                       'film_coefficient': 7}},
        surface_tilt=0, surface_length=500, building_width=20,
        building_height=5)
    boundary = ET.Element('Boundary')
    cond_2.to_transient_data_xml(boundary, 150.5)
    td = boundary.find('TransientData')
    assert [child.tag for child in td] == \
        ['UUID', 'TimestepFileName', 'Surface', 'Building']
    assert td.findtext('Surface/Tilt') == '0.0'
    assert td.findtext('Surface/Length') == '500.0'
    assert td.findtext('Building/Width') == '20.0'
    assert td.findtext('Building/Height') == '5.0'
    # SteadyState records reference their constant-step timestep member
    cond_3 = Transient(bc_type='SteadyState', temperature=22,
                       film_coefficient=2.5)
    boundary = ET.Element('Boundary')
    cond_3.to_transient_data_xml(boundary, 150.5)
    assert boundary.findtext('TransientData/TimestepFileName') == \
        cond_3.timestep_file_name
    # the constant member echoes the record constants at Index 1
    steady_root = cond_3.to_steady_timestep_xml()
    steps = steady_root.findall(
        'BoundaryConditionTransient/ConvectionTimesteps/'
        'FixedConvectionFilmTimestep')
    assert len(steps) == 1
    assert steps[0].findtext('Index') == '1'
    assert steps[0].findtext('Temperature') == '22.0'


def test_transient_dict_methods():
    """Test the to/from dict methods."""
    cond = _exterior_transient()

    cond_dict = cond.to_dict()
    cond_dup = Transient.from_dict(cond_dict)

    assert cond_dict == cond_dup.to_dict()
    assert cond == cond_dup
    assert cond_dict['type'] == 'Transient'
    assert cond_dict['timesteps']['1']['film_coefficient'] == 7
    assert cond_dict['timesteps']['2']['emissivity'] == 0.9


def test_transient_from_dict_list_timesteps():
    """Timesteps may be given as an ordered list."""
    cond = Transient.from_dict({
        'type': 'Transient',
        'timesteps': [
            {'temperature': 10, 'humidity': 0.1, 'film_coefficient': 7},
            {'temperature': 11, 'humidity': 0.2, 'film_coefficient': 8}]})
    assert sorted(cond.timesteps) == [1, 2]
    assert cond.timesteps[2]['temperature'] == 11


def test_non_driven_records_reject_model_declarations():
    """Convection and radiation models belong to convection-driven records.

    A record driven by use_heat_flux, use_temperature or a humidity pin does
    not read its Convection block; declaring one (including the constructor
    default) is a mixed setting that is rejected rather than silently
    ignored, matching the pinned-edges-first dispatch of the solver.
    """
    with pytest.raises(ValueError, match='does not drive convection'):
        Transient(bc_model='Dirichlet', use_humidity=True,
                  timesteps={1: {'humidity': 0.8}})  # default model leaks in
    with pytest.raises(ValueError, match='does not drive convection'):
        Transient(bc_model='Dirichlet', use_humidity=True,
                  convection_model='ASHRAE/NFRC Inside',
                  timesteps={1: {'humidity': 0.8}})
    with pytest.raises(ValueError, match='does not drive convection'):
        Transient(bc_model='Dirichlet', use_humidity=True,
                  convection_model=None,
                  radiation_model='Black Body Radiation',
                  timesteps={1: {'humidity': 0.8}})
    with pytest.raises(ValueError, match='does not drive convection'):
        Transient(bc_model='Dirichlet', use_temperature=True,
                  timesteps={1: {'surface_temperature': 20}})  # default model
    with pytest.raises(ValueError, match='does not drive convection'):
        Transient(bc_type='SteadyState', bc_model='Dirichlet',
                  use_humidity=True, imposed_humidity=0.8)  # default model


def test_foreign_pin_keeps_declared_inert_models():
    """Foreign records keep an inert Convection declaration on parse.

    THERM archives may carry the default Convection block on a pure humidity
    pin; the read path preserves it for lossless roundtrip even though new
    Transient objects cannot declare one on a non-driven record.
    """
    cond = Transient(
        bc_model='Dirichlet', use_humidity=True, convection_model=None,
        timesteps={1: {'humidity': 0.8}})
    record = cond.to_therm_xml()
    conv = ET.SubElement(record, 'Convection')
    ET.SubElement(conv, 'Model').text = 'ASHRAE/NFRC Outside'
    ET.SubElement(conv, 'WindSpeed').text = '4.0'

    parsed = Transient.from_therm_xml(record, cond.timesteps)
    assert parsed.convection_model == 'ASHRAE/NFRC Outside'
    assert parsed.wind_speed == 4.0
    # dict and duplicate roundtrips preserve the inert declaration
    parsed_dup = parsed.duplicate()
    assert parsed_dup.convection_model == 'ASHRAE/NFRC Outside'
    parsed_dict = Transient.from_dict(parsed.to_dict())
    assert parsed_dict.convection_model == 'ASHRAE/NFRC Outside'
    # the timestep member still writes the pin series only
    root = parsed.to_timestep_xml()
    assert root.find('BoundaryConditionTransient/ConvectionTimesteps') is None
    assert [h.findtext('Humidity') for h in root.findall(
        'BoundaryConditionTransient/HumidityTimestep')] == ['0.8']


def test_foreign_dirichlet_record_preserves_convection_series():
    """A foreign pin record roundtrips declared convection timesteps."""
    cond = Transient(
        bc_model='Dirichlet', use_temperature=True, convection_model=None,
        timesteps={1: {'surface_temperature': 20, 'temperature': 10,
                       'humidity': 0.5, 'film_coefficient': 4}})
    record = cond.to_therm_xml()
    conv = ET.SubElement(record, 'Convection')
    ET.SubElement(conv, 'Model').text = 'Fixed Convection Coefficient'
    parsed = Transient.from_therm_xml(record, dict(cond.timesteps))

    root = parsed.to_timestep_xml()
    steps = root.findall(
        'BoundaryConditionTransient/ConvectionTimesteps/'
        'FixedConvectionFilmTimestep')
    assert len(steps) == 1
    assert steps[0].findtext('FilmCoefficient') == '4'


def test_steady_humidity_pin_requires_humidity_constant():
    """A SteadyState humidity pin must carry its imposed humidity."""
    cond = Transient(
        bc_type='SteadyState', bc_model='Dirichlet', use_humidity=True,
        convection_model=None, imposed_humidity=0.8)
    root = cond.to_steady_timestep_xml()
    steps = root.findall('BoundaryConditionTransient/HumidityTimestep')
    assert [s.findtext('Humidity') for s in steps] == ['0.8']
    assert root.find('BoundaryConditionTransient/ConvectionTimesteps') is None

    cond_missing = Transient(
        bc_type='SteadyState', bc_model='Dirichlet', use_humidity=True,
        convection_model=None)
    with pytest.raises(ValueError, match='imposed_humidity'):
        cond_missing.to_steady_timestep_xml()


def test_steady_convection_humidity_column_stays_inert():
    """A plain convection record keeps the inert Humidity column fill."""
    cond = Transient(
        bc_type='SteadyState', temperature=22, film_coefficient=2.5)
    root = cond.to_steady_timestep_xml()
    step = root.find(
        'BoundaryConditionTransient/ConvectionTimesteps/'
        'FixedConvectionFilmTimestep')
    assert step.findtext('Humidity') == '0.0'


def test_dict_to_condition_dispatch():
    """Condition dictionaries dispatch by type."""
    from fairyfly_next_therm.condition.dictutil import dict_to_condition
    steady = SteadyState(-18, 26)
    assert isinstance(dict_to_condition(steady.to_dict()), SteadyState)
    transient = _exterior_transient()
    assert isinstance(dict_to_condition(transient.to_dict()), Transient)
    with pytest.raises(ValueError, match='condition type'):
        dict_to_condition({'type': 'Solar'})


def test_transient_xml_roundtrip_does_not_depend_on_dict_insertion_order():
    """Step indices determine equality, not the insertion order of a dictionary."""
    condition = Transient(timesteps={
        2: {'temperature': 12, 'humidity': 0.6, 'film_coefficient': 8},
        1: {'temperature': 10, 'humidity': 0.4, 'film_coefficient': 7}})
    steps = Transient.timesteps_from_xml(condition.to_timestep_xml())
    parsed = Transient.from_therm_xml(condition.to_therm_xml(), steps)
    assert parsed == condition
    assert hash(parsed) == hash(condition)

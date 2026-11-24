# coding=utf-8
"""Lossless-or-explicitly-rejected transient XML at the public object boundary."""
from copy import deepcopy
import xml.etree.ElementTree as ET

import pytest

from fairyfly_next_therm.condition.transient import Transient


def _condition():
    """Return a boundary with all supported record subtrees and timestep families."""
    return Transient(
        use_humidity=True, radiation_model='Black Body Radiation',
        imposed_humidity=0.5, solar_radiation=0, absorptance=0.2,
        timesteps=[dict(temperature=10, humidity=0.4, film_coefficient=7,
                        radiation_temperature=5, emissivity=0.9, solar_radiation=0),
                   dict(temperature=12, humidity=0.6, film_coefficient=8,
                        radiation_temperature=6, emissivity=0.8, solar_radiation=0)])


@pytest.mark.parametrize('path, kind, code', [
    ('.', 'unknown', 'E2001'),
    ('Convection', 'unknown', 'E2001'),
    ('Radiation', 'unknown', 'E2001'),
    ('Solar', 'unknown', 'E2001'),
    ('Humidity', 'unknown', 'E2001'),
    ('.', 'attribute', 'E2001'),
    ('Convection/Model', 'attribute', 'E2001'),
    ('Humidity', 'duplicate', 'E2002'),
    ('Convection', 'duplicate', 'E2002'),
])
def test_transient_type_xml_rejects_unrepresentable_fields(path, kind, code):
    """Unknown or duplicate record data must not disappear on write-back."""
    condition = _condition()
    condition.display_name = 'XML Acceptance'
    root = condition.to_therm_xml()
    element = root if path == '.' else root.find(path)
    if kind == 'unknown':
        ET.SubElement(element, 'UnmodeledValue').text = '123'
    elif kind == 'attribute':
        element.set('unmodeled', '123')
    else:
        root.append(deepcopy(element))
    with pytest.raises(ValueError, match='THMZ-' + code) as error:
        Transient.from_therm_xml(root, condition.timesteps)
    assert 'XML Acceptance' in str(error.value)
    assert 'BoundaryConditionType' in str(error.value)


@pytest.mark.parametrize('path, kind, code', [
    ('.', 'unknown', 'E2001'),
    ('BoundaryConditionTransient', 'unknown', 'E2001'),
    ('BoundaryConditionTransient/ConvectionTimesteps', 'unknown', 'E2001'),
    ('BoundaryConditionTransient/ConvectionTimesteps/FixedConvectionFilmTimestep',
     'unknown', 'E2001'),
    ('BoundaryConditionTransient/HumidityTimestep/Humidity', 'unknown', 'E2001'),
    ('.', 'attribute', 'E2001'),
    ('BoundaryConditionTransient/ConvectionTimesteps/FixedConvectionFilmTimestep',
     'attribute', 'E2001'),
    ('BoundaryConditionTransient/HumidityTimestep/Humidity', 'attribute', 'E2001'),
    ('BoundaryConditionTransient/HumidityTimestep/Humidity', 'duplicate', 'E2002'),
])
def test_timestep_xml_rejects_unrepresentable_fields(path, kind, code):
    """The public timestep parser rejects unknown data at every relevant depth."""
    condition = _condition()
    condition.display_name = 'XML Acceptance'
    root = condition.to_timestep_xml()
    element = root if path == '.' else root.find(path)
    if kind == 'unknown':
        ET.SubElement(element, 'UnmodeledValue').text = '123'
    elif kind == 'attribute':
        element.set('unmodeled', '123')
    else:
        root.find('BoundaryConditionTransient/HumidityTimestep').append(
            deepcopy(element))
    with pytest.raises(ValueError, match='THMZ-' + code) as error:
        Transient.timesteps_from_xml(root)
    assert 'XML Acceptance' in str(error.value)
    assert 'InputBoundaryConditionsData' in str(error.value)


def test_timestep_restart_is_explicitly_unrepresentable_not_collapsed():
    """A valid restarted-index sequence must not collapse into an index-keyed dict.

    Repeated indices are legal input to the independent reader; the current
    Transient object cannot preserve multiple occurrences of the same family.
    It must reject this representational limitation without calling the XML
    invalid or pretending a two-entry dictionary preserves three records.
    """
    root = _condition().to_timestep_xml()
    group = root.find('BoundaryConditionTransient/ConvectionTimesteps')
    restarted = deepcopy(group[0])
    restarted.find('Temperature').text = '14'
    group.append(restarted)
    with pytest.raises(ValueError, match='THMZ-E2005') as error:
        Transient.timesteps_from_xml(root)
    assert 'cannot preserve' in str(error.value)
    assert 'Index=1' in str(error.value)
    assert '14' in str(error.value)


def test_cross_family_same_index_roundtrip_is_lossless():
    """Convection, radiation, solar and humidity may legitimately share an index."""
    condition = _condition()
    steps = Transient.timesteps_from_xml(condition.to_timestep_xml())
    assert steps == condition.timesteps
    parsed = Transient.from_therm_xml(condition.to_therm_xml(), steps)
    assert parsed == condition
    assert Transient.timesteps_from_xml(parsed.to_timestep_xml()) == steps


def test_conflicting_cross_family_humidity_is_not_overwritten():
    """The one modeled humidity cannot silently replace a distinct second value."""
    root = _condition().to_timestep_xml()
    root.find('BoundaryConditionTransient/HumidityTimestep/Humidity').text = '0.9'
    with pytest.raises(ValueError, match='THMZ-E2005'):
        Transient.timesteps_from_xml(root)


def test_foreign_pin_montazeri_rejection_is_model_level():
    """Unsupported Montazeri cannot bypass validation as inert pin metadata."""
    condition = Transient(bc_model='Dirichlet', use_humidity=True,
                          convection_model=None, timesteps=[{'humidity': 0.8}])
    root = condition.to_therm_xml()
    ET.SubElement(ET.SubElement(root, 'Convection'), 'Model').text = 'Montazeri'
    with pytest.raises(ValueError, match='THMZ-E5001'):
        Transient.from_therm_xml(root, condition.timesteps)
    data = condition.to_dict()
    data['convection_model'] = 'Montazeri'
    with pytest.raises(ValueError, match='THMZ-E5001'):
        Transient.from_dict(data)


@pytest.mark.parametrize('field, value', [
    ('humidity', 1.1), ('temperature', -274), ('humidity', float('nan')),
    ('film_coefficient', float('inf')), ('emissivity', -0.1),
])
def test_invalid_timestep_numbers_are_explicit(field, value):
    """Numeric violations follow the same E2004 contract as the reader."""
    root = _condition().to_timestep_xml()
    paths = {
        'humidity': 'ConvectionTimesteps/FixedConvectionFilmTimestep/Humidity',
        'temperature': 'ConvectionTimesteps/FixedConvectionFilmTimestep/Temperature',
        'film_coefficient': 'ConvectionTimesteps/FixedConvectionFilmTimestep/FilmCoefficient',
        'emissivity': 'RadiationTimesteps/BlackBodyRadiationTimestep/Emissivity'}
    root.find('BoundaryConditionTransient/' + paths[field]).text = str(value)
    with pytest.raises(ValueError, match='THMZ-E2004'):
        Transient.timesteps_from_xml(root)


def test_valid_project_name_extension_survives_record_xml():
    """ProjectName is a modeled reader extension, not an unknown field."""
    condition = _condition()
    root = condition.to_therm_xml()
    ET.SubElement(root, 'ProjectName').text = 'XML Project'
    parsed = Transient.from_therm_xml(root, condition.timesteps)
    assert parsed.project_tag == 'XML Project'
    assert parsed.to_therm_xml().findtext('ProjectName') == 'XML Project'


def test_timestep_values_without_a_serialized_family_are_rejected():
    """Known but unused per-step values must not silently vanish from XML."""
    condition = _condition()
    condition.timesteps[1]['heat_flux'] = 123
    with pytest.raises(ValueError, match='THMZ-E2005') as error:
        condition.to_timestep_xml()
    assert 'heat_flux' in str(error.value)
    assert '123' in str(error.value)


def test_different_family_periods_are_not_silently_extended():
    """A shorter valid family cannot be padded by merged values from another family."""
    root = _condition().to_timestep_xml()
    transient = root.find('BoundaryConditionTransient')
    transient.remove(transient.findall('HumidityTimestep')[1])
    with pytest.raises(ValueError, match='THMZ-E2005') as error:
        Transient.timesteps_from_xml(root)
    assert 'cannot preserve' in str(error.value)
    assert 'HumidityTimestep' in str(error.value)


@pytest.mark.parametrize('field, value', [
    ('humidity', float('nan')), ('temperature', float('inf')),
    ('humidity', 1.1), ('film_coefficient', -7),
    ('wind_speed', -1), ('hr', -1), ('emissivity', -0.1),
    ('temperature', True),
])
def test_object_timestep_write_rejects_invalid_numbers(field, value):
    """The object entry and writer cannot bypass necessary numeric validation."""
    steps = _condition().timesteps
    steps[1][field] = value
    with pytest.raises(ValueError, match='THMZ-E2004'):
        Transient(use_humidity=True, radiation_model='Black Body Radiation',
                  solar_radiation=0, absorptance=0.2, timesteps=steps)
    condition = _condition()
    condition.timesteps[1][field] = value
    with pytest.raises(ValueError, match='THMZ-E2004'):
        condition.to_timestep_xml()


def test_negative_timestep_film_coefficient_is_rejected_on_read():
    """A finite but negative heat transfer coefficient is not physically valid."""
    root = _condition().to_timestep_xml()
    root.find('BoundaryConditionTransient/ConvectionTimesteps/'
              'FixedConvectionFilmTimestep/FilmCoefficient').text = '-7'
    with pytest.raises(ValueError, match='THMZ-E2004'):
        Transient.timesteps_from_xml(root)

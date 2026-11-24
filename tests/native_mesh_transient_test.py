# coding=utf-8
"""Tests for transient boundary segments in the native mesh writer."""
import xml.etree.ElementTree as ET

import pytest

from fairyfly_next_therm.condition.transient import Transient
from fairyfly_next_therm.native_mesh import mesh_to_xml


MODEL_XML = ET.fromstring('''
<ThermModel>
  <GlazingOrigin><x>500</x><y>500</y></GlazingOrigin>
  <Polygons><Polygon><Type>Material</Type><Points>
    <Point><x>0</x><y>0</y></Point>
    <Point><x>1000</x><y>0</y></Point>
    <Point><x>1000</x><y>1000</y></Point>
    <Point><x>0</x><y>1000</y></Point>
  </Points></Polygon></Polygons>
  <Boundaries>
    <Boundary><ID>1</ID><Name>Hot</Name><Type>Boundary Condition</Type>
      <StartPoint><x>0</x><y>1000</y></StartPoint>
      <EndPoint><x>0</x><y>0</y></EndPoint></Boundary>
    <Boundary><ID>2</ID><Name>Cold</Name><Type>Boundary Condition</Type>
      <StartPoint><x>1000</x><y>0</y></StartPoint>
      <EndPoint><x>1000</x><y>1000</y></EndPoint></Boundary>
    <Boundary><ID>3</ID><Name>Adiabatic</Name><Type>Boundary Condition</Type>
      <StartPoint><x>0</x><y>0</y></StartPoint>
      <EndPoint><x>1000</x><y>0</y></EndPoint></Boundary>
    <Boundary><ID>4</ID><Name>Adiabatic</Name><Type>Boundary Condition</Type>
      <StartPoint><x>1000</x><y>1000</y></StartPoint>
      <EndPoint><x>0</x><y>1000</y></EndPoint></Boundary>
  </Boundaries>
</ThermModel>''')

BOUNDARY_CONDITIONS = ET.fromstring('''
<BoundaryConditions>
  <BoundaryCondition><Name>Hot</Name><Simplified>
    <Temperature>20</Temperature><FilmCoefficient>10</FilmCoefficient>
  </Simplified></BoundaryCondition>
  <BoundaryCondition><Name>Cold</Name><Simplified>
    <Temperature>0</Temperature><FilmCoefficient>10</FilmCoefficient>
  </Simplified></BoundaryCondition>
  <BoundaryCondition><Name>Adiabatic</Name><Simplified>
    <Temperature>0</Temperature><FilmCoefficient>0</FilmCoefficient>
  </Simplified></BoundaryCondition>
</BoundaryConditions>''')


class _Point(object):
    def __init__(self, x, y, z=0):
        self.X, self.Y, self.Z = x, y, z


class _Face(object):
    def __init__(self, a, b, c, d):
        self.A, self.B, self.C, self.D = a, b, c, d


class _Mesh(object):
    Vertices = [_Point(0, 0), _Point(1000, 0),
                _Point(1000, 1000), _Point(0, 1000)]
    Faces = [_Face(0, 3, 2, 1)]  # Rhino may return clockwise face winding.


def _transient(name, **kwargs):
    cond = Transient(**kwargs)
    cond.display_name = name
    return cond


def test_transient_convection_and_dirichlet_segments():
    """Transient records become Convections or Temperatures segments."""
    hot = _transient(
        'Hot', bc_model='Dirichlet', use_temperature=True,
        convection_model=None, timesteps={1: {'surface_temperature': 25}})
    cold = _transient(
        'Cold', convection_model='ASHRAE/NFRC Outside',
        timesteps={1: {'temperature': -10, 'humidity': 0.7,
                       'wind_speed': 4.0}})
    transient = {'Hot': hot, 'Cold': cold}

    root = mesh_to_xml(MODEL_XML, BOUNDARY_CONDITIONS, _Mesh(),
                       transient_conditions=transient)

    temps = root.findall('Case/BCSegments/Temperatures/Temperature')
    assert len(temps) == 2
    assert all(t.findtext('temperature') == '25.0' for t in temps)
    assert all(t.findtext('label') == '1' for t in temps)
    convections = root.findall('Case/BCSegments/Convections/Convection')
    assert len(convections) == 3
    cold_segments = [c for c in convections if c.findtext('label') == '2']
    assert len(cold_segments) == 1
    assert cold_segments[0].findtext('filmCoefficient') == '0.0'
    assert cold_segments[0].findtext('temperature1') == '-10.0'
    assert root.find('Case/BCSegments/Fluxes') is None


def test_transient_heat_flux_and_fixed_film_segments():
    """UseHeatFlux records become Fluxes; fixed film keeps its first step."""
    hot = _transient(
        'Hot', use_heat_flux=True, convection_model=None,
        timesteps={1: {'heat_flux': -20}, 2: {'heat_flux': -15}})
    cold = _transient(
        'Cold', timesteps={1: {'temperature': 0, 'humidity': 0.2,
                               'film_coefficient': 4},
                           2: {'temperature': 1, 'humidity': 0.2,
                               'film_coefficient': 5}})
    transient = {'Hot': hot, 'Cold': cold}

    root = mesh_to_xml(MODEL_XML, BOUNDARY_CONDITIONS, _Mesh(),
                       transient_conditions=transient)

    fluxes = root.findall('Case/BCSegments/Fluxes/Flux')
    assert len(fluxes) == 1
    assert fluxes[0].findtext('flux1') == fluxes[0].findtext('flux2') == '-20.0'
    assert fluxes[0].findtext('label') == '1'
    cold_segments = [c for c in
                     root.findall('Case/BCSegments/Convections/Convection')
                     if c.findtext('label') == '2']
    assert len(cold_segments) == 1
    assert cold_segments[0].findtext('filmCoefficient') == '4.0'


def test_transient_steady_type_uses_constant_values():
    """A bcType=SteadyState record drives segments from its constants."""
    hot = _transient(
        'Hot', bc_type='SteadyState', temperature=22, film_coefficient=2.5)
    transient = {'Hot': hot}

    root = mesh_to_xml(MODEL_XML, BOUNDARY_CONDITIONS, _Mesh(),
                       transient_conditions=transient)

    hot_segments = [c for c in
                    root.findall('Case/BCSegments/Convections/Convection')
                    if c.findtext('label') == '1']
    assert len(hot_segments) == 1
    assert hot_segments[0].findtext('filmCoefficient') == '2.5'
    assert hot_segments[0].findtext('temperature1') == '22.0'


def test_transient_dirichlet_missing_temperature_is_rejected():
    """A temperature-driven transient boundary needs its driving value."""
    hot = _transient('Hot', bc_model='Dirichlet', use_temperature=True,
                     convection_model=None,
                     timesteps={1: {'surface_temperature': 25}})
    hot._timesteps[1] = {}  # strip the value after construction checks
    transient = {'Hot': hot}

    with pytest.raises(ValueError, match='imposed temperature'):
        mesh_to_xml(MODEL_XML, BOUNDARY_CONDITIONS, _Mesh(),
                    transient_conditions=transient)


def test_humidity_only_dirichlet_needs_no_temperature():
    """A UseHumidity Dirichlet pin without UseTemperature emits a
    Temperatures segment with the kernel-ignored 0 placeholder.

    The solver reads HumidityTimestep only for a pure humidity pin
    (ticket 09 convention); Mesh.xml has no humidity segment type, so the
    Temperatures member carries an inert placeholder.
    """
    cold = _transient(
        'Cold', bc_model='Dirichlet', use_humidity=True,
        convection_model=None, timesteps={1: {'humidity': 0.8}})
    transient = {'Cold': cold}

    root = mesh_to_xml(MODEL_XML, BOUNDARY_CONDITIONS, _Mesh(),
                       transient_conditions=transient)

    temps = root.findall('Case/BCSegments/Temperatures/Temperature')
    assert len(temps) == 2
    assert all(t.findtext('label') == '2' for t in temps)
    assert all(t.findtext('temperature') == '0.0' for t in temps)
    # the pin emits no convection segment; other boundaries keep theirs
    conv_labels = [c.findtext('label') for c in
                   root.findall('Case/BCSegments/Convections/Convection')]
    assert '2' not in conv_labels
    assert sorted(conv_labels) == ['1', '3', '4']


def test_humidity_only_dirichlet_missing_humidity_is_rejected():
    """A pure humidity pin must declare a humidity value."""
    cold = _transient(
        'Cold', bc_model='Dirichlet', use_humidity=True,
        convection_model=None, timesteps={1: {'humidity': 0.8}})
    cold._timesteps[1] = {}  # strip the value after construction checks
    transient = {'Cold': cold}

    with pytest.raises(ValueError, match='humidity'):
        mesh_to_xml(MODEL_XML, BOUNDARY_CONDITIONS, _Mesh(),
                    transient_conditions=transient)


def test_transient_radiation_is_not_emitted():
    """Radiation timestep models never produce Radiations segments."""
    hot = _transient(
        'Hot', radiation_model='Black Body Radiation',
        timesteps={1: {'temperature': 10, 'humidity': 0.1,
                       'film_coefficient': 7, 'radiation_temperature': 10,
                       'emissivity': 0.9}})
    transient = {'Hot': hot}

    root = mesh_to_xml(MODEL_XML, BOUNDARY_CONDITIONS, _Mesh(),
                       transient_conditions=transient)

    assert root.find('Case/BCSegments/Radiations') is None
    assert root.find('Case/BCSegments/RadiationEnclosures') is None


def test_steady_mesh_output_unchanged_without_transient_conditions():
    """The default path emits only the Convections group as before."""
    root = mesh_to_xml(MODEL_XML, BOUNDARY_CONDITIONS, _Mesh())
    bc_segments = root.find('Case/BCSegments')
    assert [child.tag for child in bc_segments] == ['Convections']
    assert len(bc_segments.findall('Convections/Convection')) == 4

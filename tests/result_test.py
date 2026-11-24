# coding=utf-8
"""Test result parsing with synthetic THMZ archives."""

import copy
import json
import xml.etree.ElementTree as ET
import zipfile

import pytest
from ladybug_geometry.geometry2d import Vector2D
from ladybug_geometry.geometry3d import Mesh3D, Plane, Point3D

from fairyfly_next_therm.result import THMZResult, UFactor


def _add_fields(parent, fields):
    """Add scalar XML elements to a parent."""
    for name, value in fields.items():
        ET.SubElement(parent, name).text = str(value)


def _write_thmz(path, members):
    """Write the XML members of a synthetic THMZ file."""
    with zipfile.ZipFile(path, 'w') as archive:
        for name, xml in members.items():
            archive.writestr(name, ET.tostring(xml, encoding='utf-8'))
    return str(path)


@pytest.fixture(scope='module')
def thmz_files(tmp_path_factory):
    """Generate unsolved and solved archives for a single quad."""
    folder = tmp_path_factory.mktemp('synthetic_results')
    coordinates = ((0, 0), (100, 0), (100, 80), (0, 80))
    model = ET.fromstring(
        '<Model><Properties><General><Notes/></General></Properties>'
        '<Polygons><Polygon><Points/></Polygon></Polygons>'
        '<GlazingOrigin><x>0</x><y>0</y></GlazingOrigin></Model>')
    plane = Plane(o=Point3D(12, 23, 0))
    model.find('Properties/General/Notes').text = 'Plane: ' + json.dumps(plane.to_dict())

    mesh = ET.fromstring(
        '<Mesh><Case><Nodes/><Elements><Element/></Elements></Case></Mesh>')
    mesh_results = ET.fromstring('<Results><Case><Nodes/></Case></Results>')
    points = model.find('Polygons/Polygon/Points')
    nodes = mesh.find('Case/Nodes')
    element = mesh.find('Case/Elements/Element')
    result_nodes = mesh_results.find('Case/Nodes')
    for index, (x, y) in enumerate(coordinates):
        _add_fields(ET.SubElement(points, 'Point'), {'x': x, 'y': y})
        _add_fields(ET.SubElement(nodes, 'Node'), {'x': x / 1000, 'y': y / 1000})
        ET.SubElement(element, 'node{}'.format(index)).text = str(index)
        _add_fields(ET.SubElement(result_nodes, 'Node'),
                    {'Temperature': 10 + index, 'X-flux': 3, 'Y-flux': 4})

    results = ET.fromstring('<Results><Case/></Results>')
    case = results.find('Case')
    exterior = ET.SubElement(case, 'U-factors')
    _add_fields(exterior, {'Tag': 'Exterior', 'DeltaT': 20, 'HeatFlux': -6})
    for name, length, u_factor in (
        ('Total Length', 100, 3),
        ('Projected X', 60, 5),
        ('Projected Y', 80, 3.75),
        ('Projected in glass plane', 100, 3),
        ('Custom Rotation', 50, 6),
    ):
        _add_fields(ET.SubElement(exterior, 'Projection'),
                    {'Length-type': name, 'Length': length, 'U-factor': u_factor})
    edge = ET.SubElement(case, 'U-factors')
    _add_fields(edge, {'Tag': 'Edge', 'DeltaT': 20, 'HeatFlux': -0.8})
    _add_fields(ET.SubElement(edge, 'Projection'),
                {'Length-type': 'Total Length', 'Length': 20, 'U-factor': 2})
    return {
        'unsolved': _write_thmz(folder / 'unsolved.thmz', {'Model.xml': model}),
        'solved': _write_thmz(folder / 'solved.thmz', {
            'Model.xml': model,
            'Mesh.xml': mesh,
            'SteadyStateMeshResults.xml': mesh_results,
            'SteadyStateResults.xml': results,
        }),
    }


def _rewrite_thmz(source_path, target_path, member, update):
    """Write a THMZ copy after updating a single XML member."""
    with zipfile.ZipFile(source_path, 'r') as source:
        members = {name: source.read(name) for name in source.namelist()}
    tree = ET.fromstring(members[member])
    update(tree)
    members[member] = ET.tostring(tree, encoding='utf-8')
    with zipfile.ZipFile(target_path, 'w') as target:
        for name, content in members.items():
            target.writestr(name, content)
    return str(target_path)


def test_thmz_load_mesh(thmz_files):
    """Load the plane, polygon, and single-quad mesh."""
    solved = THMZResult(thmz_files['solved'])
    assert isinstance(solved.plane, Plane)
    assert solved.plane.o == Point3D(12, 23, 0)
    assert len(solved.shape_polygons) == 1
    assert isinstance(solved.mesh, Mesh3D)
    assert len(solved.mesh.faces) == 1
    assert len(solved.mesh.vertices) == 4

    unsolved = THMZResult(thmz_files['unsolved'])
    assert isinstance(unsolved.plane, Plane)
    assert unsolved.mesh is None


def test_thmz_load_mesh_results(thmz_files):
    """Read per-node temperatures, fluxes, and flux magnitudes."""
    solved = THMZResult(thmz_files['solved'])
    assert solved.temperatures == (10.0, 11.0, 12.0, 13.0)
    assert solved.heat_fluxes == (Vector2D(3, 4),) * 4
    assert solved.heat_flux_magnitudes == (5.0,) * 4

    unsolved = THMZResult(thmz_files['unsolved'])
    assert unsolved.temperatures is None
    assert unsolved.heat_fluxes is None
    assert unsolved.heat_flux_magnitudes is None
    assert unsolved.humidities is None
    assert unsolved.water_contents is None


def test_thmz_load_node_humidity_and_water_content(thmz_files, tmp_path):
    """Read optional humidity and water content fields when present."""
    def add_moisture_fields(mesh_results):
        nodes = mesh_results.findall('Case/Nodes/Node')
        for index, node in enumerate(nodes):
            _add_fields(node, {'Humidity': 0.4 + index * 0.01})
            if index % 2 == 0:
                _add_fields(node, {'WaterContent': index * 2})

    path = _rewrite_thmz(thmz_files['solved'], tmp_path / 'moisture.thmz',
                         'SteadyStateMeshResults.xml', add_moisture_fields)
    moist = THMZResult(path)
    assert moist.humidities == pytest.approx((0.4, 0.41, 0.42, 0.43))
    assert moist.water_contents == (0.0, None, 4.0, None)

    dry = THMZResult(thmz_files['solved'])
    assert dry.humidities is None
    assert dry.water_contents is None


def test_thmz_load_u_factor_results(thmz_files):
    """Read multiple U-factor tags and preserve missing results."""
    solved = THMZResult(thmz_files['solved'])
    assert len(solved.u_factors) == 2
    assert all(isinstance(value, UFactor) for value in solved.u_factors)
    assert THMZResult(thmz_files['unsolved']).u_factors is None


def test_thmz_u_factor_projections_and_units(thmz_files):
    """Read every supported projection and handle missing projections."""
    exterior, edge = THMZResult(thmz_files['solved']).u_factors
    assert exterior.name == 'Exterior'
    assert exterior.delta_temperature == 20  # Celsius
    assert exterior.heat_flux == -6  # W/m of depth
    assert exterior.total_u_factor == 3  # W/m2-K
    assert exterior.total_length == 100  # mm
    assert exterior.projected_x_u_factor == 5
    assert exterior.projected_x_length == 60
    assert exterior.projected_y_u_factor == 3.75
    assert exterior.projected_y_length == 80
    assert exterior.projected_in_glass_plane_u_factor == 3
    assert exterior.projected_in_glass_plane_length == 100
    assert exterior.custom_rotation_u_factor == 6
    assert exterior.custom_rotation_length == 50

    assert edge.name == 'Edge'
    assert edge.projected_x_u_factor is None
    assert edge.projected_x_length == 0
    assert edge.custom_rotation_u_factor is None
    assert edge.custom_rotation_length == 0


def test_thmz_u_factor_empty_and_undefined_values(thmz_files, tmp_path):
    """Distinguish absent tags, zero temperature difference, and zero length."""
    def remove_tags(results):
        case = results.find('Case')
        for factor in case.findall('U-factors'):
            case.remove(factor)

    def make_undefined(results):
        case = results.find('Case')
        first = case.find('U-factors')
        zero_length = copy.deepcopy(first)
        first.find('DeltaT').text = '0'
        zero_length.find('Tag').text = 'Zero Length'
        zero_length.find("Projection[Length-type='Total Length']/Length").text = '0'
        case.insert(1, zero_length)

    member = 'SteadyStateResults.xml'
    no_tags = _rewrite_thmz(thmz_files['solved'], tmp_path / 'no_tags.thmz',
                            member, remove_tags)
    assert THMZResult(no_tags).u_factors == ()

    undefined = _rewrite_thmz(thmz_files['solved'], tmp_path / 'undefined.thmz',
                              member, make_undefined)
    zero_delta, zero_length, _ = THMZResult(undefined).u_factors
    assert zero_delta.total_length > 0
    assert zero_delta.total_u_factor is None
    assert zero_delta.projected_y_u_factor is None
    assert zero_length.total_length == 0
    assert zero_length.total_u_factor is None
    assert zero_length.projected_y_u_factor == 3.75

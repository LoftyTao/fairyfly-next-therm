"""Tests for per-surface emissivity selection in THERM boundary output."""
import json
import zipfile
from xml.etree import ElementTree as ET

import pytest
from fairyfly.model import Model
from fairyfly_next_therm.lib.conditions import exterior, interior
from fairyfly_next_therm.material.cavity import CavityMaterial
from fairyfly_next_therm.material.solid import SolidMaterial
from fairyfly_next_therm.lib.gases import _gases
from fairyfly_next_therm.writer import model_to_therm_xml, model_to_thmz


def _model_with_cavity(left_sides=None, right_sides=None):
    model = Model.from_layers([100, 100, 100], height=100)
    left, cavity, right = model.shapes
    left.properties.therm.material = SolidMaterial(0.5, 0.81, 0.21)
    cavity.properties.therm.material = CavityMaterial(
        cavity_model='ISO15099', emissivity=0.9)
    right.properties.therm.material = SolidMaterial(0.8, 0.68, 0.37)
    if left_sides is not None:
        left.user_data = {'therm_surface_sides': left_sides}
    if right_sides is not None:
        right.user_data = {'therm_surface_sides': right_sides}
    model.boundaries[0].properties.therm.condition = exterior
    model.boundaries[1].properties.therm.condition = interior
    return model


def _sides_with_back_at_x(shape, x_coordinate):
    return [
        'Back' if all(abs(point.x - x_coordinate) < 0.01
                      for point in segment.vertices) else 'Front'
        for segment in shape.geometry.segments
    ]


def _therm_boundary_for_neighbor(root, neighbor_uuid, boundary_type=None):
    for boundary in root.findall('./Boundaries/Boundary'):
        if boundary_type is not None and boundary.findtext('Type') != boundary_type:
            continue
        if any(node.tag.startswith('NeighborPolygonUUID') and
               node.text == neighbor_uuid for node in boundary):
            yield boundary


def _assert_boundary_surface(boundary, side, emissivity):
    assert boundary.findtext('MaterialSide') == side
    assert boundary.findtext('ThermalEmissionProperties/Emissivity') == \
        str(emissivity)


def test_external_boundaries_use_selected_material_sides():
    """The exterior/interior boundary emits selected side and matching value."""
    model = _model_with_cavity()
    model.shapes[0].user_data = {
        'therm_surface_sides': _sides_with_back_at_x(model.shapes[0], 100)}
    model.shapes[2].user_data = {
        'therm_surface_sides': _sides_with_back_at_x(model.shapes[2], 300)}
    root = model_to_therm_xml(model)

    exterior_boundary = next(_therm_boundary_for_neighbor(
        root, model.shapes[0].therm_uuid, 'Boundary Condition'))
    interior_boundary = next(_therm_boundary_for_neighbor(
        root, model.shapes[2].therm_uuid, 'Boundary Condition'))
    _assert_boundary_surface(exterior_boundary, 'Front', 0.81)
    _assert_boundary_surface(interior_boundary, 'Back', 0.37)


def test_frame_cavity_boundaries_use_adjacent_solid_surface_sides():
    """Each cavity-contact edge uses the side selected on its adjacent solid."""
    model = _model_with_cavity()
    model.shapes[0].user_data = {
        'therm_surface_sides': _sides_with_back_at_x(model.shapes[0], 100)}
    model.shapes[2].user_data = {
        'therm_surface_sides': _sides_with_back_at_x(model.shapes[2], 300)}
    root = model_to_therm_xml(model)
    cavity_uuid = model.shapes[1].therm_uuid
    left_uuid = model.shapes[0].therm_uuid
    right_uuid = model.shapes[2].therm_uuid

    frame_boundaries = list(_therm_boundary_for_neighbor(
        root, cavity_uuid, 'Frame Cavity'))
    left_contact = next(boundary for boundary in frame_boundaries
                        if any(node.tag.startswith('NeighborPolygonUUID') and
                               node.text == left_uuid for node in boundary))
    right_contact = next(boundary for boundary in frame_boundaries
                         if any(node.tag.startswith('NeighborPolygonUUID') and
                                node.text == right_uuid for node in boundary))
    _assert_boundary_surface(left_contact, 'Back', 0.21)
    _assert_boundary_surface(right_contact, 'Front', 0.68)


def test_missing_surface_sides_preserves_front_default():
    """Models produced before per-surface choices retain Front emissivity."""
    model = _model_with_cavity()
    root = model_to_therm_xml(model)

    exterior_boundary = next(_therm_boundary_for_neighbor(
        root, model.shapes[0].therm_uuid, 'Boundary Condition'))
    left_contact = next(boundary for boundary in _therm_boundary_for_neighbor(
        root, model.shapes[1].therm_uuid, 'Frame Cavity')
        if any(node.text == model.shapes[0].therm_uuid for node in
               (child for child in boundary
                if child.tag.startswith('NeighborPolygonUUID'))))
    _assert_boundary_surface(exterior_boundary, 'Front', 0.81)
    _assert_boundary_surface(left_contact, 'Front', 0.81)


def test_surface_choices_follow_source_edges_when_writer_flips_shapes():
    """Per-edge choices survive writer normalization of clockwise shapes."""
    model = _model_with_cavity()
    left, right = model.shapes[0], model.shapes[2]
    left._geometry = left.geometry.flip()
    right._geometry = right.geometry.flip()
    left.user_data = {'therm_surface_sides': _sides_with_back_at_x(left, 100)}
    right.user_data = {'therm_surface_sides': _sides_with_back_at_x(right, 300)}

    root = model_to_therm_xml(model)
    left_contact = next(boundary for boundary in _therm_boundary_for_neighbor(
        root, model.shapes[1].therm_uuid, 'Frame Cavity')
        if any(node.text == left.therm_uuid for node in boundary
               if node.tag.startswith('NeighborPolygonUUID')))
    _assert_boundary_surface(left_contact, 'Back', 0.21)


def test_surface_sides_are_preserved_in_thmz_model_xml(tmp_path):
    """The public THMZ writer persists selected sides on cavity and outer edges."""
    model = _model_with_cavity()
    model.shapes[0].user_data = {
        'therm_surface_sides': _sides_with_back_at_x(model.shapes[0], 100)}
    model.shapes[2].user_data = {
        'therm_surface_sides': _sides_with_back_at_x(model.shapes[2], 300)}
    thmz_path = str(tmp_path / 'surface-sides.thmz')
    model_to_thmz(model, thmz_path)

    with zipfile.ZipFile(thmz_path) as archive:
        root = ET.fromstring(archive.read('Model.xml'))
    exterior_boundary = next(_therm_boundary_for_neighbor(
        root, model.shapes[0].therm_uuid, 'Boundary Condition'))
    left_contact = next(boundary for boundary in _therm_boundary_for_neighbor(
        root, model.shapes[1].therm_uuid, 'Frame Cavity')
        if any(node.text == model.shapes[0].therm_uuid for node in boundary
               if node.tag.startswith('NeighborPolygonUUID')))
    _assert_boundary_surface(exterior_boundary, 'Front', 0.81)
    _assert_boundary_surface(left_contact, 'Back', 0.21)


@pytest.mark.parametrize('sides', [['Back'], ['Front', 'Back', 'Front', 'sideways']])
def test_invalid_surface_sides_are_rejected(sides):
    """Side metadata cannot silently drift from the source geometry."""
    model = _model_with_cavity(left_sides=sides)
    with pytest.raises(ValueError, match='therm_surface_sides'):
        model_to_therm_xml(model)


def test_nfrc_export_records_actual_iso_model_and_requested_label(tmp_path):
    model = _model_with_cavity()
    cavity = CavityMaterial(cavity_model='NFRC', emissivity=0.9)
    model.shapes[1].properties.therm.material = cavity
    thmz_path = str(tmp_path / 'nfrc.thmz')
    model_to_thmz(model, thmz_path)

    with zipfile.ZipFile(thmz_path) as archive:
        materials = ET.fromstring(archive.read('Materials.xml'))
        mapping = json.loads(archive.read('FairyflyNext.json'))[
            'cavity_model_mappings']
    record = next(item for item in materials.findall('Material')
                  if item.findtext('UUID') == cavity.therm_uuid)
    assert record.findtext('Cavity/CavityStandard') == 'ISO15099'
    assert mapping == [{
        'material_uuid': cavity.therm_uuid,
        'requested': 'NFRC', 'effective': 'ISO15099',
        'reference': 'LBNL NFRC Simulation Manual 6.3.6',
    }]
    assert cavity.cavity_model == 'NFRC'


def test_nfrc_export_rejects_non_air_gas(tmp_path):
    model = _model_with_cavity()
    for shape in (model.shapes[0], model.shapes[2]):
        solid = SolidMaterial(0.5)
        solid.display_name = 'Duplicate'
        shape.properties.therm.material = solid
    gas = _gases['Argon'].duplicate()
    gas.unlock()
    gas.display_name = 'Air'
    model.shapes[1].properties.therm.material = CavityMaterial(
        gas=gas, cavity_model='NFRC')
    thmz_path = str(tmp_path / 'unsupported-nfrc.thmz')
    with pytest.raises(ValueError, match='NFRC.*Air'):
        model_to_thmz(model, thmz_path)
    assert not (tmp_path / 'unsupported-nfrc.thmz').exists()
    assert all(shape.properties.therm.material.display_name == 'Duplicate'
               for shape in (model.shapes[0], model.shapes[2]))

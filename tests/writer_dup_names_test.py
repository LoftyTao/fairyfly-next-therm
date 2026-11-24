"""Tests for temporary material renames during THMZ export.

The writer assigns unique temporary display names to materials that share a
display_name so that the THMZ contains one unambiguous record per material.
These tests pin down that the renames are deterministic, never collide with
a pre-existing suffixed name, and are fully reverted on success and on error.
"""
import os
import zipfile
from xml.etree import ElementTree as ET

import pytest
from fairyfly.model import Model
from fairyfly_next_therm.lib.conditions import exterior, interior
from fairyfly_next_therm.material.solid import SolidMaterial
from fairyfly_next_therm.writer import model_to_thmz


def _model_with_names(names):
    """Three-layer model with a distinct SolidMaterial per Shape; the i-th
    material carries names[i] as its display_name."""
    assert len(names) == 3
    model = Model.from_layers([100, 100, 100], height=100)
    for i, shape in enumerate(model.shapes):
        mat = SolidMaterial(0.5 + i, 0.8, 0.2)
        mat.unlock()
        mat.display_name = names[i]
        shape.properties.therm.material = mat  # setter locks the material
    model.boundaries[0].properties.therm.condition = exterior
    model.boundaries[1].properties.therm.condition = interior
    return model


def _material_state(model):
    """Snapshot (identifier, display_name, raw name, lock state) per shape."""
    state = []
    for shape in model.shapes:
        mat = shape.properties.therm.material
        state.append((mat.identifier, mat.display_name, mat._display_name,
                      mat._locked))
    return state


def _thmz_materials(thmz_path):
    """Return the record map (UUID -> Name) from Materials.xml and the
    polygon map (MaterialUUID -> MaterialName) from Model.xml."""
    with zipfile.ZipFile(thmz_path) as archive:
        mats_root = ET.fromstring(archive.read('Materials.xml'))
        model_root = ET.fromstring(archive.read('Model.xml'))
    records = {m.findtext('UUID'): m.findtext('Name')
               for m in mats_root.findall('Material')}
    poly_refs = {}
    for poly in model_root.findall('.//Polygon'):
        if poly.findtext('Type') == 'Material':
            poly_refs[poly.findtext('MaterialUUID')] = \
                poly.findtext('MaterialName')
    return records, poly_refs


def test_materials_property_preserves_shape_order():
    """Unique materials follow first-encounter order, not set order."""
    model = _model_with_names(['Mat A', 'Mat B', 'Mat C'])
    mats = model.properties.therm.materials
    assert mats == [s.properties.therm.material for s in model.shapes]


def test_three_duplicate_names_fully_restored_after_export(tmp_path):
    """Every temporary rename is reverted once the THMZ is written."""
    model = _model_with_names(['Duplicate', 'Duplicate', 'Duplicate'])
    before = _material_state(model)
    thmz_path = str(tmp_path / 'three-dups.thmz')
    model_to_thmz(model, thmz_path)

    assert _material_state(model) == before
    records, poly_refs = _thmz_materials(thmz_path)
    mats = [s.properties.therm.material for s in model.shapes]
    assert len(records) == 3
    assert len(set(records.values())) == 3  # unique record names
    for mat in mats:
        assert records[mat.identifier] == poly_refs[mat.identifier]
    # suffixes are assigned in ascending identifier order so that the
    # exported name of a material is stable across writer runs
    ordered = sorted(mat.identifier for mat in mats)
    assert records[ordered[0]] == 'Duplicate'
    assert records[ordered[1]] == 'Duplicate_2'
    assert records[ordered[2]] == 'Duplicate_3'


def test_temporary_names_skip_pre_existing_suffixed_name(tmp_path):
    """A material already named 'Duplicate_2' is never shadowed by a rename."""
    model = _model_with_names(['Duplicate', 'Duplicate', 'Duplicate_2'])
    before = _material_state(model)
    owner = model.shapes[2].properties.therm.material
    thmz_path = str(tmp_path / 'collision.thmz')
    model_to_thmz(model, thmz_path)

    assert _material_state(model) == before
    records, poly_refs = _thmz_materials(thmz_path)
    names = list(records.values())
    assert len(records) == 3
    assert len(set(names)) == 3  # no two records share a Name
    # the pre-existing 'Duplicate_2' record still belongs to its own material
    assert records[owner.identifier] == 'Duplicate_2'
    assert poly_refs[owner.identifier] == 'Duplicate_2'


def test_failed_export_restores_original_display_names(tmp_path):
    """An exception mid-write cannot leak the temporary names."""
    model = _model_with_names(['Duplicate'] * 3)
    before = _material_state(model)
    # invalid per-surface metadata raises inside model_to_therm_xml, which
    # runs after the temporary renames
    model.shapes[0].user_data = {'therm_surface_sides': ['Front']}
    with pytest.raises(ValueError, match='therm_surface_sides'):
        model_to_thmz(model, str(tmp_path / 'exception.thmz'))
    assert _material_state(model) == before


def test_unlocked_duplicate_material_keeps_unlocked_state(tmp_path):
    """An unlocked duplicate-name material is not left locked by export."""
    model = _model_with_names(['Duplicate'] * 3)
    mat = model.shapes[1].properties.therm.material
    mat.unlock()
    assert mat._locked is False
    before = _material_state(model)
    model_to_thmz(model, str(tmp_path / 'locks.thmz'))
    assert mat._locked is False
    # model_to_therm_xml duplicates the Model; the duplicate shares the same
    # material objects and must not re-lock any of them
    assert _material_state(model) == before


def test_unlocked_condition_keeps_unlocked_state(tmp_path):
    """An unlocked boundary condition is not left locked by export."""
    model = _model_with_names(['Mat A', 'Mat B', 'Mat C'])
    con = model.boundaries[1].properties.therm.condition
    con.unlock()
    assert con._locked is False
    model_to_thmz(model, str(tmp_path / 'condition-lock.thmz'))
    assert con._locked is False

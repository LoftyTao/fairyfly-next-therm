"""Tests the features that fairyfly_next_therm adds to fairyfly Shape."""
from ladybug_geometry.geometry3d import Point3D, Face3D

from fairyfly.shape import Shape
from fairyfly_next_therm.properties.shape import ShapeThermProperties
from fairyfly_next_therm.material.solid import SolidMaterial
from fairyfly_next_therm.lib.materials import concrete, air_cavity


def test_therm_properties():
    """Test the existence of the Shape therm properties."""
    pts = (Point3D(0, 0, 0), Point3D(0, 0, 3), Point3D(1, 0, 3), Point3D(1, 0, 0))
    shape = Shape(Face3D(pts))
    shape.display_name = 'TestShape'
    assert hasattr(shape.properties, 'therm')
    assert isinstance(shape.properties.therm, ShapeThermProperties)

    assert shape.properties.therm.material == concrete
    shape.properties.therm.material = air_cavity
    assert shape.properties.therm.material == air_cavity

    insulation = SolidMaterial(0.049, 0.9, None, 265, None, 836)
    insulation.display_name = 'Insulation'
    shape.properties.therm.material = insulation
    assert shape.properties.therm.material == insulation


def test_duplicate():
    """Test what happens to therm properties when duplicating a Shape."""
    pts = (Point3D(0, 0, 0), Point3D(0, 0, 3), Point3D(1, 0, 3), Point3D(1, 0, 0))
    insulation = SolidMaterial(0.049, 0.9, None, 265, None, 836)
    insulation.display_name = 'Insulation'
    shape_original = Shape(Face3D(pts))
    shape_dup_1 = shape_original.duplicate()

    assert shape_original.properties.therm.host is shape_original
    assert shape_dup_1.properties.therm.host is shape_dup_1
    assert shape_original.properties.therm.host is not shape_dup_1.properties.therm.host

    assert shape_original.properties.therm.material == \
        shape_dup_1.properties.therm.material
    shape_dup_1.properties.therm.material = insulation
    assert shape_original.properties.therm.material != \
        shape_dup_1.properties.therm.material

    shape_dup_2 = shape_dup_1.duplicate()

    assert shape_dup_1.properties.therm.material == \
        shape_dup_2.properties.therm.material
    shape_dup_2.properties.therm.material = None
    assert shape_dup_1.properties.therm.material != \
        shape_dup_2.properties.therm.material


def test_duplicate_preserves_material_lock_state():
    """Duplicating a Shape must not change the shared material's lock state."""
    pts = (Point3D(0, 0, 0), Point3D(0, 0, 3), Point3D(1, 0, 3), Point3D(1, 0, 0))
    insulation = SolidMaterial(0.049, 0.9, None, 265, None, 836)
    insulation.display_name = 'Insulation'
    shape = Shape(Face3D(pts))
    shape.properties.therm.material = insulation  # setter locks it
    assert insulation._locked is True
    shape.duplicate()
    assert insulation._locked is True

    insulation.unlock()
    shape.duplicate()
    assert insulation._locked is False


def test_to_dict():
    """Test the Shape to_dict method with therm properties."""
    pts = (Point3D(0, 0, 0), Point3D(0, 0, 3), Point3D(1, 0, 3), Point3D(1, 0, 0))
    shape = Shape(Face3D(pts))
    shape.display_name = 'TestShape'
    insulation = SolidMaterial(0.049, 0.9, None, 265, None, 836)
    insulation.display_name = 'Insulation'

    sd = shape.to_dict()
    assert 'properties' in sd
    assert sd['properties']['type'] == 'ShapeProperties'
    assert 'therm' in sd['properties']
    assert sd['properties']['therm']['type'] == 'ShapeThermProperties'

    shape.properties.therm.material = insulation
    sd = shape.to_dict()
    assert 'material' in sd['properties']['therm']
    assert sd['properties']['therm']['material'] is not None
    assert sd['properties']['therm']['material']['display_name'] == 'Insulation'


def test_from_dict():
    """Test the Shape from_dict method with therm properties."""
    pts = (Point3D(0, 0, 0), Point3D(0, 0, 3), Point3D(1, 0, 3), Point3D(1, 0, 0))
    shape = Shape(Face3D(pts))
    shape.display_name = 'TestShape'
    insulation = SolidMaterial(0.049, 0.9, None, 265, None, 836)
    insulation.display_name = 'Insulation'
    shape.properties.therm.material = insulation

    sd = shape.to_dict()
    new_shape = Shape.from_dict(sd)
    assert new_shape.properties.therm.material == insulation
    assert new_shape.to_dict() == sd


def test_hygrothermal_material_extension():
    """Shape therm properties accept HygrothermalMaterial."""
    import pytest
    from fairyfly_next_therm.material.hygrothermal import \
        HygrothermalMaterial
    from fairyfly_next_therm.condition.steadystate import SteadyState

    pts = (Point3D(0, 0, 0), Point3D(0, 0, 3), Point3D(1, 0, 3),
           Point3D(1, 0, 0))
    shape = Shape(Face3D(pts))
    brick = HygrothermalMaterial(
        0.62, density=1700, specific_heat=840,
        moisture_storage_function=[[0.0, 0.0], [1.0, 300.0]])
    brick.display_name = 'Brick'
    shape.properties.therm.material = brick
    assert shape.properties.therm.material == brick

    # dict roundtrip keeps the HygrothermalMaterial
    sd = shape.to_dict()
    new_shape = Shape.from_dict(sd)
    assert new_shape.properties.therm.material == brick
    assert isinstance(new_shape.properties.therm.material,
                      HygrothermalMaterial)

    # non-material values are rejected with an explicit error
    with pytest.raises(ValueError, match='Material'):
        shape.properties.therm.material = SteadyState(20, 10)


def test_writer_to_therm_xml():
    """Test the Shape therm_xml method."""
    pts = (Point3D(0, 0, 0), Point3D(0, 0, 3), Point3D(1, 0, 3), Point3D(1, 0, 0))
    shape = Shape(Face3D(pts))
    shape.display_name = 'TestShape'
    insulation = SolidMaterial(0.049, 0.9, None, 265, None, 836)
    insulation.display_name = 'Insulation'
    shape.properties.therm.material = insulation

    assert hasattr(shape.to, 'therm_xml')
    xml_string = shape.to.therm_xml(shape)
    assert insulation.identifier in xml_string
    assert 'Insulation' in xml_string

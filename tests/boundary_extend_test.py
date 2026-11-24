"""Tests the features that fairyfly_next_therm adds to fairyfly Boundary."""
from ladybug_geometry.geometry3d import Point3D, LineSegment3D

from fairyfly.boundary import Boundary
from fairyfly_next_therm.properties.boundary import BoundaryThermProperties
from fairyfly_next_therm.condition.steadystate import SteadyState
from fairyfly_next_therm.lib.conditions import exterior, interior


def test_therm_properties():
    """Test the existence of the Boundary therm properties."""
    line_1 = LineSegment3D.from_end_points(Point3D(0, 0, 0), Point3D(0, 0, 3))
    line_2 = LineSegment3D.from_end_points(Point3D(1, 0, 0), Point3D(1, 0, 3))
    boundary = Boundary((line_1, line_2))
    boundary.display_name = 'TestBoundary'
    assert hasattr(boundary.properties, 'therm')
    assert isinstance(boundary.properties.therm, BoundaryThermProperties)

    assert boundary.properties.therm.condition == exterior
    boundary.properties.therm.condition = interior
    assert boundary.properties.therm.condition == interior

    interior_wood = SteadyState(24, 2.44)
    interior_wood.display_name = 'Interior Wood/Vinyl Frame'
    boundary.properties.therm.condition = interior_wood
    assert boundary.properties.therm.condition == interior_wood


def test_duplicate():
    """Test what happens to therm properties when duplicating a Boundary."""
    line_1 = LineSegment3D.from_end_points(Point3D(0, 0, 0), Point3D(0, 0, 3))
    line_2 = LineSegment3D.from_end_points(Point3D(1, 0, 0), Point3D(1, 0, 3))
    interior_wood = SteadyState(24, 2.44)
    interior_wood.display_name = 'Interior Wood/Vinyl Frame'
    boundary_original = Boundary((line_1, line_2))
    boundary_dup_1 = boundary_original.duplicate()

    assert boundary_original.properties.therm.host is boundary_original
    assert boundary_dup_1.properties.therm.host is boundary_dup_1
    assert boundary_original.properties.therm.host is not boundary_dup_1.properties.therm.host

    assert boundary_original.properties.therm.condition == \
        boundary_dup_1.properties.therm.condition
    boundary_dup_1.properties.therm.condition = interior_wood
    assert boundary_original.properties.therm.condition != \
        boundary_dup_1.properties.therm.condition

    boundary_dup_2 = boundary_dup_1.duplicate()

    assert boundary_dup_1.properties.therm.condition == \
        boundary_dup_2.properties.therm.condition
    boundary_dup_2.properties.therm.condition = None
    assert boundary_dup_1.properties.therm.condition != \
        boundary_dup_2.properties.therm.condition


def test_duplicate_preserves_condition_lock_state():
    """Duplicating a Boundary must not change the shared condition's lock state."""
    line_1 = LineSegment3D.from_end_points(Point3D(0, 0, 0), Point3D(0, 0, 3))
    line_2 = LineSegment3D.from_end_points(Point3D(1, 0, 0), Point3D(1, 0, 3))
    interior_wood = SteadyState(24, 2.44)
    interior_wood.display_name = 'Interior Wood/Vinyl Frame'
    boundary = Boundary((line_1, line_2))
    boundary.properties.therm.condition = interior_wood  # setter locks it
    assert interior_wood._locked is True
    boundary.duplicate()
    assert interior_wood._locked is True

    interior_wood.unlock()
    boundary.duplicate()
    assert interior_wood._locked is False


def test_to_dict():
    """Test the Boundary to_dict method with therm properties."""
    line_1 = LineSegment3D.from_end_points(Point3D(0, 0, 0), Point3D(0, 0, 3))
    line_2 = LineSegment3D.from_end_points(Point3D(1, 0, 0), Point3D(1, 0, 3))
    boundary = Boundary((line_1, line_2))
    boundary.display_name = 'TestBoundary'
    interior_wood = SteadyState(24, 2.44)
    interior_wood.display_name = 'Interior Wood/Vinyl Frame'

    bd = boundary.to_dict()
    assert 'properties' in bd
    assert bd['properties']['type'] == 'BoundaryProperties'
    assert 'therm' in bd['properties']
    assert bd['properties']['therm']['type'] == 'BoundaryThermProperties'

    boundary.properties.therm.condition = interior_wood
    bd = boundary.to_dict()
    assert 'condition' in bd['properties']['therm']
    assert bd['properties']['therm']['condition'] is not None
    assert bd['properties']['therm']['condition']['display_name'] == 'Interior Wood/Vinyl Frame'


def test_from_dict():
    """Test the Boundary from_dict method with therm properties."""
    line_1 = LineSegment3D.from_end_points(Point3D(0, 0, 0), Point3D(0, 0, 3))
    line_2 = LineSegment3D.from_end_points(Point3D(1, 0, 0), Point3D(1, 0, 3))
    boundary = Boundary((line_1, line_2))
    boundary.display_name = 'TestBoundary'
    interior_wood = SteadyState(24, 2.44)
    interior_wood.display_name = 'Interior Wood/Vinyl Frame'
    boundary.properties.therm.condition = interior_wood

    bd = boundary.to_dict()
    new_boundary = Boundary.from_dict(bd)
    assert new_boundary.properties.therm.condition == interior_wood
    assert new_boundary.to_dict() == bd


def test_transient_condition_extension():
    """Boundary therm properties accept Transient conditions."""
    import pytest
    from fairyfly_next_therm.condition.transient import Transient
    from fairyfly_next_therm.material.solid import SolidMaterial

    line_1 = LineSegment3D.from_end_points(Point3D(0, 0, 0), Point3D(0, 0, 3))
    line_2 = LineSegment3D.from_end_points(Point3D(1, 0, 0), Point3D(1, 0, 3))
    boundary = Boundary((line_1, line_2))
    transient = Transient(
        timesteps={1: {'temperature': 10, 'humidity': 0.5,
                       'film_coefficient': 7}})
    transient.display_name = 'Transient Exterior'
    boundary.properties.therm.condition = transient
    assert boundary.properties.therm.condition == transient

    # dict roundtrip keeps the Transient condition
    bd = boundary.to_dict()
    new_boundary = Boundary.from_dict(bd)
    assert new_boundary.properties.therm.condition == transient

    # non-condition values are rejected with an explicit error
    with pytest.raises(ValueError, match='SteadyState or Transient'):
        boundary.properties.therm.condition = SolidMaterial(1.0)


def test_writer_to_therm_xml():
    """Test the Boundary therm_xml method."""
    line_1 = LineSegment3D.from_end_points(Point3D(0, 0, 0), Point3D(0, 0, 3))
    line_2 = LineSegment3D.from_end_points(Point3D(1, 0, 0), Point3D(1, 0, 3))
    boundary = Boundary((line_1, line_2))
    boundary.display_name = 'TestBoundary'
    interior_wood = SteadyState(24, 2.44)
    interior_wood.display_name = 'Interior Wood/Vinyl Frame'
    boundary.properties.therm.condition = interior_wood

    assert hasattr(boundary.to, 'therm_xml')
    xml_string = boundary.to.therm_xml(boundary)
    assert interior_wood.display_name in xml_string
    assert boundary.therm_uuid[:-12] in xml_string

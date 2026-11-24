"""Public THMZ export checks for a void and a thin material layer."""
import zipfile
import xml.etree.ElementTree as ET

import pytest

from fairyfly.model import Model
from fairyfly.shape import Shape
from fairyfly.boundary import Boundary
from fairyfly_next_therm.lib.materials import concrete
from fairyfly_next_therm.lib.conditions import interior, exterior
from fairyfly_next_therm.material import SolidMaterial
from fairyfly_next_therm import native_mesh
from fairyfly_next_therm.writer import model_to_thmz


class _Point(object):
    def __init__(self, x, y):
        self.X, self.Y, self.Z = x, y, 0


class _Face(object):
    def __init__(self, nodes):
        self.A, self.B, self.C, self.D = nodes


def _rectangle(x0, y0, x1, y1, material=concrete):
    shape = Shape.from_vertices(((x0, y0, 0), (x1, y0, 0),
                                 (x1, y1, 0), (x0, y1, 0)))
    shape.properties.therm.material = material
    return shape


def _model(shapes, split_boundary=False):
    left = [(0, 0), (0, 350), (0, 1000)] if split_boundary else \
        [(0, 0), (0, 1000)]
    boundaries = []
    for vertices, condition in ((left, interior),
                                ([(1000, 0), (1000, 1000)], exterior)):
        boundary = Boundary.from_vertices([[(x, y, 0) for x, y in vertices]])
        boundary.properties.therm.condition = condition
        boundaries.append(boundary)
    return Model(shapes, boundaries)


def _native_grid(model_xml, skip_center=False):
    """A Q4 stand-in; real Rhino remeshing is checked in Rhino acceptance."""
    points = model_xml.findall('Polygons/Polygon/Points/Point')
    xs = sorted(set(float(p.findtext('x')) for p in points))
    ys = sorted(set(float(p.findtext('y')) for p in points))
    mesh = type('Mesh', (), {})()
    mesh.Vertices = [_Point(x, y) for y in ys for x in xs]
    mesh.Faces = []
    for row in range(len(ys) - 1):
        for column in range(len(xs) - 1):
            if skip_center and row == column == 1:
                continue
            node = row * len(xs) + column
            mesh.Faces.append(_Face((node, node + 1, node + len(xs) + 1,
                                     node + len(xs))))
    return mesh


def _xml_from_thmz(path, name):
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read(name))


def test_hole_stays_empty_and_its_perimeter_gets_boundary_segments(
        tmp_path, monkeypatch):
    model = _model([_rectangle(0, 0, 1000, 400),
                    _rectangle(0, 600, 1000, 1000),
                    _rectangle(0, 400, 400, 600),
                    _rectangle(600, 400, 1000, 600)])
    assert tuple(len(part) for part in model.properties.therm.problem_areas) == (0, 1)
    with pytest.raises(ValueError, match='without any holes'):
        model_to_thmz(model, str(tmp_path / 'legacy.thmz'))
    monkeypatch.setattr(native_mesh, '_quad_remesh',
                        lambda xml, target: _native_grid(xml, skip_center=True))
    path = str(tmp_path / 'hole.thmz')
    model_to_thmz(model, path, rhino_mesh=True)

    mesh = _xml_from_thmz(path, 'Mesh.xml')
    model_xml = _xml_from_thmz(path, 'Model.xml')
    assert len(mesh.findall('Case/Elements/Element')) == 8
    assert len(mesh.findall('Case/BCSegments/Convections/Convection')) == 16
    assert len(model_xml.findall('Polygons/Polygon')) == 4
    assert len(model_xml.findall('Boundaries/Boundary')) == 12
    with pytest.raises(ValueError, match='exactly one material polygon'):
        native_mesh.mesh_to_xml(model_xml, _xml_from_thmz(path, 'SteadyStateBC.xml'),
                                _native_grid(model_xml))


def test_one_millimeter_layer_and_offset_boundary_endpoint_survive_export(
        tmp_path, monkeypatch):
    layer = SolidMaterial(0.1, 0.9, None, 400, 0.81, 850, 7.9)
    model = _model([_rectangle(0, 0, 499, 1000),
                    _rectangle(499, 0, 500, 1000, layer),
                    _rectangle(500, 0, 1000, 1000)], split_boundary=True)
    monkeypatch.setattr(native_mesh, '_quad_remesh',
                        lambda xml, target: _native_grid(xml))
    path = str(tmp_path / 'thin.thmz')
    model_to_thmz(model, path, rhino_mesh=True)

    mesh = _xml_from_thmz(path, 'Mesh.xml')
    nodes = [(float(n.findtext('x')), float(n.findtext('y')))
             for n in mesh.findall('Case/Nodes/Node')]
    elements = mesh.findall('Case/Elements/Element')
    thin = [e for e in elements if e.findtext('materialID') == '2']
    assert len(thin) >= 1
    assert all(max(nodes[int(e.findtext('node{}'.format(i)))][0]
                   for i in range(1, 5)) -
               min(nodes[int(e.findtext('node{}'.format(i)))][0]
                   for i in range(1, 5)) == pytest.approx(0.001)
               for e in thin)
    labels = [s.findtext('label') for s in
              mesh.findall('Case/BCSegments/Convections/Convection')]
    assert len(labels) == len(set((s.findtext('node1'), s.findtext('node2'))
                                  for s in mesh.findall(
                                      'Case/BCSegments/Convections/Convection')))
    assert set(labels) == {b.findtext('ID') for b in _xml_from_thmz(
        path, 'Model.xml').findall('Boundaries/Boundary')}


def test_sub_tolerance_layer_is_rejected_instead_of_silently_deleted(
        tmp_path, monkeypatch):
    layer = SolidMaterial(0.01)
    model = _model([_rectangle(0, 0, 499.95, 1000),
                    _rectangle(499.95, 0, 500, 1000, layer),
                    _rectangle(500, 0, 1000, 1000)])
    monkeypatch.setattr(native_mesh, '_quad_remesh',
                        lambda xml, target: _native_grid(xml))
    path = str(tmp_path / 'lost-layer.thmz')
    with pytest.raises(ValueError, match='removed.*Shape'):
        model_to_thmz(model, path, rhino_mesh=True)

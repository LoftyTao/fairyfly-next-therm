import xml.etree.ElementTree as ET

import pytest

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


def test_rhino_quad_mesh_writes_q4_units_origin_and_boundary_labels():
    root = mesh_to_xml(MODEL_XML, BOUNDARY_CONDITIONS, _Mesh())
    assert root.findtext('Case/ModelType') == 'U-factor'
    assert [(node.findtext('x'), node.findtext('y'))
            for node in root.findall('Case/Nodes/Node')] == [
                ('-0.5', '-0.5'), ('0.5', '-0.5'),
                ('0.5', '0.5'), ('-0.5', '0.5')]
    element = root.find('Case/Elements/Element')
    assert [element.findtext('node{}'.format(i)) for i in range(1, 5)] == [
        '0', '1', '2', '3']
    assert element.findtext('materialID') == '1'
    conditions = root.findall('Case/BCSegments/Convections/Convection')
    assert len(conditions) == 4
    assert {condition.findtext('label') for condition in conditions} == {
        '1', '2', '3', '4'}


def test_frame_cavity_metadata_does_not_become_an_exterior_bc():
    model = ET.fromstring(ET.tostring(MODEL_XML))
    frame = ET.fromstring(ET.tostring(model.find('Boundaries/Boundary')))
    frame.find('ID').text = '5'
    frame.find('Type').text = 'Frame Cavity'
    model.find('Boundaries').append(frame)
    root = mesh_to_xml(model, BOUNDARY_CONDITIONS, _Mesh())
    assert {segment.findtext('label') for segment in
            root.findall('Case/BCSegments/Convections/Convection')} == {
                '1', '2', '3', '4'}


def test_native_mesh_rejects_triangles_instead_of_writing_them_as_quads():
    mesh = _Mesh()
    mesh.Faces = [_Face(0, 1, 2, 2)]
    with pytest.raises(ValueError, match='triangle'):
        mesh_to_xml(MODEL_XML, BOUNDARY_CONDITIONS, mesh)


def _junction():
    model = ET.fromstring(ET.tostring(MODEL_XML))
    polygons = model.find('Polygons')
    polygons.clear()
    for label, material, points in (
            (42, 'left', [(0, 0), (500, 0), (500, 500),
                          (500, 1000), (0, 1000)]),
            (7, 'right-bottom', [(500, 0), (1000, 0),
                                 (1000, 500), (500, 500)]),
            (99, 'right-top', [(500, 500), (1000, 500),
                               (1000, 1000), (500, 1000)])):
        polygon = ET.SubElement(polygons, 'Polygon')
        ET.SubElement(polygon, 'ID').text = str(label)
        ET.SubElement(polygon, 'Type').text = 'Material'
        ET.SubElement(polygon, 'MaterialUUID').text = material
        vertices = ET.SubElement(polygon, 'Points')
        for x, y in points:
            point = ET.SubElement(vertices, 'Point')
            ET.SubElement(point, 'x').text = str(x)
            ET.SubElement(point, 'y').text = str(y)
    mesh = _Mesh()
    mesh.Vertices = [_Point(x, y) for y in (0, 500, 1000)
                     for x in (0, 500, 1000)]
    mesh.Faces = [_Face(0, 1, 4, 3), _Face(1, 2, 5, 4),
                  _Face(3, 4, 7, 6), _Face(4, 5, 8, 7)]
    return model, mesh


def test_t_junction_preserves_shared_nodes_materials_and_exterior_labels():
    model, mesh = _junction()
    root = mesh_to_xml(model, BOUNDARY_CONDITIONS, mesh)
    assert len(root.findall('Case/Nodes/Node')) == 9
    assert [e.findtext('materialID') for e in
            root.findall('Case/Elements/Element')] == ['1', '2', '1', '3']
    conditions = root.findall('Case/BCSegments/Convections/Convection')
    assert len(conditions) == 8
    assert all('4' not in (bc.findtext('node1'), bc.findtext('node2'))
               for bc in conditions)  # The T vertex is interior.
    # Reusing a material preserves its ID even when polygon labels differ.
    model.findall('Polygons/Polygon')[2].find('MaterialUUID').text = 'right-bottom'
    root = mesh_to_xml(model, BOUNDARY_CONDITIONS, mesh)
    assert [e.findtext('materialID') for e in
            root.findall('Case/Elements/Element')] == ['1', '2', '1', '2']


def test_t_junction_rejects_a_quad_crossing_an_interface_and_unmeshed_regions():
    model, mesh = _junction()
    with pytest.raises(ValueError, match='exactly one material polygon'):
        mesh_to_xml(model, BOUNDARY_CONDITIONS, _Mesh())
    mesh.Faces.pop()
    with pytest.raises(ValueError, match='gap or overlap'):
        mesh_to_xml(model, BOUNDARY_CONDITIONS, mesh)

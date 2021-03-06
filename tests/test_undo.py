import logging

import pytest

from gaphor import UML
from gaphor.application import Application
from gaphor.core import Transaction
from gaphor.core.modeling import Diagram
from gaphor.diagram.tests.fixtures import connect
from gaphor.UML.classes import AssociationItem, ClassItem, GeneralizationItem


@pytest.fixture
def application():
    app = Application()
    yield app
    app.shutdown()


@pytest.fixture
def session(application):
    return application.new_session()


@pytest.fixture
def event_manager(session):
    return session.get_service("event_manager")


@pytest.fixture
def element_factory(session):
    return session.get_service("element_factory")


@pytest.fixture
def undo_manager(session):
    return session.get_service("undo_manager")


def test_class_association_undo_redo(event_manager, element_factory, undo_manager):
    with Transaction(event_manager):
        diagram = element_factory.create(Diagram)

    assert 0 == len(diagram.connections.solver.constraints)

    with Transaction(event_manager):
        ci1 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
    assert 6 == len(diagram.connections.solver.constraints)

    with Transaction(event_manager):
        ci2 = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
    assert 12 == len(diagram.connections.solver.constraints)

    with Transaction(event_manager):
        a = diagram.create(AssociationItem)

        connect(a, a.head, ci1)
        connect(a, a.tail, ci2)

    # Diagram, Association, 2x Class, Property, LiteralSpecification
    assert 6 == len(element_factory.lselect())
    assert 14 == len(diagram.connections.solver.constraints)

    undo_manager.clear_undo_stack()
    assert not undo_manager.can_undo()

    with Transaction(event_manager):
        ci2.unlink()

    assert undo_manager.can_undo()

    def get_connected(handle):
        """Get item connected to line via handle."""
        cinfo = diagram.connections.get_connection(handle)
        if cinfo:
            return cinfo.connected
        return None

    assert ci1 == get_connected(a.head)
    assert None is get_connected(a.tail)

    for i in range(3):
        assert 7 == len(diagram.connections.solver.constraints)

        undo_manager.undo_transaction()

        assert 14 == len(diagram.connections.solver.constraints)

        assert ci1 == get_connected(a.head)
        assert ci2.id == get_connected(a.tail).id

        undo_manager.redo_transaction()


def test_diagram_item_can_undo_(event_manager, element_factory, undo_manager, caplog):
    caplog.set_level(logging.INFO)
    with Transaction(event_manager):
        diagram = element_factory.create(Diagram)

    with Transaction(event_manager):
        cls = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        cls.matrix.translate(10, 10)

    undo_manager.undo_transaction()
    undo_manager.redo_transaction()

    assert diagram.ownedPresentation[0].matrix.tuple() == (1, 0, 0, 1, 10, 10)
    assert not caplog.records


def test_diagram_item_should_not_end_up_in_element_factory(
    event_manager, element_factory, undo_manager
):
    with Transaction(event_manager):
        diagram = element_factory.create(Diagram)

    with Transaction(event_manager):
        cls = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

    undo_manager.undo_transaction()
    undo_manager.redo_transaction()

    assert cls not in element_factory.lselect(), element_factory.lselect()


def test_deleted_diagram_item_should_not_end_up_in_element_factory(
    event_manager, element_factory, undo_manager
):
    with Transaction(event_manager):
        diagram = element_factory.create(Diagram)
        cls = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

    with Transaction(event_manager):
        cls.unlink()

    undo_manager.undo_transaction()

    assert cls not in element_factory.lselect(), element_factory.lselect()

    undo_manager.redo_transaction()

    assert cls not in element_factory.lselect(), element_factory.lselect()


def test_undo_should_not_cause_warnings(
    event_manager, element_factory, undo_manager, caplog
):
    caplog.set_level(logging.INFO)
    with Transaction(event_manager):
        diagram = element_factory.create(Diagram)

    with Transaction(event_manager):
        diagram.create(ClassItem, subject=element_factory.create(UML.Class))

    assert not caplog.records

    undo_manager.undo_transaction()

    assert not diagram.ownedPresentation
    assert not caplog.records


def test_can_undo_connected_generalization(
    event_manager, element_factory, undo_manager, caplog
):
    caplog.set_level(logging.INFO)
    with Transaction(event_manager):
        diagram: Diagram = element_factory.create(Diagram)
        general = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        specific = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

    with Transaction(event_manager):
        generalization = diagram.create(GeneralizationItem)
        connect(generalization, generalization.head, general)
        connect(generalization, generalization.tail, specific)

    assert not caplog.records

    undo_manager.undo_transaction()

    assert not list(diagram.select(GeneralizationItem))
    assert not caplog.records

    undo_manager.redo_transaction()
    new_generalization_item = next(diagram.select(GeneralizationItem))
    new_generalization = next(element_factory.select(UML.Generalization))

    assert len(list(diagram.select(GeneralizationItem))) == 1
    assert len(element_factory.lselect(UML.Generalization)) == 1
    assert new_generalization_item.subject is new_generalization
    assert not caplog.records


def test_can_undo_connected_association(
    event_manager, element_factory, undo_manager, caplog
):
    caplog.set_level(logging.INFO)
    with Transaction(event_manager):
        diagram: Diagram = element_factory.create(Diagram)
        parent = diagram.create(ClassItem, subject=element_factory.create(UML.Class))
        child = diagram.create(ClassItem, subject=element_factory.create(UML.Class))

    with Transaction(event_manager):
        association = diagram.create(AssociationItem)
        connect(association, association.head, parent)
        connect(association, association.tail, child)

    assert not caplog.records

    undo_manager.undo_transaction()

    assert not list(diagram.select(AssociationItem))
    assert not caplog.records

    undo_manager.redo_transaction()
    new_association_item = next(diagram.select(AssociationItem))
    new_association = next(element_factory.select(UML.Association))

    assert len(list(diagram.select(AssociationItem))) == 1
    assert len(element_factory.lselect(UML.Association)) == 1

    assert len(new_association.memberEnd) == 2
    assert new_association_item.subject is new_association
    assert new_association_item.head_subject
    assert new_association_item.tail_subject
    assert not caplog.records

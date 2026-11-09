from types import SimpleNamespace

from app.org_directory import organization_ids_with_ancestors, organizations_in_hierarchy


def test_organization_ids_with_ancestors_includes_full_hierarchy():
    parent_by_id = {
        1: None,
        2: 1,
        3: 2,
        4: None,
    }

    assert organization_ids_with_ancestors({3, 4}, parent_by_id) == {1, 2, 3, 4}


def test_organization_ids_with_ancestors_handles_cycles():
    assert organization_ids_with_ancestors({1}, {1: 2, 2: 1}) == {1, 2}


def test_organizations_in_hierarchy_nests_children_below_parents():
    organizations = [
        SimpleNamespace(id=3, parent_id=1, name='Zulu'),
        SimpleNamespace(id=2, parent_id=1, name='Alpha'),
        SimpleNamespace(id=1, parent_id=None, name='Faculty'),
        SimpleNamespace(id=4, parent_id=2, name='Unit'),
    ]

    assert [
        (organization.id, depth)
        for organization, depth in organizations_in_hierarchy(organizations)
    ] == [(1, 0), (2, 1), (4, 2), (3, 1)]

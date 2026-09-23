"""Hierarchy validation and public navigation trees."""
import json


def menu_mapping(settings, key):
    try:
        value = json.loads(settings.get(key, '{}'))
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def validate_parents(parents, nodes, groups):
    for key, parent in parents.items():
        if key not in nodes or (parent and parent not in groups):
            raise ValueError('Unknown menu item')
        seen = {key}
        while parent:
            if parent in seen or len(seen) >= 5:
                raise ValueError('Menu cycle or excessive nesting')
            seen.add(parent)
            parent = parents.get(parent, '')


def menu_tree(items, parents, existing_groups):
    """Hide descendants of hidden parents; promote children of deleted parents."""
    nodes = {item['key']: dict(item, children=[]) for item in items}
    roots = []
    for key, node in nodes.items():
        parent = parents.get(key, '')
        if not isinstance(parent, str) or parent not in existing_groups:
            parent = ''
        ancestor, seen, visible = parent, {key}, True
        while ancestor:
            if ancestor in seen or ancestor not in nodes or len(seen) >= 5:
                visible = False
                break
            seen.add(ancestor)
            ancestor = parents.get(ancestor, '')
            if not isinstance(ancestor, str) or ancestor not in existing_groups:
                ancestor = ''
        if visible:
            (nodes[parent]['children'] if parent else roots).append(node)

    def tidy(branch):
        for item in branch:
            item['children'] = tidy(item['children'])
        return sorted((item for item in branch if item['url'] or item['children']),
                      key=lambda item: (item['sort_order'], item['label'].casefold(), item['key']))
    return tidy(roots)

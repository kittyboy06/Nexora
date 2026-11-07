"""Accessibility Tree Inspection and Query Service."""

from typing import Optional

from backend.app.desktop.adapter import DesktopAdapter
from backend.app.desktop.models import UIElementNode


class AccessibilityTreeInspector:
    """Provides structured UI Automation tree exploration and element discovery."""

    def __init__(self, adapter: DesktopAdapter) -> None:
        self.adapter = adapter

    def inspect_and_sanitize(self, hwnd: int, max_depth: int = 4) -> UIElementNode:
        """Inspect window tree and mask password control values."""
        raw_tree = self.adapter.inspect_tree(hwnd, max_depth=max_depth)
        return self._sanitize_node(raw_tree)

    def find_element(self, root: UIElementNode, query: str) -> Optional[UIElementNode]:
        """Find element matching query against element_id, automation_id, or name (case-insensitive)."""
        q = query.strip().lower()
        if (
            q == root.element_id.lower()
            or q == root.automation_id.lower()
            or q in root.name.lower()
        ):
            return root

        for child in root.children:
            found = self.find_element(child, query)
            if found:
                return found
        return None

    def flatten_tree(self, root: UIElementNode) -> list[UIElementNode]:
        """Flatten tree into a list of accessible nodes."""
        nodes = [root]
        for child in root.children:
            nodes.extend(self.flatten_tree(child))
        return nodes

    def _sanitize_node(self, node: UIElementNode) -> UIElementNode:
        """Clone node with password values masked to protect privacy."""
        is_pwd = (
            node.is_password
            or "password" in node.name.lower()
            or "password" in node.automation_id.lower()
        )
        val = "******" if (is_pwd and node.value) else node.value

        sanitized_children = [self._sanitize_node(child) for child in node.children]

        return node.model_copy(
            update={
                "is_password": is_pwd,
                "value": val,
                "children": sanitized_children,
            }
        )

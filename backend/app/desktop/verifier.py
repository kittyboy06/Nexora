"""Postcondition Verification and Visual State Diffing."""

import logging
from typing import Optional

from backend.app.desktop.models import ScreenshotEvidence, UIElementNode
from backend.app.desktop.tree import AccessibilityTreeInspector

logger = logging.getLogger("nexora.desktop.verifier")


class PostconditionVerifier:
    """Verifies that an executed desktop action produced the expected UI state change."""

    def __init__(self, tree_inspector: AccessibilityTreeInspector) -> None:
        self.tree_inspector = tree_inspector

    def verify_action(
        self,
        expected: Optional[str],
        pre_evidence: Optional[ScreenshotEvidence],
        post_evidence: Optional[ScreenshotEvidence],
        post_tree: UIElementNode,
    ) -> tuple[bool, str]:
        """Check whether the observed post-action state satisfies expected conditions."""
        if not expected or not expected.strip():
            # If no explicit postcondition specified, verify visual frame capture succeeded
            if pre_evidence and post_evidence:
                return True, "Action completed with pre/post visual confirmation."
            return True, "Action executed."

        rule = expected.strip().lower()

        # Rule 1: Visual difference check
        if rule in ("visual_change", "hash_changed", "screen_updated"):
            if not pre_evidence or not post_evidence:
                return False, "Verification failed: Screenshot evidence was missing for visual diff."
            if pre_evidence.sha256_hash == post_evidence.sha256_hash:
                return False, "Verification failed: No visual difference detected after action."
            return True, "Visual change confirmed."

        # Rule 2: Explicit element text check
        target_text = rule
        if rule.startswith("text_contains:"):
            target_text = rule.split("text_contains:", 1)[1].strip()
        elif rule.startswith("text:"):
            target_text = rule.split("text:", 1)[1].strip()

        all_nodes = self.tree_inspector.flatten_tree(post_tree)
        for node in all_nodes:
            node_text = (node.name or "") + " " + (node.value or "")
            if target_text in node_text.lower():
                return True, f"Found expected text '{target_text}' in element '{node.name or node.element_id}'."

        return False, f"Postcondition unfulfilled: '{target_text}' was not observed in target window after action."

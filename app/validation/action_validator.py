"""Deterministic action validator enforcing budget, allowlist, deduplication, and content rules."""

import re
from typing import Dict, List, Optional, Set
from app.config import Settings
from app.models.action import ActionPlan, ProposedAction, ValidatedAction
from app.models.persona import PersonaConfig
from app.models.post import NormalizedPost
from app.observability.logging import get_logger

logger = get_logger("validation.validator")


class ActionValidator:
    """Validates proposed AI actions against strict safety, persona, and operational constraints."""

    def __init__(self, settings: Settings, persona: Optional[PersonaConfig] = None):
        self.settings = settings
        self.persona = persona or settings.get_persona()

    @staticmethod
    def _matches_keyword(text: str, keyword: str) -> bool:
        """Check if keyword appears in text with word boundary matching for single words."""
        kw = keyword.strip().lower()
        if not kw:
            return False
        if " " in kw or not kw.isalnum():
            return kw in text.lower()
        return bool(re.search(rf"\b{re.escape(kw)}\b", text, flags=re.IGNORECASE))

    def validate_plan(
        self,
        plan: ActionPlan,
        known_posts: List[NormalizedPost],
        interacted_post_ids: Set[str],
        remaining_budget: int,
    ) -> List[ValidatedAction]:
        """Validate proposed actions and return only approved ValidatedAction objects.
        
        Strictly enforces:
        1. Action type in allowed_actions (or skip)
        2. Post exists in known_posts batch
        3. Post not previously interacted with in DB history
        4. Author not in blocked_accounts list
        5. Post text does not contain forbidden negative keywords
        6. Budget limit (approved actions <= remaining_budget)
        7. Content presence, character limit, and safety for comments/replies
        """
        approved_actions: List[ValidatedAction] = []
        known_posts_map: Dict[str, NormalizedPost] = {p.post_id: p for p in known_posts}

        # Retrieve negative filters from persona
        avoid_cfg = self.persona.what_to_not_interact_with
        blocked_accounts = {a.lower().lstrip("@") for a in avoid_cfg.blocked_accounts}
        neg_keywords = [nk.strip() for nk in avoid_cfg.negative_keywords if nk.strip()]

        # Sort proposed actions by priority (1 = highest)
        sorted_proposals = sorted(plan.actions, key=lambda a: a.priority)

        current_budget = max(0, remaining_budget)

        for proposal in sorted_proposals:
            post_id = proposal.post_id

            # Rule 1: Skip actions are valid but require no execution
            if proposal.action == "skip":
                logger.debug(f"Action 'skip' for post {post_id}: {proposal.reason}")
                continue

            # Rule 2: Action must be in allowed_actions
            if proposal.action not in self.settings.allowed_actions:
                logger.warning(
                    f"Rejected action '{proposal.action}' on post {post_id}: Not in allowed_actions ({self.settings.allowed_actions})."
                )
                continue

            # Rule 3: Post must exist in the known batch
            if post_id not in known_posts_map:
                logger.warning(
                    f"Rejected action on post {post_id}: Post not found in current known posts batch."
                )
                continue

            post_obj = known_posts_map[post_id]

            # Rule 4: Post must not have been previously interacted with in history
            if post_id in interacted_post_ids:
                logger.warning(
                    f"Rejected action on post {post_id}: Post was already interacted with in previous runs."
                )
                continue

            # Rule 5: Author must not be in blocked_accounts
            post_author = post_obj.author_handle.lower().lstrip("@")
            if post_author in blocked_accounts:
                logger.warning(
                    f"Rejected action on post {post_id}: Author '{post_obj.author_handle}' is in blocked_accounts list."
                )
                continue

            # Rule 6: Post must not contain forbidden negative keywords
            matched_neg = [
                kw for kw in neg_keywords if self._matches_keyword(post_obj.text, kw)
            ]
            if matched_neg:
                logger.warning(
                    f"Rejected action on post {post_id}: Post contains forbidden negative keyword(s): {matched_neg}."
                )
                continue

            # Rule 7: Interaction budget check
            if current_budget <= 0:
                logger.info(
                    f"Skipping action on post {post_id}: Interaction budget reached limit."
                )
                break

            # Rule 8: Content validation for comment/reply
            if proposal.action in ("comment", "reply"):
                if not proposal.content or not proposal.content.strip():
                    logger.warning(
                        f"Rejected {proposal.action} on post {post_id}: Missing required content."
                    )
                    continue

                clean_content = proposal.content.strip()
                if len(clean_content) > 280:
                    logger.warning(
                        f"Rejected {proposal.action} on post {post_id}: Content exceeds 280 characters ({len(clean_content)} chars)."
                    )
                    continue

                matched_content_neg = [
                    kw for kw in neg_keywords if self._matches_keyword(clean_content, kw)
                ]
                if matched_content_neg:
                    logger.warning(
                        f"Rejected {proposal.action} on post {post_id}: Drafted comment contains forbidden keyword(s): {matched_content_neg}."
                    )
                    continue

                content = clean_content
            else:
                content = None

            validated = ValidatedAction(
                post_id=post_id,
                action=proposal.action,
                reason=proposal.reason,
                content=content,
                priority=proposal.priority,
                post_url=post_obj.url,
                author_username=post_obj.author_handle,
                explore_thread=proposal.explore_thread or (proposal.interest_score is not None and proposal.interest_score >= 8),
            )

            approved_actions.append(validated)
            current_budget -= 1
            logger.info(
                f"Approved action: {validated.action.upper()} on post {post_id} by {validated.author_username} (Priority {validated.priority})."
            )

        return approved_actions

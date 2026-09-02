"""Unit tests for the ActionValidator layer."""

import pytest
from app.config import Settings
from app.models.action import ActionPlan, ProposedAction
from app.models.post import Author, NormalizedPost
from app.validation.action_validator import ActionValidator


class TestActionValidator:
    """Test suite for ActionValidator rules and safety enforcement."""

    def test_approve_valid_actions(self, test_settings, sample_normalized_posts):
        validator = ActionValidator(test_settings)
        plan = ActionPlan(
            actions=[
                ProposedAction(
                    post_id="post_101",
                    action="like",
                    reason="Relevant AI topic",
                    priority=1,
                ),
                ProposedAction(
                    post_id="post_103",
                    action="comment",
                    reason="Interesting paper",
                    content="Fascinating paper on multi-agent consensus! Very clear methodology.",
                    priority=2,
                ),
                ProposedAction(
                    post_id="post_102",
                    action="skip",
                    reason="Not relevant",
                    priority=3,
                ),
            ]
        )

        approved = validator.validate_plan(
            plan=plan,
            known_posts=sample_normalized_posts,
            interacted_post_ids=set(),
            remaining_budget=5,
        )

        assert len(approved) == 2
        assert approved[0].post_id == "post_101"
        assert approved[0].action == "like"
        assert approved[0].post_url == "https://x.com/tech_builder/status/101"
        assert approved[0].author_username == "@tech_builder"

        assert approved[1].post_id == "post_103"
        assert approved[1].action == "comment"
        assert approved[1].content is not None

    def test_reject_unsupported_action(self, test_settings, sample_normalized_posts):
        validator = ActionValidator(test_settings)
        # Assuming "repost" is not in test_settings.allowed_actions
        test_settings.allowed_actions = ["like"]
        plan = ActionPlan(
            actions=[
                ProposedAction(
                    post_id="post_101",
                    action="comment",  # not in allowed_actions
                    reason="Testing allowlist",
                    content="A comment",
                    priority=1,
                )
            ]
        )
        approved = validator.validate_plan(
            plan=plan,
            known_posts=sample_normalized_posts,
            interacted_post_ids=set(),
            remaining_budget=5,
        )
        assert len(approved) == 0

    def test_reject_unknown_post(self, test_settings, sample_normalized_posts):
        validator = ActionValidator(test_settings)
        plan = ActionPlan(
            actions=[
                ProposedAction(
                    post_id="non_existent_post",
                    action="like",
                    reason="Testing unknown post",
                    priority=1,
                )
            ]
        )
        approved = validator.validate_plan(
            plan=plan,
            known_posts=sample_normalized_posts,
            interacted_post_ids=set(),
            remaining_budget=5,
        )
        assert len(approved) == 0

    def test_reject_already_interacted_post(self, test_settings, sample_normalized_posts):
        validator = ActionValidator(test_settings)
        plan = ActionPlan(
            actions=[
                ProposedAction(
                    post_id="post_101",
                    action="like",
                    reason="Testing history check",
                    priority=1,
                )
            ]
        )
        approved = validator.validate_plan(
            plan=plan,
            known_posts=sample_normalized_posts,
            interacted_post_ids={"post_101"},
            remaining_budget=5,
        )
        assert len(approved) == 0

    def test_enforce_budget_limit(self, test_settings, sample_normalized_posts):
        validator = ActionValidator(test_settings)
        plan = ActionPlan(
            actions=[
                ProposedAction(
                    post_id="post_101",
                    action="like",
                    reason="First action",
                    priority=1,
                ),
                ProposedAction(
                    post_id="post_103",
                    action="like",
                    reason="Second action",
                    priority=2,
                ),
            ]
        )
        # Only 1 budget remaining
        approved = validator.validate_plan(
            plan=plan,
            known_posts=sample_normalized_posts,
            interacted_post_ids=set(),
            remaining_budget=1,
        )
        assert len(approved) == 1
        assert approved[0].post_id == "post_101"

    def test_reject_empty_or_too_long_comment(self, test_settings, sample_normalized_posts):
        validator = ActionValidator(test_settings)
        plan = ActionPlan(
            actions=[
                # Empty comment
                ProposedAction(
                    post_id="post_101",
                    action="comment",
                    reason="Missing content",
                    content="   ",
                    priority=1,
                ),
                # Comment exceeding 280 characters
                ProposedAction(
                    post_id="post_103",
                    action="comment",
                    reason="Too long",
                    content="a" * 285,
                    priority=2,
                ),
            ]
        )
        approved = validator.validate_plan(
            plan=plan,
            known_posts=sample_normalized_posts,
            interacted_post_ids=set(),
            remaining_budget=5,
        )
        assert len(approved) == 0


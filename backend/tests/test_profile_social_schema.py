"""Profile social-handle PATCH schema tests; no database fixtures required."""

import pytest
from pydantic import ValidationError

from app.schemas.profile import BrandProfilePatch, CreatorProfilePatch


@pytest.mark.parametrize("schema", [CreatorProfilePatch, BrandProfilePatch])
@pytest.mark.parametrize("unverified", [True, False])
def test_profile_patch_accepts_verified_and_unverified_handles(
    schema: type[CreatorProfilePatch] | type[BrandProfilePatch],
    unverified: bool,
) -> None:
    patch = schema.model_validate(
        {
            "social_handles": [
                {
                    "platform": "Instagram",
                    "handle": "@creator",
                    "follower_count": 123,
                    "unverified": unverified,
                }
            ]
        }
    )

    assert patch.social_handles[0].unverified is unverified
    assert patch.social_handles[0].follower_count == 123


@pytest.mark.parametrize("schema", [CreatorProfilePatch, BrandProfilePatch])
def test_profile_patch_keeps_unverified_default_true(
    schema: type[CreatorProfilePatch] | type[BrandProfilePatch],
) -> None:
    patch = schema.model_validate(
        {"social_handles": [{"platform": "Instagram", "handle": "@creator"}]}
    )

    assert patch.social_handles[0].unverified is True


@pytest.mark.parametrize("schema", [CreatorProfilePatch, BrandProfilePatch])
def test_profile_patch_still_rejects_extra_social_properties(
    schema: type[CreatorProfilePatch] | type[BrandProfilePatch],
) -> None:
    with pytest.raises(ValidationError, match="legacy_note"):
        schema.model_validate(
            {
                "social_handles": [
                    {
                        "platform": "Instagram",
                        "handle": "@creator",
                        "unverified": False,
                        "legacy_note": "keep out of PATCH",
                    }
                ]
            }
        )

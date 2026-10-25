from __future__ import annotations

import unittest

from research.pre_line_limit_alias_contract import (
    PreLineLimitContractError,
    resolve_pre_daily_line_limit,
)


class PreLineLimitAliasContractTests(unittest.TestCase):
    def test_pre_specific_value_has_precedence(self) -> None:
        resolved = resolve_pre_daily_line_limit(
            pre_daily_line_limit="2",
            legacy_daily_line_limit="9",
        )
        self.assertEqual(resolved.value, 2)
        self.assertEqual(resolved.source, "PRE_DAILY_LINE_LIMIT")

    def test_legacy_value_is_backward_compatible_fallback(self) -> None:
        resolved = resolve_pre_daily_line_limit(
            pre_daily_line_limit=None,
            legacy_daily_line_limit="4",
        )
        self.assertEqual(resolved.value, 4)
        self.assertEqual(resolved.source, "DAILY_LINE_LIMIT")

    def test_default_is_three_when_neither_variable_is_present(self) -> None:
        resolved = resolve_pre_daily_line_limit(
            pre_daily_line_limit=None,
            legacy_daily_line_limit=None,
        )
        self.assertEqual(resolved.value, 3)
        self.assertEqual(resolved.source, "default")

    def test_blank_pre_value_does_not_mask_legacy_value(self) -> None:
        resolved = resolve_pre_daily_line_limit(
            pre_daily_line_limit="  ",
            legacy_daily_line_limit="5",
        )
        self.assertEqual(resolved.value, 5)
        self.assertEqual(resolved.source, "DAILY_LINE_LIMIT")

    def test_invalid_pre_value_fails_closed_instead_of_silently_falling_back(self) -> None:
        with self.assertRaises(PreLineLimitContractError):
            resolve_pre_daily_line_limit(
                pre_daily_line_limit="zero",
                legacy_daily_line_limit="3",
            )

    def test_nonpositive_values_fail_closed(self) -> None:
        for value in ("0", "-1"):
            with self.subTest(value=value):
                with self.assertRaises(PreLineLimitContractError):
                    resolve_pre_daily_line_limit(
                        pre_daily_line_limit=value,
                        legacy_daily_line_limit=None,
                    )


if __name__ == "__main__":
    unittest.main()

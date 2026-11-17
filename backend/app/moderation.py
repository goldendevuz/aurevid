# SPDX-License-Identifier: AGPL-3.0-or-later
"""Basic prompt moderation hook.

This is a first line of defence only: a keyword screen. It is NOT a full safety system.
Swap `Moderator` for a real classifier later; the call sites stay the same.
"""

import re
import unicodedata
from dataclasses import dataclass

# Hard-blocked: any sexual content combined with minors, plus explicit sexual terms.
_MINOR_TERMS = r"(child|children|kid|kids|minor|underage|teen|teenager|loli|schoolgirl|schoolboy|preteen|bola|qizcha|o'smir|ребенок|ребёнок|девочк|мальчик|подрост|несовершеннолет)"
_SEXUAL_TERMS = r"(nude|naked|nsfw|sex|sexual|porn|erotic|explicit|lewd|fetish|yalang'och|порн|секс|голая|голый|эрот)"
_VIOLENT_EXTREME = r"(beheading|gore|terrorist propaganda)"


@dataclass
class ModerationResult:
    allowed: bool
    category: str | None = None


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[​-‏⁠]", "", text)  # strip zero-width chars


class Moderator:
    def check_prompt(self, prompt: str) -> ModerationResult:
        t = _normalize(prompt)
        sexual = re.search(_SEXUAL_TERMS, t)
        if sexual and re.search(_MINOR_TERMS, t):
            return ModerationResult(False, "minors")
        if sexual:
            return ModerationResult(False, "sexual")
        if re.search(_VIOLENT_EXTREME, t):
            return ModerationResult(False, "violence")
        return ModerationResult(True)


moderator = Moderator()

import re

from pyparsing import Group, Opt, ParserElement, Regex, Suppress


class BodyItem:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value[0]

    def __repr__(self):
        return f"{self.__class__.__name__}({self.value})"


class SideNoteItem(BodyItem):
    pass


class QuestionItem(BodyItem):
    pass


class SpeakerItem(BodyItem):
    pass


class SpeechItem(BodyItem):
    pass


function_prefixes = [
    "SRS",
    "StS",
    "Vorsitzende",
    "Vorsitzender",
    "Staatssekretär",
    "Minister",
]


def re_make_groups(prefixes, postfixes=None):
    if postfixes is None:
        postfixes = [""]
    else:
        postfixes = [""] + postfixes
    return "|".join(
        re.escape(f"{prefix}{postfix}") for postfix in postfixes for prefix in prefixes
    )


def re_add_in_group(group_str: str, after: str = " "):
    return "|".join([s + after for s in group_str.split("|")])


postfixes = [f"{x}in" for x in ("`", "’", "'")]

function_re = re_add_in_group(re_make_groups(function_prefixes, postfixes))

known_name_re = re_add_in_group(
    function_re
    + "|"
    + re_make_groups(["Dr.", "Prof.", "Vorsitzende", "Vorsitzender", "Vors."])
)


ParserElement.set_default_whitespace_chars("")
lb = Suppress(Regex(r"\n"))
sb = Suppress(Regex(r"\n\n?"))
ws = Regex(r"[ \t]")
colon = Suppress(Regex(r" *: +"))

speaker_marker = Regex(r"^(?:Sprecherinnen und )?Sprecher:?")
speaker_name = Suppress(Regex(r" *•? *")) + Regex(r"[^\n]{4,}")
speaker_break = Suppress(Regex(", ?") | lb)
speaker_list = speaker_name + (speaker_break + speaker_name)[...]
speaker_section = (
    speaker_marker
    + Suppress(Regex(r"\n{0,2}"))
    + Group(speaker_list[1, ...]).set_results_name("speaker_list")
)
sidenote = (
    (Suppress(Regex(r"[(\[]")) + Regex(r"[^\]\)]+") + Suppress(Regex(r"[\)\]]")) + sb)
    | (Regex(r"Zuruf(?: [^: ]+)?: ?[^\n]+") + sb)
).set_parse_action(SideNoteItem)

question_re = r"\w*frage|Zusatzfrage|Zusatz"
question = (Regex(question_re, re.I) + sb).set_parse_action(QuestionItem)
question_prefix = (Regex(question_re, re.I) + colon).set_parse_action(QuestionItem)
ministry_speaker = Regex(
    r"([\w-]+) \(([A-Z]\w{,6})\)",
).set_name("ministry speaker")
function_speaker = Regex(
    r"(%s)([A-ZÄÖÜ][\w-]+)" % function_re,
).set_name("function speaker")
name_speaker = Regex(
    r"(?:%s)?[A-ZÄÖÜ][\w-]+" % known_name_re,
).set_name("name speaker")
speaker = ((ministry_speaker | function_speaker) + sb).set_parse_action(SpeakerItem)
speaker_prefix = (
    (ministry_speaker | function_speaker | name_speaker) + colon
).set_parse_action(SpeakerItem)
speech = (Regex(r"[^\n]+") + sb).set_parse_action(SpeechItem)

intro = Opt(speaker_section + sb) + Opt(sidenote)
body_elements = (
    sidenote
    | (question_prefix + speech)
    | (speaker_prefix + speech)
    | (question + speech)
    | (speaker + speech)
    | speech
)
body_sequence = body_elements
body = body_sequence[1, ...]
bpk_grammar = intro + body


if __name__ == "__main__":
    bpk_grammar.create_diagram("bpk_grammar.html")

from ..sources.cvd_grammar import SideNoteItem, SpeakerItem, SpeechItem, bpk_grammar


def test_speaker_detection():
    s = "Wagner (AA)\n\nBeispiel-Antwort sowieso interessant.\n\n"

    result = bpk_grammar.parse_string(s, parse_all=True).as_list()
    assert isinstance(result[0], SpeakerItem)
    assert str(result[0]) == "Wagner (AA)"
    assert isinstance(result[1], SpeechItem)
    assert str(result[1]) == "Beispiel-Antwort sowieso interessant."

    s = "SRS Hille\n\nWir verfolgen, wie Sie sich vorstellen können.\n\nWeiterer Absatz es geht hier weiter.\n\n"
    result = bpk_grammar.parse_string(s, parse_all=True).as_list()
    assert isinstance(result[0], SpeakerItem)
    assert str(result[0]) == "SRS Hille"
    assert isinstance(result[1], SpeechItem)
    assert str(result[1]) == "Wir verfolgen, wie Sie sich vorstellen können."
    assert isinstance(result[2], SpeechItem)
    assert str(result[2]) == "Weiterer Absatz es geht hier weiter."


def test_speaker_list():
    s = """Sprecherinnen und Sprecher

stellvertretender Regierungssprecher Hille
• Müller (BMVg)
• Dr. Laiadhi (BMF)
• Harmsen (BMI)
• Giese (AA)
• Stolzenberg (BMUKN)
• Alexandrin (BMV)

(Vorsitzende Hamberger eröffnet die Pressekonferenz und begrüßt SRS Hille sowie die Sprecherinnen und Sprecher der Ministerien.)

SRS Hille

Einen schönen, guten Tag auch von mir! Leider müssen wir auch heute wieder mit einem traurigen Thema beginnen. Gestern ist es zu einem tragischen Hubschrauberabsturz gekommen. Dabei sind mehrere Menschen ums Leben gekommen. Besonders tragisch ist es, wenn Menschen im Dienst für unser Land ums Leben kommen. Das ist in diesem Fall der Fall. Ihnen gelten unser Dank und unsere Anerkennung für ihren Einsatz für unser Land. Unsere Gedanken sind bei den Angehörigen und Freunden. Ihnen gilt in diesen schweren Stunden unsere tief empfundene Anteilnahme.
"""
    result = bpk_grammar.parse_string(s, parse_all=True)
    data = result.as_dict()
    assert "speaker_list" in data
    assert len(data["speaker_list"]) == 7
    assert data["speaker_list"][0] == "stellvertretender Regierungssprecher Hille"
    assert data["speaker_list"][-1] == "Alexandrin (BMV)"
    stream = result.as_list()
    assert isinstance(stream[2], SideNoteItem)
    assert isinstance(stream[3], SpeakerItem)
    assert isinstance(stream[4], SpeechItem)

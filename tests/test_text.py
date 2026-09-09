from agents.text import plain_dashes


def test_a_spaced_em_dash_becomes_a_spaced_hyphen():
    assert plain_dashes("Orlando — $257") == "Orlando - $257"


def test_a_spaced_en_dash_becomes_a_spaced_hyphen():
    assert plain_dashes("Orlando – $257") == "Orlando - $257"


def test_a_dash_joining_two_words_becomes_a_plain_hyphen():
    assert plain_dashes("territories—Orlando—account") == "territories-Orlando-account"


def test_a_non_breaking_hyphen_becomes_an_ordinary_one():
    assert plain_dashes("highest‑earning") == "highest-earning"


def test_text_without_dashes_is_untouched():
    assert plain_dashes("nothing to do here") == "nothing to do here"


def test_ordinary_hyphens_survive():
    assert plain_dashes("GLP-1 and follow-up") == "GLP-1 and follow-up"


def test_empty_text_is_safe():
    assert plain_dashes("") == ""


def test_no_em_dash_survives_anywhere():
    messy = "One — two – three—four–five"
    assert "—" not in plain_dashes(messy)
    assert "–" not in plain_dashes(messy)

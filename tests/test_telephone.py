from app.services.telephone import normaliser_telephone, telephone_est_valide


def test_normalisation_supprime_espaces_points_tirets_parentheses():
    assert normaliser_telephone(" 77 123 45 67 ") == "771234567"
    assert normaliser_telephone("77.123.45.67") == "771234567"
    assert normaliser_telephone("(+221) 77-123-45-67") == "+221771234567"


def test_deux_formats_designent_le_meme_numero():
    # RG1 : « 77 123 45 67 » et « 771234567 » désignent le même client
    assert normaliser_telephone("77 123 45 67") == normaliser_telephone("771234567")


def test_formes_valides():
    assert telephone_est_valide("771234567")
    assert telephone_est_valide("+221771234567")
    assert telephone_est_valide("123456")              # 6 chiffres
    assert telephone_est_valide("1" * 20)              # 20 chiffres


def test_formes_invalides():
    assert not telephone_est_valide("12345")           # trop court
    assert not telephone_est_valide("1" * 21)          # trop long
    assert not telephone_est_valide("77abc4567")       # lettres
    assert not telephone_est_valide("77+1234567")      # + au milieu
    assert not telephone_est_valide("")
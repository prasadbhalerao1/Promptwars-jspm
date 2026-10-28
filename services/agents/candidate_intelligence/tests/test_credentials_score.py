from services.agents.candidate_intelligence.tools.credentials_score import verified_credentials


def test_none_when_nothing_provided():
    result = verified_credentials([], experience=[], education=[], skills=[])
    assert result.value is None


def test_resume_alone_cannot_carry_the_score():
    result = verified_credentials(
        [],
        experience=[{"years": 20}],
        education=[{"degree": "B.Tech"}],
        skills=[{"name": "Python", "source": "resume"}],
    )
    assert result.value is not None
    assert result.value <= 22


def test_verified_certificate_outweighs_pending():
    verified = verified_credentials(
        [{"title": "AWS SAA", "verification_status": "verified"}], experience=[], education=[], skills=[]
    )
    pending = verified_credentials(
        [{"title": "AWS SAA", "verification_status": "unverified", "ocr_confidence": 0.9}],
        experience=[],
        education=[],
        skills=[],
    )
    assert verified.value > pending.value > 0


def test_unreadable_pending_certificate_earns_nothing():
    result = verified_credentials(
        [{"title": "blurry", "verification_status": "unverified", "ocr_confidence": 0.2}],
        experience=[],
        education=[],
        skills=[],
    )
    assert result.value == 0


def test_corroborated_skills_score_higher():
    claimed = verified_credentials(
        [], experience=[], education=[], skills=[{"name": "Go", "source": "resume"}]
    )
    corroborated = verified_credentials(
        [], experience=[], education=[], skills=[{"name": "Go", "source": "github_analysis"}]
    )
    assert corroborated.value > claimed.value

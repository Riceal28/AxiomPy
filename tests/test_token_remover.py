"""Filename token-removal corpus."""

import pytest

from axiom.core.generate.naming import token_remover
from axiom.core.state import AxiomState


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        (
            "Movie.Title.2020.2160p.4K.UHD.BluRay.x265.10bit.DDP5.1.Atmos-GROUP",
            "Movie.Title.2020.-GROUP",
        ),
        (
            "Another.Movie.1080p.WEB-DL.x264.AAC5.1.English.Subs",
            "Another.Movie",
        ),
        ("Song.Title.320kbps.FLAC.44.1kHz", "Song.Title"),
        ("Clip.GoPro.H.264.NVENC.Hi10P.2Pass.CRF23.5MB", "Clip.GoPro"),
        ("Movie.2020.1080p.BluRay.DTS-HD.MA.5.1", "Movie.2020"),
        ("[Release] Show.S01E02.Multi-Subs.1080p", "Show.S01E02"),
    ],
)
def test_token_remover_corpus(filename, expected):
    state = AxiomState({"Configure.InputFileNameTokens_SelectedItem": "Remove"})
    assert token_remover(state, filename) == expected


def test_token_remover_custom_tokens():
    state = AxiomState(
        {
            "Configure.InputFileNameTokens_SelectedItem": "Remove",
            "Configure.InputFileNameTokensCustom_Text": "Draft, Final",
        }
    )
    assert token_remover(state, "Movie.Draft.Final.1080p") == "Movie"


def test_token_remover_keep_mode_is_identity():
    state = AxiomState({"Configure.InputFileNameTokens_SelectedItem": "Keep"})
    assert token_remover(state, "Movie.1080p.x264") == "Movie.1080p.x264"
